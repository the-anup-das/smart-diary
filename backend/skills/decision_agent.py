import os
import yaml
import re
import json
from pathlib import Path
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# 1. Build the Skill Catalog by reading SKILL.md files from disk
SKILLS_DIR = Path(__file__).parent
SKILL_CATALOG = {}

# Parse all SKILL.md files in subdirectories
for skill_dir in SKILLS_DIR.iterdir():
    if skill_dir.is_dir():
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            content = skill_file.read_text(encoding="utf-8")
            # Parse YAML frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    metadata = yaml.safe_load(parts[1])
                    body = parts[2].strip()
                    skill_name = metadata.get("name", skill_dir.name)
                    SKILL_CATALOG[skill_name] = {
                        "description": metadata.get("description", ""),
                        "content": body
                    }

# 2. Define the load_skill tool as per the Agent Skills specification
@tool
def load_skill(skill_name: str) -> str:
    """
    Load the detailed instructions for a specific decision framework skill.
    Pass the name of the skill exactly as listed in the catalog.
    """
    if skill_name in SKILL_CATALOG:
        return f"SUCCESSFULLY LOADED SKILL: {skill_name}\n\n{SKILL_CATALOG[skill_name]['content']}"
    return f"ERROR: Skill '{skill_name}' not found."

# 3. Initialize the LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

# 4. Create the Agent using the progressive skill-loading pattern
def get_system_prompt() -> str:
    catalog_list = "\n".join([f"- **{name}**: {data['description']}" for name, data in SKILL_CATALOG.items()])
    
    return (
        "You are the Smart Diary Decision Assistant — a deeply empathetic and analytically rigorous life coach. "
        "Your goal is to help the user deeply understand a decision they are struggling with, using their diary as context.\n\n"
        "You have access to a catalog of specialized decision frameworks. "
        f"Available skills:\n{catalog_list}\n\n"
        "FRAMEWORK SELECTION — read the decision carefully and pick EXACTLY ONE:\n\n"
        "→ **10_10_10_rule**: User is anxious, fearful, or emotionally stuck. The decision feels urgent or scary right now. "
        "Use this to give them time-horizon perspective (10 min / 10 months / 10 years) and cut through the emotion.\n\n"
        "→ **weighted_matrix**: There are 2 or more specific, named options to compare (e.g. 'Option A vs Option B'). "
        "The user needs structured, analytical scoring across dimensions to see which option wins on paper.\n\n"
        "→ **second_order_thinking**: The decision has complex, non-obvious long-term ripple effects. "
        "The user is underestimating what happens next — use this to map cascading 1st, 2nd, 3rd order consequences.\n\n"
        "ALWAYS call `load_skill` first to get the full instructions before analyzing. "
        "NEVER attempt the analysis without loading the skill first. "
        "Your analysis must be deeply personal to the user's diary context — reference specific memories and details, never give generic advice."
    )

decision_agent = create_react_agent(
    model=llm,
    tools=[load_skill],
    prompt=get_system_prompt()
)

def _extract_json(text: str) -> str:
    """Aggressively extracts JSON from a string, handling markdown wrappers."""
    text = text.strip()
    if text.startswith("```"):
        # Use regex to find content between ```json and ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()
    
    # Optional fallback: try to find the first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
        
    return text

def run_decision_agent(detected_decision: str, context: str, user_input: str, memories: str = "") -> dict:
    """Entry point to trigger the Decision Agent."""
    
    # Build the memory context block — injected first so it grounds all analysis
    memory_block = ""
    if memories:
        memory_block = (
            f"{memories}\n\n"
            "---\n"
            "The above memories are extracted facts from this user's past diary entries. "
            "They represent real things they have written about their life. "
            "Ground your entire analysis in these facts — reference them explicitly.\n\n"
        )
    
    prompt = (
        f"{memory_block}"
        f"DECISION: {detected_decision}\n\n"
        f"RECENT DIARY CONTEXT:\n{context}\n\n"
        f"USER REQUEST: {user_input}\n\n"
        "INSTRUCTIONS:\n"
        "1. Select the BEST framework from your catalog and call `load_skill` first.\n"
        "2. You MUST compare at least TWO paths. If the user only mentions one (e.g. 'Should I quit?'), "
        "your paths MUST be 'Path A: Quit' and 'Path B: Status Quo (Don't quit)'.\n"
        "3. For every path, you MUST explicitly analyze the impact on these 4 Life Domains: "
        "**Finance/Career**, **Family/Relationships**, **Future Trajectory**, and **Mental Health**.\n"
        "4. Ground your analysis in the provided memories and diary context. Be specific, personal, and analytical.\n"
        "5. Return the analysis in the exact JSON format required by the skill."
    )
    
    result = decision_agent.invoke({"messages": [("user", prompt)]})
    final_message = result["messages"][-1].content
    
    # Strip markdown so frontend can safely JSON.parse
    clean_json = _extract_json(final_message)
    
    # Extract which framework was used from tool calls
    framework_used = "auto-selected"
    for message in result["messages"]:
        if hasattr(message, "tool_calls"):
            for call in message.tool_calls:
                if call["name"] == "load_skill":
                    framework_used = call["args"].get("skill_name", framework_used)
    
    return {
        "analysis_result": clean_json,
        "framework_used": framework_used
    }


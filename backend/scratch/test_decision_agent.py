import os
import sys
from pathlib import Path

# Add backend to path so we can import skills
sys.path.append(str(Path(__file__).parent.parent))

from skills.decision_agent import run_decision_agent

def test_agent():
    print("Testing Decision Junction Agent...")
    print("Scenario: User is considering quitting their job to start a bakery.")
    
    context = """
    Entry 1: I'm feeling so burnt out at my software engineering job. I love baking, and I've been thinking about it all day.
    Entry 2: Today I made 50 sourdough loaves for the local market. They sold out in an hour. It was the happiest I've been in years.
    Entry 3: I'm scared about the money. I have $50k in savings, but I don't know if it's enough. My current salary is $150k.
    """
    
    detected_decision = "Should I quit my software engineering job to start a bakery?"
    
    print("\n--- RUNNING AGENT ---")
    result = run_decision_agent(
        detected_decision=detected_decision,
        context=context,
        user_input="Please help me analyze this. I'm especially worried about the long-term impact on my life."
    )
    
    print("\n--- AGENT RESULT ---")
    print(f"Analysis Result:\n{result['analysis_result']}")
    print(f"\nFramework Used: {result['framework_used']}")

if __name__ == "__main__":
    test_agent()

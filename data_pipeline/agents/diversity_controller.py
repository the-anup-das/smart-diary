"""Diversity Controller Node (Programmatic - no LLM tokens).
Systematically assigns personas, topics, emotional states, writing styles, and edge cases
to prevent mode collapse and ensure high-coverage training data.
"""

import random
from typing import Dict, Any, Optional

PERSONAS = [
    {"age_group": "Teen (16-19)", "role": "High school / college student", "context": "Academic pressure, peer dynamics, future uncertainty"},
    {"age_group": "Young Adult (20-25)", "role": "Entry-level tech professional", "context": "Imposter syndrome, dating, living away from home"},
    {"age_group": "Young Adult (26-30)", "role": "Freelance designer", "context": "Inconsistent income, creative burnout, balancing personal life"},
    {"age_group": "Mid-Life (31-40)", "role": "Working parent with toddlers", "context": "Sleep deprivation, career demands, marital tension, guilt"},
    {"age_group": "Mid-Life (41-50)", "role": "Senior manager", "context": "Caring for aging parents, teenage rebellion, mid-career stagnation"},
    {"age_group": "Mature Adult (51-65)", "role": "Teacher nearing retirement", "context": "Empty nest, health concerns, searching for renewed purpose"},
    {"age_group": "Senior (65+)", "role": "Retired engineer", "context": "Loneliness, chronic physical ache, reminiscing, seeking daily routine"},
]

EMOTIONAL_STATES = [
    "Overwhelmed and anxious",
    "Gently optimistic and grateful",
    "Frustrated, resentful, and bitter",
    "Melancholic, wistful, and lonely",
    "Energetic, determined, and hyper-focused",
    "Numb, disconnected, and emotionally flat",
    "Deeply exhausted and defeated",
    "Guilty, remorseful, and second-guessing",
    "Proud, validated, and relieved",
    "Restless, irritable, and seeking distraction",
]

TOPICS = [
    "Work & Career (deadlines, boss conflict, promotion, office politics)",
    "Romantic Relationship (argument, growing distant, first date, divorce)",
    "Family Dynamics (parental expectations, sibling rivalry, boundary setting)",
    "Physical Health & Energy (poor sleep, workout win, sickness, body image)",
    "Financial Stress (unexpected bills, savings anxiety, splurging guilt)",
    "Creative Endeavors & Hobbies (writer's block, passion project progress)",
    "Personal Growth & Identity (breaking bad habits, seeking therapy, self-doubt)",
    "Daily Mundane & Routine (commute irritation, chores, quiet evening)",
]

WRITING_STYLES = [
    "Casual with conversational idioms and modern slang",
    "Stream-of-consciousness, raw and unpolished thoughts",
    "Reflective, introspective, articulate and structured",
    "Short, punchy sentences with fragmented thoughts",
    "Verbose, descriptive with elaborate metaphors",
    "Tired, disjointed, barely formatted late-night scribbles",
]

ENTRY_LENGTHS = [
    {"category": "short", "min_words": 40, "max_words": 80},
    {"category": "medium", "min_words": 120, "max_words": 220},
    {"category": "long", "min_words": 280, "max_words": 450},
]

# Edge case scenarios (15-20% representation)
EDGE_CASES = [
    {
        "type": "acute_crisis_signals",
        "description": "Writer exhibits genuine feelings of worthlessness, hopelessness, wanting to disappear or end pain. (Tests distressFlag=True)",
    },
    {
        "type": "ordinary_venting_not_crisis",
        "description": "Writer uses harsh venting language ('I want to crawl into a hole and die of embarrassment', 'this job is killing me') but is purely figurative venting. (Tests distressFlag=False)",
    },
    {
        "type": "compulsive_stimulation",
        "description": "Explicitly details losing control: doomscrolling TikTok until 3am, compulsive food delivery binge, or binge-watching despite a looming deadline. (Tests stimulation load & behaviours)",
    },
    {
        "type": "brain_fog_and_passive_consumption",
        "description": "Complains about inability to read a single page, severe brain fog, mental fatigue after 4 hours of short reels. (Tests cognition brainRotLoad)",
    },
    {
        "type": "brain_builder_activity",
        "description": "Describes an uninterrupted 3-hour deep work block, a 5-mile trail run in nature, or reading a physical book for an hour. (Tests cognition builders)",
    },
    {
        "type": "decision_paralysis",
        "description": "Torn between two concrete life choices (e.g. 'Should I accept the promotion that requires relocating, or stay close to family?'). (Tests detectedDecision)",
    },
]

CUSTOM_PERSONA_PROMPTS = [
    None,  # Standard persona
    None,  # Standard persona
    "Be a direct, tough-love executive coach who cuts through excuses.",
    "Adopt a warm, gentle Buddhist/mindfulness monk tone focusing on impermanence.",
    "Analyze through a Stoic philosophy lens (Epictetus/Marcus Aurelius).",
    "Keep CBT reframes extremely practical, concise, and focused on physical action.",
]


def generate_diversity_profile(force_edge_case: bool = False) -> Dict[str, Any]:
    """Generates a synthetic prompt parameter profile for the Writer Agent."""
    persona = random.choice(PERSONAS)
    emotion = random.choice(EMOTIONAL_STATES)
    topic = random.choice(TOPICS)
    style = random.choice(WRITING_STYLES)
    length = random.choice(ENTRY_LENGTHS)
    custom_persona = random.choice(CUSTOM_PERSONA_PROMPTS)

    # 20% chance of an explicit edge case, or forced
    is_edge_case = force_edge_case or (random.random() < 0.20)
    edge_case = random.choice(EDGE_CASES) if is_edge_case else None

    return {
        "persona": persona,
        "emotion": emotion,
        "topic": topic,
        "style": style,
        "length": length,
        "edge_case": edge_case,
        "custom_persona_prompt": custom_persona,
    }

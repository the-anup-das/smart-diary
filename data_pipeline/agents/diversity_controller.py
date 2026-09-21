"""
Diversity controller (programmatic, no tokens). Every sample gets a persona, emotion, topic,
style, length, sometimes an edge case and sometimes a custom persona instruction, all drawn
from a seeded random generator so a run can be reproduced.
"""
from __future__ import annotations

import random
from typing import Any

PERSONAS = [
    {"age_group": "Teen (16-19)", "role": "High school / college student", "context": "Academic pressure, peer dynamics, future uncertainty"},
    {"age_group": "Young Adult (20-25)", "role": "Entry-level tech professional", "context": "Imposter syndrome, dating, living away from home"},
    {"age_group": "Young Adult (26-30)", "role": "Freelance designer", "context": "Inconsistent income, creative burnout, balancing personal life"},
    {"age_group": "Mid-Life (31-40)", "role": "Working parent with toddlers", "context": "Sleep deprivation, career demands, marital tension, guilt"},
    {"age_group": "Mid-Life (41-50)", "role": "Senior manager", "context": "Caring for aging parents, teenage rebellion, mid-career stagnation"},
    {"age_group": "Mature Adult (51-65)", "role": "Teacher nearing retirement", "context": "Empty nest, health concerns, searching for renewed purpose"},
    {"age_group": "Senior (65+)", "role": "Retired engineer", "context": "Loneliness, chronic physical ache, reminiscing, seeking daily routine"},
    {"age_group": "Young Adult (22-28)", "role": "Nurse on rotating shifts", "context": "Night shifts, compassion fatigue, a body clock that never settles"},
    {"age_group": "Mid-Life (35-45)", "role": "Small business owner", "context": "Cash flow, staff who quit, no real days off"},
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
    "Content and unremarkable, a plain okay day",
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
    "Friendship & Social Life (a friend drifting away, a good evening out, feeling left out)",
    "Home & Living Situation (a landlord, a noisy flatmate, moving, a broken boiler)",
]

WRITING_STYLES = [
    "Casual with conversational idioms and modern slang",
    "Stream-of-consciousness, raw and unpolished thoughts",
    "Reflective, introspective, articulate and structured",
    "Short, punchy sentences with fragmented thoughts",
    "Verbose, descriptive with elaborate metaphors",
    "Tired, disjointed, barely formatted late-night scribbles",
    "Plain and factual, like notes to self, little emotion on the surface",
]

ENTRY_LENGTHS = [
    {"category": "short", "min_words": 40, "max_words": 80},
    {"category": "medium", "min_words": 120, "max_words": 220},
    {"category": "long", "min_words": 280, "max_words": 450},
]

EDGE_CASES = [
    {"type": "acute_crisis_signals", "description": "The writer expresses genuine hopelessness, worthlessness, wanting to disappear or to end the pain. (distressFlag must be true)"},
    {"type": "ordinary_venting_not_crisis", "description": "Harsh figurative venting ('I want to crawl into a hole and die of embarrassment', 'this job is killing me') that is clearly not a crisis. (distressFlag must be false)"},
    {"type": "compulsive_stimulation", "description": "Losing control to a high-stimulation habit: doomscrolling until 3am, a food delivery binge, or binge-watching with a deadline looming, with the after-feeling and what it pushed aside. (stimulation behaviours and load)"},
    {"type": "brain_fog_and_passive_consumption", "description": "Cannot read a single page, brain feels like cotton wool, mentally fried after hours of short reels; the minutes are stated or clearly implied. (cognition fog, minutes, brainRotLoad)"},
    {"type": "brain_builder_activity", "description": "An uninterrupted deep-work block, a long run outdoors, an hour with a physical book or a real conversation actually happened today. (cognition builders)"},
    {"type": "decision_paralysis", "description": "Torn between two concrete life choices, e.g. accept the promotion that means relocating or stay near family. (detectedDecision)"},
    {"type": "rumination_high", "description": "Replays one conversation or mistake again and again, what-ifs, cannot switch it off at night. (ruminationLevel high)"},
    {"type": "calm_low_rumination", "description": "A settled, ordinary day described plainly, with no looping worry at all. (ruminationLevel low)"},
    {"type": "no_signals_control", "description": "No screens, scrolling, fog, cravings or compulsive habits are mentioned anywhere; the entry is entirely about something else. (every stimulation and cognition signal at zero)"},
    {"type": "messy_grammar", "description": "Typos, run-on sentences, missing capitals and a few wrong words, as if typed fast on a phone. (grammarFixes and grammarScore)"},
    {"type": "multi_topic_split", "description": "Two clearly separate concerns get roughly equal attention, e.g. money worries and a health scare. (topic weights split)"},
]

# Custom instructions a person might set in the app. Most people set none, so most samples get None.
CUSTOM_PERSONA_PROMPTS = [
    "Be a direct, tough-love coach who cuts through excuses.",
    "Adopt a warm, gentle mindfulness tone, focusing on impermanence and self-compassion.",
    "Analyse through a Stoic lens: what is in my control and what is not.",
    "Keep the reframes extremely practical and physical; no abstract advice.",
    "Keep it short and plain. No therapy-speak.",
    "Look at sleep and body signals before anything else.",
    "Speak like a supportive older sibling.",
    "Give the relationships angle the most attention.",
    "Use light humour, never at my expense.",
    "Treat me like a scientist: hypotheses, evidence, next experiment.",
]


EDGE_CASE_TYPES = tuple(e["type"] for e in EDGE_CASES)


def generate_diversity_profile(
    rng: random.Random | None = None,
    force_edge_case: bool = False,
    edge_case_rate: float = 0.30,
    persona_rate: float = 0.15,
    edge_case_types: list[str] | None = None,
) -> dict[str, Any]:
    """A profile for the writer. Pass a seeded `random.Random` for reproducible runs."""
    rng = rng or random.Random()
    pool = EDGE_CASES if not edge_case_types else [e for e in EDGE_CASES if e["type"] in set(edge_case_types)]
    if not pool:
        raise ValueError(f"no edge case matches {edge_case_types}; known types: {sorted(EDGE_CASE_TYPES)}")
    is_edge_case = force_edge_case or rng.random() < edge_case_rate
    edge_case = rng.choice(pool) if is_edge_case else None
    custom_persona = rng.choice(CUSTOM_PERSONA_PROMPTS) if rng.random() < persona_rate else None
    return {
        "persona": rng.choice(PERSONAS),
        "emotion": rng.choice(EMOTIONAL_STATES),
        "topic": rng.choice(TOPICS),
        "style": rng.choice(WRITING_STYLES),
        "length": rng.choice(ENTRY_LENGTHS),
        "edge_case": edge_case,
        "custom_persona_prompt": custom_persona,
    }

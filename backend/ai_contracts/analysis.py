"""
The Save & Reflect analysis contract.

This module is the single source of truth for the analysis schema and the system prompt.
Production (`routers/analyze.py`), the synthetic-data pipeline (`data_pipeline/`) and the
evaluator all import it, so the student model is trained on, evaluated with and served
exactly the same prompt. It is pure Pydantic and strings, with no database imports, so it
can be loaded from outside the backend through a small sys.path shim.

Bump PROMPT_VERSION whenever the prompt text or the schema changes. The analysis cache is
keyed on it, and `tests/test_ai_contracts.py` pins the prompt hash so a change cannot slip
through unnoticed.
"""
from __future__ import annotations

import copy
import hashlib
from typing import Literal, get_args

from pydantic import BaseModel, Field

PROMPT_VERSION = "2026.09-v2"

# Controlled vocabulary for topics. The schema keeps `topic` as a free string because
# existing rows hold free-form values, but the prompt asks for these and the energy
# battery (analyze.py) and domain history rely on them.
TOPIC_VOCAB: tuple[str, ...] = (
    "work", "health", "mental_health", "family", "relationships", "social",
    "personal_growth", "finances", "creativity", "home", "daily_life",
)

# Business rules that the JSON schema cannot express (or that strict structured-output
# modes do not support as schema keywords). Enforced by `check_business_rules`.
TOPIC_WEIGHT_TOLERANCE = 0.05
MICRO_ACTIONS_REQUIRED = 3
EMOTION_LABELS_MIN, EMOTION_LABELS_MAX = 1, 3
GRAMMAR_FIXES_REQUIRED_BELOW = 5   # a low grammar score with no listed fix is an inconsistent label


class GrammarFix(BaseModel):
    original: str
    correction: str
    explanation: str


class CognitiveReframe(BaseModel):
    negativeThought: str
    reframe: str


class TopicWeight(BaseModel):
    topic: str = Field(description="Lowercase topic name from the topic vocabulary (e.g. 'work', 'health', 'family', 'relationships', 'personal_growth', 'finances', 'creativity').")
    weight: float = Field(description="Percentage weight as a float (0.0 to 1.0). All weights should sum to 1.0.")


class EnergyMicroAction(BaseModel):
    id: str = Field(description="A unique UUID string for this action.")
    text: str = Field(description="A short, actionable micro-action to recharge energy.")


class EnergyItem(BaseModel):
    item: str
    reframe: str = Field(description="A short, one-sentence empowering reframe or tip for this specific item.")


class EnergyAnalysisSchema(BaseModel):
    chargers: list[str] = Field(description="Things that recharged the user's energy in this entry (e.g., sleep, exercise, positive events).")
    drainers: list[str] = Field(description="Things that drained the user's energy in this entry (e.g., poor diet, arguments, stress).")
    controllables: list[EnergyItem] = Field(description="Factors in the entry that are within the user's control.")
    uncontrollables: list[EnergyItem] = Field(description="Factors in the entry that are outside the user's control.")
    ruminationLevel: Literal["low", "moderate", "high"] = Field(description="How much the writer is looping on the same worry: 'low', 'moderate', or 'high'.")
    ruminationCoaching: str = Field(description="One gentle coaching line about their overthinking.")
    microActions: list[EnergyMicroAction] = Field(description="Exactly 3 actionable micro-actions personalized to their dominant topics and drainers.")
    tomorrowFocus: str = Field(description="A 1-2 sentence strategy to build or protect energy for the next day, based on today's drainers.")


class StimulationBehaviour(BaseModel):
    behaviour: str = Field(description="Short label for the reward-seeking behaviour mentioned, e.g. 'late-night scrolling', 'binge-watching', 'online shopping'.")
    category: Literal["screens", "social_media", "video", "gaming", "porn", "gambling", "food", "shopping", "substances", "other"]
    trigger: str = Field(description="What led to it, in a few words (boredom, loneliness, avoiding a task, stress, habit, tiredness). 'unclear' if not stated.")
    timeOfDay: Literal["morning", "afternoon", "evening", "night", "unknown"]
    lostControl: bool = Field(description="True when the writer describes going past what they intended: 'could not stop', 'one more', 'until 2am', 'lost hours'.")


class StimulationSignalsSchema(BaseModel):
    behaviours: list[StimulationBehaviour] = Field(description="Compulsive or high-stimulation behaviours the entry actually mentions. Empty when none are mentioned. Never infer.")
    cravingLanguage: bool = Field(description="True when the writer describes craving, urges or checking compulsively.")
    afterState: Literal["none", "guilt", "flat", "restless", "fine"] = Field(description="How the writer felt after the behaviour, if described. 'none' when no behaviour was mentioned.")
    lowMotivation: bool = Field(description="True when the writer says ordinary activities feel pointless or nothing feels enjoyable.")
    sleepDisrupted: bool = Field(description="True when a behaviour cut into sleep.")
    displaced: list[str] = Field(description="Things the writer says were skipped or delayed because of the behaviour. Empty if none.")
    load: int = Field(ge=0, le=3, description="Overall stimulation load in this entry: 0 none mentioned, 1 mild, 2 notable (lost time or guilt), 3 heavy (lost control, sleep or duties affected).")


class CognitionSignalsSchema(BaseModel):
    fogOrAttention: bool = Field(description="True when the writer describes trouble focusing, brain fog, forgetfulness, mental fatigue, rereading without taking it in, or not being able to finish what they started.")
    attentionNote: str = Field(description="A short paraphrase of the attention or fog complaint, or an empty string.")
    passiveConsumptionMinutes: int = Field(ge=0, le=1440, description="Minutes of passive feed or video consumption the entry states or clearly implies, e.g. 'two hours of reels' is 120. 0 when not mentioned. Never guess a number that is not there.")
    shortFormVideo: bool = Field(description="True when short-form video is mentioned: reels, shorts, TikTok, endless clips.")
    builders: list[Literal["deep_reading", "learning", "creating", "deep_work", "exercise", "nature", "conversation", "play", "rest", "sleep"]] = Field(description="Brain-building activities the entry says actually happened today: deep_reading (a book or long article), learning (a skill, course, language), creating (writing, music, making something), deep_work (a long uninterrupted block of focused work), exercise, nature (time outdoors), conversation (a real conversation with someone), play (sport, games or hobbies with people), rest (unplugged rest or deliberate boredom), sleep (a good night's sleep). Empty if none.")
    brainRotLoad: int = Field(ge=0, le=3, description="0 nothing relevant; 1 passive consumption or fog mentioned; 2 both, or one of them with an intended deep activity displaced; 3 heavy: fog plus hours of passive consumption plus sleep, work or reading displaced.")


class FeedbackReportSchema(BaseModel):
    moodScore: int = Field(ge=1, le=10, description="Score the emotional state from 1 (Despair) to 10 (Euphoric).")
    sentiment: str = Field(description="A single word describing the core sentiment (Stressed, Joyful, Neutral, Anxious, Focused, Calm, etc).")
    grammarScore: int = Field(ge=1, le=10, description="Score the English grammar quality.")
    grammarFixes: list[GrammarFix] = Field(description="List of corrections. Empty array if perfect.")
    openLoops: list[str] = Field(description="List of actionable tasks, worries, or unresolved issues from the text.")
    cognitiveReframes: list[CognitiveReframe] = Field(description="CBT positive reframes for negative thoughts.")
    topics: list[TopicWeight] = Field(description="Percentage breakdown of the entry's primary focus areas. List of topic/weight pairs summing to 1.0.")
    selfFocusScore: int = Field(ge=1, le=10, description="Score from 1 (Focused on others/environment) to 10 (Extremely self-focused/I-centric).")
    selfFocusFeedback: str = Field(description="Brief, gentle psychological insight about their focus balance.")
    repetitiveWords: list[str] = Field(description="List of words or short phrases overused in this entry (3-5 items).")
    repetitiveWordingFeedback: str = Field(description="Brief coaching tip on how to vary their vocabulary.")
    detectedDecision: str | None = Field(default=None, description="If the user is struggling with a specific decision (e.g., 'Should I quit my job?'), summarize the topic here. Otherwise null.")
    emotionLabels: list[str] = Field(description="1-3 precise emotion words the writer is expressing (e.g. 'overwhelmed', 'wistful', 'resentful', 'proud'). Granular words, not generic ones like 'bad' or 'sad' unless truly the best fit.")
    distressFlag: bool = Field(description="True ONLY when the entry contains clear signals of self-harm, suicidal thoughts, or acute crisis (e.g. hopelessness about being alive, wanting to disappear or end things). Ordinary sadness, stress, anger, or venting must be False.")
    energyAnalysis: EnergyAnalysisSchema = Field(description="Analysis of the user's energy, control, and actionable steps.")
    stimulation: StimulationSignalsSchema = Field(description="Reward-seeking and overstimulation signals, only from what the entry explicitly says.")
    cognition: CognitionSignalsSchema = Field(description="Attention, brain fog, passive consumption and brain-building activities, only from what the entry explicitly says.")


# ---------------------------------------------------------------------------
# Enum values, read from the schema so the prompt can never disagree with it
# ---------------------------------------------------------------------------

def literal_values(model: type[BaseModel], field: str) -> tuple[str, ...]:
    """The allowed values of a `Literal[...]` or `list[Literal[...]]` field."""
    annotation = model.model_fields[field].annotation
    args = get_args(annotation)
    if args and get_args(args[0]):  # list[Literal[...]]
        args = get_args(args[0])
    return tuple(str(a) for a in args)


RUMINATION_LEVELS = literal_values(EnergyAnalysisSchema, "ruminationLevel")
STIMULATION_CATEGORIES = literal_values(StimulationBehaviour, "category")
TIMES_OF_DAY = literal_values(StimulationBehaviour, "timeOfDay")
AFTER_STATES = literal_values(StimulationSignalsSchema, "afterState")
BUILDERS = literal_values(CognitionSignalsSchema, "builders")


# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------

_BASE_PROMPT = (
    "You are an empathetic AI psychologist and writing coach. Parse entries into strict JSON. "
    "Use CBT to reframe negatives. Life areas must sum to 1.0 weight.\n\n"
    "Focus:\n"
    "1. Self-Focus: Score 1 (external) to 10 (self-absorbed). Provide gentle balance feedback.\n"
    "2. Repetitive Wording: Identify overused words. Suggest variety.\n"
    "3. Energy: Extract chargers/drainers. Identify controllables vs uncontrollables. "
    "Provide a 1-sentence reframe/tip for each. Give a rumination coaching line. "
    "Generate 3 topic-tailored micro-actions and a 'tomorrowFocus' strategy.\n"
    "4. Emotions: name 1-3 precise emotion words the writer expresses (granularity over generic terms).\n"
    "5. Safety: set distressFlag true ONLY for clear self-harm/suicidal/acute-crisis signals — "
    "never for ordinary sadness, stress, or venting.\n"
    "6. Stimulation: record compulsive or high-stimulation behaviours ONLY when the entry mentions them "
    "(scrolling, social media, video, gaming, porn, gambling, food, shopping, substances), with trigger, time of day, "
    "loss of control, the after-state, sleep impact and what was displaced. If nothing is mentioned, return an empty "
    "list, afterState 'none' and load 0. Never diagnose; describe behaviour.\n"
    "7. Mind: note attention trouble or brain fog the writer describes, minutes of passive feed or video consumption "
    "only when stated, whether short-form video is mentioned, and brain-building activities that actually happened "
    "(deep reading, learning, creating, deep work, exercise, nature, conversation, play, rest, sleep). brainRotLoad 0 "
    "when nothing relevant is mentioned. Describe, never diagnose."
)


def _field_guide() -> str:
    """Enum lists and counts rendered from the schema, so they stay in step with it."""
    join = lambda values: ", ".join(values)  # noqa: E731
    return (
        "\n\nField guide, use these exact values:\n"
        f"- topics[].topic: prefer {join(TOPIC_VOCAB)}; weights sum to 1.0.\n"
        f"- energyAnalysis.ruminationLevel: one of {join(RUMINATION_LEVELS)}.\n"
        f"- energyAnalysis.microActions: exactly {MICRO_ACTIONS_REQUIRED} items, each with a unique id.\n"
        f"- emotionLabels: {EMOTION_LABELS_MIN} to {EMOTION_LABELS_MAX} words.\n"
        f"- grammarScore: 10 is flawless; a score below {GRAMMAR_FIXES_REQUIRED_BELOW} must come with grammarFixes listing the errors.\n"
        f"- stimulation.behaviours[].category: one of {join(STIMULATION_CATEGORIES)}; "
        f"timeOfDay: one of {join(TIMES_OF_DAY)}; stimulation.afterState: one of {join(AFTER_STATES)}.\n"
        f"- cognition.builders: any of {join(BUILDERS)}, only when the entry says it happened.\n"
        "\nRules: use only what the entry says; never infer, never diagnose. Output only the JSON object."
    )


PERSONA_HEADER = "USER'S CUSTOM INSTRUCTIONS: "


def build_analysis_system_prompt(custom_persona: str = "") -> str:
    """The production system prompt, with the person's custom instructions appended when set."""
    prompt = _BASE_PROMPT + _field_guide()
    persona = (custom_persona or "").strip()
    if persona:
        prompt += f"\n\n{PERSONA_HEADER}{persona}"
    return prompt


def analysis_messages(entry_text: str, custom_persona: str = "") -> list[dict]:
    """The exact chat messages production sends: system prompt plus the raw entry as the user turn."""
    return [
        {"role": "system", "content": build_analysis_system_prompt(custom_persona)},
        {"role": "user", "content": entry_text},
    ]


PROMPT_SHA256 = hashlib.sha256(build_analysis_system_prompt().encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Validation beyond the schema
# ---------------------------------------------------------------------------

def check_business_rules(report: FeedbackReportSchema) -> list[str]:
    """
    Rules the JSON schema cannot express. Returns a list of problems, empty when the report is
    consistent. The pipeline treats any problem as a rejection; production retries once with the
    problems fed back and then accepts the report, because a topic weight of 0.9 is not worth a
    failed analysis for the person waiting.
    """
    problems: list[str] = []
    if not report.topics:
        problems.append("topics is empty; give at least one topic with a weight")
    else:
        total = sum(t.weight for t in report.topics)
        if abs(total - 1.0) > TOPIC_WEIGHT_TOLERANCE:
            problems.append(f"topic weights sum to {total:.2f}; they must sum to 1.0")
        unknown = sorted({t.topic for t in report.topics if t.topic not in TOPIC_VOCAB})
        if unknown:
            problems.append(f"topics not in the vocabulary: {', '.join(unknown)}; use {', '.join(TOPIC_VOCAB)}")
    n_actions = len(report.energyAnalysis.microActions)
    if n_actions != MICRO_ACTIONS_REQUIRED:
        problems.append(f"energyAnalysis.microActions has {n_actions} items; exactly {MICRO_ACTIONS_REQUIRED} are required")
    n_emotions = len(report.emotionLabels)
    if not (EMOTION_LABELS_MIN <= n_emotions <= EMOTION_LABELS_MAX):
        problems.append(f"emotionLabels has {n_emotions} items; give {EMOTION_LABELS_MIN} to {EMOTION_LABELS_MAX}")
    if report.grammarScore < GRAMMAR_FIXES_REQUIRED_BELOW and not report.grammarFixes:
        problems.append(f"grammarScore is {report.grammarScore} but grammarFixes is empty; list the errors or raise the score")
    stim = report.stimulation
    if not stim.behaviours and (stim.load != 0 or stim.afterState != "none"):
        problems.append("stimulation has no behaviours, so load must be 0 and afterState 'none'")
    if stim.behaviours and stim.load == 0:
        problems.append("stimulation lists behaviours, so load must be at least 1")
    cog = report.cognition
    if not cog.fogOrAttention and cog.passiveConsumptionMinutes == 0 and not cog.shortFormVideo and cog.brainRotLoad != 0:
        problems.append("cognition reports no fog, no minutes and no short-form video, so brainRotLoad must be 0")
    return problems


# ---------------------------------------------------------------------------
# JSON schema for constrained decoding on local servers
# ---------------------------------------------------------------------------

_LOCAL_STRIP_KEYS = ("description", "title", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "examples")


def _strip(node, keys: tuple[str, ...]):
    if isinstance(node, dict):
        for key in keys:
            node.pop(key, None)
        if node.get("type") == "object" and "properties" in node:
            node.setdefault("additionalProperties", False)
        for value in node.values():
            _strip(value, keys)
    elif isinstance(node, list):
        for item in node:
            _strip(item, keys)
    return node


def analysis_json_schema(for_local: bool = False) -> dict:
    """
    The report's JSON schema. For local servers (llama.cpp, vLLM) descriptions and numeric bounds
    are removed: they only enlarge the grammar, and Pydantic enforces the bounds afterwards anyway.
    Every object also gets additionalProperties: false so the model cannot invent keys.
    """
    schema = copy.deepcopy(FeedbackReportSchema.model_json_schema())
    if for_local:
        _strip(schema, _LOCAL_STRIP_KEYS)
    return schema


__all__ = [
    "PROMPT_VERSION", "PROMPT_SHA256", "PERSONA_HEADER", "TOPIC_VOCAB",
    "RUMINATION_LEVELS", "STIMULATION_CATEGORIES", "TIMES_OF_DAY", "AFTER_STATES", "BUILDERS",
    "MICRO_ACTIONS_REQUIRED", "EMOTION_LABELS_MIN", "EMOTION_LABELS_MAX", "TOPIC_WEIGHT_TOLERANCE", "GRAMMAR_FIXES_REQUIRED_BELOW",
    "GrammarFix", "CognitiveReframe", "TopicWeight", "EnergyMicroAction", "EnergyItem",
    "EnergyAnalysisSchema", "StimulationBehaviour", "StimulationSignalsSchema", "CognitionSignalsSchema",
    "FeedbackReportSchema",
    "literal_values", "build_analysis_system_prompt", "analysis_messages", "check_business_rules", "analysis_json_schema",
]

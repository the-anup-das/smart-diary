"""Pydantic schemas for the diary feedback report.
Mirrored from backend/routers/analyze.py to ensure 100% compatibility.
"""

from typing import Literal, Optional, List, Dict
from pydantic import BaseModel, Field


class GrammarFix(BaseModel):
    original: str
    correction: str
    explanation: str


class CognitiveReframe(BaseModel):
    negativeThought: str
    reframe: str


class TopicWeight(BaseModel):
    topic: str = Field(description="Lowercase topic name (e.g. 'work', 'health', 'family', 'relationships', 'personal_growth', 'finances', 'creativity').")
    weight: float = Field(description="Percentage weight as a float (0.0 to 1.0). All weights should sum to 1.0.")


class EnergyMicroAction(BaseModel):
    id: str = Field(description="A unique UUID string for this action.")
    text: str = Field(description="A short, actionable micro-action to recharge energy.")


class EnergyItem(BaseModel):
    item: str
    reframe: str = Field(description="A short, one-sentence empowering reframe or tip for this specific item.")


class EnergyAnalysisSchema(BaseModel):
    chargers: List[str] = Field(description="Things that recharged the user's energy in this entry (e.g., sleep, exercise, positive events).")
    drainers: List[str] = Field(description="Things that drained the user's energy in this entry (e.g., poor diet, arguments, stress).")
    controllables: List[EnergyItem] = Field(description="Factors in the entry that are within the user's control.")
    uncontrollables: List[EnergyItem] = Field(description="Factors in the entry that are outside the user's control.")
    ruminationLevel: str = Field(description="'low', 'moderate', or 'high'")
    ruminationCoaching: str = Field(description="One gentle coaching line about their overthinking.")
    microActions: List[EnergyMicroAction] = Field(description="Exactly 3 actionable micro-actions personalized to their dominant topics and drainers.")
    tomorrowFocus: str = Field(description="A 1-2 sentence strategy to build or protect energy for the next day, based on today's drainers.")


class StimulationBehaviour(BaseModel):
    behaviour: str = Field(description="Short label for the reward-seeking behaviour mentioned, e.g. 'late-night scrolling', 'binge-watching', 'online shopping'.")
    category: Literal["screens", "social_media", "video", "gaming", "porn", "gambling", "food", "shopping", "substances", "other"]
    trigger: str = Field(description="What led to it, in a few words (boredom, loneliness, avoiding a task, stress, habit, tiredness). 'unclear' if not stated.")
    timeOfDay: Literal["morning", "afternoon", "evening", "night", "unknown"]
    lostControl: bool = Field(description="True when the writer describes going past what they intended: 'could not stop', 'one more', 'until 2am', 'lost hours'.")


class StimulationSignalsSchema(BaseModel):
    behaviours: List[StimulationBehaviour] = Field(description="Compulsive or high-stimulation behaviours the entry actually mentions. Empty when none are mentioned. Never infer.")
    cravingLanguage: bool = Field(description="True when the writer describes craving, urges or checking compulsively.")
    afterState: Literal["none", "guilt", "flat", "restless", "fine"] = Field(description="How the writer felt after the behaviour, if described. 'none' when no behaviour was mentioned.")
    lowMotivation: bool = Field(description="True when the writer says ordinary activities feel pointless or nothing feels enjoyable.")
    sleepDisrupted: bool = Field(description="True when a behaviour cut into sleep.")
    displaced: List[str] = Field(description="Things the writer says were skipped or delayed because of the behaviour. Empty if none.")
    load: int = Field(ge=0, le=3, description="Overall stimulation load in this entry: 0 none mentioned, 1 mild, 2 notable (lost time or guilt), 3 heavy (lost control, sleep or duties affected).")


class CognitionSignalsSchema(BaseModel):
    fogOrAttention: bool = Field(description="True when the writer describes trouble focusing, brain fog, forgetfulness, mental fatigue, rereading without taking it in, or not being able to finish what they started.")
    attentionNote: str = Field(description="A short paraphrase of the attention or fog complaint, or an empty string.")
    passiveConsumptionMinutes: int = Field(ge=0, le=1440, description="Minutes of passive feed or video consumption the entry states or clearly implies, e.g. 'two hours of reels' is 120. 0 when not mentioned. Never guess a number that is not there.")
    shortFormVideo: bool = Field(description="True when short-form video is mentioned: reels, shorts, TikTok, endless clips.")
    builders: List[Literal["deep_reading", "learning", "creating", "deep_work", "exercise", "nature", "conversation", "play", "rest", "sleep"]] = Field(description="Brain-building activities the entry says actually happened today. Empty if none.")
    brainRotLoad: int = Field(ge=0, le=3, description="0 nothing relevant; 1 passive consumption or fog mentioned; 2 both, or one of them with an intended deep activity displaced; 3 heavy: fog plus hours of passive consumption plus sleep, work or reading displaced.")


class FeedbackReportSchema(BaseModel):
    thought_reasoning: str = Field(default="", description="Internal reasoning block. Must be the first field generated to allow Chain-of-Thought before finalizing the report.")
    moodScore: int = Field(ge=1, le=10, description="Score the emotional state from 1 (Despair) to 10 (Euphoric).")
    sentiment: str = Field(description="A single word describing the core sentiment (Stressed, Joyful, Neutral, Anxious, Focused, Calm, etc).")
    grammarScore: int = Field(ge=1, le=10, description="Score the English grammar quality.")
    grammarFixes: List[GrammarFix] = Field(description="List of corrections. Empty array if perfect.")
    openLoops: List[str] = Field(description="List of actionable tasks, worries, or unresolved issues from the text.")
    cognitiveReframes: List[CognitiveReframe] = Field(description="CBT positive reframes for negative thoughts.")
    topics: List[TopicWeight] = Field(description="Percentage breakdown of the entry's primary focus areas. List of topic/weight pairs summing to 1.0.")
    selfFocusScore: int = Field(ge=1, le=10, description="Score from 1 (Focused on others/environment) to 10 (Extremely self-focused/I-centric).")
    selfFocusFeedback: str = Field(description="Brief, gentle psychological insight about their focus balance.")
    repetitiveWords: List[str] = Field(description="List of words or short phrases overused in this entry (3-5 items).")
    repetitiveWordingFeedback: str = Field(description="Brief coaching tip on how to vary their vocabulary.")
    detectedDecision: Optional[str] = Field(default=None, description="If the user is struggling with a specific decision, summarize the topic here. Otherwise null.")
    emotionLabels: List[str] = Field(description="1-3 precise emotion words the writer is expressing.")
    distressFlag: bool = Field(description="True ONLY when the entry contains clear signals of self-harm, suicidal thoughts, or acute crisis. Ordinary sadness/stress must be False.")
    energyAnalysis: EnergyAnalysisSchema = Field(description="Analysis of the user's energy, control, and actionable steps.")
    stimulation: StimulationSignalsSchema = Field(description="Reward-seeking and overstimulation signals, only from what the entry explicitly says.")
    cognition: CognitionSignalsSchema = Field(description="Attention, brain fog, passive consumption and brain-building activities, only from what the entry explicitly says.")

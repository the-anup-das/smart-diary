"""
Value-level scoring of an analysis against a reference.

A reference is either a golden `expected` block (ranges and sets written by hand) or a
teacher analysis (turned into ranges by `expected_from_analysis`). Every row scores the
fields that matter to the app: the safety flag, mood, rumination, the top topic, the
stimulation and brain-rot loads, builders, the decision flag, grammar consistency and the
validity of enums and business rules. `aggregate` turns rows into rates and errors and
`gate` compares them with thresholds.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from data_pipeline.contracts import TOPIC_VOCAB, FeedbackReportSchema, check_business_rules

THRESHOLDS_PATH = Path(__file__).resolve().parent / "thresholds.json"


def load_thresholds(path: Path | None = None) -> dict:
    return json.loads((path or THRESHOLDS_PATH).read_text(encoding="utf-8"))


def _range(value) -> tuple[float, float] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return float(value[0]), float(value[1])
    return float(value), float(value)


def _distance(value: float, bounds: tuple[float, float]) -> float:
    lo, hi = bounds
    if value < lo:
        return lo - value
    if value > hi:
        return value - hi
    return 0.0


def expected_from_analysis(analysis: dict) -> dict:
    """Ranges derived from a teacher analysis, so a student can be scored against it."""
    energy = analysis.get("energyAnalysis") or {}
    stim = analysis.get("stimulation") or {}
    cog = analysis.get("cognition") or {}
    topics = sorted(analysis.get("topics") or [], key=lambda t: -float(t.get("weight", 0)))
    minutes = int(cog.get("passiveConsumptionMinutes") or 0)
    return {
        "distressFlag": bool(analysis.get("distressFlag")),
        "moodScore": [max(1, int(analysis.get("moodScore", 5)) - 1), min(10, int(analysis.get("moodScore", 5)) + 1)],
        "ruminationLevel": [energy.get("ruminationLevel")] if energy.get("ruminationLevel") else None,
        "topTopic": [topics[0]["topic"]] if topics else None,
        "stimulationLoad": [int(stim.get("load", 0))] * 2,
        "brainRotLoad": [int(cog.get("brainRotLoad", 0))] * 2,
        "builders": list(cog.get("builders") or []),
        "detectedDecision": bool(analysis.get("detectedDecision")),
        "shortFormVideo": bool(cog.get("shortFormVideo")),
        "minutes": [int(minutes * 0.8), int(minutes * 1.2) + 5],
    }


def score_one(analysis: dict | None, expected: dict, *, latency_s: float | None = None, tokens: int | None = None, error: str | None = None) -> dict[str, Any]:
    """Score one analysis. Missing or invalid analyses score every field as wrong."""
    row: dict[str, Any] = {"schema_valid": False, "rules_ok": False, "enum_valid": False, "latency_s": latency_s, "tokens": tokens, "error": error}
    report = None
    if analysis is not None:
        try:
            report = FeedbackReportSchema.model_validate(analysis)
            row["schema_valid"] = True
            row["enum_valid"] = True  # Literal fields validated
            problems = check_business_rules(report)
            row["rules_ok"] = not problems
            row["rule_problems"] = problems
        except ValidationError as ve:
            row["error"] = error or "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in ve.errors()[:3])

    def flag(name: str, value: bool | None) -> None:
        if value is not None:
            row[name] = bool(value)

    exp_distress = expected.get("distressFlag")
    if exp_distress is not None:
        row["distress_expected"] = bool(exp_distress)
        row["distress_predicted"] = bool(report.distressFlag) if report else None
        flag("distress_correct", (report.distressFlag == exp_distress) if report else False)

    mood = _range(expected.get("moodScore"))
    if mood:
        row["mood_error"] = _distance(report.moodScore, mood) if report else 10.0
        flag("mood_in_range", row["mood_error"] == 0)

    rum = expected.get("ruminationLevel")
    if rum:
        flag("rumination_correct", (report.energyAnalysis.ruminationLevel in rum) if report else False)

    top = expected.get("topTopic")
    if top:
        predicted_top = max(report.topics, key=lambda t: t.weight).topic if report and report.topics else None
        row["top_topic_predicted"] = predicted_top
        flag("top_topic_correct", predicted_top in top if predicted_top else False)
        if report:
            row["topics_in_vocab"] = all(t.topic in TOPIC_VOCAB for t in report.topics)

    stim = _range(expected.get("stimulationLoad"))
    if stim:
        row["stim_load_error"] = _distance(report.stimulation.load, stim) if report else 3.0
    cats = expected.get("stimulationCategories")
    if cats:
        predicted = {b.category for b in report.stimulation.behaviours} if report else set()
        flag("stim_category_correct", bool(predicted & set(cats)))
    if expected.get("cravingLanguage") is not None:
        flag("craving_correct", (report.stimulation.cravingLanguage == expected["cravingLanguage"]) if report else False)
    if expected.get("sleepDisrupted") is not None:
        flag("sleep_correct", (report.stimulation.sleepDisrupted == expected["sleepDisrupted"]) if report else False)

    rot = _range(expected.get("brainRotLoad"))
    if rot:
        row["rot_load_error"] = _distance(report.cognition.brainRotLoad, rot) if report else 3.0
    if expected.get("fogOrAttention") is not None:
        flag("fog_correct", (report.cognition.fogOrAttention == expected["fogOrAttention"]) if report else False)
    if expected.get("shortFormVideo") is not None:
        flag("short_form_correct", (report.cognition.shortFormVideo == expected["shortFormVideo"]) if report else False)
    minutes = _range(expected.get("minutes"))
    if minutes:
        flag("minutes_in_range", (_distance(report.cognition.passiveConsumptionMinutes, minutes) == 0) if report else False)

    builders = expected.get("builders")
    if builders:
        predicted = set(report.cognition.builders) if report else set()
        hits = len(set(builders) & predicted)
        row["builders_recall"] = hits / len(builders)
        row["builders_predicted"] = sorted(predicted)

    if expected.get("detectedDecision") is not None:
        flag("decision_correct", (bool(report.detectedDecision) == bool(expected["detectedDecision"])) if report else False)

    grammar = _range(expected.get("grammarScore"))
    if grammar:
        flag("grammar_in_range", (_distance(report.grammarScore, grammar) == 0) if report else False)
    if expected.get("grammarFixesMin") is not None:
        flag("grammar_fixes_enough", (len(report.grammarFixes) >= int(expected["grammarFixesMin"])) if report else False)
    return row


def _rate(rows: list[dict], key: str) -> float | None:
    values = [r[key] for r in rows if key in r and r[key] is not None]
    return (sum(1 for v in values if v) / len(values)) if values else None


def _mean(rows: list[dict], key: str) -> float | None:
    values = [float(r[key]) for r in rows if key in r and r[key] is not None]
    return (sum(values) / len(values)) if values else None


def aggregate(rows: list[dict]) -> dict:
    """Rates, errors and the safety confusion matrix over scored rows."""
    tp = sum(1 for r in rows if r.get("distress_expected") is True and r.get("distress_predicted") is True)
    fn = sum(1 for r in rows if r.get("distress_expected") is True and r.get("distress_predicted") is not True)
    fp = sum(1 for r in rows if r.get("distress_expected") is False and r.get("distress_predicted") is True)
    tn = sum(1 for r in rows if r.get("distress_expected") is False and r.get("distress_predicted") is False)
    recall = tp / (tp + fn) if tp + fn else None
    precision = tp / (tp + fp) if tp + fp else None
    return {
        "count": len(rows),
        "schema_valid_rate": _rate(rows, "schema_valid"),
        "rules_ok_rate": _rate(rows, "rules_ok"),
        "enum_valid_rate": _rate(rows, "enum_valid"),
        "distress_recall": recall,
        "distress_precision": precision,
        "distress_confusion": {"tp": tp, "fn": fn, "fp": fp, "tn": tn},
        "distress_accuracy": _rate(rows, "distress_correct"),
        "mood_mae": _mean(rows, "mood_error"),
        "mood_in_range_rate": _rate(rows, "mood_in_range"),
        "rumination_accuracy": _rate(rows, "rumination_correct"),
        "top_topic_accuracy": _rate(rows, "top_topic_correct"),
        "topics_in_vocab_rate": _rate(rows, "topics_in_vocab"),
        "stimulation_load_mae": _mean(rows, "stim_load_error"),
        "stim_category_accuracy": _rate(rows, "stim_category_correct"),
        "brain_rot_load_mae": _mean(rows, "rot_load_error"),
        "fog_accuracy": _rate(rows, "fog_correct"),
        "short_form_accuracy": _rate(rows, "short_form_correct"),
        "minutes_in_range_rate": _rate(rows, "minutes_in_range"),
        "builders_recall": _mean(rows, "builders_recall"),
        "decision_accuracy": _rate(rows, "decision_correct"),
        "grammar_in_range_rate": _rate(rows, "grammar_in_range"),
        "grammar_fixes_enough_rate": _rate(rows, "grammar_fixes_enough"),
        "avg_latency_s": _mean(rows, "latency_s"),
        "avg_tokens": _mean(rows, "tokens"),
        "failures": sum(1 for r in rows if not r.get("schema_valid")),
    }


HIGHER_IS_BETTER = {"schema_valid_rate", "rules_ok_rate", "enum_valid_rate", "distress_recall", "distress_precision", "rumination_accuracy",
                    "top_topic_accuracy", "builders_recall", "decision_accuracy"}
LOWER_IS_BETTER = {"mood_mae", "stimulation_load_mae", "brain_rot_load_mae"}


def gate(agg: dict, thresholds: dict) -> tuple[bool, list[str]]:
    """Which thresholds the aggregate misses. A metric with no data is reported, not failed."""
    failures: list[str] = []
    for name, limit in thresholds.items():
        value = agg.get(name)
        if value is None:
            failures.append(f"{name}: no data")
            continue
        if name in LOWER_IS_BETTER:
            if value > limit:
                failures.append(f"{name}: {value:.2f} above {limit}")
        elif value < limit:
            failures.append(f"{name}: {value:.2f} below {limit}")
    hard = [f for f in failures if not f.endswith("no data")]
    return not hard, failures

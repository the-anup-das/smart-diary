"""
wellbeing.py - the Wellbeing Profile: six capacities on one 0-100 scale, higher is always better.

Every analysed entry already carries the raw signals (mood, grammar, self-focus, battery,
rumination, controllables). This module turns them into a fixed set of axes so they can be
drawn as a radar and compared across periods. The axis list and the mapping are mirrored in
frontend/src/lib/wellbeing.ts, which computes the same profile for a single entry client-side.

Axes point the same way on purpose: a bigger shape is always better, which is the one rule
a radar chart needs to be readable.
"""

from typing import Optional

WELLBEING_AXES = [
    {"key": "mood", "label": "Mood", "description": "Emotional state rated by the analysis, 1 to 10."},
    {"key": "energy", "label": "Energy", "description": "The Find Your Energy battery level."},
    {"key": "calm", "label": "Calm", "description": "The inverse of the rumination level: little overthinking scores high."},
    {"key": "agency", "label": "Agency", "description": "Share of what you wrote about that sits within your control."},
    {"key": "outward", "label": "Outward focus", "description": "The inverse of the self-focus score: attention on the world, not only on yourself."},
    {"key": "clarity", "label": "Clarity", "description": "Linguistic clarity, the grammar score."},
]

RUMINATION_TO_CALM = {"low": 100.0, "moderate": 50.0, "high": 0.0}


def _pct10(score) -> Optional[float]:
    if score is None:
        return None
    return max(0.0, min(100.0, float(score) / 10.0 * 100.0))


def axes_from_feedback(fb) -> dict:
    """Axis values for one FeedbackReport, or None where the analysis produced no signal."""
    energy = (getattr(fb, "energy_data", None) or {}) if fb is not None else {}
    controllables = energy.get("controllables") or []
    uncontrollables = energy.get("uncontrollables") or []
    n_control = len(controllables) + len(uncontrollables)

    rumination = energy.get("rumination_level")
    calm = RUMINATION_TO_CALM.get(rumination.lower()) if isinstance(rumination, str) else None

    battery = energy.get("battery_level")
    energy_value = max(0.0, min(100.0, float(battery))) if isinstance(battery, (int, float)) else None

    self_focus = getattr(fb, "self_focus_score", None) if fb is not None else None
    outward = max(0.0, min(100.0, (10.0 - float(self_focus)) / 10.0 * 100.0)) if self_focus is not None else None

    return {
        "mood": _pct10(getattr(fb, "mood_score", None) if fb is not None else None),
        "energy": energy_value,
        "calm": calm,
        "agency": (len(controllables) / n_control * 100.0) if n_control else None,
        "outward": outward,
        "clarity": _pct10(getattr(fb, "grammar_score", None) if fb is not None else None),
    }


def average_axes(feedbacks) -> tuple[dict, int]:
    """
    Average each axis over the entries that have it. Returns (values, entries), where values maps
    axis key to a rounded 0-100 number or None, and entries counts reports that contributed at all.
    """
    totals: dict = {a["key"]: [0.0, 0] for a in WELLBEING_AXES}
    contributing = 0
    for fb in feedbacks:
        axes = axes_from_feedback(fb)
        if not any(v is not None for v in axes.values()):
            continue
        contributing += 1
        for key, value in axes.items():
            if value is not None:
                totals[key][0] += value
                totals[key][1] += 1
    values = {key: (round(total / count, 1) if count else None) for key, (total, count) in totals.items()}
    return values, contributing

"""
fuels.py - Four Fuels: what a week of entries says about the four drives behind mood and motivation.

The framing comes from the DOSE idea (dopamine, oxytocin, serotonin, endorphins): modern life hands
out cheap dopamine on tap and starves the other three, and the fix is small daily acts. This
module does not claim to measure brain chemistry. It counts what the analysed entries mention,
day by day, and says so: "fed on 2 of 5 days, drained on 4". Every score points back at the
sentences that produced it, and every low fuel comes with one small act to try today.

Pure functions only, no database: the router buckets entries by local day and passes them in.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Optional

FUELS = [
    {
        "key": "drive", "label": "Drive", "chemical": "dopamine",
        "tagline": "motivation and follow-through",
        "fedBy": "effort, finishing things, deep work",
        "drainedBy": "cheap rewards: scrolling, short video, late-night screens",
    },
    {
        "key": "bond", "label": "Bond", "chemical": "oxytocin",
        "tagline": "connection and trust",
        "fedBy": "real conversation, play, time with people and pets",
        "drainedBy": "isolation, conflict, feeling unseen",
    },
    {
        "key": "calm", "label": "Calm", "chemical": "serotonin",
        "tagline": "mood and steadiness",
        "fedBy": "daylight, nature, sleep, rest, gratitude",
        "drainedBy": "looping worry, broken sleep, low days",
    },
    {
        "key": "spark", "label": "Spark", "chemical": "endorphins",
        "tagline": "energy and stress tolerance",
        "fedBy": "exercise, laughter, cold water, singing",
        "drainedBy": "sitting all day, flat exhausted days",
    },
]
FUEL_KEYS = tuple(f["key"] for f in FUELS)

# One small act per situation, in our own words. `builder` is the Mind Fitness activity the act
# also counts towards, when there is one, so a done challenge shows up there too.
CHALLENGES = {
    "drive": [
        {"id": "phone_outside_bedroom", "when": "night_screens", "builder": "sleep",
         "text": "Charge your phone outside the bedroom tonight.",
         "why": "The last thing before sleep sets the first craving of the morning."},
        {"id": "phone_free_first_hour", "when": "morning_screens", "builder": None,
         "text": "Keep the phone out of reach for the first hour after waking.",
         "why": "An hour of your own attention before anyone else's feed gets it."},
        {"id": "short_video_cap", "when": "short_video", "builder": None,
         "text": "Set a 20-minute timer for short video today and stop when it rings.",
         "why": "Short clips are the cheapest reward there is; a cap keeps the taste for slower ones."},
        {"id": "hard_thing_first", "when": "screens", "builder": "deep_work",
         "text": "Do the hardest thing on your list first, before any screen.",
         "why": "Effort before reward is what makes reward feel like anything."},
        {"id": "finish_one_thing", "when": None, "builder": "deep_work",
         "text": "Finish one small thing you have been putting off, and write down that you did.",
         "why": "Drive is fed by finishing, not by starting."},
    ],
    "bond": [
        {"id": "message_someone", "when": "lonely", "builder": "conversation",
         "text": "Message one person you have not spoken to in a while and ask how they are.",
         "why": "Connection needs a first move, and it is almost never as awkward as it looks."},
        {"id": "listen_only", "when": "conflict", "builder": "conversation",
         "text": "Have one conversation today where you only ask questions and listen.",
         "why": "Being heard rebuilds trust faster than being right."},
        {"id": "pet_or_hug", "when": "strain", "builder": None,
         "text": "Hug someone, or spend ten unhurried minutes with a pet.",
         "why": "Touch and warmth work even on days when talking is too much."},
        {"id": "call_a_friend", "when": None, "builder": "conversation",
         "text": "Call a friend and ask about their week, not yours.",
         "why": "Attention given is the fastest way to feel connected."},
    ],
    "calm": [
        {"id": "walk_no_headphones", "when": "rumination", "builder": "nature",
         "text": "Take a twenty-minute walk without headphones and let the thought run out.",
         "why": "A looping worry needs somewhere to go; a walk gives it distance."},
        {"id": "lights_off_earlier", "when": "sleep", "builder": "sleep",
         "text": "Lights off thirty minutes earlier tonight, screen off first.",
         "why": "Steady mood is built at night."},
        {"id": "three_things_right", "when": "low_mood", "builder": None,
         "text": "Write three specific things that went right today, however small.",
         "why": "Specific is the point: 'the coffee was good' beats 'I am grateful'."},
        {"id": "daylight_before_noon", "when": None, "builder": "nature",
         "text": "Get outside in daylight for fifteen minutes before noon.",
         "why": "Morning light is the cheapest mood medicine there is."},
    ],
    "spark": [
        {"id": "ten_squats", "when": "sedentary", "builder": "exercise",
         "text": "Stand up and do ten squats right now, then again after lunch.",
         "why": "Two minutes of effort beats an hour of intending to."},
        {"id": "cold_finish", "when": "flat", "builder": None,
         "text": "End your shower with thirty seconds of cold water.",
         "why": "A short shock the body recovers from leaves it steadier afterwards."},
        {"id": "laugh_out_loud", "when": "flat", "builder": "play",
         "text": "Watch or read something that makes you laugh out loud.",
         "why": "Laughter is exercise for the same chemistry."},
        {"id": "twenty_minutes_moving", "when": None, "builder": "exercise",
         "text": "Twenty minutes of any movement that raises your heart rate.",
         "why": "It does not have to be a workout, it has to be a pulse."},
    ],
}
CHALLENGE_BY_ID = {c["id"]: dict(c, fuel=fuel) for fuel, items in CHALLENGES.items() for c in items}

# ---------------------------------------------------------------- what the analysis can tell us

_WARM = {"loved", "connected", "grateful", "supported", "close", "warm", "affectionate", "appreciated", "included", "cared", "belonging", "safe"}
_LONELY = {"lonely", "isolated", "rejected", "ignored", "disconnected", "unloved", "alone", "abandoned", "unseen", "excluded"}
_SETTLED = {"calm", "content", "peaceful", "relaxed", "hopeful", "settled", "serene", "grateful", "steady", "rested"}
_ANXIOUS = {"anxious", "overwhelmed", "restless", "stressed", "panicked", "worried", "tense", "on edge"}
_LOW = {"hopeless", "sad", "empty", "numb", "despairing", "defeated", "miserable", "worthless"}
_ENERGISED = {"energised", "energized", "proud", "alive", "strong", "exhilarated", "invigorated", "accomplished", "refreshed"}
_SLUGGISH = {"sluggish", "drained", "lethargic", "flat", "exhausted", "depleted", "tired", "heavy"}

_FINISHED = re.compile(r"finish|complet|progress|done with|shipped|built|wrote|solved|submitted|cleared", re.I)
_PEOPLE = re.compile(r"friend|call|hug|dinner with|lunch with|partner|family|kids|mum|mom|dad|sister|brother|dog|cat|laugh(ed|ing) with|chat|(?-i:\bwith [A-Z][a-z]+)", re.I)   # "with Sam": a capitalised name
_ALONE = re.compile(r"alone|lonely|isolat|ignored|nobody|no one|by myself", re.I)
_CONFLICT = re.compile(r"argu|fight|fought|conflict|snapped|yelled|tension|row with|fell out", re.I)
_OUTDOORS = re.compile(r"walk|sun|outside|garden|park|beach|forest|fresh air|nap|slept well|early night", re.I)
_SLEEPLESS = re.compile(r"insomnia|[23] ?am|late night|couldn'?t sleep|no sleep|awake all night|slept badly", re.I)
_MOVING = re.compile(r"\brun\b|ran\b|gym|walk|swim|yoga|workout|cycl|bike|hike|dance|laugh|sing|cold shower|stretch|football|climb", re.I)
_SEDENTARY = re.compile(r"sitting all day|sat all day|desk all day|couch|no exercise|sedentary|didn'?t move|haven'?t moved", re.I)

_PEOPLE_TOPICS = {"family", "relationships", "social"}


def _labels(fb) -> set[str]:
    return {str(x).strip().lower() for x in (getattr(fb, "emotion_labels", None) or [])}


def _topics(fb) -> dict[str, float]:
    """Topic weights whether stored as [{"topic", "weight"}] or as {"topic": weight}."""
    raw = getattr(fb, "topics", None) or []
    out: dict[str, float] = {}
    if isinstance(raw, dict):
        return {str(k): float(v or 0) for k, v in raw.items() if isinstance(v, (int, float))}
    for t in raw:
        if isinstance(t, dict) and t.get("topic"):
            out[str(t["topic"])] = float(t.get("weight") or 0)
    return out


def _texts(items) -> str:
    return " ".join(str(x.get("item") if isinstance(x, dict) else x) for x in (items or []))


def evidence_from_feedback(fb) -> dict[str, dict[str, list[tuple[str, str]]]]:
    """For one analysed entry: per fuel, the `(tag, reason)` pairs that fed it and drained it.

    Tags are what challenges match on; reasons are what the person reads.
    """
    out = {k: {"fed": [], "drained": []} for k in FUEL_KEYS}
    if fb is None:
        return out
    energy = getattr(fb, "energy_data", None) or {}
    stim = getattr(fb, "stimulation_data", None) or {}
    cog = getattr(fb, "cognition_data", None) or {}
    labels = _labels(fb)
    topics = _topics(fb)
    mood = getattr(fb, "mood_score", None)
    builders = set(cog.get("builders") or [])
    chargers = _texts(energy.get("chargers"))
    drainers = _texts(energy.get("drainers"))
    rumination = energy.get("rumination_level")

    # ---- Drive
    fed, drained = out["drive"]["fed"], out["drive"]["drained"]
    for b, text in (("deep_work", "a block of deep work"), ("learning", "learning something"), ("creating", "making something")):
        if b in builders:
            fed.append(("effort", text))
    ticked = sum(1 for a in energy.get("micro_actions") or [] if isinstance(a, dict) and a.get("completed"))
    if ticked:
        fed.append(("effort", f"ticked off {ticked} micro-action{'s' if ticked > 1 else ''}"))
    if _FINISHED.search(chargers):
        fed.append(("effort", "finishing something felt good"))
    load = int(stim.get("load") or 0)
    times = {str(b.get("timeOfDay")) for b in stim.get("behaviours") or [] if isinstance(b, dict)}
    if load >= 2:
        if times & {"night", "evening"}:
            drained.append(("night_screens", "screens late into the night"))
        elif "morning" in times:
            drained.append(("morning_screens", "the phone first thing in the morning"))
        else:
            drained.append(("screens", "a heavy stimulation habit"))
    elif load == 1:
        drained.append(("screens", "some reward-seeking scrolling"))
    if cog.get("shortFormVideo"):
        drained.append(("short_video", "short-form video"))
    if int(cog.get("brainRotLoad") or 0) >= 2:
        drained.append(("screens", "feeling fried after hours of feeds"))
    if stim.get("cravingLanguage"):
        drained.append(("screens", "craving language about a habit"))
    if stim.get("afterState") in ("guilt", "flat", "restless"):
        drained.append(("screens", f"feeling {stim.get('afterState')} afterwards"))

    # ---- Bond
    fed, drained = out["bond"]["fed"], out["bond"]["drained"]
    if "conversation" in builders:
        fed.append(("contact", "a real conversation"))
    if "play" in builders:
        fed.append(("contact", "playing with someone"))
    if labels & _WARM:
        fed.append(("contact", "feeling " + ", ".join(sorted(labels & _WARM)[:2])))
    if _PEOPLE.search(chargers):
        fed.append(("contact", "time with people charged you"))
    if any(topics.get(t, 0) >= 0.25 for t in _PEOPLE_TOPICS) and mood is not None and mood >= 6:
        fed.append(("contact", "a good day with people"))
    if labels & _LONELY or _ALONE.search(drainers):
        drained.append(("lonely", "feeling " + (", ".join(sorted(labels & _LONELY)[:2]) or "alone")))
    if _CONFLICT.search(drainers):
        drained.append(("conflict", "a clash with someone"))
    if any(topics.get(t, 0) >= 0.25 for t in _PEOPLE_TOPICS) and mood is not None and mood <= 4 and not drained:
        drained.append(("strain", "a hard day around people"))

    # ---- Calm
    fed, drained = out["calm"]["fed"], out["calm"]["drained"]
    for b, text in (("nature", "time in nature"), ("sleep", "a proper night's sleep"), ("rest", "real rest")):
        if b in builders:
            fed.append(("steady", text))
    if rumination == "low":
        fed.append(("steady", "no looping worry"))
    if mood is not None and mood >= 7:
        fed.append(("steady", f"a good day, mood {mood}/10"))
    if labels & _SETTLED:
        fed.append(("steady", "feeling " + ", ".join(sorted(labels & _SETTLED)[:2])))
    if _OUTDOORS.search(chargers):
        fed.append(("steady", "daylight or a walk charged you"))
    if rumination == "high":
        drained.append(("rumination", "replaying the same worry"))
    if labels & _ANXIOUS:
        drained.append(("rumination", "feeling " + ", ".join(sorted(labels & _ANXIOUS)[:2])))
    if stim.get("sleepDisrupted") or _SLEEPLESS.search(drainers):
        drained.append(("sleep", "broken sleep"))
    if (mood is not None and mood <= 3) or labels & _LOW:
        drained.append(("low_mood", f"a low day, mood {mood}/10" if mood is not None else "a low day"))

    # ---- Spark
    fed, drained = out["spark"]["fed"], out["spark"]["drained"]
    if "exercise" in builders:
        fed.append(("moving", "exercise"))
    if "play" in builders:
        fed.append(("moving", "play"))
    if _MOVING.search(chargers):
        fed.append(("moving", "moving your body charged you"))
    if labels & _ENERGISED:
        fed.append(("moving", "feeling " + ", ".join(sorted(labels & _ENERGISED)[:2])))
    if int(cog.get("passiveConsumptionMinutes") or 0) >= 180 or _SEDENTARY.search(drainers):
        drained.append(("sedentary", "a long stretch of sitting"))
    if labels & _SLUGGISH:
        drained.append(("flat", "feeling " + ", ".join(sorted(labels & _SLUGGISH)[:2])))
    return out


def merge_evidence(items: Iterable[dict]) -> dict[str, dict[str, list[tuple[str, str]]]]:
    """Several entries on one day: the union of what they said."""
    out = {k: {"fed": [], "drained": []} for k in FUEL_KEYS}
    for ev in items:
        for k in FUEL_KEYS:
            out[k]["fed"].extend(ev[k]["fed"])
            out[k]["drained"].extend(ev[k]["drained"])
    return out


# ---------------------------------------------------------------- a week of days

LEVELS = (("low", 0, 40), ("steady", 40, 65), ("strong", 65, 101))


def level_for(score: Optional[float], signal: int) -> str:
    if score is None:
        return "none"
    if signal == 0:
        return "quiet"
    for name, lo, hi in LEVELS:
        if lo <= score < hi:
            return name
    return "strong"


def score_days(days: list[dict], key: str) -> tuple[Optional[int], int, int]:
    """(score 0-100 or None without entries, fed days, drained days) for one fuel over the days given.

    Each analysed day counts once as fed, drained, both or neither, so one bad night cannot sink a
    week on its own and one good walk cannot rescue it: the score is the balance of days.
    """
    analysed = [d for d in days if d.get("analysed")]
    if not analysed:
        return None, 0, 0
    fed = sum(1 for d in analysed if d["evidence"][key]["fed"])
    drained = sum(1 for d in analysed if d["evidence"][key]["drained"])
    score = 50 + 50 * (fed - drained) / len(analysed)
    return int(round(max(0.0, min(100.0, score)))), fed, drained


def top_reasons(days: list[dict], key: str, side: str, limit: int = 3) -> list[dict]:
    """The reasons that came up most, with how many days each appeared on."""
    counts: Counter = Counter()
    for d in days:
        if not d.get("analysed"):
            continue
        for _tag, reason in dict.fromkeys(d["evidence"][key][side]):   # once per day, in the order the rules fired, so ties read the same every time
            counts[reason] += 1
    return [{"text": text, "days": n} for text, n in counts.most_common(limit)]


def top_tag(days: list[dict], key: str) -> Optional[str]:
    counts: Counter = Counter()
    for d in days:
        if d.get("analysed"):
            counts.update(tag for tag, _ in d["evidence"][key]["drained"])
    return counts.most_common(1)[0][0] if counts else None


def pick_challenge(key: str, tag: Optional[str], done_ids: set[str]) -> dict:
    """The act that answers the week's main drain; otherwise the fuel's default. Done today wins, so the tick stays visible."""
    items = CHALLENGES[key]
    for c in items:
        if c["id"] in done_ids:
            return c
    for c in items:
        if tag and c["when"] == tag:
            return c
    return next(c for c in items if c["when"] is None)


def because_line(label: str, score: Optional[int], fed: int, drained: int, analysed: int, fed_by: list[dict], drained_by: list[dict]) -> str:
    if score is None:
        return "No analysed entries in this window yet."
    if fed == 0 and drained == 0:
        return f"Your entries this week do not mention anything that feeds or drains {label}. Try the challenge and write about it."
    parts = []
    if drained:
        parts.append(f"drained on {drained} of {analysed} day{'s' if analysed > 1 else ''}" + (f" ({drained_by[0]['text']})" if drained_by else ""))
    if fed:
        parts.append(f"fed on {fed}" + (f" ({fed_by[0]['text']})" if fed_by else ""))
    return f"{label} was " + ", ".join(parts) + "."


def headline(fuels: list[dict]) -> str:
    scored = [f for f in fuels if f["score"] is not None and f["level"] != "quiet"]
    if not scored:
        return "Write and reflect on an entry or two and the gauges light up."
    low = min(scored, key=lambda f: f["score"])
    high = max(scored, key=lambda f: f["score"])
    if low["score"] >= 65:
        return "All four fuels held up this week. Keep the habits that did it."
    if high is low or high["score"] < 50:
        return f"Light on {low['label']} this week; one small act a day is the way back."
    return f"Light on {low['label']} this week, strong on {high['label']}."


def build_fuels(days: list[dict], previous_days: list[dict], done_today: set[str], today: str) -> dict:
    """The response body: one block per fuel plus a headline. `days` are local days, oldest first,
    each `{"date", "analysed": bool, "evidence": {fuel: {"fed": [...], "drained": [...]}}}`."""
    analysed = sum(1 for d in days if d.get("analysed"))
    fuels = []
    for meta in FUELS:
        key = meta["key"]
        score, fed, drained = score_days(days, key)
        previous, _, _ = score_days(previous_days, key)
        fed_by = top_reasons(days, key, "fed")
        drained_by = top_reasons(days, key, "drained")
        challenge = pick_challenge(key, top_tag(days, key), done_today)
        fuels.append({
            **meta,
            "score": score, "previous": previous, "level": level_for(score, fed + drained),
            "fedDays": fed, "drainedDays": drained,
            "days": [{"date": d["date"], "analysed": bool(d.get("analysed")),
                      "fed": bool(d.get("analysed") and d["evidence"][key]["fed"]),
                      "drained": bool(d.get("analysed") and d["evidence"][key]["drained"])} for d in days],
            "fedByReasons": fed_by, "drainedByReasons": drained_by,
            "because": because_line(meta["label"], score, fed, drained, analysed, fed_by, drained_by),
            "challenge": {"id": challenge["id"], "text": challenge["text"], "why": challenge["why"],
                          "builder": challenge["builder"], "doneToday": challenge["id"] in done_today},
        })
    return {
        "window": {"days": len(days), "entries": analysed, "previousEntries": sum(1 for d in previous_days if d.get("analysed")), "today": today},
        "fuels": fuels,
        "headline": headline(fuels),
        "note": "Not a measurement of brain chemistry: a count of what your entries mention, day by day, and one small act for whichever fuel ran low.",
    }


__all__ = ["FUELS", "FUEL_KEYS", "CHALLENGES", "CHALLENGE_BY_ID", "evidence_from_feedback", "merge_evidence", "score_days", "build_fuels", "level_for", "pick_challenge"]

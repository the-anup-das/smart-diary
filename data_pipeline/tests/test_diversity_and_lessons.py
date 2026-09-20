import asyncio
import random

from data_pipeline.agents.diversity_controller import CUSTOM_PERSONA_PROMPTS, EDGE_CASES, generate_diversity_profile
from data_pipeline.lessons import LessonsStore, normalise


def test_profiles_are_reproducible_from_the_seed():
    a = generate_diversity_profile(random.Random(42))
    b = generate_diversity_profile(random.Random(42))
    c = generate_diversity_profile(random.Random(43))
    assert a == b and a != c


def test_edge_and_persona_rates_are_honoured():
    rng = random.Random(1)
    all_edge = [generate_diversity_profile(rng, edge_case_rate=1.0, persona_rate=0.0) for _ in range(50)]
    assert all(p["edge_case"] for p in all_edge) and all(p["custom_persona_prompt"] is None for p in all_edge)
    none_edge = [generate_diversity_profile(rng, edge_case_rate=0.0, persona_rate=1.0) for _ in range(50)]
    assert all(p["edge_case"] is None for p in none_edge) and all(p["custom_persona_prompt"] in CUSTOM_PERSONA_PROMPTS for p in none_edge)
    forced = generate_diversity_profile(random.Random(2), force_edge_case=True, edge_case_rate=0.0)
    assert forced["edge_case"] in EDGE_CASES


def test_edge_cases_cover_the_new_signals():
    types = {e["type"] for e in EDGE_CASES}
    for needed in ("rumination_high", "calm_low_rumination", "no_signals_control", "messy_grammar", "multi_topic_split", "acute_crisis_signals", "ordinary_venting_not_crisis"):
        assert needed in types


def test_lessons_dedup_count_persist_and_reload(tmp_path):
    path = tmp_path / "lessons.json"
    store = LessonsStore(path, max_items=2)

    async def fill():
        await store.add("labels", "Invented passiveConsumptionMinutes when the entry gave no number.")
        await store.add("labels", "invented passiveconsumptionminutes when the entry gave no number")  # same lesson, different case
        await store.add("labels", "Topic weights summed to 0.8.")
        await store.add("labels", "distressFlag set for figurative venting.")
        await store.add("entry", "short")  # too short to be a lesson
        await store.add("entry", "Ends with a tidy moral lesson, unlike a real diary.")

    asyncio.run(fill())
    top = store.top("labels")
    assert len(top) == 2 and top[0].startswith("Invented passiveConsumptionMinutes")
    assert store.counts() == {"entry": 1, "reviewer": 0, "labels": 3, "judge": 0}
    reloaded = LessonsStore(path, max_items=8)
    assert reloaded.counts() == {"entry": 1, "reviewer": 0, "labels": 3, "judge": 0} and reloaded.top("entry") == ["Ends with a tidy moral lesson, unlike a real diary."]
    assert normalise("Hello,  World!!") == "hello world"


def test_disabled_store_records_nothing(tmp_path):
    store = LessonsStore(tmp_path / "x.json", enabled=False)
    asyncio.run(store.add("labels", "something long enough to count as a lesson"))
    assert store.top("labels") == [] and not (tmp_path / "x.json").exists()

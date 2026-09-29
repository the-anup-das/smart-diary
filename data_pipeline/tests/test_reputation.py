import asyncio

from data_pipeline.reputation import JudgeReputation


def test_rewards_penalties_ordering_and_persistence(tmp_path):
    path = tmp_path / "rep.json"
    rep = JudgeReputation(path)

    async def play():
        await rep.record("a", first_passed=True, second_passed=True)      # +1
        await rep.record("a", first_passed=False, second_passed=False)    # +1
        await rep.record("b", first_passed=True, second_passed=False)     # -3
        await rep.record("b", first_passed=False, second_passed=True)     # -1
        await rep.record("c", first_passed=True, second_passed=False)     # -3

    asyncio.run(play())
    assert rep.score("a") == 2 and rep.score("b") == -4 and rep.score("c") == -3 and rep.score("unknown") == 0
    assert rep.ordered(["c", "b", "a", "unknown"]) == ["a", "unknown", "c", "b"]
    assert rep.threshold_bump("a") == 0 and rep.threshold_bump("b") == 0
    asyncio.run(rep.record("b", first_passed=True, second_passed=False))  # two overturned passes: leniency -6
    assert rep.leniency("b") == -6 and rep.threshold_bump("b") == 1
    for _ in range(2):
        asyncio.run(rep.record("b", first_passed=True, second_passed=False))  # four: leniency -12
    assert rep.threshold_bump("b") == 2
    reloaded = JudgeReputation(path)
    assert reloaded.snapshot()["b"]["overturned_pass"] == 4 and reloaded.score("a") == 2


def test_a_judge_overturned_for_strictness_is_never_made_stricter(tmp_path):
    """The spiral this prevents: a strict judge fails samples, a second judge passes them, the strict
    judge's score falls, and a falling score used to raise its bar, so it failed even more."""
    rep = JudgeReputation(tmp_path / "rep.json")

    async def play():
        for _ in range(500):
            await rep.record("strict", first_passed=False, second_passed=True)   # overturned fail, -1 each

    asyncio.run(play())
    assert rep.score("strict") == -500                   # it still sinks in the ordering, so it is asked last
    assert rep.leniency("strict") == 0 and rep.threshold_bump("strict") == 0   # but its bar is not raised
    assert rep.ordered(["strict", "new"]) == ["new", "strict"]

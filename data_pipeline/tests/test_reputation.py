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
    asyncio.run(rep.record("b", first_passed=True, second_passed=False))  # -7
    assert rep.threshold_bump("b") == 1
    asyncio.run(rep.record("b", first_passed=True, second_passed=False))  # -10
    assert rep.threshold_bump("b") == 2
    reloaded = JudgeReputation(path)
    assert reloaded.snapshot()["b"]["overturned_pass"] == 3 and reloaded.score("a") == 2

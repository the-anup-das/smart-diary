import time

from conftest import good_analysis, good_verdict
from test_graph_flow import APPROVED, _fakes, _run, _runtime

from data_pipeline.run import PipelineManager, describe_profile, stage_event
from data_pipeline.status import CURRENT_SAMPLE, TRACKER, StatusTracker, fmt_seconds


def test_tracker_follows_the_sample_set_by_the_context_variable():
    tracker = StatusTracker()
    tracker.start(3)
    assert CURRENT_SAMPLE.get() == 3 and tracker.rows()[0].stage == "queued"
    tracker.stage("reviewer", "round 1")
    first = tracker.rows()[0].stage_started
    tracker.stage("reviewer", "round 1")            # same stage: the step timer keeps running
    assert tracker.rows()[0].stage_started == first
    time.sleep(0.05)   # monotonic() ticks every 15 ms on Windows
    tracker.stage("editor", "revision 1")           # new stage: the step timer restarts
    assert tracker.rows()[0].stage_started > first and tracker.rows()[0].elapsed() >= 0.03
    notes = []
    tracker.note_listeners.append(lambda attempt, text: notes.append((attempt, text)))
    tracker.note("retry 2/3 after timeout")
    assert notes == [(3, "retry 2/3 after timeout")] and tracker.rows()[0].note == "retry 2/3 after timeout"
    tracker.stage("analyzer")                       # a new stage clears the note
    assert tracker.rows()[0].note == ""
    tracker.stage("judge", attempt=99)              # unknown sample: ignored
    tracker.note("ignored", attempt=99)
    assert len(tracker) == 1 and len(notes) == 1
    tracker.finish(3)
    assert len(tracker) == 0
    assert fmt_seconds(0) == "0:00" and fmt_seconds(125.7) == "2:05"


def test_graph_nodes_report_their_stage_for_the_running_sample(tmp_path, monkeypatch):
    _fakes(monkeypatch, reviews=[{"approved": False, "critique": "Too tidy."}, APPROVED], analyses=[good_analysis()], verdicts=[good_verdict()])
    seen: list[tuple[str, str]] = []
    original = TRACKER.stage

    def recording(stage, detail="", **kw):
        seen.append((stage, detail))
        original(stage, detail, **kw)

    monkeypatch.setattr(TRACKER, "stage", recording)
    TRACKER.start(1)
    try:
        state = _run(_runtime(tmp_path))
        row = TRACKER.samples[1]
    finally:
        TRACKER.finish(1)
    assert state["final_status"] == "PASSED"
    stages = [s for s, _ in seen]
    collapsed = [s for i, s in enumerate(stages) if i == 0 or s != stages[i - 1]]
    assert collapsed == ["writer", "reviewer", "editor", "reviewer", "analyzer", "validator", "judge"]
    assert ("reviewer", "round 2 on a") in seen and ("editor", "revision 1 from the reviewer's critique on a") in seen
    assert row.stage == "judge" and row.detail == "grading on judge-a"   # the context variable reached the nodes through LangGraph


def test_stage_events_describe_each_decision():
    assert stage_event("writer", {"entry": "one two three"}, {}) == "writer drafted 3 words"
    approved = stage_event("reviewer", {"review": {"approved": True}}, {"editor_iteration": 1})
    assert "approved" in approved and "round 2" in approved
    changes = stage_event("reviewer", {"review": {"approved": False, "critique": "Ends [with] a moral."}}, {"editor_iteration": 3})
    assert "discarding" in changes and "Ends \\[with] a moral." in changes
    invalid = stage_event("schema_validator", {"analysis_error": "topics sum to 0.4", "schema_retry_count": 1}, {})
    assert "retry 1" in invalid and "topics sum to 0.4" in invalid
    assert stage_event("schema_validator", {"analysis_error": None}, {}).endswith("ok")
    verdict = good_verdict(overall=4, entry_notes="Entry ends with a lesson.")
    entry_back = stage_event("judge", {"judge_verdict": verdict, "judge_host": "h", "final_status": "REPAIRING_ENTRY"}, {})
    assert "overall 4/10" in entry_back and "back to the editor" in entry_back and "ends with a lesson" in entry_back
    discard = stage_event("judge", {"judge_verdict": verdict, "judge_host": "h", "final_status": "FAILED_JUDGE", "discard_reason": "overall 4"}, {})
    assert "discard" in discard
    agree = stage_event("judge2", {"judge2_verdict": good_verdict(), "judge2_host": "h2", "judge2_passed": True}, {"first_judge_passed": True})
    assert agree.endswith("agrees with the first judge")
    overturned = stage_event("judge2", {"judge2_verdict": good_verdict(overall=3), "judge2_host": "h2", "judge2_passed": False, "discard_reason": "second opinion: weak"}, {"first_judge_passed": True})
    assert "overturned" in overturned and "weak" in overturned
    assert stage_event("judge2", {"judge2_verdict": {"skipped": "429"}, "judge2_passed": None}, {}).endswith("429")
    assert stage_event("failed_review", {"final_status": "FAILED_REVIEW"}, {}) is None
    text = describe_profile({"persona": "nurse", "emotion": "tired", "topic": "work", "style": "terse", "length": {"category": "short"}, "edge_case": {"type": "messy_grammar"}})
    assert text.startswith("nurse / tired / work / terse / short") and "messy_grammar" in text
    who = describe_profile({"persona": {"role": "Small business owner", "age_group": "Mid-Life (35-45)"}, "emotion": "Content and unremarkable, a plain okay day", "topic": "Personal Growth & Identity (breaking bad habits)", "style": "Plain and factual, like notes to self, little emotion", "length": {"category": "long"}})
    assert who.startswith("Small business owner, Mid-Life / Content and unremarkable, a plain okay day / Personal Growth & Identity / Plain and factual, like notes… / long")


def test_manager_runs_without_a_board(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from data_pipeline import config
    from data_pipeline.endpoints import Endpoint

    class Graph:
        async def astream(self, state, cfg=None):
            yield {"writer": {"entry": "a long day", "writer_model": "w"}}
            yield {"judge": {"analysis_json": good_analysis(), "judge_verdict": good_verdict(), "judge_host": "h", "final_status": "PASSED"}}

    monkeypatch.setattr(config, "TELEMETRY_LOG_PATH", tmp_path / "t.jsonl")
    monkeypatch.setattr(config, "REJECTIONS_LOG_PATH", tmp_path / "r.log")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    ep = Endpoint(base_url="http://t/v1", api_key="k", model="teacher", name="analyzer")
    runtime = SimpleNamespace(analyzer=ep)
    manager = PipelineManager(1, runtime, Graph(), seed=1, raw_path=tmp_path / "raw.jsonl")
    import asyncio

    assert asyncio.run(manager.run_single_pipeline()) is not None
    assert len(TRACKER) == 0   # the row is removed when the sample finishes


def test_board_fits_the_terminal_and_counts_every_sample(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from rich.console import Console

    from data_pipeline import config
    from data_pipeline.endpoints import Endpoint
    from data_pipeline.run import RunBoard

    monkeypatch.setattr(config, "TELEMETRY_LOG_PATH", tmp_path / "t.jsonl")
    ep = Endpoint(base_url="http://t/v1", api_key="k", model="teacher", name="analyzer")
    manager = PipelineManager(100, SimpleNamespace(analyzer=ep), None, seed=1, dry_run=True)
    console = Console(width=160, height=20, force_terminal=False)
    board = RunBoard(manager, to_add=100, existing=8, console=console)
    for i in range(1, 16):
        TRACKER.start(i)
        TRACKER.stage("writer" if i > 3 else "judge", "drafting on api.example.com")
    try:
        assert board.visible_rows() == 10                       # 20 rows of terminal minus the bar, counters, tally, header and key hint
        rendered = console.render_str  # noqa: F841
        with console.capture() as cap:
            console.print(board.table())
        text = cap.get()
        assert "and 5 more" in text and text.count("drafting on api.example.com") == 10
        assert "\n 1 " in "\n" + text and "#15" not in text     # oldest first, the newest are the hidden ones
        with console.capture() as cap:
            console.print(board.tally())
        tally = cap.get()
        assert "judge 3" in tally and "writer 12" in tally      # every sample is counted even when its row is hidden
        assert board.table(max_rows=50).row_count == 15
    finally:
        for i in range(1, 16):
            TRACKER.finish(i)
    with console.capture() as cap:
        console.print(board.tally())
    assert "Nothing in flight" in cap.get()


def test_plain_mode_prints_lines_instead_of_a_live_region(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from rich.console import Console

    from data_pipeline import config
    from data_pipeline.endpoints import Endpoint
    from data_pipeline.run import RunBoard

    monkeypatch.setattr(config, "TELEMETRY_LOG_PATH", tmp_path / "t.jsonl")
    ep = Endpoint(base_url="http://t/v1", api_key="k", model="teacher", name="analyzer")
    manager = PipelineManager(100, SimpleNamespace(analyzer=ep), None, seed=1, dry_run=True)
    console = Console(width=160, height=20, force_terminal=False)

    board = RunBoard(manager, to_add=100, existing=8, console=console)
    assert board.plain and board.live is None          # not a terminal: no live region, so a redirected log stays readable
    board = RunBoard(manager, to_add=100, existing=8, console=console, plain=True)
    monkeypatch.setattr(type(console), "is_terminal", property(lambda self: True))
    assert RunBoard(manager, to_add=1, existing=0, console=console).live is not None   # a terminal gets the board back
    assert RunBoard(manager, to_add=1, existing=0, console=console, plain=True).live is None

    for i in (1, 2):
        TRACKER.start(i)
        TRACKER.stage("writer", "drafting on api.example.com")
    try:
        with console.capture() as cap:
            board.heartbeat(force=True)
        line = cap.get()
        assert "approved 0/100" in line and "#1 writer" in line and "#2 writer" in line
        with console.capture() as cap:
            board.heartbeat()                           # too soon after the last one
        assert cap.get() == ""
    finally:
        TRACKER.finish(1)
        TRACKER.finish(2)


def _board(tmp_path, monkeypatch, *, height=20, plain=False):
    from types import SimpleNamespace

    from rich.console import Console

    from data_pipeline import config
    from data_pipeline.endpoints import Endpoint
    from data_pipeline.run import RunBoard

    monkeypatch.setattr(config, "TELEMETRY_LOG_PATH", tmp_path / "t.jsonl")
    ep = Endpoint(base_url="http://t/v1", api_key="k", model="teacher", name="analyzer")
    manager = PipelineManager(100, SimpleNamespace(analyzer=ep), None, seed=1, dry_run=True)
    console = Console(width=160, height=height, force_terminal=False)
    board = RunBoard(manager, to_add=100, existing=8, console=console, plain=plain)
    board.plain = plain          # a captured console is not a terminal; the board under test owns one
    return board, console


def test_arrow_keys_scroll_a_window_over_the_samples(tmp_path, monkeypatch):
    board, console = _board(tmp_path, monkeypatch)
    monkeypatch.setattr(type(board.keys), "active", property(lambda self: True))   # pretend the key reader is running
    for i in range(1, 21):
        TRACKER.start(i)
        TRACKER.stage("writer", f"drafting sample {i}")
    try:
        rows = board.visible_rows()
        assert rows == 10 and board.follow

        def shown():
            with console.capture() as cap:
                console.print(board.table())
            return cap.get()

        assert "drafting sample 1" in shown() and f"drafting sample {rows}" in shown() and f"drafting sample {rows + 1}" not in shown()
        board.handle_key("down")
        board.handle_key("down")
        assert board.scroll == 2 and not board.follow
        assert "drafting sample 1\n" not in shown() and "drafting sample 3" in shown() and f"drafting sample {rows + 2}" in shown()
        board.handle_key("up")
        assert board.scroll == 1
        board.handle_key("pgdn")
        assert board.scroll == 1 + rows - 1
        board.handle_key("end")
        assert board.scroll == 20 - rows and "drafting sample 20" in shown()
        board.handle_key("down")                                   # already at the end: stays put
        assert board.scroll == 20 - rows
        board.handle_key("home")
        assert board.scroll == 0 and board.follow and "drafting sample 1" in shown()
        board.handle_key("pgup")
        assert board.scroll == 0
        with console.capture() as cap:
            console.print(board.hint(rows, len(TRACKER)))
        assert "showing 1 to 10 of 20" in cap.get() and "q finishes" in cap.get()
    finally:
        for i in range(1, 21):
            TRACKER.finish(i)


def test_q_asks_the_run_to_stop_after_the_samples_in_flight(tmp_path, monkeypatch):
    board, console = _board(tmp_path, monkeypatch)
    assert not board.stop_requested
    with console.capture() as cap:
        board.handle_key("quit")
    assert board.stop_requested and "Finishing the samples in flight" in cap.get()
    with console.capture() as cap:
        board.handle_key("quit")                                   # pressed twice: said once
    assert cap.get() == ""


def test_typed_keys_reach_the_board(tmp_path, monkeypatch):
    board, _ = _board(tmp_path, monkeypatch)
    for key in ("down", "down", "quit"):
        board.keys.push(key)
    board.handle_keys()
    assert board.keys.drain() == [] and board.stop_requested


def test_key_sequences_are_decoded_per_platform():
    from data_pipeline.keys import KeyReader, decode_posix, decode_windows

    assert decode_windows("\xe0", "H") == "up" and decode_windows("\x00", "P") == "down"
    assert decode_windows("\xe0", "Q") == "pgdn" and decode_windows("\xe0", "G") == "home"
    assert decode_windows("q", "") == "quit" and decode_windows("z", "") is None
    assert decode_posix("\x1b[A") == "up" and decode_posix("\x1b[B") == "down"
    assert decode_posix("\x1b[6~") == "pgdn" and decode_posix("\x1b[H") == "home"
    assert decode_posix("q") == "quit" and decode_posix("\x1b[Z") is None
    assert decode_windows("\x03", "") == "quit" and decode_posix("\x03") == "quit"   # a console that hands Ctrl+C to the reader still stops the run

    reader = KeyReader()
    assert not reader.available() or reader.available()            # no terminal under pytest, but it must not raise
    assert reader.start() is False and not reader.active           # nothing to read from: stays off, board still works
    reader.push("up")
    assert reader.drain() == ["up"] and reader.drain() == []
    reader.stop()

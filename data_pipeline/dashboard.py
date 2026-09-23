"""Streamlit dashboard for a generation run: one section per agent, judge reputation, lessons, samples.

    streamlit run data_pipeline/dashboard.py
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Distillation dashboard", layout="wide")
st.title("Synthetic data distillation")

BASE_DIR = Path(__file__).resolve().parent
TELEMETRY_PATH = BASE_DIR / "logs" / "telemetry.jsonl"
CALLS_PATH = BASE_DIR / "logs" / "calls.jsonl"
RAW_PATH = BASE_DIR / "output" / "dataset_raw.jsonl"
LESSONS_PATH = BASE_DIR / "output" / "lessons.json"
REPUTATION_PATH = BASE_DIR / "output" / "judge_reputation.json"
DISAGREEMENTS_PATH = BASE_DIR / "output" / "judge_disagreements.jsonl"
MANIFEST_PATH = BASE_DIR / "output" / "splits_manifest.json"

COLUMNS = ["timestamp", "status", "editor_iterations", "entry_repairs", "schema_retries", "judge_retries", "judge_overall", "judge_safety",
           "judge_model", "judge_host", "judge_label", "first_judge_passed", "judge2_model", "judge2_host", "judge2_passed", "judge2_overall",
           "writer_model", "reviewer_model", "reviewer_approved_first", "edge_case", "tokens", "calls", "cost", "discard_reason", "error"]
NUMERIC = ("tokens", "calls", "cost", "judge_overall", "judge_safety", "judge2_overall", "editor_iterations", "entry_repairs", "schema_retries", "judge_retries")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError:
        return {}


def load_telemetry() -> pd.DataFrame:
    df = pd.DataFrame(read_jsonl(TELEMETRY_PATH))
    if df.empty:
        return df
    df = df.reindex(columns=COLUMNS)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    for col in NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["status"] = df["status"].fillna("UNKNOWN")
    return df


def pct(part: float, whole: float) -> str:
    return f"{part / whole * 100:.0f}%" if whole else "-"


df = load_telemetry()
if df.empty:
    st.warning("No telemetry yet. Run `python -m data_pipeline.run --count 5` first.")
    st.stop()

total = len(df)
passed = int((df["status"] == "PASSED").sum())
finished = df[df["status"] != "CRASH"]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Attempts", total)
c2.metric("Approved", passed)
c3.metric("Pass rate", pct(passed, total))
c4.metric("Tokens", f"{int(df['tokens'].sum()):,}")
c5.metric("Cost", f"${df['cost'].sum():.2f}")

st.markdown("#### Outcomes")
st.bar_chart(df["status"].value_counts())

# ---------------------------------------------------------------- agents
st.markdown("---")
st.markdown("### Agents")
a1, a2, a3 = st.columns(3)

with a1:
    st.markdown("#### Writer")
    writers = finished.groupby(finished["writer_model"].fillna("-"))
    st.dataframe(pd.DataFrame({
        "samples": writers.size(),
        "pass rate": writers["status"].apply(lambda s: pct((s == "PASSED").sum(), len(s))),
        "avg tokens": writers["tokens"].mean().round(0),
    }))
    st.caption("Writers rotate per batch when WRITER_MODELS lists several models.")

with a2:
    st.markdown("#### Reviewer and editor")
    approved_first = finished["reviewer_approved_first"]
    st.metric("Approved on first review", pct(int(approved_first.fillna(False).astype(bool).sum()), int(approved_first.notna().sum())))
    st.metric("Rejected after three rounds", int((df["status"] == "FAILED_REVIEW").sum()))
    st.bar_chart(finished["editor_iterations"].astype(int).value_counts().sort_index().rename("samples by editor rounds"))
    st.caption(f"Reviewer: {', '.join(finished['reviewer_model'].dropna().unique()) or '-'}")

with a3:
    st.markdown("#### Analyzer")
    st.metric("Schema retries per sample", f"{finished['schema_retries'].mean():.2f}")
    st.metric("Failed validation after retries", int((df["status"] == "FAILED_SCHEMA").sum()))
    st.metric("Label repairs after a judge fail", int(finished["judge_retries"].sum()))
    st.metric("Entries rewritten after a judge fail", int(finished["entry_repairs"].sum()))

st.markdown("#### Judge")
j1, j2 = st.columns(2)
judged = finished[finished["judge_overall"] > 0]
with j1:
    by_host = judged.groupby(judged["judge_label"].fillna(judged["judge_host"]).fillna("-"))
    st.dataframe(pd.DataFrame({
        "samples": by_host.size(),
        "first-judge pass rate": by_host["first_judge_passed"].apply(lambda s: pct(int(s.fillna(False).astype(bool).sum()), len(s))),
        "mean overall": by_host["judge_overall"].mean().round(2),
        "mean safety": by_host["judge_safety"].mean().round(2),
    }))
    if not judged.empty:
        st.bar_chart(judged["judge_overall"].astype(int).value_counts().sort_index().rename("overall score"))
with j2:
    st.markdown("**Second judge and reputation**")
    second = finished[finished["judge2_passed"].notna()]
    if not second.empty:
        agree = (second["judge2_passed"].astype(bool) == second["first_judge_passed"].fillna(False).astype(bool)).sum()
        st.metric("Re-judged samples", len(second))
        st.metric("Agreement with the first judge", pct(int(agree), len(second)))
        st.metric("Passes overturned", int((second["first_judge_passed"].fillna(False).astype(bool) & ~second["judge2_passed"].astype(bool)).sum()))
    else:
        st.info("No second-judge verdicts yet.")
    reputation = read_json(REPUTATION_PATH)
    if reputation:
        st.dataframe(pd.DataFrame(reputation).T[["score", "agreed", "overturned_pass", "overturned_fail"]].sort_values("score", ascending=False))
        st.caption("Agreement +1, overturned pass -3, overturned fail -1. The best-scored host is asked first; a slipping one must award more points to pass a sample.")
    disagreements = read_jsonl(DISAGREEMENTS_PATH)
    if disagreements:
        with st.expander(f"Disagreements ({len(disagreements)})"):
            for row in disagreements[-5:][::-1]:
                st.write(f"first {row['first'].get('model')}: {'pass' if row['first'].get('passed') else 'fail'} | second {row['second'].get('model')}: {'pass' if row['second'].get('passed') else 'fail'}")
                st.caption((row["second"].get("verdict") or {}).get("label_notes") or (row["second"].get("verdict") or {}).get("hard_fail_reason") or "")

# ---------------------------------------------------------------- learning over time
st.markdown("---")
st.markdown("#### Judge pass rate per batch of 25 (is the feedback loop helping?)")
if len(judged) >= 25:
    batches = judged.reset_index(drop=True)
    batches["batch"] = batches.index // 25
    per_batch = batches.groupby("batch").agg(pass_rate=("status", lambda s: (s == "PASSED").mean() * 100), mean_overall=("judge_overall", "mean"))
    st.line_chart(per_batch)
else:
    st.info("Fewer than 25 judged samples so far.")

lessons = read_json(LESSONS_PATH)
if lessons:
    st.markdown("#### Lessons the agents are applying")
    cols = st.columns(4)
    for col, bucket, who in zip(cols, ("entry", "reviewer", "labels", "judge"), ("writer", "reviewer", "analyzer", "judge")):
        rows = sorted(lessons.get(bucket, {}).values(), key=lambda r: -r.get("count", 0))[:6]
        with col:
            st.markdown(f"**{who}** ({len(lessons.get(bucket, {}))})")
            for r in rows:
                st.write(f"- ({r.get('count', 1)}) {r.get('text')}")

failed = df[df["status"] != "PASSED"]
if not failed.empty:
    st.markdown("#### Rejection reasons (top 8)")
    st.bar_chart(failed["discard_reason"].fillna(failed["error"]).fillna("unknown").str.slice(0, 60).value_counts().head(8))

if MANIFEST_PATH.exists():
    with st.expander("Latest splits manifest"):
        st.json(read_json(MANIFEST_PATH))


# ---------------------------------------------------------------- model speed
st.markdown("---")
st.markdown("### Model speed")
calls = pd.DataFrame(read_jsonl(CALLS_PATH))
if calls.empty:
    st.write("No call log yet. Every model call a run makes is written to `logs/calls.jsonl` with its latency and tokens per second.")
else:
    calls["timestamp"] = pd.to_datetime(calls["timestamp"], errors="coerce")
    calls["label"] = calls["model"].fillna("?") + "@" + calls["host"].fillna("?")
    calls["ok"] = calls["ok"].fillna(False).astype(bool)
    calls["timeout"] = calls["timeout"].fillna(False).astype(bool)
    calls["role"] = calls["role"].fillna("").replace("", "-")
    ok = calls[calls["ok"]]
    by_model = calls.groupby("label")
    good = ok.groupby("label")
    speed = pd.DataFrame({
        "calls": by_model.size(),
        "roles": by_model["role"].apply(lambda s: ", ".join(sorted(set(s)))),
        "median latency s": good["latency_s"].median().round(1),
        "p90 latency s": good["latency_s"].quantile(0.9).round(1),
        "median tok/s": good["tokens_per_s"].median().round(1),
        "best tok/s": good["tokens_per_s"].max().round(1),
        "avg reply tokens": good["completion_tokens"].mean().round(0),
        "errors": by_model["ok"].apply(lambda s: int((~s).sum())),
        "timeouts": by_model["timeout"].apply(lambda s: int(s.sum())),
    }).sort_values("calls", ascending=False)
    st.dataframe(speed)
    st.caption("Tokens per second is reply tokens over the whole call, so prompt processing and queueing on the server count against it. "
               "Latency is wall-clock from request to reply, after the pipeline's own per-host queue.")

    m1, m2 = st.columns(2)
    with m1:
        st.markdown("#### Speed over time")
        recent = ok.dropna(subset=["tokens_per_s", "timestamp"]).tail(400)
        if recent.empty:
            st.write("No timed calls with token counts yet.")
        else:
            st.line_chart(recent.pivot_table(index="timestamp", columns="label", values="tokens_per_s"))
            st.caption("Each point is one call; a falling line on one model means its server is queueing or swapping.")
    with m2:
        st.markdown("#### By role")
        by_role = ok.groupby(["role", "label"]).agg(
            calls=("ok", "size"), median_latency_s=("latency_s", "median"), median_tps=("tokens_per_s", "median"),
        ).round(1).sort_values("calls", ascending=False)
        st.dataframe(by_role)
        st.caption("The same model can be slow as a judge and quick as a reviewer: the prompts differ in length.")
    slow = ok.sort_values("latency_s", ascending=False).head(5)[["timestamp", "label", "role", "latency_s", "completion_tokens", "tokens_per_s"]]
    with st.expander("Slowest five calls"):
        st.dataframe(slow)

# ---------------------------------------------------------------- samples
st.markdown("---")
st.markdown("### Dataset explorer")
raw = read_jsonl(RAW_PATH)
tab1, tab2 = st.tabs([f"Recent approved samples ({len(raw)} total)", "Recent rejections"])
with tab1:
    if raw:
        for offset, sample in enumerate(reversed(raw[-5:])):
            meta = sample.get("meta", {})
            with st.expander(f"Sample {len(raw) - offset}: {meta.get('edge_case') or 'plain'} | judge {meta.get('judge_scores', {}).get('overall')}/10 via {meta.get('judge_model')} | writer {meta.get('writer_model')}"):
                st.markdown("**Entry**")
                st.info(sample.get("entry", ""))
                st.markdown("**Analysis**")
                st.code(json.dumps(sample.get("analysis", {}), ensure_ascii=False, indent=1), language="json")
                st.markdown("**Meta**")
                st.json(meta)
    else:
        st.write("No approved samples yet.")
with tab2:
    recent = failed.tail(10)
    if recent.empty:
        st.write("No rejections to show.")
    for _, row in recent.iloc[::-1].iterrows():
        when = row["timestamp"].strftime("%H:%M:%S") if pd.notna(row["timestamp"]) else "?"
        with st.expander(f"{row['status']} at {when} | judge {row['judge_overall']:.0f}/10"):
            st.error(f"{row['discard_reason'] or row['error'] or 'unknown'}")
            st.write(f"tokens {int(row['tokens'])}, calls {int(row['calls'])}, cost ${row['cost']:.4f}")

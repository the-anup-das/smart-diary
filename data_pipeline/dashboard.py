"""Streamlit dashboard for a generation run: outcomes, judge scores, lessons, and the raw dataset.

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
RAW_PATH = BASE_DIR / "output" / "dataset_raw.jsonl"
LESSONS_PATH = BASE_DIR / "output" / "lessons.json"
MANIFEST_PATH = BASE_DIR / "output" / "splits_manifest.json"

COLUMNS = ["timestamp", "status", "editor_iterations", "schema_retries", "judge_retries", "judge_overall", "judge_safety",
           "judge_model", "judge_host", "judge2_model", "writer_model", "edge_case", "tokens", "calls", "cost", "discard_reason", "error"]


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


def load_telemetry() -> pd.DataFrame:
    df = pd.DataFrame(read_jsonl(TELEMETRY_PATH))
    if df.empty:
        return df
    df = df.reindex(columns=COLUMNS)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    for col in ("tokens", "calls", "cost", "judge_overall", "judge_safety", "editor_iterations", "schema_retries", "judge_retries"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["status"] = df["status"].fillna("UNKNOWN")
    return df


df = load_telemetry()
if df.empty:
    st.warning("No telemetry yet. Run `python -m data_pipeline.run --count 5` first.")
    st.stop()

total = len(df)
passed = int((df["status"] == "PASSED").sum())
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Attempts", total)
c2.metric("Approved", passed)
c3.metric("Pass rate", f"{passed / total * 100:.1f}%")
c4.metric("Tokens", f"{int(df['tokens'].sum()):,}")
c5.metric("Cost", f"${df['cost'].sum():.2f}")

st.markdown("---")
left, right = st.columns(2)

with left:
    st.markdown("#### Outcomes over time")
    if total > 10:
        counts = df.set_index("timestamp").groupby([pd.Grouper(freq="15Min"), "status"]).size().unstack(fill_value=0)
        st.bar_chart(counts)
    else:
        st.info("Not enough attempts to chart yet.")

with right:
    st.markdown("#### Judge pass rate per batch of 25 (does the feedback loop help?)")
    judged = df[df["judge_overall"] > 0].reset_index(drop=True)
    if len(judged) >= 25:
        judged["batch"] = judged.index // 25
        per_batch = judged.groupby("batch").agg(pass_rate=("status", lambda s: (s == "PASSED").mean() * 100), mean_overall=("judge_overall", "mean"))
        st.line_chart(per_batch)
    else:
        st.info("Fewer than 25 judged samples so far.")

left2, right2 = st.columns(2)
with left2:
    st.markdown("#### Judge overall score")
    scored = df[df["judge_overall"] > 0]["judge_overall"]
    if not scored.empty:
        st.bar_chart(scored.value_counts().sort_index())
with right2:
    st.markdown("#### Rejection reasons (top 8)")
    failed = df[df["status"] != "PASSED"]
    if not failed.empty:
        st.bar_chart(failed["discard_reason"].fillna(failed["error"]).fillna("unknown").str.slice(0, 60).value_counts().head(8))
    else:
        st.success("No rejections yet.")

st.markdown("#### Judge hosts and writers")
h1, h2 = st.columns(2)
h1.dataframe(df["judge_host"].fillna("-").value_counts().rename("samples"))
h2.dataframe(df["writer_model"].fillna("-").value_counts().rename("samples"))

if LESSONS_PATH.exists():
    st.markdown("#### Lessons the pipeline is applying")
    try:
        lessons = json.loads(LESSONS_PATH.read_text(encoding="utf-8"))
        for bucket in ("entry", "labels"):
            rows = sorted(lessons.get(bucket, {}).values(), key=lambda r: -r.get("count", 0))[:8]
            if rows:
                st.markdown(f"**{bucket}**")
                for r in rows:
                    st.write(f"- ({r.get('count', 1)}) {r.get('text')}")
    except ValueError:
        st.write("lessons.json is not readable")

if MANIFEST_PATH.exists():
    st.markdown("#### Latest splits manifest")
    st.json(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))

st.markdown("---")
st.markdown("### Dataset explorer")
raw = read_jsonl(RAW_PATH)
tab1, tab2 = st.tabs([f"Recent approved samples ({len(raw)} total)", "Recent rejections"])
with tab1:
    if raw:
        for offset, sample in enumerate(reversed(raw[-5:])):
            meta = sample.get("meta", {})
            with st.expander(f"Sample {len(raw) - offset}: {meta.get('edge_case') or 'plain'} | judge {meta.get('judge_scores', {}).get('overall')}/10 | {meta.get('writer_model')}"):
                st.markdown("**Entry**")
                st.info(sample.get("entry", ""))
                st.markdown("**Analysis**")
                st.code(json.dumps(sample.get("analysis", {}), ensure_ascii=False, indent=1), language="json")
                st.markdown("**Meta**")
                st.json(meta)
    else:
        st.write("No approved samples yet.")
with tab2:
    recent = df[df["status"] != "PASSED"].tail(10)
    if recent.empty:
        st.write("No rejections to show.")
    for _, row in recent.iloc[::-1].iterrows():
        when = row["timestamp"].strftime("%H:%M:%S") if pd.notna(row["timestamp"]) else "?"
        with st.expander(f"{row['status']} at {when} | judge {row['judge_overall']:.0f}/10"):
            st.error(f"{row['discard_reason'] or row['error'] or 'unknown'}")
            st.write(f"tokens {int(row['tokens'])}, calls {int(row['calls'])}, cost ${row['cost']:.4f}")

"""Streamlit Dashboard for analyzing Synthetic Data Pipeline generation."""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title="Data Distillation Dashboard", layout="wide")
st.title("🤖 Synthetic Data Distillation Dashboard")

# Paths
BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
TELEMETRY_PATH = LOGS_DIR / "telemetry.jsonl"
REJECTIONS_PATH = LOGS_DIR / "rejections.log"
TRAIN_DATASET_PATH = BASE_DIR / "output" / "training_dataset.jsonl"

def load_telemetry():
    if not TELEMETRY_PATH.exists():
        return pd.DataFrame()
    
    data = []
    with open(TELEMETRY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    data.append(json.loads(line))
                except:
                    pass
    df = pd.DataFrame(data)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

df = load_telemetry()

if df.empty:
    st.warning("No telemetry data found. Run `python data_pipeline/run.py` to start generating data.")
    st.stop()

# Overall Metrics
st.markdown("### 📊 Live Pipeline Metrics")
col1, col2, col3, col4 = st.columns(4)

total_attempts = len(df)
passed = len(df[df["status"] == "PASSED"])
failed = total_attempts - passed
pass_rate = (passed / total_attempts) * 100 if total_attempts > 0 else 0
total_cost = df["cost"].sum()

col1.metric("Total Generation Attempts", total_attempts)
col2.metric("Approved Samples", passed)
col3.metric("Pass Rate", f"{pass_rate:.1f}%")
col4.metric("Total API Cost", f"${total_cost:.2f}")

st.markdown("---")

# Charts row 1
col_c1, col_c2 = st.columns(2)

with col_c1:
    st.markdown("#### Pass vs Reject Over Time")
    # Resample by hour or 10-minute intervals
    df_time = df.set_index("timestamp").copy()
    if len(df_time) > 10:
        counts = df_time.groupby([pd.Grouper(freq='5Min'), 'status']).size().unstack(fill_value=0)
        st.bar_chart(counts, color=["#ff4b4b", "#00cc66"] if "PASSED" in counts else None)
    else:
        st.info("Not enough data to plot time series yet.")

with col_c2:
    st.markdown("#### Quality Engineering (QE) Score Progression")
    st.line_chart(df["qe_score"])

# Charts row 2
col_c3, col_c4 = st.columns(2)

with col_c3:
    st.markdown("#### Cumulative API Cost ($)")
    df["cumulative_cost"] = df["cost"].cumsum()
    st.line_chart(df["cumulative_cost"])

with col_c4:
    st.markdown("#### Rejection Reasons (Top 5)")
    if failed > 0:
        reasons = df[df["status"] != "PASSED"]["discard_reason"].value_counts().head(5)
        st.bar_chart(reasons)
    else:
        st.success("No rejections yet!")

st.markdown("---")

# Data Explorer
st.markdown("### 🔍 Dataset Explorer")
tab1, tab2 = st.tabs(["Recent Approved Samples", "Recent Rejections"])

with tab1:
    if TRAIN_DATASET_PATH.exists():
        samples = []
        # Get last 5 samples
        with open(TRAIN_DATASET_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()[-5:]
            for line in lines:
                samples.append(json.loads(line))
        
        for idx, sample in enumerate(reversed(samples)):
            with st.expander(f"Approved Sample #{len(lines) - idx}"):
                msgs = sample.get("conversations", [])
                user_msg = next((m["value"] for m in msgs if m["from"] == "human"), "N/A")
                assistant_msg = next((m["value"] for m in msgs if m["from"] == "gpt"), "N/A")
                st.markdown("**User Entry:**")
                st.info(user_msg)
                st.markdown("**Agent Output (CoT + JSON):**")
                st.code(assistant_msg, language="json")
    else:
        st.write("No approved samples written to disk yet.")

with tab2:
    if failed > 0:
        recent_fails = df[df["status"] != "PASSED"].tail(10)
        for _, row in recent_fails.iloc[::-1].iterrows():
            with st.expander(f"Rejected at {row['timestamp'].strftime('%H:%M:%S')} - Score: {row['qe_score']}"):
                st.error(f"**Reason:** {row['discard_reason']}")
                st.write(f"Tokens wasted: {row['tokens']}")
                st.write(f"Cost wasted: ${row['cost']:.4f}")
    else:
        st.write("No rejections to show.")

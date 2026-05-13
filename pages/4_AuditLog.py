"""
Page 4: Audit Log.
Displays override logs, security events, and observability traces.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(
    page_title="Audit Log",
    page_icon="📋",
    layout="wide",
)

st.title("📋 Audit Log")

# --- Override Logs ---
st.subheader("Override Events")

from agent.override_manager import get_override_logs

override_logs = get_override_logs()

if override_logs:
    df_overrides = pd.DataFrame(override_logs)
    st.dataframe(
        df_overrides,
        use_container_width=True,
        column_config={
            "timestamp": st.column_config.DatetimeColumn("Timestamp"),
            "candidate_id": st.column_config.TextColumn("Candidate ID"),
            "candidate_name": st.column_config.TextColumn("Name"),
            "dimension": st.column_config.TextColumn("Dimension"),
            "old_score": st.column_config.NumberColumn("Old Score"),
            "new_score": st.column_config.NumberColumn("New Score"),
            "reason": st.column_config.TextColumn("Reason"),
        },
    )
    
    # Export as CSV
    csv = df_overrides.to_csv(index=False)
    st.download_button(
        label="📥 Export Overrides as CSV",
        data=csv,
        file_name="override_logs.csv",
        mime="text/csv",
        use_container_width=True,
    )
else:
    st.info("No override events recorded yet.")

# --- Security Logs ---
st.markdown("---")
st.subheader("Security Events")

from agent.override_manager import get_security_logs

security_logs = get_security_logs()

if security_logs:
    st.warning(f"⚠️ {len(security_logs)} security event(s) detected!")
    
    df_security = pd.DataFrame(security_logs)
    st.dataframe(
        df_security,
        use_container_width=True,
        column_config={
            "timestamp": st.column_config.DatetimeColumn("Timestamp"),
            "event_type": st.column_config.TextColumn("Event Type"),
            "candidate_id": st.column_config.TextColumn("Candidate ID"),
            "stripped_content": st.column_config.TextColumn("Stripped Content"),
            "reason": st.column_config.TextColumn("Reason"),
        },
    )
    
    # Export as CSV
    csv_sec = df_security.to_csv(index=False)
    st.download_button(
        label="📥 Export Security Events as CSV",
        data=csv_sec,
        file_name="security_logs.csv",
        mime="text/csv",
        use_container_width=True,
    )
else:
    st.success("✅ No security events detected. All inputs clean.")

# --- Observability ---
st.markdown("---")
st.subheader("Observability")

langsmith_key = os.getenv("LANGCHAIN_API_KEY")
langsmith_project = os.getenv("LANGCHAIN_PROJECT", "hr-shortlisting-agent")

if langsmith_key:
    st.success("✅ LangSmith tracing is configured")
    st.markdown(f"**Project:** {langsmith_project}")
    st.markdown("View traces at: https://smith.langchain.com/")
else:
    st.info("LangSmith tracing is not configured. Set `LANGCHAIN_API_KEY` in `.env` to enable.")

# --- Session Statistics ---
st.markdown("---")
st.subheader("Session Statistics")

if "ranked_candidates" in st.session_state and st.session_state["ranked_candidates"]:
    candidates = st.session_state["ranked_candidates"]
    
    col1, col2, col3 = st.columns(3)
    
    total_overrides = sum(1 for c in candidates if c.override_applied)
    total_escalated = sum(1 for c in candidates if c.escalate_for_interview)
    total_low_conf = sum(1 for c in candidates if c.low_confidence)
    
    col1.metric("Overrides Applied", total_overrides)
    col2.metric("Escalated for Interview", total_escalated)
    col3.metric("Low Confidence Flags", total_low_conf)
    
    # Score distribution
    st.markdown("**Score Distribution:**")
    scores = [c.weighted_total for c in candidates]
    
    import plotly.express as px
    
    fig = px.histogram(
        x=scores,
        nbins=10,
        range_x=[0, 10],
        labels={"x": "Weighted Total Score", "y": "Count"},
        title="Distribution of Weighted Total Scores",
        color_discrete_sequence=["#667eea"],
    )
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True, key="score_dist")
else:
    st.info("No session data available. Run the pipeline first.")

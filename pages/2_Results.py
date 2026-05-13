"""
Page 2: Shortlist Results.
Displays ranked candidates with scores, charts, and download options.
"""

from __future__ import annotations

import os
import sys

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(
    page_title="Shortlist Results",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Shortlist Results")

if "ranked_candidates" not in st.session_state or not st.session_state["ranked_candidates"]:
    st.info("No results available yet. Go to **Upload & Configure** to run the analysis first.")
    st.stop()

candidates = st.session_state["ranked_candidates"]
jd = st.session_state.get("jd_requirements")

# --- Summary Metrics ---
st.subheader("Summary")

col1, col2, col3, col4, col5 = st.columns(5)

strong_hire = sum(1 for c in candidates if c.hire_recommendation.value == "Strong Hire")
hire = sum(1 for c in candidates if c.hire_recommendation.value == "Hire")
maybe = sum(1 for c in candidates if c.hire_recommendation.value == "Maybe")
no_hire = sum(1 for c in candidates if c.hire_recommendation.value == "No Hire")

col1.metric("Total Evaluated", len(candidates))
col2.metric("Strong Hire", strong_hire)
col3.metric("Hire", hire)
col4.metric("Maybe", maybe)
col5.metric("No Hire", no_hire)

# --- Download Buttons ---
st.markdown("---")
report_paths = st.session_state.get("report_paths", {})

cols = st.columns(3)

if "json" in report_paths and os.path.exists(report_paths["json"]):
    with open(report_paths["json"], "r") as f:
        cols[0].download_button(
            label="📥 Download JSON",
            data=f.read(),
            file_name=os.path.basename(report_paths["json"]),
            mime="application/json",
            use_container_width=True,
        )

if "html" in report_paths and os.path.exists(report_paths["html"]):
    with open(report_paths["html"], "r") as f:
        cols[1].download_button(
            label="🌐 Download HTML",
            data=f.read(),
            file_name=os.path.basename(report_paths["html"]),
            mime="text/html",
            use_container_width=True,
        )

if "pdf" in report_paths and os.path.exists(report_paths["pdf"]):
    with open(report_paths["pdf"], "rb") as f:
        cols[2].download_button(
            label="📄 Download PDF",
            data=f.read(),
            file_name=os.path.basename(report_paths["pdf"]),
            mime="application/pdf",
            use_container_width=True,
        )

# --- Ranked Candidate Table ---
st.markdown("---")
st.subheader("Ranked Candidates")

# Prepare table data
table_data = []
for c in candidates:
    table_data.append({
        "Rank": c.rank,
        "Name": c.candidate_name,
        "Skills": f"{c.skills.score:.1f}",
        "Experience": f"{c.experience.score:.1f}",
        "Education": f"{c.education.score:.1f}",
        "Portfolio": f"{c.portfolio.score:.1f}",
        "Communication": f"{c.communication.score:.1f}",
        "Total": f"{c.weighted_total:.2f}",
        "Recommendation": c.hire_recommendation.value,
        "Low Confidence": "⚠️" if c.low_confidence else "",
    })

# Color coding for recommendation
def color_recommendation(val):
    colors = {
        "Strong Hire": "color: #28a745; font-weight: bold;",
        "Hire": "color: #007bff; font-weight: bold;",
        "Maybe": "color: #ffc107; font-weight: bold;",
        "No Hire": "color: #dc3545; font-weight: bold;",
    }
    return colors.get(val, "")

st.dataframe(
    table_data,
    column_config={
        "Rank": st.column_config.NumberColumn("Rank", width="small"),
        "Total": st.column_config.NumberColumn("Weighted Total", width="medium"),
        "Recommendation": st.column_config.TextColumn("Recommendation", width="medium"),
    },
    use_container_width=True,
    hide_index=True,
)

# --- Per-Candidate Detail Expanders ---
st.markdown("---")
st.subheader("Candidate Details")

for candidate in candidates:
    # Build label with indicators
    label = f"#{candidate.rank} — {candidate.candidate_name} ({candidate.hire_recommendation.value}) — {candidate.weighted_total:.2f}"
    if candidate.low_confidence:
        label += " ⚠️"
    if candidate.escalate_for_interview:
        label += " ⭐"
    
    with st.expander(label):
        col1, col2 = st.columns([2, 3])
        
        with col1:
            # Radar chart
            fig = go.Figure()
            
            fig.add_trace(go.Scatterpolar(
                r=[
                    candidate.skills.score,
                    candidate.experience.score,
                    candidate.education.score,
                    candidate.portfolio.score,
                    candidate.communication.score,
                ],
                theta=["Skills\n(30%)", "Experience\n(25%)", "Education\n(15%)", "Portfolio\n(20%)", "Communication\n(10%)"],
                fill="toself",
                fillcolor="rgba(102, 126, 234, 0.3)",
                line=dict(color="rgb(102, 126, 234)", width=2),
                name=candidate.candidate_name,
            ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 10],
                        tickfont=dict(size=10),
                    ),
                    angularaxis=dict(tickfont=dict(size=10)),
                ),
                showlegend=False,
                margin=dict(l=40, r=40, t=30, b=30),
                height=300,
            )
            
            st.plotly_chart(fig, use_container_width=True, key=f"radar_{candidate.candidate_id}")
        
        with col2:
            # Dimension score table
            st.markdown("**Dimension Scores:**")
            
            score_data = [
                ["Skills Match (30%)", f"{candidate.skills.score:.1f}/10", candidate.skills.justification],
                ["Experience (25%)", f"{candidate.experience.score:.1f}/10", candidate.experience.justification],
                ["Education & Certs (15%)", f"{candidate.education.score:.1f}/10", candidate.education.justification],
                ["Portfolio (20%)", f"{candidate.portfolio.score:.1f}/10", candidate.portfolio.justification],
                ["Communication (10%)", f"{candidate.communication.score:.1f}/10", candidate.communication.justification],
            ]
            
            for dim, score, just in score_data:
                st.markdown(f"**{dim}:** {score}")
                st.markdown(f"*{just}*")
                st.markdown("---")
            
            st.markdown(f"**Overall Summary:** {candidate.overall_summary}")
            
            if candidate.embedding_skills_score is not None:
                st.markdown(f"*(Embedding similarity score: {candidate.embedding_skills_score:.3f})*")
        
        # Action buttons
        col_a, col_b = st.columns(2)
        
        if candidate.escalate_for_interview:
            if col_a.button("Remove Interview Flag", key=f"deesc_{candidate.candidate_id}"):
                from agent.override_manager import toggle_escalate
                toggle_escalate(candidate)
                st.rerun()
        else:
            if col_a.button("⭐ Flag for Interview", key=f"esc_{candidate.candidate_id}"):
                from agent.override_manager import toggle_escalate
                toggle_escalate(candidate)
                st.rerun()
        
        if candidate.low_confidence:
            col_b.warning("⚠️ Low Confidence — This candidate's scores may need manual review")
        
        if candidate.override_applied:
            st.info(f"✏️ Override Applied: {candidate.override_reason}")

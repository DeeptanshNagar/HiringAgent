"""
Page 3: Override Panel.
Allows HR to manually adjust scores with justification and re-rank.
"""

from __future__ import annotations

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(
    page_title="Override Panel",
    page_icon="✏️",
    layout="wide",
)

st.title("✏️ Override Panel")

if "ranked_candidates" not in st.session_state or not st.session_state["ranked_candidates"]:
    st.info("No candidates to override. Go to **Upload & Configure** to run the analysis first.")
    st.stop()

candidates = st.session_state["ranked_candidates"]
jd = st.session_state.get("jd_requirements")

# --- Candidate Selector ---
st.subheader("Select Candidate to Override")

candidate_options = {
    f"#{c.rank} — {c.candidate_name} ({c.weighted_total:.2f})": c
    for c in candidates
}

selected_label = st.selectbox(
    "Choose candidate:",
    options=list(candidate_options.keys()),
)

selected_candidate = candidate_options[selected_label]

st.markdown("---")

# --- Score Override Form ---
st.subheader(f"Override Scores for: {selected_candidate.candidate_name}")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Current Scores:**")
    st.markdown(f"- Skills: {selected_candidate.skills.score:.1f}")
    st.markdown(f"- Experience: {selected_candidate.experience.score:.1f}")
    st.markdown(f"- Education: {selected_candidate.education.score:.1f}")
    st.markdown(f"- Portfolio: {selected_candidate.portfolio.score:.1f}")
    st.markdown(f"- Communication: {selected_candidate.communication.score:.1f}")
    st.markdown(f"- **Weighted Total: {selected_candidate.weighted_total:.2f}**")
    st.markdown(f"- **Recommendation: {selected_candidate.hire_recommendation.value}**")

with col2:
    st.markdown("**New Scores:**")
    
    new_skills = st.number_input(
        "Skills Match",
        min_value=0.0,
        max_value=10.0,
        value=float(selected_candidate.skills.score),
        step=0.5,
        key="override_skills",
    )
    new_experience = st.number_input(
        "Experience Relevance",
        min_value=0.0,
        max_value=10.0,
        value=float(selected_candidate.experience.score),
        step=0.5,
        key="override_experience",
    )
    new_education = st.number_input(
        "Education & Certs",
        min_value=0.0,
        max_value=10.0,
        value=float(selected_candidate.education.score),
        step=0.5,
        key="override_education",
    )
    new_portfolio = st.number_input(
        "Project / Portfolio",
        min_value=0.0,
        max_value=10.0,
        value=float(selected_candidate.portfolio.score),
        step=0.5,
        key="override_portfolio",
    )
    new_communication = st.number_input(
        "Communication Quality",
        min_value=0.0,
        max_value=10.0,
        value=float(selected_candidate.communication.score),
        step=0.5,
        key="override_communication",
    )

# --- Override Reason ---
override_reason = st.text_area(
    "Reason for Override (required if any score changed):",
    placeholder="Explain why you are changing these scores...",
    key="override_reason",
)

# --- Visual Diff ---
st.markdown("---")
st.subheader("Score Comparison")

diff_data = {
    "Dimension": ["Skills", "Experience", "Education", "Portfolio", "Communication"],
    "Original": [
        selected_candidate.skills.score,
        selected_candidate.experience.score,
        selected_candidate.education.score,
        selected_candidate.portfolio.score,
        selected_candidate.communication.score,
    ],
    "New": [new_skills, new_experience, new_education, new_portfolio, new_communication],
}

# Highlight changes
import pandas as pd
diff_df = pd.DataFrame(diff_data)
diff_df["Changed"] = diff_df["Original"] != diff_df["New"]

st.dataframe(
    diff_df,
    column_config={
        "Changed": st.column_config.CheckboxColumn("Modified"),
    },
    use_container_width=True,
    hide_index=True,
)

# --- Apply Override Button ---
st.markdown("---")

has_changes = any([
    new_skills != selected_candidate.skills.score,
    new_experience != selected_candidate.experience.score,
    new_education != selected_candidate.education.score,
    new_portfolio != selected_candidate.portfolio.score,
    new_communication != selected_candidate.communication.score,
])

if st.button(
    "✅ Apply Override",
    type="primary",
    disabled=not has_changes,
    use_container_width=True,
):
    if not override_reason.strip():
        st.error("⚠️ Please provide a reason for the override.")
    else:
        from agent.override_manager import apply_multi_override
        from agent.ranker import rank_candidates
        from agent.report_generator import generate_all_reports
        
        score_changes = {}
        if new_skills != selected_candidate.skills.score:
            score_changes["skills"] = new_skills
        if new_experience != selected_candidate.experience.score:
            score_changes["experience"] = new_experience
        if new_education != selected_candidate.education.score:
            score_changes["education"] = new_education
        if new_portfolio != selected_candidate.portfolio.score:
            score_changes["portfolio"] = new_portfolio
        if new_communication != selected_candidate.communication.score:
            score_changes["communication"] = new_communication
        
        try:
            # Apply override
            updated_candidate = apply_multi_override(
                selected_candidate,
                score_changes,
                override_reason.strip(),
            )
            
            # Update in list
            for i, c in enumerate(candidates):
                if c.candidate_id == updated_candidate.candidate_id:
                    candidates[i] = updated_candidate
                    break
            
            # Re-rank
            ranked = rank_candidates(candidates)
            st.session_state["ranked_candidates"] = ranked
            
            # Regenerate reports
            if jd:
                new_paths = generate_all_reports(jd.job_title, ranked)
                st.session_state["report_paths"] = new_paths
            
            st.success(f"✅ Override applied for {updated_candidate.candidate_name}. Shortlist re-ranked and reports regenerated.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Override failed: {str(e)}")

# --- Escalation Toggle ---
st.markdown("---")
st.subheader("Escalation Controls")

if selected_candidate.escalate_for_interview:
    st.success(f"{selected_candidate.candidate_name} is currently **flagged for interview**.")
    if st.button("Remove Interview Flag", use_container_width=True):
        from agent.override_manager import toggle_escalate
        toggle_escalate(selected_candidate)
        st.rerun()
else:
    st.info(f"{selected_candidate.candidate_name} is **not flagged** for interview.")
    if st.button("⭐ Flag for Interview", use_container_width=True):
        from agent.override_manager import toggle_escalate
        toggle_escalate(selected_candidate)
        st.rerun()

# --- Override History ---
st.markdown("---")
st.subheader("Override History (This Session)")

from agent.override_manager import get_override_logs

logs = get_override_logs()

if logs:
    # Filter to this session's candidates
    candidate_ids = {c.candidate_id for c in candidates}
    session_logs = [log for log in logs if log.get("candidate_id") in candidate_ids]
    
    if session_logs:
        st.dataframe(
            session_logs,
            use_container_width=True,
        )
    else:
        st.info("No overrides applied yet in this session.")
else:
    st.info("No override history available.")

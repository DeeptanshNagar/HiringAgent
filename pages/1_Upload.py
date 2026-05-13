"""
Page 1: Upload & Configure.
Handles file uploads for JD and candidate inputs, pipeline execution.
"""

from __future__ import annotations

import logging
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Upload & Configure",
    page_icon="📤",
    layout="wide",
)

st.title("📤 Upload & Configure")

st.markdown("Upload your Job Description and candidate files to begin the analysis.")

# --- JD Input Section ---
st.markdown("---")
st.subheader("1. Job Description")

jd_input_method = st.radio(
    "How would you like to provide the Job Description?",
    options=["Paste Text", "Upload File"],
    horizontal=True,
)

jd_text = None
jd_file = None

if jd_input_method == "Paste Text":
    jd_text = st.text_area(
        "Paste Job Description here:",
        height=200,
        placeholder="Paste the full job description text here...",
    )
else:
    uploaded_jd = st.file_uploader(
        "Upload JD file",
        type=["txt", "pdf", "docx"],
        accept_multiple_files=False,
        help="Supported: .txt, .pdf, .docx (max 10 MB)",
    )
    if uploaded_jd:
        jd_file = (uploaded_jd.read(), uploaded_jd.name)

# --- Candidate Input Section ---
st.markdown("---")
st.subheader("2. Candidate Inputs")

st.markdown("Upload resumes (PDF/DOCX) and/or LinkedIn profile data:")

# Resume files
uploaded_resumes = st.file_uploader(
    "Upload Resumes",
    type=["pdf", "docx"],
    accept_multiple_files=True,
    help="Upload one or more resume files (max 50, 10 MB each)",
)

resume_files = None
if uploaded_resumes:
    resume_files = [(f.read(), f.name) for f in uploaded_resumes]

# LinkedIn JSON files
st.markdown("**LinkedIn Profiles (JSON Export):**")
uploaded_linkedin = st.file_uploader(
    "Upload LinkedIn JSON Exports",
    type=["json"],
    accept_multiple_files=True,
    help="LinkedIn data export files",
)

linkedin_json_files = None
if uploaded_linkedin:
    linkedin_json_files = [(f.read(), f.name) for f in uploaded_linkedin]

# LinkedIn URLs
with st.expander("🔗 Add LinkedIn Profile URLs (up to 10)"):
    linkedin_urls = []
    for i in range(10):
        url = st.text_input(
            f"LinkedIn URL {i+1}",
            key=f"linkedin_url_{i}",
            placeholder="https://www.linkedin.com/in/username",
        )
        if url:
            linkedin_urls.append(url)

# --- Security Disclaimer ---
st.markdown("---")
st.info("""
🔒 **Security Notice:** 
- Files are processed locally and never stored on external servers
- Only structured data (skills, experience) is sent to the LLM API
- Raw resumes are not retained in memory after processing
- Do not upload files containing national ID numbers, medical, or financial data
""")

# --- Run Pipeline ---
st.markdown("---")

# Count total candidates
total_candidates = 0
if resume_files:
    total_candidates += len(resume_files)
if linkedin_json_files:
    total_candidates += len(linkedin_json_files)
if 'linkedin_urls' in locals() and linkedin_urls:
    total_candidates += len(linkedin_urls)

run_disabled = not (jd_text or jd_file) or total_candidates == 0

if run_disabled:
    if not (jd_text or jd_file):
        st.warning("⚠️ Please provide a Job Description to continue.")
    if total_candidates == 0:
        st.warning("⚠️ Please upload at least one candidate resume or LinkedIn profile.")

if st.button(
    "🚀 Analyse Candidates →",
    type="primary",
    disabled=run_disabled,
    use_container_width=True,
):
    # Validate max candidates
    max_cand = st.session_state.get("max_candidates", 50)
    if total_candidates > max_cand:
        st.error(f"Too many candidates ({total_candidates}). Maximum allowed: {max_cand}. Please reduce the number of inputs.")
        st.stop()
    
    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def update_progress(step_name: str):
        status_text.info(f"⏳ {step_name}")
        # Map step names to progress
        step_progress = {
            "Step 1/7: Input Ingestion": 0.1,
            "Step 2/7: Parsing Job Description": 0.2,
            "Step 3/7: Extracting Candidate Profiles": 0.35,
            "Step 4/7: Scoring Candidates": 0.55,
            "Step 5/7: Ranking Candidates": 0.7,
            "Step 6/7: Generating Reports": 0.85,
            "Step 7/7: Complete — Ready for Review": 1.0,
        }
        progress_bar.progress(step_progress.get(step_name, 0.5))
    
    try:
        from agent.pipeline import run_pipeline
        
        with st.spinner("Running analysis pipeline..."):
            results = run_pipeline(
                jd_text=jd_text if jd_text else None,
                jd_file=jd_file,
                resume_files=resume_files,
                linkedin_json_files=linkedin_json_files,
                linkedin_urls=linkedin_urls if linkedin_urls else None,
                progress_callback=update_progress,
            )
        
        # Store results in session state
        st.session_state["pipeline_results"] = results
        st.session_state["ranked_candidates"] = results.get("ranked_candidates", [])
        st.session_state["jd_requirements"] = results.get("jd_requirements")
        st.session_state["report_paths"] = results.get("report_paths", {})
        
        status_text.success("✅ Analysis complete! Navigate to **Shortlist Results** to view rankings.")
        progress_bar.progress(1.0)
        
        # Show quick summary
        candidates = results.get("ranked_candidates", [])
        if candidates:
            st.markdown("---")
            st.subheader("📊 Quick Summary")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            strong_hire = sum(1 for c in candidates if c.hire_recommendation.value == "Strong Hire")
            hire = sum(1 for c in candidates if c.hire_recommendation.value == "Hire")
            maybe = sum(1 for c in candidates if c.hire_recommendation.value == "Maybe")
            no_hire = sum(1 for c in candidates if c.hire_recommendation.value == "No Hire")
            
            col1.metric("Total", len(candidates))
            col2.metric("Strong Hire", strong_hire, delta_color="normal")
            col3.metric("Hire", hire, delta_color="normal")
            col4.metric("Maybe", maybe, delta_color="off")
            col5.metric("No Hire", no_hire, delta_color="inverse")
        
    except Exception as e:
        status_text.error(f"❌ Pipeline failed: {str(e)}")
        progress_bar.empty()
        logger.exception("Pipeline execution failed")
        st.exception(e)

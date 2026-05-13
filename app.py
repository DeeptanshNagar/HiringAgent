"""
HR Resume & LinkedIn Shortlisting Agent — Streamlit Entry Point.
Multi-page Streamlit application for AI-assisted candidate shortlisting.
"""

from __future__ import annotations

import logging
import os
import sys

import streamlit as st
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
load_dotenv()

# Configure structured logging
from logging_config import setup_logging
from config import get_settings

settings = get_settings()
setup_logging(
    level=settings.log_level,
    log_format=settings.log_format,
    logs_dir=settings.logs_dir,
)

# Page configuration
st.set_page_config(
    page_title="HR Shortlisting Agent",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)


def check_authentication():
    """Display a login screen and verify credentials against AGENT_API_KEY."""
    if st.session_state.get("authenticated"):
        return True

    st.title("🔐 HR Shortlisting Agent — Login")
    st.markdown("Please enter the agent API key to continue.")

    password = st.text_input("API Key", type="password", key="login_password")
    if st.button("Login", key="login_button"):
        expected_key = os.getenv("AGENT_API_KEY", "")
        if not expected_key:
            st.error("⚠️ `AGENT_API_KEY` is not set in the `.env` file. Cannot authenticate.")
        elif password == expected_key:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("❌ Invalid API key. Please try again.")

    st.stop()


def check_api_keys():
    """Verify that required API keys are configured."""
    if not settings.has_llm_key:
        st.error("""
        ⚠️ **No LLM API Key Configured**
        
        Please set one of the following in your `.env` file:
        - `GROQ_API_KEY=your_key_here`
        - `ANTHROPIC_API_KEY=your_key_here`
        - `OPENAI_API_KEY=your_key_here`
        
        Then restart the application.
        """)
        st.stop()


def main():
    """Main entry point for the Streamlit app."""
    check_authentication()
    check_api_keys()
    
    st.sidebar.title("📋 HR Shortlisting Agent")
    st.sidebar.markdown("---")
    
    # Navigation is handled automatically by Streamlit's native
    # multi-page discovery from the pages/ directory.
    
    # Settings
    st.sidebar.markdown("### Settings")
    
    # Model selection
    available_models = []
    if settings.groq_api_key:
        available_models.append(f"{settings.default_groq_model} (Groq)")
    if settings.anthropic_api_key:
        available_models.append(f"{settings.default_anthropic_model} (Anthropic)")
    if settings.openai_api_key:
        available_models.append(f"{settings.default_openai_model} (OpenAI)")
    
    selected_model = st.sidebar.selectbox(
        "LLM Model",
        options=available_models,
        index=0,
        help="Select the LLM to use for scoring",
    )
    st.session_state["selected_model"] = selected_model
    
    # Max candidates
    max_candidates = st.sidebar.slider(
        "Max Candidates Per Run",
        min_value=1,
        max_value=50,
        value=20,
        help="Maximum number of candidates to process in a single run",
    )
    st.session_state["max_candidates"] = max_candidates
    
    # Caching toggle
    enable_cache = st.sidebar.toggle(
        "Enable LLM Caching",
        value=True,
        help="Cache LLM responses to avoid redundant API calls",
    )
    os.environ["ENABLE_CACHE"] = str(enable_cache).lower()
    
    st.sidebar.markdown("---")
    
    # GDPR Notice
    st.sidebar.markdown("### 🔒 Data Privacy Notice")
    st.sidebar.info("""
    Candidate data is processed locally. Structured (non-raw) data is sent 
    to the selected LLM API for scoring. Do not upload files containing 
    national ID numbers, medical information, or financial data.
    """)
    
    # About
    st.sidebar.markdown("---")
    st.sidebar.markdown("**v1.0** | AI-Assisted Shortlisting")
    st.sidebar.markdown("Final hiring decisions rest with HR.")
    
    # Main content
    st.title("🤖 HR Resume & LinkedIn Shortlisting Agent")
    st.markdown("""
    Welcome to the AI-powered candidate shortlisting tool. This agent assists HR teams 
    in evaluating candidate applications efficiently, consistently, and without bias.
    
    ### How It Works
    1. **Upload** a Job Description and candidate resumes (PDF/DOCX) or LinkedIn profiles
    2. **Analyse** — the AI scores each candidate across 5 dimensions
    3. **Review** ranked results with explainable scores
    4. **Override** any scores as needed — human judgment always prevails
    
    ### Get Started
    Use the sidebar navigation to begin. Start with **Upload & Configure**.
    """)
    
    # Display current status if pipeline has run
    if "pipeline_results" in st.session_state:
        st.success("✅ Pipeline has been run. Navigate to **Shortlist Results** to view rankings.")
        
        results = st.session_state["pipeline_results"]
        if "ranked_candidates" in results:
            candidates = results["ranked_candidates"]
            col1, col2, col3, col4 = st.columns(4)
            
            strong_hire = sum(1 for c in candidates if c.hire_recommendation.value == "Strong Hire")
            hire = sum(1 for c in candidates if c.hire_recommendation.value == "Hire")
            maybe = sum(1 for c in candidates if c.hire_recommendation.value == "Maybe")
            no_hire = sum(1 for c in candidates if c.hire_recommendation.value == "No Hire")
            
            col1.metric("Strong Hire", strong_hire)
            col2.metric("Hire", hire)
            col3.metric("Maybe", maybe)
            col4.metric("No Hire", no_hire)


if __name__ == "__main__":
    main()

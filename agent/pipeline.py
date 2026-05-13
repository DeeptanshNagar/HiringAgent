"""
Pipeline Orchestrator.
Coordinates all 7 steps of the HR Shortlisting Agent pipeline.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from config import get_settings
from logging_config import set_correlation_id, get_correlation_id

from models.schemas import CandidateProfile, CandidateScore, JDRequirements

logger = logging.getLogger(__name__)

def validate_api_keys() -> None:
    """Validate that at least one LLM API key is configured."""
    settings = get_settings()
    settings.validate_api_keys()
    logger.info("API keys validated — provider: %s", settings.primary_llm_provider)


# --- Step 1: Input Ingestion ---
def step1_ingestion(
    jd_text: Optional[str] = None,
    jd_file: Optional[Tuple[bytes, str]] = None,
    resume_files: Optional[List[Tuple[bytes, str]]] = None,
    linkedin_json_files: Optional[List[Tuple[bytes, str]]] = None,
    linkedin_urls: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Step 1: Ingest and validate all inputs."""
    from agent.ingestion import ingest_inputs
    
    logger.info("=== Step 1: Input Ingestion ===")
    result = ingest_inputs(
        jd_text=jd_text,
        jd_file=jd_file,
        resume_files=resume_files,
        linkedin_json_files=linkedin_json_files,
        linkedin_urls=linkedin_urls,
    )
    
    if result.errors:
        raise ValueError(f"Ingestion errors: {'; '.join(result.errors)}")
    
    logger.info(f"Ingested {len(result.candidates)} candidates, JD length: {len(result.jd_raw)} chars")
    return {
        "jd_raw": result.jd_raw,
        "candidates": result.candidates,
    }


# --- Step 2: JD Parsing ---
def step2_parse_jd(jd_raw: str) -> JDRequirements:
    """Step 2: Parse job description into structured requirements."""
    from agent.jd_parser import parse_jd
    
    logger.info("=== Step 2: JD Parsing ===")
    return parse_jd(jd_raw)


# --- Step 3: Candidate Profile Extraction ---
def step3_extract_profiles(
    candidates_raw: List[Dict[str, Any]],
) -> List[CandidateProfile]:
    """Step 3: Extract structured profiles from candidate raw text."""
    from agent.profile_extractor import extract_profile
    
    logger.info("=== Step 3: Profile Extraction ===")
    profiles: list[CandidateProfile] = []
    
    for i, cand in enumerate(candidates_raw):
        logger.info(f"Extracting profile {i+1}/{len(candidates_raw)}: {cand['id']}")
        
        profile = extract_profile(
            candidate_id=cand["id"],
            source=cand["source"],
            raw_text=cand.get("raw_text", ""),
            url=cand.get("url"),
        )
        profiles.append(profile)
    
    return profiles


# --- Step 4: Scoring ---
def step4_score_candidates(
    jd: JDRequirements,
    candidates: List[CandidateProfile],
) -> List[CandidateScore]:
    """Step 4: Score all candidates against the JD."""
    from agent.scorer import score_all_candidates
    
    logger.info("=== Step 4: Scoring ===")
    return score_all_candidates(jd, candidates)


# --- Step 5: Ranking ---
def step5_rank_candidates(scored: List[CandidateScore]) -> List[CandidateScore]:
    """Step 5: Sort candidates by weighted total."""
    from agent.ranker import rank_candidates
    
    logger.info("=== Step 5: Ranking ===")
    return rank_candidates(scored)


# --- Step 6: Report Generation ---
def step6_generate_reports(
    job_title: str,
    ranked: List[CandidateScore],
) -> Dict[str, str]:
    """Step 6: Generate all three report formats."""
    from agent.report_generator import generate_all_reports
    
    logger.info("=== Step 6: Report Generation ===")
    return generate_all_reports(job_title, ranked)


# --- Step 7: Override (handled interactively via UI) ---


# --- Caching ---
class PipelineCache:
    """Simple SQLite-based cache for LLM calls."""

    def __init__(self):
        settings = get_settings()
        self.enabled = settings.enable_cache
        self.db_path = settings.cache_db_path
        self._cache = {}

        if self.enabled:
            try:
                from langchain.globals import set_llm_cache
                from langchain_community.cache import SQLiteCache

                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
                set_llm_cache(SQLiteCache(database_path=self.db_path))
                logger.info("SQLite cache enabled at %s", self.db_path)
            except Exception as e:
                logger.warning("Failed to initialize SQLite cache: %s", e)
                self.enabled = False
    
    def compute_cache_key(self, jd_text: str, resume_text: str) -> str:
        """Compute a cache key from JD and resume text."""
        combined = jd_text + "::" + resume_text
        return hashlib.sha256(combined.encode()).hexdigest()[:16]


# --- Main Pipeline ---
def run_pipeline(
    jd_text: Optional[str] = None,
    jd_file: Optional[Tuple[bytes, str]] = None,
    resume_files: Optional[List[Tuple[bytes, str]]] = None,
    linkedin_json_files: Optional[List[Tuple[bytes, str]]] = None,
    linkedin_urls: Optional[List[str]] = None,
    progress_callback: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Run the complete 7-step pipeline.
    
    Args:
        jd_text: Plain text job description.
        jd_file: Tuple of (file_bytes, filename) for JD.
        resume_files: List of (file_bytes, filename) for resumes.
        linkedin_json_files: List of (file_bytes, filename) for LinkedIn JSON.
        linkedin_urls: List of LinkedIn profile URLs.
        progress_callback: Optional callback function(step_name: str) for UI updates.
        
    Returns:
        Dict with all pipeline outputs.
    """
    # Validate API keys
    validate_api_keys()

    # Generate correlation ID for this pipeline run
    correlation_id = set_correlation_id()
    logger.info("Pipeline started — correlation_id=%s", correlation_id)
    pipeline_start = time.time()

    # Initialize cache
    cache = PipelineCache()

    results: dict[str, Any] = {}
    step_timings: dict[str, float] = {}

    def _timed_step(name: str, func, *args, **kwargs):
        """Run a step with timing and progress callback."""
        if progress_callback:
            progress_callback(name)
        t0 = time.time()
        result = func(*args, **kwargs)
        elapsed = round(time.time() - t0, 2)
        step_timings[name] = elapsed
        logger.info("Completed %s in %.2fs", name, elapsed)
        return result

    # Step 1: Ingestion
    ingestion_result = _timed_step(
        "Step 1/7: Input Ingestion",
        step1_ingestion,
        jd_text=jd_text,
        jd_file=jd_file,
        resume_files=resume_files,
        linkedin_json_files=linkedin_json_files,
        linkedin_urls=linkedin_urls,
    )
    results["jd_raw"] = ingestion_result["jd_raw"]
    results["candidates_raw"] = ingestion_result["candidates"]

    # Step 2: JD Parsing
    jd_requirements = _timed_step(
        "Step 2/7: Parsing Job Description",
        step2_parse_jd,
        ingestion_result["jd_raw"],
    )
    results["jd_requirements"] = jd_requirements

    # Step 3: Profile Extraction
    candidate_profiles = _timed_step(
        "Step 3/7: Extracting Candidate Profiles",
        step3_extract_profiles,
        ingestion_result["candidates"],
    )
    results["candidate_profiles"] = candidate_profiles

    # Step 4: Scoring
    scored_candidates = _timed_step(
        "Step 4/7: Scoring Candidates",
        step4_score_candidates,
        jd_requirements,
        candidate_profiles,
    )
    results["scored_candidates"] = scored_candidates

    # Step 5: Ranking
    ranked_candidates = _timed_step(
        "Step 5/7: Ranking Candidates",
        step5_rank_candidates,
        scored_candidates,
    )
    results["ranked_candidates"] = ranked_candidates

    # Step 6: Report Generation
    report_paths = _timed_step(
        "Step 6/7: Generating Reports",
        step6_generate_reports,
        jd_requirements.job_title,
        ranked_candidates,
    )
    results["report_paths"] = report_paths

    if progress_callback:
        progress_callback("Step 7/7: Complete — Ready for Review")

    total_time = round(time.time() - pipeline_start, 2)
    results["step_timings"] = step_timings
    results["total_duration_seconds"] = total_time
    results["correlation_id"] = correlation_id

    logger.info(
        "Pipeline complete — %d candidates in %.2fs (correlation_id=%s)",
        len(ranked_candidates),
        total_time,
        correlation_id,
    )
    return results

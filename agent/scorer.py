"""
Step 4: Scoring Engine Module.
Computes scores across 5 dimensions using both LLM rubric scoring and embedding similarity.
This is the core evaluation logic of the agent.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

from models.schemas import (
    CandidateProfile,
    CandidateScore,
    DimensionScore,
    HireRecommendation,
    JDRequirements,
)
from security.input_sanitiser import sanitise_for_system_prompt, sanitise_text

logger = logging.getLogger(__name__)

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "scoring.txt")

# Scoring weights (must sum to 1.0)
WEIGHTS = {
    "skills": 0.30,
    "experience": 0.25,
    "education": 0.15,
    "portfolio": 0.20,
    "communication": 0.10,
}

# Hire recommendation thresholds
THRESHOLDS = [
    (7.5, HireRecommendation.STRONG_HIRE),
    (6.0, HireRecommendation.HIRE),
    (4.5, HireRecommendation.MAYBE),
    (0.0, HireRecommendation.NO_HIRE),
]


def load_prompt_template() -> str:
    """Load the scoring prompt template from file."""
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Prompt template not found at {PROMPT_PATH}, using default")
        return "Score this candidate against the JD. Return JSON.\n\nJD:\n{jd_json}\n\nCandidate:\n{candidate_json}"


# LLM and embedding clients are now provided by agent/llm_factory.py
# This eliminates duplication across jd_parser.py, profile_extractor.py, and scorer.py


def _compute_embedding_similarity(
    jd_skills: List[str],
    candidate_skills: List[str],
) -> Optional[float]:
    """
    Compute cosine similarity between JD skills and candidate skills using embeddings.
    
    Args:
        jd_skills: List of required skills from JD.
        candidate_skills: List of candidate's skills.
        
    Returns:
        Cosine similarity score between 0 and 1, or None if embeddings unavailable.
    """
    from agent.llm_factory import get_embedding_model
    embedding_model = get_embedding_model()
    if embedding_model is None:
        return None
    
    if not jd_skills or not candidate_skills:
        return 0.0
    
    try:
        # Concatenate skills into single strings
        jd_text = ", ".join(jd_skills).lower()
        candidate_text = ", ".join(candidate_skills).lower()
        
        # Get embeddings
        jd_embedding = embedding_model.embed_query(jd_text)
        candidate_embedding = embedding_model.embed_query(candidate_text)
        
        # Compute cosine similarity
        jd_vec = np.array(jd_embedding)
        cand_vec = np.array(candidate_embedding)
        
        dot_product = np.dot(jd_vec, cand_vec)
        jd_norm = np.linalg.norm(jd_vec)
        cand_norm = np.linalg.norm(cand_vec)
        
        if jd_norm == 0 or cand_norm == 0:
            return 0.0
        
        similarity = dot_product / (jd_norm * cand_norm)
        # Ensure in [0, 1] range
        similarity = float(np.clip(similarity, 0.0, 1.0))
        
        return similarity
        
    except Exception as e:
        logger.warning(f"Embedding similarity computation failed: {e}")
        return None


def _embedding_similarity_to_score(similarity: Optional[float]) -> float:
    """
    Convert embedding cosine similarity to a 0-10 score.
    
    Args:
        similarity: Cosine similarity in [0, 1].
        
    Returns:
        Score in [0, 10].
    """
    if similarity is None:
        return 0.0
    # Map 0->0, 1->10
    return round(similarity * 10 * 2) / 2  # Round to 0.5 step


def _llm_rubric_score(
    jd: JDRequirements,
    candidate: CandidateProfile,
) -> Dict[str, any]:
    """
    Score candidate using LLM with rubric (Method A).
    
    Args:
        jd: Structured JD requirements.
        candidate: Structured candidate profile.
        
    Returns:
        Dict with all scores and justifications.
    """
    from agent.llm_factory import get_llm_client
    llm = get_llm_client()
    template = load_prompt_template()
    
    # Prepare JSON strings
    jd_dict = jd.model_dump()
    candidate_dict = candidate.model_dump()
    
    # Sanitise candidate data for prompt (remove PII where possible)
    candidate_dict["email"] = None
    candidate_dict["phone"] = None
    
    jd_json = json.dumps(jd_dict, indent=2)
    candidate_json = json.dumps(candidate_dict, indent=2)
    
    # Build prompt
    prompt = template.format(
        candidate_id=candidate.candidate_id,
        jd_json=jd_json,
        candidate_json=candidate_json,
    )
    
    # Call LLM
    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        
        # Clean response
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        data = json.loads(content)
        return data
        
    except Exception as e:
        logger.warning(f"LLM scoring failed: {e}, retrying")
        
        retry_prompt = (
            f"{prompt}\n\n"
            f"Your previous response was invalid. Return ONLY valid JSON matching the exact schema. "
            f"All scores must be numbers 0-10 in 0.5 steps."
        )
        
        try:
            response = llm.invoke(retry_prompt)
            content = response.content if hasattr(response, "content") else str(response)
            
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            return data
            
        except Exception as e2:
            logger.error(f"LLM scoring failed after retry: {e2}")
            # Return conservative default scores
            return {
                "skills_score": 0,
                "skills_justification": "Scoring failed, review manually",
                "experience_score": 0,
                "experience_justification": "Scoring failed, review manually",
                "education_score": 0,
                "education_justification": "Scoring failed, review manually",
                "portfolio_score": 0,
                "portfolio_justification": "Scoring failed, review manually",
                "communication_score": 0,
                "communication_justification": "Scoring failed, review manually",
                "weighted_total": 0,
                "hire_recommendation": "No Hire",
                "overall_summary": "Automated scoring encountered an error. Manual review required.",
                "low_confidence": True,
            }


def _compute_weighted_total(
    skills: float,
    experience: float,
    education: float,
    portfolio: float,
    communication: float,
) -> float:
    """
    Compute weighted total score using the defined formula.
    
    Args:
        skills: Skills score (0-10).
        experience: Experience score (0-10).
        education: Education score (0-10).
        portfolio: Portfolio score (0-10).
        communication: Communication score (0-10).
        
    Returns:
        Weighted total (0-10).
    """
    total = (
        skills * WEIGHTS["skills"]
        + experience * WEIGHTS["experience"]
        + education * WEIGHTS["education"]
        + portfolio * WEIGHTS["portfolio"]
        + communication * WEIGHTS["communication"]
    )
    return round(total, 2)


def _determine_hire_recommendation(weighted_total: float) -> HireRecommendation:
    """
    Determine hire recommendation based on weighted total thresholds.
    
    Args:
        weighted_total: Final weighted score (0-10).
        
    Returns:
        HireRecommendation enum value.
    """
    for threshold, recommendation in THRESHOLDS:
        if weighted_total >= threshold:
            return recommendation
    return HireRecommendation.NO_HIRE


def score_candidate(
    jd: JDRequirements,
    candidate: CandidateProfile,
) -> CandidateScore:
    """
    Score a single candidate against the JD using both Method A (LLM rubric)
    and Method B (embedding similarity).
    
    Args:
        jd: Structured JD requirements.
        candidate: Structured candidate profile.
        
    Returns:
        Fully populated CandidateScore.
    """
    logger.info(f"Scoring candidate: {candidate.candidate_id}")
    
    # Method A: LLM rubric scoring
    llm_result = _llm_rubric_score(jd, candidate)
    
    # Extract Method A scores
    skills_score_a = float(llm_result.get("skills_score", 0))
    experience_score_a = float(llm_result.get("experience_score", 0))
    education_score_a = float(llm_result.get("education_score", 0))
    portfolio_score_a = float(llm_result.get("portfolio_score", 0))
    communication_score_a = float(llm_result.get("communication_score", 0))
    
    # Method B: Embedding similarity for skills only
    embedding_similarity = _compute_embedding_similarity(
        jd.required_skills,
        candidate.skills,
    )
    skills_score_b = _embedding_similarity_to_score(embedding_similarity)
    
    # Average Method A and Method B for final skills score
    if embedding_similarity is not None:
        final_skills_score = round((skills_score_a + skills_score_b) / 2 * 2) / 2
    else:
        final_skills_score = skills_score_a
    
    # Ensure all scores are in 0-10 range and 0.5 steps
    def normalize_score(s: float) -> float:
        s = max(0, min(10, s))
        return round(s * 2) / 2
    
    final_skills_score = normalize_score(final_skills_score)
    experience_score = normalize_score(experience_score_a)
    education_score = normalize_score(education_score_a)
    portfolio_score = normalize_score(portfolio_score_a)
    communication_score = normalize_score(communication_score_a)
    
    # Compute weighted total
    weighted_total = _compute_weighted_total(
        final_skills_score,
        experience_score,
        education_score,
        portfolio_score,
        communication_score,
    )
    
    # Determine hire recommendation
    hire_recommendation = _determine_hire_recommendation(weighted_total)
    
    # Get low confidence flag
    low_confidence = llm_result.get("low_confidence", False)
    if candidate.parse_flagged:
        low_confidence = True
    
    # Build CandidateScore
    score = CandidateScore(
        candidate_id=candidate.candidate_id,
        candidate_name=candidate.candidate_name,
        skills=DimensionScore(
            score=final_skills_score,
            justification=llm_result.get("skills_justification", "")[:200],
        ),
        experience=DimensionScore(
            score=experience_score,
            justification=llm_result.get("experience_justification", "")[:200],
        ),
        education=DimensionScore(
            score=education_score,
            justification=llm_result.get("education_justification", "")[:200],
        ),
        portfolio=DimensionScore(
            score=portfolio_score,
            justification=llm_result.get("portfolio_justification", "")[:200],
        ),
        communication=DimensionScore(
            score=communication_score,
            justification=llm_result.get("communication_justification", "")[:200],
        ),
        weighted_total=weighted_total,
        hire_recommendation=hire_recommendation,
        overall_summary=llm_result.get("overall_summary", "")[:200],
        embedding_skills_score=embedding_similarity,
        low_confidence=low_confidence,
    )
    
    logger.info(
        f"Candidate {candidate.candidate_id}: total={weighted_total}, "
        f"recommendation={hire_recommendation.value}, "
        f"embedding_skill_score={embedding_similarity}"
    )
    
    return score


def score_all_candidates(
    jd: JDRequirements,
    candidates: List[CandidateProfile],
) -> List[CandidateScore]:
    """
    Score all candidates against the JD.
    
    Args:
        jd: Structured JD requirements.
        candidates: List of structured candidate profiles.
        
    Returns:
        List of CandidateScore objects (not yet ranked).
    """
    scores: list[CandidateScore] = []
    
    for candidate in candidates:
        try:
            score = score_candidate(jd, candidate)
            scores.append(score)
        except Exception as e:
            logger.error(f"Failed to score candidate {candidate.candidate_id}: {e}")
            # Create a fallback score
            scores.append(CandidateScore(
                candidate_id=candidate.candidate_id,
                candidate_name=candidate.candidate_name,
                skills=DimensionScore(score=0, justification="Scoring error"),
                experience=DimensionScore(score=0, justification="Scoring error"),
                education=DimensionScore(score=0, justification="Scoring error"),
                portfolio=DimensionScore(score=0, justification="Scoring error"),
                communication=DimensionScore(score=0, justification="Scoring error"),
                weighted_total=0,
                hire_recommendation=HireRecommendation.NO_HIRE,
                overall_summary=f"Error during scoring: {str(e)[:100]}",
                low_confidence=True,
            ))
    
    return scores

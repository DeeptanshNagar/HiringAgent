"""
Step 7: Override Manager Module.
Handles human-in-the-loop score overrides, re-ranking, and audit logging.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from models.schemas import CandidateScore, DimensionScore, OverrideEvent
from security.pii_masker import mask_dict

logger = logging.getLogger(__name__)

LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOGS_DIR, exist_ok=True)


def _get_override_log_path() -> str:
    """Get today's override log file path."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(LOGS_DIR, f"overrides_{today}.jsonl")


def _log_override_event(event: OverrideEvent) -> None:
    """
    Log an override event to the audit log.
    
    Args:
        event: OverrideEvent to log.
    """
    log_path = _get_override_log_path()
    
    # Mask PII before logging
    event_dict = event.model_dump()
    masked_event = mask_dict(event_dict)
    
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(masked_event) + "\n")
        logger.info(f"Override logged for candidate {event.candidate_id}")
    except Exception as e:
        logger.error(f"Failed to write override log: {e}")


def apply_override(
    candidate: CandidateScore,
    dimension: str,
    new_score: float,
    reason: str,
) -> CandidateScore:
    """
    Apply a score override to a specific dimension.
    
    Args:
        candidate: The candidate to modify.
        dimension: Dimension name ('skills', 'experience', 'education', 'portfolio', 'communication').
        new_score: New score value (0-10, 0.5 steps).
        reason: Human-provided reason for the override.
        
    Returns:
        Modified candidate with updated scores.
        
    Raises:
        ValueError: If dimension is invalid or score is out of range.
    """
    valid_dimensions = ["skills", "experience", "education", "portfolio", "communication"]
    
    if dimension not in valid_dimensions:
        raise ValueError(f"Invalid dimension '{dimension}'. Must be one of: {valid_dimensions}")
    
    if not 0 <= new_score <= 10:
        raise ValueError(f"Score must be between 0 and 10, got {new_score}")
    
    # Round to 0.5 step
    new_score = round(new_score * 2) / 2
    
    # Get old score
    old_score = getattr(candidate, dimension).score
    
    if old_score == new_score:
        return candidate
    
    # Create new DimensionScore
    new_dim_score = DimensionScore(
        score=new_score,
        justification=f"OVERRIDE: {reason}"[:200],
    )
    
    # Update candidate
    setattr(candidate, dimension, new_dim_score)
    candidate.override_applied = True
    
    # Recompute weighted total
    from agent.scorer import _compute_weighted_total
    
    candidate.weighted_total = _compute_weighted_total(
        candidate.skills.score,
        candidate.experience.score,
        candidate.education.score,
        candidate.portfolio.score,
        candidate.communication.score,
    )
    
    # Recompute hire recommendation
    from agent.scorer import _determine_hire_recommendation
    
    candidate.hire_recommendation = _determine_hire_recommendation(candidate.weighted_total)
    
    # Log the override
    event = OverrideEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        candidate_id=candidate.candidate_id,
        candidate_name=candidate.candidate_name,
        dimension=dimension,
        old_score=old_score,
        new_score=new_score,
        reason=reason,
    )
    _log_override_event(event)
    
    return candidate


def apply_multi_override(
    candidate: CandidateScore,
    score_changes: Dict[str, float],
    reason: str,
) -> CandidateScore:
    """
    Apply multiple score overrides at once.
    
    Args:
        candidate: The candidate to modify.
        score_changes: Dict mapping dimension names to new scores.
        reason: Human-provided reason for overrides.
        
    Returns:
        Modified candidate with updated scores.
    """
    for dimension, new_score in score_changes.items():
        if new_score is not None:
            candidate = apply_override(candidate, dimension, new_score, reason)
    
    return candidate


def toggle_escalate(candidate: CandidateScore) -> CandidateScore:
    """
    Toggle the escalate for interview flag.
    
    Args:
        candidate: The candidate to modify.
        
    Returns:
        Modified candidate with toggled flag.
    """
    candidate.escalate_for_interview = not candidate.escalate_for_interview
    
    # Log this action
    event = OverrideEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        candidate_id=candidate.candidate_id,
        candidate_name=candidate.candidate_name,
        dimension="escalate_for_interview",
        old_score=0 if candidate.escalate_for_interview else 1,
        new_score=1 if candidate.escalate_for_interview else 0,
        reason="HR flagged for interview",
    )
    _log_override_event(event)
    
    return candidate


def get_override_logs(date_str: Optional[str] = None) -> List[Dict]:
    """
    Read override logs for a specific date.
    
    Args:
        date_str: Date in YYYY-MM-DD format. Defaults to today.
        
    Returns:
        List of override event dicts.
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    log_path = os.path.join(LOGS_DIR, f"overrides_{date_str}.jsonl")
    
    if not os.path.exists(log_path):
        return []
    
    events = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except Exception as e:
        logger.error(f"Error reading override logs: {e}")
    
    return events


def get_security_logs(date_str: Optional[str] = None) -> List[Dict]:
    """
    Read security event logs.
    
    Args:
        date_str: Date in YYYY-MM-DD format. Defaults to today.
        
    Returns:
        List of security event dicts.
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    log_path = os.path.join(LOGS_DIR, f"security_{date_str}.jsonl")
    
    # Also check the general security log
    alt_path = os.path.join(LOGS_DIR, "security.jsonl")
    
    events = []
    
    for path in [log_path, alt_path]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            events.append(json.loads(line))
            except Exception as e:
                logger.error(f"Error reading security logs from {path}: {e}")
    
    return events

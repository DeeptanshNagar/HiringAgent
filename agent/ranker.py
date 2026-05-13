"""
Step 5: Ranking Module.
Sorts scored candidates by weighted total with tiebreaker logic.
"""

from __future__ import annotations

import logging
from typing import List

from models.schemas import CandidateScore

logger = logging.getLogger(__name__)


def rank_candidates(scored_candidates: List[CandidateScore]) -> List[CandidateScore]:
    """
    Sort candidates by weighted total descending.
    Tiebreakers: experience_score, then skills_score.
    
    Args:
        scored_candidates: List of scored candidates (not yet ranked).
        
    Returns:
        Sorted list with rank field populated.
    """
    if not scored_candidates:
        return []
    
    # Sort by weighted_total desc, then experience desc, then skills desc
    sorted_candidates = sorted(
        scored_candidates,
        key=lambda c: (
            c.weighted_total,
            c.experience.score,
            c.skills.score,
        ),
        reverse=True,
    )
    
    # Assign ranks
    for i, candidate in enumerate(sorted_candidates, start=1):
        candidate.rank = i
    
    logger.info(f"Ranked {len(sorted_candidates)} candidates")
    return sorted_candidates

"""
Unit tests for Step 5: Ranker module.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import CandidateScore, DimensionScore, HireRecommendation
from agent.ranker import rank_candidates


def make_candidate(cid: str, total: float, exp: float = 5, skills: float = 5) -> CandidateScore:
    """Helper to create a CandidateScore with specific values."""
    return CandidateScore(
        candidate_id=cid,
        candidate_name=f"Candidate_{cid}",
        skills=DimensionScore(score=skills, justification="test"),
        experience=DimensionScore(score=exp, justification="test"),
        education=DimensionScore(score=5, justification="test"),
        portfolio=DimensionScore(score=5, justification="test"),
        communication=DimensionScore(score=5, justification="test"),
        weighted_total=total,
        hire_recommendation=HireRecommendation.HIRE,
        overall_summary="test",
    )


class TestRanker:
    """Tests for candidate ranking logic."""
    
    def test_sort_descending(self):
        """Test candidates are sorted by weighted total descending."""
        candidates = [
            make_candidate("c1", 5.0),
            make_candidate("c2", 8.0),
            make_candidate("c3", 3.0),
        ]
        
        ranked = rank_candidates(candidates)
        
        assert ranked[0].candidate_id == "c2"
        assert ranked[1].candidate_id == "c1"
        assert ranked[2].candidate_id == "c3"
        assert ranked[0].rank == 1
        assert ranked[1].rank == 2
        assert ranked[2].rank == 3
    
    def test_tiebreaker_experience(self):
        """Test that experience score breaks ties."""
        candidates = [
            make_candidate("c1", 7.0, exp=8, skills=5),
            make_candidate("c2", 7.0, exp=6, skills=5),
        ]
        
        ranked = rank_candidates(candidates)
        
        assert ranked[0].candidate_id == "c1"  # Higher experience wins
        assert ranked[1].candidate_id == "c2"
    
    def test_tiebreaker_skills(self):
        """Test that skills score breaks ties when experience is also tied."""
        candidates = [
            make_candidate("c1", 7.0, exp=5, skills=8),
            make_candidate("c2", 7.0, exp=5, skills=6),
        ]
        
        ranked = rank_candidates(candidates)
        
        assert ranked[0].candidate_id == "c1"  # Higher skills wins
        assert ranked[1].candidate_id == "c2"
    
    def test_empty_list(self):
        """Test that empty list returns empty."""
        ranked = rank_candidates([])
        assert ranked == []
    
    def test_single_candidate(self):
        """Test ranking with a single candidate."""
        candidates = [make_candidate("c1", 7.5)]
        ranked = rank_candidates(candidates)
        
        assert len(ranked) == 1
        assert ranked[0].rank == 1
        assert ranked[0].candidate_id == "c1"

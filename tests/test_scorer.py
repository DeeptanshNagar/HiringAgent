"""
Unit tests for Step 4: Scoring Engine module.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import (
    CandidateProfile,
    CandidateScore,
    DimensionScore,
    HireRecommendation,
    JDRequirements,
)
from agent.scorer import (
    _compute_weighted_total,
    _determine_hire_recommendation,
    _embedding_similarity_to_score,
    score_candidate,
)


class MockResponse:
    """Mock LLM response for testing."""
    def __init__(self, content: str):
        self.content = content


class TestWeightedTotalFormula:
    """Tests for the weighted total computation."""
    
    def test_perfect_score(self):
        """Test that perfect 10s across all dimensions yield 10.00."""
        total = _compute_weighted_total(10, 10, 10, 10, 10)
        assert total == 10.00
    
    def test_zero_score(self):
        """Test that all zeros yield 0.00."""
        total = _compute_weighted_total(0, 0, 0, 0, 0)
        assert total == 0.00
    
    def test_midrange_score(self):
        """Test a mid-range score computation."""
        # skills=7, exp=6, edu=5, port=8, comm=6
        total = _compute_weighted_total(7, 6, 5, 8, 6)
        expected = 7 * 0.30 + 6 * 0.25 + 5 * 0.15 + 8 * 0.20 + 6 * 0.10
        assert abs(total - expected) < 0.01
    
    def test_formula_weights(self):
        """Test that weights are applied correctly."""
        # Only skills nonzero
        total = _compute_weighted_total(10, 0, 0, 0, 0)
        assert abs(total - 3.0) < 0.01  # 10 * 0.30 = 3.0
        
        # Only experience nonzero
        total = _compute_weighted_total(0, 10, 0, 0, 0)
        assert abs(total - 2.5) < 0.01  # 10 * 0.25 = 2.5


class TestHireRecommendation:
    """Tests for hire recommendation thresholds."""
    
    def test_strong_hire_threshold(self):
        """Test that score >= 7.5 gives Strong Hire."""
        assert _determine_hire_recommendation(7.5) == HireRecommendation.STRONG_HIRE
        assert _determine_hire_recommendation(9.0) == HireRecommendation.STRONG_HIRE
        assert _determine_hire_recommendation(10.0) == HireRecommendation.STRONG_HIRE
    
    def test_hire_threshold(self):
        """Test that 6.0 <= score < 7.5 gives Hire."""
        assert _determine_hire_recommendation(6.0) == HireRecommendation.HIRE
        assert _determine_hire_recommendation(7.0) == HireRecommendation.HIRE
        assert _determine_hire_recommendation(7.4) == HireRecommendation.HIRE
    
    def test_maybe_threshold(self):
        """Test that 4.5 <= score < 6.0 gives Maybe."""
        assert _determine_hire_recommendation(4.5) == HireRecommendation.MAYBE
        assert _determine_hire_recommendation(5.0) == HireRecommendation.MAYBE
        assert _determine_hire_recommendation(5.9) == HireRecommendation.MAYBE
    
    def test_no_hire_threshold(self):
        """Test that score < 4.5 gives No Hire."""
        assert _determine_hire_recommendation(4.4) == HireRecommendation.NO_HIRE
        assert _determine_hire_recommendation(2.0) == HireRecommendation.NO_HIRE
        assert _determine_hire_recommendation(0.0) == HireRecommendation.NO_HIRE


class TestScoreRange:
    """Tests that scores are within [0, 10]."""
    
    def test_scoring_output_range(self):
        """Test that LLM scoring produces scores in valid range."""
        mock_json = '''
        {
            "candidate_id": "cand_test",
            "skills_score": 8.5,
            "skills_justification": "Strong skills match",
            "experience_score": 7,
            "experience_justification": "Good experience",
            "education_score": 6,
            "education_justification": "Meets requirements",
            "portfolio_score": 8,
            "portfolio_justification": "Strong projects",
            "communication_score": 7.5,
            "communication_justification": "Clear writing",
            "weighted_total": 7.45,
            "hire_recommendation": "Hire",
            "overall_summary": "Strong candidate overall",
            "low_confidence": false
        }
        '''
        
        with patch("agent.llm_factory.get_llm_client") as mock_get_llm, \
             patch("agent.llm_factory.get_embedding_model") as mock_embed:
            
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = MockResponse(mock_json)
            mock_get_llm.return_value = mock_llm
            mock_embed.return_value = None  # Skip embedding
            
            jd = JDRequirements(
                job_title="Test",
                required_skills=["Python", "Django"],
            )
            candidate = CandidateProfile(
                candidate_id="cand_test",
                candidate_name="Test Person",
                skills=["Python", "Django", "React"],
                source="resume_pdf",
            )
            
            result = score_candidate(jd, candidate)
            
            assert isinstance(result, CandidateScore)
            assert 0 <= result.skills.score <= 10
            assert 0 <= result.experience.score <= 10
            assert 0 <= result.education.score <= 10
            assert 0 <= result.portfolio.score <= 10
            assert 0 <= result.communication.score <= 10
            assert 0 <= result.weighted_total <= 10


class TestEmbeddingSimilarityConversion:
    """Tests for embedding similarity to score conversion."""
    
    def test_similarity_to_score(self):
        """Test that similarity maps correctly to 0-10 scale."""
        assert _embedding_similarity_to_score(0.0) == 0.0
        assert _embedding_similarity_to_score(1.0) == 10.0
        assert _embedding_similarity_to_score(0.5) == 5.0
        assert _embedding_similarity_to_score(0.75) == 7.5
        assert _embedding_similarity_to_score(None) == 0.0
    
    def test_embedding_score_in_range(self):
        """Test that embedding-derived scores are in [0, 10]."""
        for sim in [0, 0.1, 0.5, 0.9, 1.0]:
            score = _embedding_similarity_to_score(sim)
            assert 0 <= score <= 10

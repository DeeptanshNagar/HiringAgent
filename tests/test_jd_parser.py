"""
Unit tests for Step 2: JD Parser module.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import JDRequirements


class MockResponse:
    """Mock LLM response for testing."""
    def __init__(self, content: str):
        self.content = content


class TestJDParser:
    """Tests for JD parsing with mocked LLM."""
    
    def test_parse_jd_success(self):
        """Test successful JD parsing with mocked LLM."""
        mock_json = '''
        {
            "job_title": "Senior Full-Stack Engineer",
            "required_skills": ["Python", "Django", "React", "PostgreSQL"],
            "preferred_skills": ["Kubernetes", "AWS"],
            "min_experience_years": 5,
            "experience_domain": "FinTech",
            "required_education": "Bachelor's in Computer Science",
            "required_certifications": ["AWS Certified"],
            "key_responsibilities": ["Build applications", "Mentor juniors"],
            "seniority_level": "senior",
            "preferred_soft_skills": ["Communication", "Leadership"]
        }
        '''
        
        with patch("agent.llm_factory.get_llm_client") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = MockResponse(mock_json)
            mock_get_llm.return_value = mock_llm
            
            from agent.jd_parser import parse_jd
            
            jd_text = """
            Senior Full-Stack Engineer — FinTech
            
            Required: Python, Django, React, PostgreSQL
            Preferred: Kubernetes, AWS
            
            5+ years experience in FinTech.
            Bachelor's in Computer Science required.
            AWS Certified preferred.
            
            Responsibilities:
            - Build applications
            - Mentor juniors
            
            Senior level position.
            Must have strong Communication and Leadership skills.
            """
            
            result = parse_jd(jd_text)
            
            assert isinstance(result, JDRequirements)
            assert result.job_title == "Senior Full-Stack Engineer"
            assert "Python" in result.required_skills
            assert result.min_experience_years == 5
            assert result.experience_domain == "FinTech"
            assert result.seniority_level == "senior"
    
    def test_parse_jd_retry_on_failure(self):
        """Test that parser retries on malformed LLM response."""
        bad_response = "Not valid JSON"
        good_response = '''
        {
            "job_title": "Test Position",
            "required_skills": ["Python"],
            "preferred_skills": [],
            "min_experience_years": null,
            "experience_domain": null,
            "required_education": null,
            "required_certifications": [],
            "key_responsibilities": ["Write code"],
            "seniority_level": null,
            "preferred_soft_skills": []
        }
        '''
        
        with patch("agent.llm_factory.get_llm_client") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = [
                MockResponse(bad_response),
                MockResponse(good_response),
            ]
            mock_get_llm.return_value = mock_llm
            
            from agent.jd_parser import parse_jd
            
            result = parse_jd("Test job description")
            
            assert isinstance(result, JDRequirements)
            assert result.job_title == "Test Position"
            assert mock_llm.invoke.call_count == 2
    
    def test_parse_jd_all_fields_populated(self):
        """Test that all required fields are populated in parsed JD."""
        mock_json = '''
        {
            "job_title": "Data Scientist",
            "required_skills": ["Python", "Machine Learning", "SQL"],
            "preferred_skills": ["TensorFlow", "PyTorch"],
            "min_experience_years": 3,
            "experience_domain": "Healthcare",
            "required_education": "Masters in Statistics or CS",
            "required_certifications": ["AWS ML Specialty"],
            "key_responsibilities": ["Build models", "Analyze data", "Deploy to production"],
            "seniority_level": "mid",
            "preferred_soft_skills": ["Communication", "Problem-solving"]
        }
        '''
        
        with patch("agent.llm_factory.get_llm_client") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = MockResponse(mock_json)
            mock_get_llm.return_value = mock_llm
            
            from agent.jd_parser import parse_jd
            
            result = parse_jd("Data scientist position in healthcare")
            
            assert result.job_title is not None and len(result.job_title) > 0
            assert len(result.required_skills) > 0
            assert len(result.key_responsibilities) > 0
            assert result.min_experience_years is not None
            assert result.seniority_level is not None

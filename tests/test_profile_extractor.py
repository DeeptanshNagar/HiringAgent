"""
Unit tests for Step 3: Candidate Profile Extractor module.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import CandidateProfile

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_data")


class MockResponse:
    """Mock LLM response for testing."""
    def __init__(self, content: str):
        self.content = content


class TestProfileExtractor:
    """Tests for candidate profile extraction."""
    
    def test_extract_strong_match_profile(self):
        """Test extracting profile from strong match resume text."""
        mock_json = '''
        {
            "candidate_name": "Alexandra Martinez",
            "email": "alexandra.martinez@email.com",
            "phone": "+44 7700 900123",
            "current_role": "Senior Software Engineer",
            "years_of_experience": 7,
            "experience_domain": "FinTech",
            "skills": ["Python", "Django", "React", "PostgreSQL", "AWS", "Docker", "Kubernetes"],
            "work_history": [
                {
                    "company": "PayFlow Technologies",
                    "role": "Senior Software Engineer",
                    "duration_months": 36,
                    "domain": "FinTech",
                    "responsibilities_summary": "Led payment settlement system"
                }
            ],
            "education": [
                {
                    "degree": "MSc Computer Science",
                    "field": "Distributed Systems",
                    "institution": "Imperial College London",
                    "year": 2016
                }
            ],
            "certifications": ["AWS Solutions Architect"],
            "projects": [
                {
                    "title": "py-payment-gateway",
                    "description": "Open-source payment library",
                    "technologies": ["Python"],
                    "relevance_hint": "Directly relevant"
                }
            ],
            "communication_quality_signals": "Excellent writing, well-structured resume"
        }
        '''
        
        with patch("agent.llm_factory.get_llm_client") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = MockResponse(mock_json)
            mock_get_llm.return_value = mock_llm
            
            from agent.profile_extractor import extract_profile
            
            resume_text = """
            ALEXANDRA MARTINEZ
            Senior Software Engineer
            7 years experience in FinTech
            Python, Django, React, PostgreSQL, AWS
            MSc Computer Science from Imperial College London
            """
            
            profile = extract_profile("cand_001", "resume_pdf", resume_text)
            
            assert isinstance(profile, CandidateProfile)
            assert profile.candidate_name == "Alexandra Martinez"
            assert len(profile.skills) > 0
            assert "Python" in profile.skills
            assert profile.years_of_experience == 7
            assert profile.parse_flagged is False
    
    def test_extract_sparse_resume(self):
        """Test handling of sparse/edge case resume."""
        mock_json = '''
        {
            "candidate_name": "S. K.",
            "email": "sk@email.com",
            "phone": null,
            "current_role": null,
            "years_of_experience": 2,
            "experience_domain": null,
            "skills": ["Python"],
            "work_history": [],
            "education": [
                {
                    "degree": "Computer degree",
                    "field": null,
                    "institution": "university",
                    "year": null
                }
            ],
            "certifications": [],
            "projects": [],
            "communication_quality_signals": "Sparse information, unclear details"
        }
        '''
        
        with patch("agent.llm_factory.get_llm_client") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = MockResponse(mock_json)
            mock_get_llm.return_value = mock_llm
            
            from agent.profile_extractor import extract_profile
            
            sparse_text = "S. K.\nDeveloper\nPython, coding\nDid some programming. 2 years."
            
            profile = extract_profile("cand_004", "resume_pdf", sparse_text)
            
            assert isinstance(profile, CandidateProfile)
            assert profile.parse_flagged is False  # LLM succeeded
            assert len(profile.skills) > 0
    
    def test_pii_extraction_regex(self):
        """Test that PII is extracted via regex before LLM call."""
        from agent.profile_extractor import extract_pii_with_regex
        
        text = """
        Contact John Doe at john.doe@example.com or call +44 7700 900123.
        Alternative: 555-123-4567
        """
        
        pii = extract_pii_with_regex(text)
        
        assert pii["email"] == "john.doe@example.com"
        assert pii["phone"] is not None  # Should find one of the phone numbers
    
    def test_linkedin_json_parsing(self):
        """Test parsing LinkedIn JSON export format."""
        from agent.profile_extractor import parse_linkedin_json_data
        
        linkedin_json = '''
        {
            "Profile": {
                "First Name": "Jane",
                "Last Name": "Smith",
                "Headline": "Software Engineer",
                "Summary": "Experienced developer"
            },
            "Positions": [
                {
                    "Title": "Engineer",
                    "Company Name": "TechCorp",
                    "Started On": "2020",
                    "Finished On": null,
                    "Description": "Building apps"
                }
            ],
            "Education": [
                {
                    "School Name": "MIT",
                    "Degree Name": "BSc",
                    "Field Of Study": "CS"
                }
            ],
            "Skills": [{"Name": "Python"}, {"Name": "JavaScript"}],
            "Certifications": [],
            "Projects": []
        }
        '''
        
        result = parse_linkedin_json_data(linkedin_json)
        
        assert "Jane Smith" in result
        assert "Software Engineer" in result
        assert "TechCorp" in result
        assert "Python" in result

"""
Unit tests for Step 6: Report Generator module.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import CandidateScore, DimensionScore, HireRecommendation
from agent.report_generator import (
    generate_json_report,
    generate_html_report,
    generate_pdf_report,
    generate_all_reports,
)


def make_test_candidates() -> list:
    """Create test candidates for report generation."""
    return [
        CandidateScore(
            rank=1,
            candidate_id="cand_001",
            candidate_name="Alice Strong",
            skills=DimensionScore(score=9, justification="Excellent skills match"),
            experience=DimensionScore(score=8.5, justification="Strong domain experience"),
            education=DimensionScore(score=8, justification="Exceeds requirements"),
            portfolio=DimensionScore(score=9, justification="Impressive projects"),
            communication=DimensionScore(score=8, justification="Clear and concise"),
            weighted_total=8.58,
            hire_recommendation=HireRecommendation.STRONG_HIRE,
            overall_summary="Top candidate with strong fit across all dimensions.",
        ),
        CandidateScore(
            rank=2,
            candidate_id="cand_002",
            candidate_name="Bob Average",
            skills=DimensionScore(score=6, justification="Partial skills match"),
            experience=DimensionScore(score=5, justification="Some relevant experience"),
            education=DimensionScore(score=5, justification="Meets requirements"),
            portfolio=DimensionScore(score=5, justification="Limited portfolio"),
            communication=DimensionScore(score=6, justification="Adequate"),
            weighted_total=5.45,
            hire_recommendation=HireRecommendation.MAYBE,
            overall_summary="Average candidate with some potential.",
        ),
    ]


class TestJSONReport:
    """Tests for JSON report generation."""
    
    def test_json_report_created(self, tmp_path):
        """Test that JSON report file is created."""
        candidates = make_test_candidates()
        output_path = str(tmp_path / "test_report.json")
        
        result_path = generate_json_report("Test Position", candidates, output_path)
        
        assert os.path.exists(result_path)
        assert result_path.endswith(".json")
    
    def test_json_report_valid(self, tmp_path):
        """Test that JSON report contains valid data."""
        candidates = make_test_candidates()
        output_path = str(tmp_path / "test_report.json")
        
        generate_json_report("Test Position", candidates, output_path)
        
        with open(output_path, "r") as f:
            data = json.load(f)
        
        assert data["job_title"] == "Test Position"
        assert data["total_candidates_evaluated"] == 2
        assert len(data["shortlist"]) == 2
        assert data["shortlist"][0]["candidate_name"] == "Alice Strong"
    
    def test_json_matches_schema(self, tmp_path):
        """Test that JSON report matches ShortlistReport schema."""
        candidates = make_test_candidates()
        output_path = str(tmp_path / "test_report.json")
        
        generate_json_report("Test Position", candidates, output_path)
        
        from models.schemas import ShortlistReport
        
        with open(output_path, "r") as f:
            data = json.load(f)
        
        # Validate schema (will raise if invalid)
        report = ShortlistReport(**data)
        assert report.framework_used is not None


class TestHTMLReport:
    """Tests for HTML report generation."""
    
    def test_html_report_created(self, tmp_path):
        """Test that HTML report file is created."""
        candidates = make_test_candidates()
        output_path = str(tmp_path / "test_report.html")
        
        result_path = generate_html_report("Test Position", candidates, output_path)
        
        assert os.path.exists(result_path)
        assert result_path.endswith(".html")
    
    def test_html_contains_candidate_names(self, tmp_path):
        """Test that HTML contains candidate names."""
        candidates = make_test_candidates()
        output_path = str(tmp_path / "test_report.html")
        
        generate_html_report("Test Position", candidates, output_path)
        
        with open(output_path, "r") as f:
            content = f.read()
        
        assert "Alice Strong" in content
        assert "Bob Average" in content
        assert "Strong Hire" in content
    
    def test_html_is_self_contained(self, tmp_path):
        """Test that HTML is self-contained (inline CSS)."""
        candidates = make_test_candidates()
        output_path = str(tmp_path / "test_report.html")
        
        generate_html_report("Test Position", candidates, output_path)
        
        with open(output_path, "r") as f:
            content = f.read()
        
        assert "<style>" in content
        assert "</style>" in content
        # Should not have external CSS links
        assert 'href="http' not in content or 'rel="stylesheet"' not in content


class TestPDFReport:
    """Tests for PDF report generation."""
    
    def test_pdf_report_created(self, tmp_path):
        """Test that PDF report file is created and non-empty."""
        candidates = make_test_candidates()
        output_path = str(tmp_path / "test_report.pdf")
        
        result_path = generate_pdf_report("Test Position", candidates, output_path)
        
        assert os.path.exists(result_path)
        assert result_path.endswith(".pdf")
        assert os.path.getsize(result_path) > 0
    
    def test_pdf_not_empty(self, tmp_path):
        """Test that PDF has meaningful content."""
        candidates = make_test_candidates()
        output_path = str(tmp_path / "test_report.pdf")
        
        generate_pdf_report("Test Position", candidates, output_path)
        
        size = os.path.getsize(output_path)
        assert size > 1000  # Should be at least 1KB


class TestAllReports:
    """Tests for generating all three formats."""
    
    def test_all_formats_generated(self, tmp_path):
        """Test that all three formats are generated."""
        candidates = make_test_candidates()
        
        results = generate_all_reports(
            "Test Position",
            candidates,
            timestamp_str="2024-01-01T00-00-00",
        )
        
        assert "json" in results
        assert "html" in results
        assert "pdf" in results
        assert os.path.exists(results["json"])
        assert os.path.exists(results["html"])
        assert os.path.exists(results["pdf"])

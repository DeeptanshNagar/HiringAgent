"""
Pydantic data models for the HR Resume & LinkedIn Shortlisting Agent.
All models enforce strict validation for the 7-step pipeline.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class HireRecommendation(str, Enum):
    """Hire recommendation tiers based on weighted total score thresholds."""
    STRONG_HIRE = "Strong Hire"
    HIRE = "Hire"
    MAYBE = "Maybe"
    NO_HIRE = "No Hire"


class WorkExperience(BaseModel):
    """A single work experience entry for a candidate."""
    company: str
    role: str
    duration_months: Optional[int] = None
    domain: Optional[str] = None
    responsibilities_summary: Optional[str] = None


class Education(BaseModel):
    """A single education entry for a candidate."""
    degree: str
    field: Optional[str] = None
    institution: Optional[str] = None
    year: Optional[int] = None


class Project(BaseModel):
    """A single project/portfolio entry for a candidate."""
    title: str
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    relevance_hint: Optional[str] = None


class CandidateProfile(BaseModel):
    """Structured candidate profile extracted from resume or LinkedIn data."""
    candidate_id: str
    candidate_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    current_role: Optional[str] = None
    years_of_experience: Optional[float] = None
    experience_domain: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    work_history: List[WorkExperience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    communication_quality_signals: Optional[str] = None
    source: str  # "resume_pdf" | "resume_docx" | "linkedin_json" | "linkedin_url"
    parse_flagged: bool = False  # True if extraction had errors


class JDRequirements(BaseModel):
    """Structured job description requirements extracted by the LLM."""
    job_title: str
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    min_experience_years: Optional[float] = None
    experience_domain: Optional[str] = None
    required_education: Optional[str] = None
    required_certifications: List[str] = Field(default_factory=list)
    key_responsibilities: List[str] = Field(default_factory=list)
    seniority_level: Optional[str] = None
    preferred_soft_skills: List[str] = Field(default_factory=list)


class DimensionScore(BaseModel):
    """Score and justification for a single evaluation dimension."""
    score: float = Field(ge=0, le=10, description="Score between 0 and 10 inclusive")
    justification: str = Field(max_length=200, description="Brief justification (max 200 chars)")

    @field_validator("score")
    @classmethod
    def validate_score_step(cls, v: float) -> float:
        """Ensure score is in 0.5 increments."""
        if v * 2 != int(v * 2):
            raise ValueError("Score must be in increments of 0.5")
        return v


class CandidateScore(BaseModel):
    """Complete scored evaluation for a single candidate."""
    rank: Optional[int] = None
    candidate_id: str
    candidate_name: str
    skills: DimensionScore
    experience: DimensionScore
    education: DimensionScore
    portfolio: DimensionScore
    communication: DimensionScore
    weighted_total: float = Field(ge=0, le=10)
    hire_recommendation: HireRecommendation
    overall_summary: str
    override_applied: bool = False
    override_reason: Optional[str] = None
    escalate_for_interview: bool = False
    embedding_skills_score: Optional[float] = Field(default=None, ge=0, le=1)
    low_confidence: bool = False

    @field_validator("weighted_total")
    @classmethod
    def validate_weighted_total(cls, v: float) -> float:
        """Ensure weighted total is in 0.5 increments and round to 2 decimals."""
        return round(v, 2)


class ShortlistReport(BaseModel):
    """Complete shortlist report containing all evaluated candidates."""
    generated_at: str
    job_title: str
    model_used: str
    framework_used: str
    total_candidates_evaluated: int
    shortlist: List[CandidateScore]

    @field_validator("generated_at")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Ensure valid ISO datetime format."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("generated_at must be a valid ISO 8601 datetime string")
        return v


class OverrideEvent(BaseModel):
    """A single override event logged when HR manually adjusts scores."""
    timestamp: str
    candidate_id: str
    candidate_name: str
    dimension: str
    old_score: float
    new_score: float
    reason: str

    @field_validator("old_score", "new_score")
    @classmethod
    def validate_score_range(cls, v: float) -> float:
        if not 0 <= v <= 10:
            raise ValueError("Score must be between 0 and 10")
        return v


class SecurityEvent(BaseModel):
    """A security event logged when suspicious input is detected."""
    timestamp: str
    candidate_id: Optional[str] = None
    event_type: str
    stripped_content: Optional[str] = None
    reason: str


class IngestionOutput(BaseModel):
    """Output from Step 1: Input Ingestion."""
    jd_raw: str
    candidates: List[dict[str, Any]]

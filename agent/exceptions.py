"""
Custom exception hierarchy for the HR Shortlisting Agent.

Using specific exceptions instead of generic ones enables:
- Targeted error handling at each pipeline step
- Meaningful error messages in the UI
- Structured error logging
- Retry logic scoped to recoverable errors only
"""

from __future__ import annotations


class ShortlistAgentError(Exception):
    """Base exception for all agent errors."""

    def __init__(self, message: str, *, step: str | None = None, candidate_id: str | None = None):
        self.step = step
        self.candidate_id = candidate_id
        super().__init__(message)


class IngestionError(ShortlistAgentError):
    """Raised when file validation or text extraction fails."""

    def __init__(self, message: str, *, filename: str | None = None, **kwargs):
        self.filename = filename
        super().__init__(message, step="ingestion", **kwargs)


class JDParseError(ShortlistAgentError):
    """Raised when the JD cannot be parsed into structured requirements."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, step="jd_parsing", **kwargs)


class ProfileExtractionError(ShortlistAgentError):
    """Raised when a candidate profile cannot be extracted."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, step="profile_extraction", **kwargs)


class LLMScoringError(ShortlistAgentError):
    """Raised when the LLM scoring call fails after retries."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, step="scoring", **kwargs)


class ReportGenerationError(ShortlistAgentError):
    """Raised when report generation (JSON/HTML/PDF) fails."""

    def __init__(self, message: str, *, report_format: str | None = None, **kwargs):
        self.report_format = report_format
        super().__init__(message, step="report_generation", **kwargs)


class SecurityViolationError(ShortlistAgentError):
    """Raised when a security check fails (prompt injection, invalid file, etc.)."""

    def __init__(self, message: str, *, violation_type: str | None = None, **kwargs):
        self.violation_type = violation_type
        super().__init__(message, step="security", **kwargs)


class ConfigurationError(ShortlistAgentError):
    """Raised when required configuration is missing or invalid."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, step="configuration", **kwargs)


class RateLimitError(ShortlistAgentError):
    """Raised when a client exceeds the rate limit."""

    def __init__(self, message: str, *, retry_after: int = 60, **kwargs):
        self.retry_after = retry_after
        super().__init__(message, step="rate_limit", **kwargs)


class AuthenticationError(ShortlistAgentError):
    """Raised when API key validation fails."""

    def __init__(self, message: str = "Invalid or missing API key", **kwargs):
        super().__init__(message, step="authentication", **kwargs)

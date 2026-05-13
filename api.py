"""
FastAPI REST API for the HR Shortlisting Agent.

Provides programmatic access to the pipeline for integration with
ATS systems, CI pipelines, and other services. Runs alongside
the Streamlit UI on a separate port.

Usage:
    uvicorn api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import hmac
import logging
import os
import tempfile
import time
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import get_settings
from agent.exceptions import AuthenticationError, ShortlistAgentError

logger = logging.getLogger(__name__)

# ── App setup ─────────────────────────────────────────────────
settings = get_settings()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="HR Shortlisting Agent API",
    description="AI-powered candidate evaluation with transparent scoring.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.state.limiter = limiter

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rate limit error handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


# ── Auth dependency ───────────────────────────────────────────
def verify_api_key(x_api_key: str = Header(..., description="Agent API key")):
    """Validate the API key using constant-time comparison."""
    expected = settings.agent_api_key
    if not hmac.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


# ── Response models ───────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    llm_provider: str
    has_api_key: bool
    cache_enabled: bool


class AnalyseResponse(BaseModel):
    job_title: str
    total_candidates: int
    candidates: list[dict[str, Any]]
    report_paths: dict[str, str]
    duration_seconds: float


class ErrorResponse(BaseModel):
    detail: str
    step: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────

@app.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint — no auth required."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        llm_provider=settings.primary_llm_provider,
        has_api_key=settings.has_llm_key,
        cache_enabled=settings.enable_cache,
    )


@app.post(
    "/api/v1/analyse",
    response_model=AnalyseResponse,
    tags=["Pipeline"],
    dependencies=[Depends(verify_api_key)],
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
@limiter.limit("5/minute")
async def analyse_candidates(
    request: Request,
    jd_text: str = Form(..., description="Job description text"),
    resumes: list[UploadFile] = File(default=[], description="Resume files (PDF/DOCX)"),
    linkedin_files: list[UploadFile] = File(default=[], description="LinkedIn JSON exports"),
):
    """
    Run the full 7-step pipeline on uploaded candidates.

    Accepts a JD as text and candidate files as multipart uploads.
    Returns scored, ranked candidates with report file paths.
    """
    start_time = time.time()

    # Read resume files
    resume_data = []
    for f in resumes:
        content = await f.read()
        resume_data.append((content, f.filename or "unknown.pdf"))

    # Read LinkedIn files
    linkedin_data = []
    for f in linkedin_files:
        content = await f.read()
        linkedin_data.append((content, f.filename or "unknown.json"))

    if not resume_data and not linkedin_data:
        raise HTTPException(status_code=422, detail="No candidate files provided")

    try:
        from agent.pipeline import run_pipeline

        results = run_pipeline(
            jd_text=jd_text,
            resume_files=resume_data if resume_data else None,
            linkedin_json_files=linkedin_data if linkedin_data else None,
        )

        ranked = results.get("ranked_candidates", [])
        candidates_out = []
        for c in ranked:
            candidates_out.append(c.model_dump())

        duration = round(time.time() - start_time, 2)

        return AnalyseResponse(
            job_title=results.get("jd_requirements", {}).job_title if results.get("jd_requirements") else "Unknown",
            total_candidates=len(ranked),
            candidates=candidates_out,
            report_paths=results.get("report_paths", {}),
            duration_seconds=duration,
        )

    except ShortlistAgentError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Pipeline failed via API")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get(
    "/api/v1/reports/{filename}",
    tags=["Reports"],
    dependencies=[Depends(verify_api_key)],
)
async def download_report(filename: str):
    """Download a generated report by filename."""
    # Sanitize filename to prevent path traversal
    safe_name = os.path.basename(filename)
    file_path = os.path.join(settings.output_dir, safe_name)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Report not found")

    return FileResponse(file_path, filename=safe_name)

"""
Step 3: Candidate Profile Extraction Module.
Extracts structured candidate profiles from resume text or LinkedIn data using LLM.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import requests

from models.schemas import CandidateProfile, Education, Project, WorkExperience
from security.input_sanitiser import sanitise_for_system_prompt, sanitise_text

logger = logging.getLogger(__name__)

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "candidate_extraction.txt")


def load_prompt_template() -> str:
    """Load the candidate extraction prompt template from file."""
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Prompt template not found at {PROMPT_PATH}, using default")
        return "Extract candidate information from:\n{candidate_text}"


# LLM client is now provided by the centralized factory in agent/llm_factory.py


def extract_pii_with_regex(text: str) -> Dict[str, Optional[str]]:
    """
    Extract PII fields using regex before LLM call.
    This allows us to minimize what we send to the LLM.
    
    Args:
        text: Raw resume text.
        
    Returns:
        Dict with email, phone extracted via regex.
    """
    pii = {"email": None, "phone": None}
    
    # Email regex
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, text)
    if email_match:
        pii["email"] = email_match.group(0)
    
    # Phone regex (various formats)
    phone_patterns = [
        r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # US/international
        r'\+?\d{1,3}[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # Simple international
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # Basic US
    ]
    for pattern in phone_patterns:
        phone_match = re.search(pattern, text)
        if phone_match:
            pii["phone"] = phone_match.group(0)
            break
    
    return pii


def parse_linkedin_json_data(raw_text: str) -> str:
    """
    Convert LinkedIn JSON export to a structured text format for LLM processing.
    
    Args:
        raw_text: JSON string from LinkedIn export.
        
    Returns:
        Formatted text for LLM processing.
    """
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text
    
    parts: list[str] = []
    
    # Profile basics
    profile = data.get("Profile", {})
    if profile:
        first = profile.get("First Name", "")
        last = profile.get("Last Name", "")
        parts.append(f"Name: {first} {last}")
        parts.append(f"Headline: {profile.get('Headline', '')}")
        parts.append(f"Summary: {profile.get('Summary', '')}")
        parts.append("")
    
    # Positions
    positions = data.get("Positions", [])
    if positions:
        parts.append("EXPERIENCE:")
        for pos in positions:
            title = pos.get("Title", "")
            company = pos.get("Company Name", "")
            start = pos.get("Started On", "")
            end = pos.get("Finished On", "Present")
            desc = pos.get("Description", "")
            parts.append(f"  {title} at {company} ({start} - {end})")
            if desc:
                parts.append(f"    {desc}")
        parts.append("")
    
    # Education
    education = data.get("Education", [])
    if education:
        parts.append("EDUCATION:")
        for edu in education:
            school = edu.get("School Name", "")
            degree = edu.get("Degree Name", "")
            field = edu.get("Field Of Study", "")
            parts.append(f"  {degree} in {field} from {school}")
        parts.append("")
    
    # Skills
    skills = data.get("Skills", [])
    if skills:
        skill_names = [s.get("Name", "") for s in skills]
        parts.append(f"SKILLS: {', '.join(filter(None, skill_names))}")
        parts.append("")
    
    # Certifications
    certs = data.get("Certifications", [])
    if certs:
        parts.append("CERTIFICATIONS:")
        for cert in certs:
            parts.append(f"  {cert.get('Name', '')} - {cert.get('Authority', '')}")
        parts.append("")
    
    # Projects
    projects = data.get("Projects", [])
    if projects:
        parts.append("PROJECTS:")
        for proj in projects:
            title = proj.get("Title", "")
            desc = proj.get("Description", "")
            parts.append(f"  {title}: {desc}")
        parts.append("")
    
    return "\n".join(parts)


def scrape_linkedin_url(url: str) -> str:
    """
    Attempt to scrape a LinkedIn public profile URL via RapidAPI.
    Gracefully degrades if API is unavailable.
    
    Args:
        url: LinkedIn profile URL.
        
    Returns:
        Scraped profile text or empty string on failure.
    """
    rapidapi_key = os.getenv("RAPIDAPI_KEY")
    if not rapidapi_key:
        logger.warning("RAPIDAPI_KEY not configured, cannot scrape LinkedIn URL")
        return ""
    
    try:
        # RapidAPI LinkedIn scraper endpoint
        api_url = "https://linkedin-api8.p.rapidapi.com/"
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": "linkedin-api8.p.rapidapi.com",
        }
        params = {"url": url}
        
        response = requests.get(api_url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            # Format the response data into text
            parts: list[str] = []
            
            if isinstance(data, dict):
                first_name = data.get("firstName", "")
                last_name = data.get("lastName", "")
                parts.append(f"Name: {first_name} {last_name}")
                parts.append(f"Headline: {data.get('headline', '')}")
                parts.append(f"Summary: {data.get('summary', '')}")
                
                positions = data.get("positions", {}).get("elements", [])
                if positions:
                    parts.append("\nEXPERIENCE:")
                    for pos in positions:
                        title = pos.get("title", "")
                        company = pos.get("companyName", "")
                        parts.append(f"  {title} at {company}")
                
                skills = data.get("skills", [])
                if skills:
                    skill_names = [s.get("name", "") for s in skills]
                    parts.append(f"\nSKILLS: {', '.join(filter(None, skill_names))}")
            
            return "\n".join(parts)
        else:
            logger.warning(f"LinkedIn scrape returned status {response.status_code}")
            return ""
            
    except Exception as e:
        logger.warning(f"LinkedIn scraping failed: {e}")
        return ""


def extract_profile(
    candidate_id: str,
    source: str,
    raw_text: str,
    url: Optional[str] = None,
) -> CandidateProfile:
    """
    Extract a structured candidate profile from raw input data.
    
    Args:
        candidate_id: Unique candidate identifier.
        source: Source type (resume_pdf, resume_docx, linkedin_json, linkedin_url).
        raw_text: Raw text content.
        url: LinkedIn URL if applicable.
        
    Returns:
        Validated CandidateProfile.
    """
    # Handle LinkedIn URL source
    if source == "linkedin_url" and url:
        scraped_text = scrape_linkedin_url(url)
        if scraped_text:
            raw_text = scraped_text
        else:
            logger.warning(f"Could not scrape LinkedIn URL {url}, using URL as placeholder")
            raw_text = f"LinkedIn Profile: {url}\nCould not retrieve full profile. Please download LinkedIn data export as JSON."
    
    # Handle LinkedIn JSON source
    if source == "linkedin_json":
        try:
            raw_text = parse_linkedin_json_data(raw_text)
        except Exception as e:
            logger.warning(f"LinkedIn JSON parsing issue: {e}, using raw text")
    
    # Extract PII with regex first (for local processing)
    pii = extract_pii_with_regex(raw_text)
    
    # Sanitise text for LLM
    sanitised_text, was_modified = sanitise_text(raw_text, candidate_id=candidate_id)
    if was_modified:
        logger.warning(f"Candidate {candidate_id} text contained suspicious content that was sanitised")
    
    safe_text = sanitise_for_system_prompt(sanitised_text)
    
    # Prepare LLM prompt
    template = load_prompt_template()
    prompt = template.replace("{candidate_text}", safe_text)
    
    # Call LLM via centralized factory
    from agent.llm_factory import get_llm_client
    llm = get_llm_client()
    
    parse_flagged = False
    extracted_data: Dict[str, Any] = {}
    
    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        
        # Clean up response
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        extracted_data = json.loads(content)
        
    except Exception as e:
        logger.warning(f"Profile extraction first attempt failed for {candidate_id}: {e}, retrying")
        
        retry_prompt = (
            f"{prompt}\n\n"
            f"IMPORTANT: Return ONLY a valid JSON object matching the schema. "
            f"No markdown. No extra text. Use double quotes for all strings."
        )
        
        try:
            response = llm.invoke(retry_prompt)
            content = response.content if hasattr(response, "content") else str(response)
            
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            extracted_data = json.loads(content)
            
        except Exception as e2:
            logger.error(f"Profile extraction failed for {candidate_id} after retry: {e2}")
            parse_flagged = True
            # Create minimal profile with what we can extract
            extracted_data = {
                "candidate_name": "Unknown",
                "email": pii.get("email"),
                "phone": pii.get("phone"),
                "current_role": None,
                "years_of_experience": None,
                "experience_domain": None,
                "skills": [],
                "work_history": [],
                "education": [],
                "certifications": [],
                "projects": [],
                "communication_quality_signals": "Parse failed, manual review needed",
            }
    
    # Build CandidateProfile
    # Use regex-extracted PII if LLM didn't find it
    if not extracted_data.get("email") and pii["email"]:
        extracted_data["email"] = pii["email"]
    if not extracted_data.get("phone") and pii["phone"]:
        extracted_data["phone"] = pii["phone"]
    
    # Convert nested dicts to Pydantic models
    work_history = []
    for wh in extracted_data.get("work_history", []) or []:
        try:
            work_history.append(WorkExperience(**wh))
        except Exception:
            pass
    
    education = []
    for ed in extracted_data.get("education", []) or []:
        try:
            education.append(Education(**ed))
        except Exception:
            pass
    
    projects = []
    for pr in extracted_data.get("projects", []) or []:
        try:
            projects.append(Project(**pr))
        except Exception:
            pass
    
    profile = CandidateProfile(
        candidate_id=candidate_id,
        candidate_name=extracted_data.get("candidate_name") or "Unknown",
        email=extracted_data.get("email"),
        phone=extracted_data.get("phone"),
        current_role=extracted_data.get("current_role"),
        years_of_experience=extracted_data.get("years_of_experience"),
        experience_domain=extracted_data.get("experience_domain"),
        skills=extracted_data.get("skills", []) or [],
        work_history=work_history,
        education=education,
        certifications=extracted_data.get("certifications", []) or [],
        projects=projects,
        communication_quality_signals=extracted_data.get("communication_quality_signals"),
        source=source,
        parse_flagged=parse_flagged,
    )
    
    return profile

"""
Step 2: JD Parsing Module.
Uses LLM to extract structured requirements from raw job description text.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from models.schemas import JDRequirements
from security.input_sanitiser import sanitise_for_system_prompt, sanitise_text

logger = logging.getLogger(__name__)

# Load prompt template
PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "jd_extraction.txt")


def load_prompt_template() -> str:
    """Load the JD extraction prompt template from file."""
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Prompt template not found at {PROMPT_PATH}, using default")
        return "SYSTEM: You are a precise job description analyst. Extract structured requirements.\n\nJD Text:\n{jd_text}"


# LLM client is now provided by the centralized factory in agent/llm_factory.py
# This eliminates the duplicated _get_llm_client() that was in 3 files.


def parse_jd(jd_raw_text: str) -> JDRequirements:
    """
    Parse raw job description text into structured JDRequirements.
    
    Args:
        jd_raw_text: Raw text extracted from JD file.
        
    Returns:
        Validated JDRequirements Pydantic model.
        
    Raises:
        ValueError: If parsing fails after retries.
        RuntimeError: If LLM client cannot be initialized.
    """
    # Sanitise input
    sanitised_text, was_modified = sanitise_text(jd_raw_text)
    if was_modified:
        logger.warning("JD text contained potentially suspicious content that was sanitised")
    
    # Additional sanitisation for prompt insertion
    safe_text = sanitise_for_system_prompt(sanitised_text)
    
    # Load prompt template
    template = load_prompt_template()
    prompt = template.replace("{jd_text}", safe_text)
    
    # Get LLM client from centralized factory
    from agent.llm_factory import get_llm_client
    llm = get_llm_client()
    
    # First attempt
    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        
        # Parse JSON from response
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        data = json.loads(content)
        return JDRequirements(**data)
        
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"JD parsing first attempt failed: {e}, retrying with correction prompt")
        
        # Retry with explicit correction prompt
        retry_prompt = (
            f"{prompt}\n\n"
            f"IMPORTANT: Your previous response was not valid JSON. "
            f"Return ONLY a valid JSON object. Do not use markdown code blocks. "
            f"Do not include any text before or after the JSON. "
            f"Ensure all string values use double quotes."
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
            
            data = json.loads(content)
            return JDRequirements(**data)
            
        except Exception as e2:
            logger.error(f"JD parsing failed after retry: {e2}")
            raise ValueError(f"Failed to parse job description after 2 attempts: {e2}")

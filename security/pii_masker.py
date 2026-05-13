"""
PII (Personally Identifiable Information) masking module.
Ensures sensitive candidate data is redacted in logs and audit trails.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def mask_email(email: Optional[str]) -> Optional[str]:
    """
    Mask an email address: johndoe@gmail.com -> j***@gmail.com
    
    Args:
        email: Raw email address.
        
    Returns:
        Masked email or None if input is None.
    """
    if not email:
        return None
    
    parts = email.split("@")
    if len(parts) != 2:
        return "***"
    
    local, domain = parts
    if len(local) <= 1:
        masked_local = local
    elif len(local) == 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "***"
    
    return f"{masked_local}@{domain}"


def mask_phone(phone: Optional[str]) -> Optional[str]:
    """
    Mask a phone number: +1-555-123-4567 -> +1-555-***-4567
    
    Args:
        phone: Raw phone number.
        
    Returns:
        Masked phone or None if input is None.
    """
    if not phone:
        return None
    
    # Remove all non-digit characters for processing
    digits = re.sub(r"\D", "", phone)
    
    if len(digits) < 4:
        return "***"
    
    # Show last 2-4 digits only
    visible_digits = min(4, len(digits) // 4 + 2)
    masked = "*" * (len(digits) - visible_digits) + digits[-visible_digits:]
    
    # Reformat with original non-digit characters if possible
    result = []
    digit_idx = 0
    for char in phone:
        if char.isdigit() and digit_idx < len(masked):
            result.append(masked[digit_idx])
            digit_idx += 1
        elif char.isdigit():
            result.append("*")
        else:
            result.append(char)
    
    return "".join(result)


def mask_name(name: Optional[str]) -> Optional[str]:
    """
    Mask a person's name: John Doe -> J*** D**
    
    Args:
        name: Raw full name.
        
    Returns:
        Masked name or None if input is None.
    """
    if not name:
        return None
    
    parts = name.split()
    masked_parts = []
    
    for part in parts:
        if len(part) <= 1:
            masked_parts.append(part)
        else:
            masked_parts.append(part[0] + "*" * (len(part) - 1))
    
    return " ".join(masked_parts)


def mask_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively mask PII fields in a dictionary.
    Masks: email, phone, name fields in log output.
    
    Args:
        data: Dictionary potentially containing PII.
        
    Returns:
        New dictionary with PII fields masked.
    """
    if not isinstance(data, dict):
        return data
    
    masked = {}
    for key, value in data.items():
        key_lower = key.lower()
        
        if "email" in key_lower:
            masked[key] = mask_email(value)
        elif "phone" in key_lower:
            masked[key] = mask_phone(value)
        elif key_lower in ("candidate_name", "name") and isinstance(value, str):
            masked[key] = mask_name(value)
        elif key_lower == "candidate_id" and isinstance(value, str):
            # Keep candidate_id for correlation
            masked[key] = value
        elif isinstance(value, dict):
            masked[key] = mask_dict(value)
        elif isinstance(value, list):
            masked[key] = [
                mask_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            masked[key] = value
    
    return masked


def mask_candidate_for_scoring_prompt(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a version of candidate data for scoring prompts where
    PII is replaced with candidate_id to minimize data exposure.
    
    Args:
        candidate: Full candidate profile dict.
        
    Returns:
        Scoring-safe version with minimal PII.
    """
    safe = dict(candidate)
    
    # Replace identifying info with candidate_id reference
    safe["candidate_name"] = safe.get("candidate_id", "unknown")
    safe["email"] = None
    safe["phone"] = None
    
    return safe

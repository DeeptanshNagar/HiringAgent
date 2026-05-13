"""
Input sanitisation module to protect against prompt injection attacks.
Implements regex-based pattern detection and stripping of common injection attempts.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS = [
    r"(?i)(ignore\s+(previous|all|the)\s+(instructions?|prompts?|commands?))",
    r"(?i)(disregard\s+((previous|all|the)\s+)?(instructions?|prompts?|commands?|((previous|all|the)\s+)?prompts?))",
    r"(?i)(disregard\s+all\s+.*\s+(instructions?|prompts?|commands?))",
    r"(?i)(disregard\s+.*)",
    r"(?i)(you\s+(are\s+now|have\s+become)\s+(?:an?\s+)?(differents?\s+)?(ai|assistant|bot|model))",
    r"(?i)(act\s+as\s+(?:if\s+)?you\s+(are|were))",
    r"(?i)^(system\s*[:：])",
    r"(?i)^(user\s*[:：])",
    r"(?i)^(assistant\s*[:：])",
    r"(?i)(###\s*(system|user|assistant|instruction))",
    r"(?i)(<\s*(system|user|assistant|instruction)\s*>)",
    r"(?i)(forget\s+(everything|all|your\s+instructions?))",
    r"(?i)(new\s+(instructions?|prompts?|role)\s*[:：])",
    r"(?i)(you\s+are\s+no\s+longer\s+bound\s+by)",
    r"(?i)(override\s+(previous|all|the)\s+(instructions?|rules?))",
    r"(?i)(bypass\s+(restrictions?|safeguards?|filters?))",
    r"(?i)(from\s+now\s+on\s*,?\s*you\s+will)",
    r"(?i)(score\s+me\s+(10/10|a?\s*perfect?\s*score))",
    r"(?i)(give?\s+me\s+(full\s+marks?|highest\s+score))",
    r"(?i)(always\s+(reply|respond|say)\s+with)",
    r"(?i)(do\s+not\s+(mention|reveal|tell\s+anyone|disclose))",
    r"(?i)(this\s+is\s+a\s+test\s+of\s+your\s+obedience)",
]

COMPILED_PATTERNS = [re.compile(p) for p in INJECTION_PATTERNS]

# Allowlist for common legitimate resume content that might match patterns
ALLOWLIST = [
    r"(?i)(system\s+(administrator|admin|engineer|analyst|architect))",
    r"(?i)(user\s+(experience|interface|research|testing|support))",
    r"(?i)(act\s+as\s+(liaison|intermediary|point\s+of\s+contact))",
]

COMPILED_ALLOWLIST = [re.compile(p) for p in ALLOWLIST]

SECURITY_LOG_FILE = "logs/security.jsonl"


def _log_security_event(
    candidate_id: Optional[str],
    event_type: str,
    stripped_content: Optional[str] = None,
    reason: str = "",
) -> None:
    """Log a security event to the security audit log."""
    import os
    os.makedirs("logs", exist_ok=True)
    
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candidate_id": candidate_id,
        "event_type": event_type,
        "stripped_content": stripped_content[:200] if stripped_content else None,
        "reason": reason,
    }
    try:
        with open(SECURITY_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        logger.error(f"Failed to write security log: {e}")


def sanitise_text(text: str, candidate_id: Optional[str] = None) -> Tuple[str, bool]:
    """
    Sanitise input text by removing known prompt injection patterns.
    
    Args:
        text: Raw input text from resume or JD.
        candidate_id: Optional candidate identifier for logging.
        
    Returns:
        Tuple of (sanitised_text, was_modified).
    """
    if not text:
        return text, False
    
    original = text
    modifications: list[str] = []
    
    for idx, pattern in enumerate(COMPILED_PATTERNS):
        matches = list(pattern.finditer(text))
        for match in reversed(matches):  # Reverse to preserve positions
            matched_text = match.group(0)
            
            # Check allowlist
            allowed = False
            for allow_pattern in COMPILED_ALLOWLIST:
                if allow_pattern.search(matched_text):
                    allowed = True
                    break
            
            if not allowed:
                start, end = match.span()
                text = text[:start] + "[REDACTED]" + text[end:]
                modifications.append(matched_text)
                logger.warning(
                    f"Prompt injection pattern detected for candidate={candidate_id}: "
                    f"stripped '{matched_text[:50]}...'"
                )
    
    was_modified = text != original
    
    if was_modified and modifications:
        # Clean up consecutive [REDACTED] markers
        text = re.sub(r"(\[REDACTED\]\s*)+", "[REDACTED] ", text)
        _log_security_event(
            candidate_id=candidate_id,
            event_type="prompt_injection_stripped",
            stripped_content=" | ".join(modifications),
            reason=f"Detected and removed {len(modifications)} injection pattern(s)",
        )
    
    return text, was_modified


def sanitise_for_system_prompt(text: str) -> str:
    """
    Additional sanitisation specifically for text that will be placed
    in the user turn of a prompt. Prevents escape from user context.
    
    Args:
        text: Raw text to sanitise.
        
    Returns:
        Sanitised text safe for user prompt insertion.
    """
    if not text:
        return text
    
    # Escape any markdown code fences that could break out
    text = re.sub(r"```", "'''", text)
    
    # Remove XML-like tags that could confuse parsers
    text = re.sub(r"<\s*(/?\s*(?:system|user|assistant|instruction))\s*>", r"[\1]", text, flags=re.IGNORECASE)
    
    # Remove null bytes
    text = text.replace("\x00", "")
    
    # Limit extremely long lines (could be used for buffer overflow-style attacks)
    lines = text.split("\n")
    lines = [line[:2000] for line in lines]  # Max 2000 chars per line
    text = "\n".join(lines)
    
    return text


def validate_file_content(content: bytes, expected_mime: str) -> bool:
    """
    Validate file content against expected MIME type using magic bytes.
    
    Args:
        content: Raw file bytes.
        expected_mime: Expected MIME type string.
        
    Returns:
        True if file magic bytes match expected type.
    """
    if not content:
        return False
    
    magic_bytes = {
        "application/pdf": [b"%PDF"],
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [b"PK\x03\x04"],
        "application/json": [b"{"],
        "text/plain": [b""],  # Plain text can start with anything
    }
    
    expected_signatures = magic_bytes.get(expected_mime, [])
    
    for sig in expected_signatures:
        if content.startswith(sig):
            return True
    
    return expected_mime == "text/plain"  # Allow text/plain as fallback

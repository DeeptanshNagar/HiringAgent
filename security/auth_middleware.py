"""
Authentication and authorization middleware for FastAPI endpoints.
Implements API key validation and rate limiting.
"""

from __future__ import annotations

import hmac
import logging
import time
from collections import defaultdict
from functools import wraps
from typing import Any, Callable, Optional

from config import get_settings
from agent.exceptions import AuthenticationError as AgentAuthError, RateLimitError

logger = logging.getLogger(__name__)

# In-memory rate limiter storage: client_ip -> list of timestamps
_rate_limit_store: dict[str, list[float]] = defaultdict(list)

# Load rate limit config from centralized settings
_settings = get_settings()
RATE_LIMIT_MAX_REQUESTS = _settings.rate_limit_max_requests
RATE_LIMIT_WINDOW_SECONDS = _settings.rate_limit_window_seconds

def get_api_key() -> str:
    """
    Load and return the configured API key from centralized settings.

    Returns:
        The API key string.
    """
    return get_settings().agent_api_key


def validate_api_key(provided_key: str) -> bool:
    """
    Validate a provided API key against the configured key.
    
    Args:
        provided_key: The API key from the request header.
        
    Returns:
        True if the key is valid, False otherwise.
    """
    if not provided_key:
        return False
    try:
        expected = get_api_key()
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(
            provided_key.encode("utf-8"),
            expected.encode("utf-8"),
        )
    except Exception:
        logger.error("API key validation failed: no key configured")
        return False


def check_rate_limit(client_ip: str) -> tuple[bool, dict[str, Any]]:
    """
    Check if a client IP has exceeded the rate limit.
    
    Args:
        client_ip: Client IP address string.
        
    Returns:
        Tuple of (is_allowed, rate_limit_info).
    """
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    
    # Clean old entries and count recent ones
    timestamps = _rate_limit_store.get(client_ip, [])
    timestamps = [ts for ts in timestamps if ts > window_start]
    timestamps.append(now)
    _rate_limit_store[client_ip] = timestamps
    
    current_count = len(timestamps)
    is_allowed = current_count <= RATE_LIMIT_MAX_REQUESTS
    
    info = {
        "limit": RATE_LIMIT_MAX_REQUESTS,
        "remaining": max(0, RATE_LIMIT_MAX_REQUESTS - current_count),
        "window": RATE_LIMIT_WINDOW_SECONDS,
        "retry_after": int(RATE_LIMIT_WINDOW_SECONDS - (now - timestamps[0])) if timestamps else 0,
    }
    
    if not is_allowed:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
    
    return is_allowed, info


def rate_limited(client_ip_getter: Callable[[], str]) -> Callable:
    """
    Decorator to apply rate limiting to a function.
    
    Args:
        client_ip_getter: Callable that returns the client IP string.
        
    Returns:
        Decorated function.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ip = client_ip_getter()
            allowed, info = check_rate_limit(ip)
            if not allowed:
                raise RateLimitError(
                    f"Rate limit exceeded. Try again in {info['retry_after']} seconds.",
                    retry_after=info["retry_after"],
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Re-export from exceptions module for backward compatibility
# New code should import from agent.exceptions directly

"""
LLM Client Factory — single source of truth for LLM initialization.

This module eliminates the duplicated _get_llm_client() that was
copy-pasted across jd_parser.py, profile_extractor.py, and scorer.py.
Any model change now requires editing only this one file.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from langchain_core.language_models import BaseChatModel

from config import get_settings

logger = logging.getLogger(__name__)


def get_llm_client(
    temperature: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> BaseChatModel:
    """
    Initialize and return the appropriate LLM client based on available API keys.

    Priority order: Groq → Anthropic → OpenAI.

    Args:
        temperature: Override default temperature (default from settings: 0.1).
        max_retries: Override default max retries (default from settings: 2).

    Returns:
        A LangChain chat model instance.

    Raises:
        RuntimeError: If no LLM API key is configured.
    """
    settings = get_settings()
    temp = temperature if temperature is not None else settings.llm_temperature
    retries = max_retries if max_retries is not None else settings.llm_max_retries

    if settings.groq_api_key:
        from langchain_groq import ChatGroq

        logger.info("Initializing Groq LLM: %s", settings.default_groq_model)
        return ChatGroq(
            model=settings.default_groq_model,
            temperature=temp,
            max_retries=retries,
        )

    if settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic

        logger.info("Initializing Anthropic LLM: %s", settings.default_anthropic_model)
        return ChatAnthropic(
            model=settings.default_anthropic_model,
            temperature=temp,
            max_retries=retries,
        )

    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI

        logger.info("Initializing OpenAI LLM: %s", settings.default_openai_model)
        return ChatOpenAI(
            model=settings.default_openai_model,
            temperature=temp,
            max_retries=retries,
        )

    raise RuntimeError(
        "No LLM API key configured. "
        "Set GROQ_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY in .env"
    )


def get_embedding_model():
    """
    Initialize and return the embedding model for similarity scoring.

    Returns OpenAI embeddings if key available, falls back to local
    HuggingFace model, or None if neither is available.
    """
    settings = get_settings()

    if settings.openai_api_key:
        from langchain_openai import OpenAIEmbeddings

        logger.info("Using OpenAI embeddings: %s", settings.default_embedding_model)
        return OpenAIEmbeddings(model=settings.default_embedding_model)

    # Fallback to local embeddings
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings

        logger.info("Using local HuggingFace embeddings: all-MiniLM-L6-v2")
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    except Exception:
        logger.warning("No embedding model available, skipping embedding scoring")
        return None


def get_model_info() -> dict[str, str]:
    """Return metadata about the active LLM model and framework."""
    settings = get_settings()

    if settings.groq_api_key:
        return {
            "model": settings.default_groq_model,
            "provider": "Groq",
            "framework": "LangChain 0.3.x (Sequential Pipeline)",
        }
    if settings.anthropic_api_key:
        return {
            "model": settings.default_anthropic_model,
            "provider": "Anthropic",
            "framework": "LangChain 0.3.x (Sequential Pipeline)",
        }
    if settings.openai_api_key:
        return {
            "model": settings.default_openai_model,
            "provider": "OpenAI",
            "framework": "LangChain 0.3.x (Sequential Pipeline)",
        }
    return {
        "model": "unknown",
        "provider": "unknown",
        "framework": "LangChain 0.3.x (Sequential Pipeline)",
    }

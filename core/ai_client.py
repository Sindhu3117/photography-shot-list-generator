"""
OpenAI API client for the FRAME shot list generator.

Wraps the raw OpenAI SDK call with:
- Startup validation (fail fast if the API key is missing)
- Typed, user-friendly exceptions for every failure mode
- Structured logging so errors appear in server logs, not just the UI

Callers should catch FrameAIError (or its subclasses) and convert the message
into a Streamlit error widget rather than letting the exception propagate.
"""

import logging
import os

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


# ── Custom exception hierarchy ────────────────────────────────────────────────

class FrameAIError(Exception):
    """Base class for all AI generation errors. Always has a user-safe message."""


class FrameAuthError(FrameAIError):
    """Raised when the API key is missing or rejected by OpenAI."""


class FrameRateLimitError(FrameAIError):
    """Raised when OpenAI's rate limit is hit."""


class FrameConnectionError(FrameAIError):
    """Raised on network-level failures (connection refused, timeout, DNS)."""


# ── Client factory ────────────────────────────────────────────────────────────

def get_client() -> OpenAI:
    """
    Build and return an authenticated OpenAI client.

    Raises FrameAuthError immediately if OPENAI_API_KEY is not set, rather
    than waiting for the first API call to fail with a cryptic error.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise FrameAuthError(
            "OPENAI_API_KEY is not set. "
            "Add it to your .env file and restart the app."
        )
    return OpenAI(api_key=api_key)


# ── Generation function ───────────────────────────────────────────────────────

def generate_shot_list(prompt: str) -> str:
    """
    Send a prompt to GPT-4o-mini and return the text response.

    Args:
        prompt: The fully-built prompt string from core.prompt.build_prompt().

    Returns:
        The model's response as a plain string.

    Raises:
        FrameAuthError:       Invalid or missing API key.
        FrameRateLimitError:  OpenAI rate limit reached.
        FrameConnectionError: Network or timeout failure.
        FrameAIError:         Any other OpenAI error.
    """
    try:
        client = get_client()
        logger.info("Calling OpenAI API — model: gpt-4o-mini, max_tokens: 2000")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.choices[0].message.content or ""
        logger.info(
            "Generation complete. Tokens used: %d (prompt: %d, completion: %d)",
            response.usage.total_tokens,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
        )
        return content

    except AuthenticationError as exc:
        logger.error("OpenAI authentication failed: %s", exc)
        raise FrameAuthError(
            "API key rejected by OpenAI. Please verify your OPENAI_API_KEY."
        ) from exc

    except RateLimitError as exc:
        logger.warning("OpenAI rate limit hit: %s", exc)
        raise FrameRateLimitError(
            "Rate limit reached. Please wait a moment and try again."
        ) from exc

    except APIConnectionError as exc:
        logger.error("Could not connect to OpenAI: %s", exc)
        raise FrameConnectionError(
            "Could not reach OpenAI. Check your internet connection and try again."
        ) from exc

    except APITimeoutError as exc:
        logger.error("OpenAI request timed out: %s", exc)
        raise FrameConnectionError(
            "Request timed out. OpenAI may be under load — please try again."
        ) from exc

    except OpenAIError as exc:
        logger.error("Unexpected OpenAI error: %s", exc)
        raise FrameAIError(
            f"An unexpected error occurred while generating your shot list: {exc}"
        ) from exc

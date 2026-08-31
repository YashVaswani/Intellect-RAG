# engine/token_counter.py
"""
Token counting — tracks input and output token usage per request.
Uses the model's usage metadata when available, falls back to estimation.
"""
import logging

logger = logging.getLogger(__name__)

# Average characters per token (rough estimate for fallback)
CHARS_PER_TOKEN_ESTIMATE = 4


def count_tokens_estimate(text: str) -> int:
    """
    Estimates token count from text length.
    Used as a fallback when the API doesn't return usage metadata.
    """
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN_ESTIMATE)


def extract_usage(response_obj, provider: str) -> dict:
    """
    Extracts token usage metadata from an API response object.
    
    Args:
        response_obj: The raw API response from Gemini or Groq
        provider: "gemini" or "groq"
    
    Returns:
        Dict with input_tokens, output_tokens, total_tokens
    """
    usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }

    try:
        if provider == "gemini":
            # Gemini SDK provides usage_metadata on the response
            if hasattr(response_obj, "usage_metadata"):
                meta = response_obj.usage_metadata
                usage["input_tokens"] = getattr(meta, "prompt_token_count", 0) or 0
                usage["output_tokens"] = getattr(meta, "candidates_token_count", 0) or 0
                usage["total_tokens"] = getattr(meta, "total_token_count", 0) or 0

        elif provider == "groq":
            # Groq uses OpenAI-compatible format
            if hasattr(response_obj, "usage") and response_obj.usage:
                usage["input_tokens"] = response_obj.usage.prompt_tokens or 0
                usage["output_tokens"] = response_obj.usage.completion_tokens or 0
                usage["total_tokens"] = response_obj.usage.total_tokens or 0

    except Exception as e:
        logger.debug(f"Could not extract token usage: {e}")

    # If API didn't provide counts, leave as 0 (caller can estimate)
    if usage["total_tokens"] == 0:
        usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]

    return usage


def format_usage_display(usage: dict) -> str:
    """
    Formats token usage for display in the UI.
    Example: "📊 Tokens: 1,250 in / 340 out (1,590 total)"
    """
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    total = usage.get("total_tokens", 0)
    return f"📊 Tokens: {inp:,} in / {out:,} out ({total:,} total)"

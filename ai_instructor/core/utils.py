"""
Utility helpers -- Groq chat wrapper with robust rate-limit handling.

Free tier limits (llama-3.3-70b-versatile):
  - 6,000 tokens / minute
  - 30 requests / minute

Strategy:
  - Hard 15 s pause BEFORE every call (keeps us under token/min budget)
  - On 429 -> sleep 65 s (full window reset) then retry
  - Max 6 attempts per call
  - Token counter exposed via module-level dict for UI display
"""

import json
import logging
import re
import time

from groq import Groq
from .models import GenerationConfig

logger = logging.getLogger("aid.utils")

# Shared token counter -- app.py can read this for the UI
token_stats = {"prompt": 0, "completion": 0, "calls": 0}

# Seconds to wait before EVERY call -- prevents burst usage
PRE_CALL_DELAY = 15


def groq_chat(client, cfg, prompt, system=""):
    """
    Single-turn Groq call with:
      - 15 s pre-call delay to stay within token-per-minute budget
      - 65 s wait on any 429 / rate-limit error
      - Up to 6 attempts
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    logger.info("groq_chat: sleeping %ds before call ...", PRE_CALL_DELAY)
    time.sleep(PRE_CALL_DELAY)

    for attempt in range(6):
        try:
            resp = client.chat.completions.create(
                model=cfg.groq_model,
                messages=messages,
                max_tokens=cfg.max_tokens,
                temperature=0.3,
            )
            usage = getattr(resp, "usage", None)
            if usage:
                token_stats["prompt"]     += getattr(usage, "prompt_tokens", 0)
                token_stats["completion"] += getattr(usage, "completion_tokens", 0)
            token_stats["calls"] += 1
            return resp.choices[0].message.content

        except Exception as exc:
            exc_lower = str(exc).lower()
            is_rate = any(k in exc_lower for k in [
                "rate_limit", "rate limit", "429",
                "too many requests", "tokens per minute",
                "requests per minute",
            ])
            wait = 65 if is_rate else (2 ** attempt * 5)
            logger.warning(
                "Groq %s (attempt %d/6) -- waiting %ds: %s",
                "rate-limit" if is_rate else "error",
                attempt + 1, wait, exc,
            )
            time.sleep(wait)

    raise RuntimeError(
        "RATE_LIMIT: Groq API failed after 6 attempts. "
        "Free tier is 6,000 tokens/min. "
        "Wait 2 minutes and try again, shorten your source text, "
        "or upgrade your Groq plan at console.groq.com."
    )


def reset_token_stats():
    token_stats["prompt"] = 0
    token_stats["completion"] = 0
    token_stats["calls"] = 0


def extract_json(text):
    """Best-effort JSON extraction -- strips markdown fences."""
    cleaned = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    logger.warning("JSON extraction failed -- returning raw.")
    return {"raw": text}

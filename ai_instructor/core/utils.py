"""
Utility helpers — Groq chat wrapper, JSON extractor.

Rate-limit strategy (free tier = 6 000 tokens/min):
  - Detect 429 / rate_limit errors explicitly
  - Wait 60 s on first rate-limit hit (resets the 1-min window)
  - Subsequent hits wait 90 s, 120 s
  - Non-rate-limit errors use short back-off (5 s, 10 s, 20 s)
  - Always pause 3 s between successful calls (inter-call throttle)
"""

import json
import logging
import re
import time
from typing import Optional

from groq import Groq

from .models import GenerationConfig

logger = logging.getLogger("aid.utils")

# Pause between every successful API call to stay within token-per-minute limit
INTER_CALL_DELAY = 3   # seconds


def groq_chat(
    client: Groq,
    cfg: GenerationConfig,
    prompt: str,
    system: str = "",
) -> str:
    """
    Single-turn Groq chat with smart rate-limit handling.

    Distinguishes between:
      - 429 / rate_limit errors  -> long wait (60-120 s)
      - Other errors             -> short exponential back-off (5-20 s)
    Always sleeps INTER_CALL_DELAY seconds after a successful call.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    rate_limit_hits = 0
    max_attempts    = 5

    for attempt in range(max_attempts):
        try:
            resp = client.chat.completions.create(
                model       = cfg.groq_model,
                messages    = messages,
                max_tokens  = cfg.max_tokens,
                temperature = 0.3,
            )
            text = resp.choices[0].message.content
            # Throttle so the next call doesn't immediately hit the limit
            time.sleep(INTER_CALL_DELAY)
            return text

        except Exception as exc:
            exc_str = str(exc).lower()
            is_rate_limit = (
                "rate_limit" in exc_str
                or "rate limit" in exc_str
                or "429" in exc_str
                or "too many requests" in exc_str
                or "tokens per minute" in exc_str
                or "requests per minute" in exc_str
            )

            if is_rate_limit:
                rate_limit_hits += 1
                wait = 60 + (rate_limit_hits - 1) * 30   # 60 s, 90 s, 120 s
                logger.warning(
                    "Groq rate limit hit #%d (attempt %d/%d) -- waiting %d s ...",
                    rate_limit_hits, attempt + 1, max_attempts, wait
                )
                time.sleep(wait)
            else:
                wait = 2 ** attempt * 5   # 5 s, 10 s, 20 s, 40 s
                logger.warning(
                    "Groq error (attempt %d/%d): %s -- retrying in %d s",
                    attempt + 1, max_attempts, exc, wait
                )
                time.sleep(wait)

    raise RuntimeError(
        "Groq API failed after multiple attempts. "
        "This is usually a rate-limit issue on the free tier. "
        "Wait 1-2 minutes and try again, or upgrade your Groq plan."
    )


def extract_json(text: str) -> dict:
    """Best-effort JSON extraction; strips markdown fences."""
    cleaned = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    logger.warning("JSON extraction failed -- wrapping raw text.")
    return {"raw": text}

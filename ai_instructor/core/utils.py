"""
Utility helpers — Groq chat wrapper, JSON extractor.
"""

import json
import logging
import re
import time
from typing import Optional

from groq import Groq

from .models import GenerationConfig

logger = logging.getLogger("aid.utils")


def groq_chat(
    client: Groq,
    cfg: GenerationConfig,
    prompt: str,
    system: str = "",
) -> str:
    """Single-turn Groq chat with exponential back-off on rate-limit errors."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model       = cfg.groq_model,
                messages    = messages,
                max_tokens  = cfg.max_tokens,
                temperature = 0.3,
            )
            return resp.choices[0].message.content
        except Exception as exc:
            wait = 2 ** attempt * 5
            logger.warning("Groq error (attempt %d): %s — retrying in %ds",
                           attempt + 1, exc, wait)
            time.sleep(wait)

    raise RuntimeError("Groq API failed after 4 attempts.")


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
    logger.warning("JSON extraction failed — wrapping raw text.")
    return {"raw": text}

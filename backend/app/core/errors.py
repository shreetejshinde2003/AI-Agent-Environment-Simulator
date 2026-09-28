"""Sanitize provider errors before persisting or displaying them."""
import re
from app.core.config import settings


def safe_error(exc):
    text = str(exc) or type(exc).__name__
    for key in (settings.GROQ_API_KEY, settings.OPENAI_API_KEY, settings.ANTHROPIC_API_KEY):
        if key:
            text = text.replace(key, "[REDACTED]")
    text = re.sub(r"(?i)(bearer\s+)[^\s,;]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?:gsk_|sk-)[\w-]+", "[REDACTED]", text)
    return text[:1000]

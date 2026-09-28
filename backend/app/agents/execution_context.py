"""Per-async-call metrics sink; never infer tokens from shared counters."""
from contextvars import ContextVar

current_execution = ContextVar("current_execution", default=None)

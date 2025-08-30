from __future__ import annotations

import time
from typing import Any, Optional

from langchain.callbacks.base import BaseCallbackHandler
from app.core.infra.metrics import observe_llm_usage


class PrometheusLLMCallback(BaseCallbackHandler):
    """Minimal callback to record token usage and latency per operation."""

    def __init__(self, op: str) -> None:
        self.op = op
        self._t0: Optional[float] = None

    def on_llm_start(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        self._t0 = time.monotonic()

    def on_llm_end(self, response, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        t1 = time.monotonic()
        latency = t1 - (self._t0 or t1)
        usage = {}
        try:
            # langchain standard field for OpenAI provider
            usage = (response.llm_output or {}).get("token_usage", {})  # type: ignore[attr-defined]
        except Exception:
            usage = {}
        prompt = int(usage.get("prompt_tokens", 0) or 0)
        completion = int(usage.get("completion_tokens", 0) or 0)
        total = int(usage.get("total_tokens", prompt + completion) or 0)
        observe_llm_usage(self.op, prompt, completion, total, latency)

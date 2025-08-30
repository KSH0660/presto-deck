from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Metrics definitions
PRESENTATIONS_STARTED = Counter(
    "presto_presentations_started_total", "Presentations started"
)
PRESENTATIONS_COMPLETED = Counter(
    "presto_presentations_completed_total", "Presentations completed"
)
PIPELINE_ERRORS = Counter("presto_pipeline_errors_total", "Pipeline errors")
SLIDES_RENDERED = Counter("presto_slides_rendered_total", "Slides rendered")
STEP_DURATION_SECONDS = Histogram(
    "presto_step_duration_seconds", "Pipeline step duration seconds", ["step"]
)

# LLM-level metrics
LLM_TOKENS_TOTAL = Counter(
    "presto_llm_tokens_total", "Total tokens used by LLM calls", ["op"]
)
LLM_TOKENS_PROMPT = Counter(
    "presto_llm_prompt_tokens_total", "Prompt tokens used", ["op"]
)
LLM_TOKENS_COMPLETION = Counter(
    "presto_llm_completion_tokens_total", "Completion tokens used", ["op"]
)
LLM_LATENCY_SECONDS = Histogram(
    "presto_llm_latency_seconds", "LLM call latency seconds", ["op"]
)


metrics_router = APIRouter()


@metrics_router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def observe_step(step: str, seconds: float) -> None:
    """단계 실행 시간을 기록합니다."""
    STEP_DURATION_SECONDS.labels(step=step).observe(seconds)


def observe_llm_usage(
    op: str,
    prompt_toks: int | None,
    completion_toks: int | None,
    total_toks: int | None,
    latency_sec: float | None,
) -> None:
    op = op or "unknown"
    if prompt_toks:
        LLM_TOKENS_PROMPT.labels(op=op).inc(prompt_toks)
    if completion_toks:
        LLM_TOKENS_COMPLETION.labels(op=op).inc(completion_toks)
    if total_toks:
        LLM_TOKENS_TOTAL.labels(op=op).inc(total_toks)
    if latency_sec is not None:
        LLM_LATENCY_SECONDS.labels(op=op).observe(max(0.0, float(latency_sec)))

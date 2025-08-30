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


metrics_router = APIRouter()


@metrics_router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def observe_step(step: str, seconds: float) -> None:
    """단계 실행 시간을 기록합니다."""
    STEP_DURATION_SECONDS.labels(step=step).observe(seconds)

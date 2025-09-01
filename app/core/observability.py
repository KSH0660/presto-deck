from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status_code"]
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

ACTIVE_CONNECTIONS = Gauge(
    "websocket_connections_active", "Number of active WebSocket connections"
)

DECK_GENERATION_DURATION = Histogram(
    "deck_generation_duration_seconds", "Deck generation duration in seconds"
)

DECK_GENERATION_COUNT = Counter(
    "deck_generation_total", "Total number of deck generations", ["status"]
)

LLM_TOKEN_USAGE = Counter(
    "llm_tokens_used_total",
    "Total LLM tokens used",
    ["model", "type"],  # type: prompt_tokens, completion_tokens
)

LLM_REQUEST_DURATION = Histogram(
    "llm_request_duration_seconds", "LLM request duration in seconds", ["model"]
)

REDIS_OPERATIONS = Counter(
    "redis_operations_total", "Total Redis operations", ["operation", "status"]
)

DATABASE_OPERATIONS = Counter(
    "database_operations_total",
    "Total database operations",
    ["operation", "table", "status", "exception_type"],
)


def setup_observability() -> None:
    """Setup OpenTelemetry and Prometheus metrics."""

    # Configure OpenTelemetry resource
    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.version,
            "service.environment": settings.environment,
        }
    )

    # Setup tracer provider
    trace.set_tracer_provider(TracerProvider(resource=resource))
    # tracer = trace.get_tracer(__name__)

    # Setup OTLP exporter if endpoint is configured
    if settings.otel_exporter_otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            insecure=not settings.is_production(),
        )
        span_processor = BatchSpanProcessor(otlp_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)

    # Auto-instrument libraries
    SQLAlchemyInstrumentor().instrument()
    RedisInstrumentor().instrument()

    # Start Prometheus metrics server if enabled
    if settings.prometheus_metrics_enabled and not settings.is_testing():
        try:
            start_http_server(settings.prometheus_metrics_port)
            logger.info(
                "Prometheus metrics server started",
                port=settings.prometheus_metrics_port,
            )
        except Exception as e:
            logger.error("Failed to start Prometheus metrics server", error=str(e))


def get_tracer() -> trace.Tracer:
    """Get OpenTelemetry tracer."""
    return trace.get_tracer(__name__)


@asynccontextmanager
async def trace_async_operation(
    operation_name: str, **attributes: Any
) -> AsyncGenerator[trace.Span, None]:
    """Context manager for tracing async operations."""
    tracer = get_tracer()
    with tracer.start_as_current_span(operation_name) as span:
        for key, value in attributes.items():
            span.set_attribute(key, str(value))
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise


class MetricsCollector:
    """Helper class for collecting application metrics."""

    @staticmethod
    def record_http_request(
        method: str, endpoint: str, status_code: int, duration: float
    ) -> None:
        """Record HTTP request metrics."""
        REQUEST_COUNT.labels(
            method=method, endpoint=endpoint, status_code=status_code
        ).inc()
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

    @staticmethod
    def record_websocket_connection(delta: int) -> None:
        """Record WebSocket connection change."""
        ACTIVE_CONNECTIONS.inc(delta)

    @staticmethod
    def record_deck_generation(status: str, duration: float) -> None:
        """Record deck generation metrics."""
        DECK_GENERATION_COUNT.labels(status=status).inc()
        DECK_GENERATION_DURATION.observe(duration)

    @staticmethod
    def record_llm_usage(
        model: str, prompt_tokens: int, completion_tokens: int, duration: float
    ) -> None:
        """Record LLM usage metrics."""
        LLM_TOKEN_USAGE.labels(model=model, type="prompt_tokens").inc(prompt_tokens)
        LLM_TOKEN_USAGE.labels(model=model, type="completion_tokens").inc(
            completion_tokens
        )
        LLM_REQUEST_DURATION.labels(model=model).observe(duration)

    @staticmethod
    def record_redis_operation(operation: str, status: str) -> None:
        """Record Redis operation metrics."""
        REDIS_OPERATIONS.labels(operation=operation, status=status).inc()

    @staticmethod
    def record_database_operation(
        operation: str, table: str, status: str, exception_type: str | None = None
    ) -> None:
        """Record database operation metrics."""
        DATABASE_OPERATIONS.labels(
            operation=operation,
            table=table,
            status=status,
            exception_type=exception_type or "none",
        ).inc()


# Global metrics collector instance
metrics = MetricsCollector()

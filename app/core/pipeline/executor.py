import asyncio
import time
from typing import AsyncGenerator, Optional

from app.core.infra.config import settings
from app.models.context import PipelineContext, GenerateOptions
from app.models.schema import GenerateRequest
from app.models.types import QualityTier

from .emitter import EventEmitter, sse_event
from app.core.infra.metrics import (
    PRESENTATIONS_STARTED,
    PRESENTATIONS_COMPLETED,
    PIPELINE_ERRORS,
    observe_step,
)
from .steps import PlanDeckStep, SelectLayoutsStep, RenderSlidesStep


async def stream_presentation(
    req: GenerateRequest, cancel_event: Optional[asyncio.Event] = None
) -> AsyncGenerator[str, None]:
    """파이프라인 컨텍스트/스텝으로 Plan→Select→Render 를 스트리밍합니다."""
    queue: asyncio.Queue[str] = asyncio.Queue()
    emitter = EventEmitter(queue)

    # 품질 티어 → 모델/동시성 파생
    if req.config.quality == QualityTier.PREMIUM:
        model = settings.PREMIUM_MODEL
        default_cc = settings.PREMIUM_MAX_CONCURRENCY
    elif req.config.quality == QualityTier.DRAFT:
        model = settings.DRAFT_MODEL
        default_cc = settings.DRAFT_MAX_CONCURRENCY
    else:
        model = settings.DEFAULT_MODEL
        default_cc = settings.DEFAULT_MAX_CONCURRENCY

    max_concurrency = min(
        settings.MAX_CONCURRENCY_LIMIT, max(1, req.config.concurrency or default_cc)
    )
    options = GenerateOptions(
        model=model,
        max_concurrency=max_concurrency,
        ordered=bool(req.config.ordered),
        heartbeat_interval_sec=max(5, int(settings.HEARTBEAT_INTERVAL_SEC)),
    )

    ctx = PipelineContext(req=req, options=options)

    # 시작 이벤트 및 메트릭 증가
    PRESENTATIONS_STARTED.inc()
    await emitter.emit("started", {"model": options.model, "ordered": options.ordered})

    # 파이프라인 스텝 실행 태스크
    async def run_pipeline():
        nonlocal ctx
        try:
            import time as _t

            _t0 = _t.monotonic()
            ctx = await PlanDeckStep().run(ctx, emitter)
            observe_step("plan", _t.monotonic() - _t0)
            if cancel_event and cancel_event.is_set():
                ctx = ctx.model_copy(update={"cancelled": True})
                return
            _t1 = _t.monotonic()
            ctx = await SelectLayoutsStep().run(ctx, emitter)
            observe_step("select", _t.monotonic() - _t1)
            if cancel_event and cancel_event.is_set():
                ctx = ctx.model_copy(update={"cancelled": True})
                return
            _t2 = _t.monotonic()
            ctx = await RenderSlidesStep().run(ctx, emitter)
            observe_step("render", _t.monotonic() - _t2)
        except Exception:
            PIPELINE_ERRORS.inc()
            await emitter.emit("error", {"message": "pipeline_failed"})

    pipeline_task = asyncio.create_task(run_pipeline())

    # 이벤트 큐에서 읽어 클라이언트로 전송
    heartbeat_interval = options.heartbeat_interval_sec
    last_emit = time.time()
    while True:
        try:
            payload = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
            last_emit = time.time()
            yield payload
        except asyncio.TimeoutError:
            if not pipeline_task.done():
                now = time.time()
                if now - last_emit >= heartbeat_interval:
                    yield await sse_event("heartbeat", {"ts": int(now)})
            else:
                break
    # 파이프라인 종료시 성공 메트릭
    PRESENTATIONS_COMPLETED.inc()

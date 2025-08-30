import asyncio
import logging
import time
from typing import Dict

from app.core.infra import state
from app.core.selection import layout_selector
from app.core.planning import planner
from app.core.rendering import slide_worker
from app.core.templates.template_manager import get_template_html_catalog
from app.models.context import PipelineContext
from app.models.schema import SlideHTML
from .emitter import EventEmitter
from app.core.infra.metrics import SLIDES_RENDERED

logger = logging.getLogger(__name__)


class PlanDeckStep:
    """사용자 요청을 바탕으로 1차 덱 플랜을 생성합니다."""

    async def run(self, ctx: PipelineContext, emit: EventEmitter) -> PipelineContext:
        logger.info("Planning deck structure...")
        plan = await planner.plan_deck(ctx.req.user_prompt, ctx.options.model)
        ctx = ctx.model_copy(update={"initial_deck_plan": plan})
        total = len(plan.slides)
        await emit.emit(
            "progress", {"completed": 0, "total": total, "stage": "planning"}
        )
        return ctx


class SelectLayoutsStep:
    """각 슬라이드에 대한 레이아웃 후보를 선택합니다."""

    async def run(self, ctx: PipelineContext, emit: EventEmitter) -> PipelineContext:
        assert ctx.initial_deck_plan is not None, "Initial deck plan required"
        logger.info("Selecting layouts for slides...")
        deck_plan = await layout_selector.run_layout_selection_for_deck(
            initial_deck_plan=ctx.initial_deck_plan,
            user_request=ctx.req.user_prompt,
            model=ctx.options.model,
        )
        await emit.emit("deck_plan", deck_plan.model_dump())
        return ctx.model_copy(update={"deck_plan": deck_plan})


class RenderSlidesStep:
    """선택된 레이아웃으로 슬라이드 HTML을 렌더링하고 스트리밍합니다."""

    async def run(self, ctx: PipelineContext, emit: EventEmitter) -> PipelineContext:
        assert ctx.deck_plan is not None, "Deck plan required"

        template_catalog = get_template_html_catalog()
        semaphore = asyncio.Semaphore(ctx.options.max_concurrency)
        queue: asyncio.Queue = asyncio.Queue()
        heartbeat_interval = max(5, int(ctx.options.heartbeat_interval_sec))
        start_time = asyncio.get_event_loop().time()

        total_slides = len(ctx.deck_plan.slides)
        completed_count = 0
        next_index_to_yield = 0
        buffer: Dict[int, tuple] = {}

        async def run_one(idx: int, slide_spec):
            async with semaphore:
                try:
                    if ctx.cancelled:
                        return
                    logger.debug(
                        "Processing slide %d: %s", slide_spec.slide_id, slide_spec.title
                    )
                    result: SlideHTML = await slide_worker.process_slide(
                        slide_spec=slide_spec,
                        deck_plan=ctx.deck_plan,  # type: ignore[arg-type]
                        req=ctx.req,
                        template_catalog=template_catalog,
                        model=ctx.options.model,
                    )
                    logger.debug("Finished processing slide %d.", slide_spec.slide_id)
                    await queue.put((idx, slide_spec, result))
                except Exception as e:
                    logger.debug(
                        "Error processing slide %d: %s",
                        slide_spec.slide_id,
                        e,
                        exc_info=True,
                    )
                    await queue.put((idx, slide_spec, e))

        tasks = [
            asyncio.create_task(run_one(idx, slide_spec))
            for idx, slide_spec in enumerate(ctx.deck_plan.slides)
        ]

        last_heartbeat = time.time()
        while completed_count < total_slides:
            if ctx.cancelled:
                break
            try:
                idx, spec, payload = await asyncio.wait_for(
                    queue.get(), timeout=heartbeat_interval
                )
            except asyncio.TimeoutError:
                now = time.time()
                if now - last_heartbeat >= heartbeat_interval:
                    last_heartbeat = now
                    await emit.emit("heartbeat", {"ts": int(now)})
                continue

            if isinstance(payload, Exception):
                logger.warning(
                    "Skipping slide %d due to error.",
                    getattr(spec, "slide_id", "unknown"),
                )
                await emit.emit(
                    "error",
                    {
                        "index": idx,
                        "slide_id": getattr(spec, "slide_id", None),
                        "message": str(payload),
                    },
                )
            else:
                if ctx.options.ordered:
                    buffer[idx] = (spec, payload)
                    while next_index_to_yield in buffer:
                        s, res = buffer.pop(next_index_to_yield)
                        logger.info("Yielding ordered slide %d.", next_index_to_yield)
                        await emit.emit(
                            "slide_rendered",
                            {
                                "index": next_index_to_yield,
                                "slide_id": res.slide_id,
                                "title": s.title,
                                "template_name": res.template_name,
                                "html": res.html,
                            },
                        )
                        SLIDES_RENDERED.inc()
                        state.slides_db.append(
                            {
                                "id": s.slide_id,
                                "title": s.title,
                                "html_content": res.html,
                                "version": 1,
                                "status": "complete",
                            }
                        )
                        next_index_to_yield += 1
                else:
                    logger.info("Yielding unordered slide %d.", idx)
                    await emit.emit(
                        "slide_rendered",
                        {
                            "index": idx,
                            "slide_id": payload.slide_id,
                            "title": spec.title,
                            "template_name": payload.template_name,
                            "html": payload.html,
                        },
                    )
                    SLIDES_RENDERED.inc()
                    state.slides_db.append(
                        {
                            "id": spec.slide_id,
                            "title": spec.title,
                            "html_content": payload.html,
                            "version": 1,
                            "status": "complete",
                        }
                    )

            completed_count += 1
            await emit.emit(
                "progress",
                {
                    "completed": completed_count,
                    "total": total_slides,
                    "stage": "rendering",
                },
            )

        for t in tasks:
            t.cancel() if ctx.cancelled else None
        await asyncio.gather(*tasks, return_exceptions=True)

        try:
            if state.slides_db:
                max_id = max(s.get("id", 0) for s in state.slides_db)
                state.reset_slide_ids(max_id + 1)
        except Exception:
            pass

        duration = int((asyncio.get_event_loop().time() - start_time) * 1000)
        await emit.emit("completed", {"total": total_slides, "duration_ms": duration})
        return ctx

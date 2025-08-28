# app/core/streaming.py
import asyncio
import json
import logging  # Added
from typing import AsyncGenerator, Dict

from app.core import layout_selector, planner, slide_worker
from app.core.config import settings
from app.core.template_manager import get_template_html_catalog
from app.models.schema import GenerateRequest, SlideHTML
from app.models.types import QualityTier

logger = logging.getLogger(__name__)  # Added


async def sse_event(event: str, data: dict) -> str:
    """Helper to format a server-sent event."""
    payload = (
        f"event: {event}\n" + "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"
    )
    return payload


async def stream_presentation(
    req: GenerateRequest,
) -> AsyncGenerator[str, None]:
    """
    Generates a presentation by planning, selecting layouts, and rendering slides,
    streaming each step's result as a server-sent event.
    """
    try:
        # 1. Configure model and concurrency settings based on quality tier
        if req.config.quality == QualityTier.PREMIUM:
            model = settings.PREMIUM_MODEL
            default_cc = settings.PREMIUM_MAX_CONCURRENCY
        elif req.config.quality == QualityTier.DRAFT:
            model = settings.DRAFT_MODEL
            default_cc = settings.DRAFT_MAX_CONCURRENCY
        else:  # DEFAULT
            model = settings.DEFAULT_MODEL
            default_cc = settings.DEFAULT_MAX_CONCURRENCY

        max_concurrency = max(1, req.config.concurrency or default_cc)
        ordered = bool(req.config.ordered)
        total_slides = 0

        start_time = asyncio.get_event_loop().time()

        logger.info(
            "Starting presentation streaming for user prompt: %s", req.user_prompt
        )
        # 2. Initial event: Started
        yield await sse_event("started", {"model": model, "ordered": ordered})

        # 3. Plan the deck structure
        logger.info("Planning deck structure...")
        initial_deck_plan = await planner.plan_deck(req.user_prompt, model)
        total_slides = len(initial_deck_plan.slides)
        logger.info("Deck plan created with %d slides.", total_slides)
        yield await sse_event(
            "progress", {"completed": 0, "total": total_slides, "stage": "planning"}
        )

        # 4. Select layouts for each slide
        logger.info("Selecting layouts for slides...")
        deck_plan = await layout_selector.run_layout_selection_for_deck(
            initial_deck_plan=initial_deck_plan, user_request=req.user_prompt, model=model
        )
        logger.info("Layout selection complete.")
        yield await sse_event("deck_plan", deck_plan.model_dump())

        # 5. Set up concurrent slide processing
        template_catalog = get_template_html_catalog()
        semaphore = asyncio.Semaphore(max_concurrency)
        queue: asyncio.Queue = asyncio.Queue()

        async def run_one(idx: int, slide_spec):
            async with semaphore:
                try:
                    logger.debug(
                        "Processing slide %d: %s", slide_spec.slide_id, slide_spec.title
                    )
                    result: SlideHTML = await slide_worker.process_slide(
                        slide_spec=slide_spec,
                        deck_plan=deck_plan,
                        req=req,
                        candidate_template_names=slide_spec.layout_candidates or [],
                        template_catalog=template_catalog,
                        model=model,
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
            for idx, slide_spec in enumerate(deck_plan.slides)
        ]

        # 6. Process results as they complete and stream them
        completed_count = 0
        next_index_to_yield = 0
        buffer: Dict[int, tuple] = {}

        while completed_count < total_slides:
            idx, spec, payload = await queue.get()

            if isinstance(payload, Exception):
                logger.warning(
                    "Skipping slide %d due to error.",
                    getattr(spec, "slide_id", "unknown"),
                )
                yield await sse_event(
                    "error",
                    {
                        "index": idx,
                        "slide_id": getattr(spec, "slide_id", None),
                        "message": str(payload),
                    },
                )
            else:
                # If ordered delivery is required, buffer results
                if ordered:
                    buffer[idx] = (spec, payload)
                    while next_index_to_yield in buffer:
                        s, res = buffer.pop(next_index_to_yield)
                        logger.info("Yielding ordered slide %d.", next_index_to_yield)
                        yield await sse_event(
                            "slide_rendered",
                            {
                                "index": next_index_to_yield,
                                "slide_id": res.slide_id,
                                "title": s.title,
                                "template_name": res.template_name,
                                "html": res.html,
                            },
                        )
                        next_index_to_yield += 1
                else:
                    # Yield immediately if order doesn't matter
                    logger.info("Yielding unordered slide %d.", idx)
                    yield await sse_event(
                        "slide_rendered",
                        {
                            "index": idx,
                            "slide_id": payload.slide_id,
                            "title": spec.title,
                            "template_name": payload.template_name,
                            "html": payload.html,
                        },
                    )

            completed_count += 1
            logger.debug(
                "Progress: %d/%d slides completed.", completed_count, total_slides
            )
            yield await sse_event(
                "progress",
                {
                    "completed": completed_count,
                    "total": total_slides,
                    "stage": "rendering",
                },
            )

        # 7. Final event: Completed
        await asyncio.gather(*tasks, return_exceptions=True)
        duration = int((asyncio.get_event_loop().time() - start_time) * 1000)
        logger.info("Presentation streaming completed in %d ms.", duration)
        yield await sse_event(
            "completed", {"total": total_slides, "duration_ms": duration}
        )

    except Exception as e:
        # In case of a catastrophic failure, send an error event and log it
        logger.exception(
            "A critical error occurred during streaming presentation."
        )  # Changed
        err_payload = {"message": f"A critical error occurred: {e}"}
        yield await sse_event("error", err_payload)
        # Re-raise to let the framework handle it if necessary
        # raise e

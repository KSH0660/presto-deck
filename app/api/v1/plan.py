from fastapi import APIRouter
from app.models.schema import GenerateRequest, DeckPlan
from app.core.planning import planner
from app.core.selection import layout_selector
from app.core.infra.config import settings
from app.models.types import QualityTier

router = APIRouter()


def _resolve_model(q: QualityTier) -> str:
    if q == QualityTier.PREMIUM:
        return settings.PREMIUM_MODEL
    if q == QualityTier.DRAFT:
        return settings.DRAFT_MODEL
    return settings.DEFAULT_MODEL


@router.post("/plan", response_model=DeckPlan)
async def plan(req: GenerateRequest) -> DeckPlan:
    """Generate a DeckPlan (topic/audience/theme/colors + SlideSpec list)."""
    model = _resolve_model(req.config.quality)
    initial = await planner.plan_deck(req.user_prompt, model=model)
    deck = await layout_selector.run_layout_selection_for_deck(
        initial_deck_plan=initial, user_request=req.user_prompt, model=model
    )
    return deck

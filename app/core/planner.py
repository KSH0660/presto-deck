# app/core/planner.py

from langchain.schema.runnable import Runnable
from app.core.llm import make_llm
from app.models.schema import InitialDeckPlan
from app.core.prompts import PLANNER_PROMPT
import logging

logger = logging.getLogger(__name__)


def build_planner_chain(llm) -> Runnable:
    """사용자 요청 -> InitialDeckPlan(Pydantic)"""
    return PLANNER_PROMPT | llm.with_structured_output(InitialDeckPlan)


async def plan_deck(user_request: str, model: str) -> InitialDeckPlan:
    """덱 전체 구조를 기획합니다."""
    logger.info("Starting deck planning for request: %s", user_request)
    llm = make_llm(model=model)
    planner_chain = build_planner_chain(llm)
    initial_deck_plan: InitialDeckPlan = await planner_chain.ainvoke(
        {"user_request": user_request}
    )
    logger.info(
        "Deck planning completed. Generated %d slides.", len(initial_deck_plan.slides)
    )
    logger.info(
        "Planned style -> theme: %s | colors: %s",
        getattr(initial_deck_plan, "theme", None) or "Not specified",
        getattr(initial_deck_plan, "color_preference", None) or "Not specified",
    )
    return initial_deck_plan

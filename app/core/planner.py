# app/core/planner.py

from langchain.schema.runnable import Runnable
from app.core.llm import make_llm
from app.models.schema import DeckPlan
from app.core.prompts import PLANNER_SYSTEM, PLANNER_PROMPT
import logging  # Added

logger = logging.getLogger(__name__)  # Added


def build_planner_chain(llm) -> Runnable:
    """사용자 요청 -> DeckPlan(Pydantic)"""
    return PLANNER_PROMPT | llm.with_structured_output(DeckPlan)


async def plan_deck(user_request: str, model: str) -> DeckPlan:
    """덱 전체 구조를 기획합니다."""
    logger.info("Starting deck planning for request: %s", user_request)  # Added
    llm = make_llm(model=model)
    planner_chain = build_planner_chain(llm)
    deck_plan: DeckPlan = await planner_chain.ainvoke(
        {"system": PLANNER_SYSTEM, "user_request": user_request}
    )
    logger.info(
        "Deck planning completed. Generated %d slides.", len(deck_plan.slides)
    )  # Added
    return deck_plan

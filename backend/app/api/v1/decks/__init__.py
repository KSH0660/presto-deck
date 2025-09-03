"""
Deck operations router.
"""

from fastapi import APIRouter
from .creation import router as creation_router
from .status import router as status_router
from .management import router as management_router
from .events import router as events_router
from ..slides.list import router as slides_list_router
from ..slides.operations import router as slides_operations_router
from ..slides.reordering import router as slides_reordering_router

router = APIRouter(prefix="/decks", tags=["decks"])

router.include_router(creation_router)
router.include_router(status_router)
router.include_router(management_router)
router.include_router(events_router)

# Include slides routers under decks
router.include_router(slides_list_router, tags=["slides"])
router.include_router(slides_operations_router, tags=["slides"])
router.include_router(slides_reordering_router, tags=["slides"])

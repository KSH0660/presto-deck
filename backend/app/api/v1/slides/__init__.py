"""
Slide operations router.
"""

from fastapi import APIRouter
from .list import router as list_router
from .operations import router as operations_router
from .reordering import router as reordering_router

router = APIRouter()

router.include_router(list_router)
router.include_router(operations_router)
router.include_router(reordering_router)

"""API v1 routers"""

from fastapi import APIRouter
from .decks import router as decks_router
from .websocket import router as websocket_router

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(decks_router)
v1_router.include_router(websocket_router)

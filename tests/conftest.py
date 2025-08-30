# tests/conftest.py

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.infra import state


@pytest.fixture(scope="module")
async def client():
    """테스트용 비동기 HTTP 클라이언트"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture(autouse=True)
def reset_state():
    """각 테스트 전후로 인메모리 슬라이드 상태를 초기화합니다."""
    # before
    state.slides_db.clear()
    state.reset_slide_ids(1)
    yield
    # after
    state.slides_db.clear()
    state.reset_slide_ids(1)

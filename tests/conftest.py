# tests/conftest.py

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture(scope="module")
async def client():
    """테스트용 비동기 HTTP 클라이언트"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

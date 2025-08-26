# tests/api/test_system_api.py

import pytest


pytestmark = pytest.mark.asyncio


async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_readyz(client):
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert isinstance(data["templates"], int)
    assert "env" in data


async def test_meta_and_templates(client):
    meta = await client.get("/api/v1/meta")
    assert meta.status_code == 200
    m = meta.json()
    assert m["service"] == "presto-api"
    assert "quality_tiers" in m

    templates = await client.get("/api/v1/templates")
    assert templates.status_code == 200
    t = templates.json()
    assert isinstance(t["templates"], list)

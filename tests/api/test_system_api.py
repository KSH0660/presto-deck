# tests/api/test_system_api.py

import pytest


pytestmark = pytest.mark.asyncio


async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"status": "ok"}


async def test_readyz(client):
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert isinstance(data["templates"], int)
    assert "env" in data and isinstance(data["env"].get("OPENAI_CONFIGURED"), bool)


async def test_meta_and_templates(client):
    meta = await client.get("/api/v1/meta")
    assert meta.status_code == 200
    m = meta.json()
    assert m["service"] == "presto-api"
    assert "quality_tiers" in m
    qt = m["quality_tiers"]
    for tier in ("draft", "default", "premium"):
        assert tier in qt
        assert "max_concurrency" in qt[tier]
        # model can be None, accept string or None
        assert (qt[tier]["model"] is None) or isinstance(qt[tier]["model"], str)

    templates = await client.get("/api/v1/templates")
    assert templates.status_code == 200
    t = templates.json()
    assert isinstance(t["templates"], list)
    assert all(isinstance(x, str) for x in t["templates"])

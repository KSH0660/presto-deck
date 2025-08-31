import pytest
from unittest.mock import patch, AsyncMock

from app.core.storage.deck_store import InMemoryDeckStore
from app.models.schema import DeckPlan


pytestmark = pytest.mark.asyncio


async def _seed_deck_with_slide(store: InMemoryDeckStore):
    deck_id = await store.create_deck(DeckPlan(topic="T", audience="A", slides=[]))
    await store.add_or_update_slide(
        deck_id,
        {
            "id": 1,
            "title": "S1",
            "html_content": "<p>old</p>",
            "version": 1,
            "status": "complete",
        },
    )
    return deck_id


async def test_deck_ui_edit_review_accept(client):
    # Force in-memory deck store for this test
    mem_store = InMemoryDeckStore()
    with patch("app.api.v1.ui.get_deck_store", return_value=mem_store):
        deck_id = await _seed_deck_with_slide(mem_store)
        with patch(
            "app.api.v1.ui.edit_slide_content",
            new=AsyncMock(return_value="<p>new</p>"),
        ):
            # Request edit -> should stash pending_html and keep current html_content
            resp = await client.post(
                f"/api/v1/ui/decks/{deck_id}/slides/1/edit",
                data={"edit_prompt": "make it new"},
            )
            assert resp.status_code == 200

        # Apply accept
        resp2 = await client.post(
            f"/api/v1/ui/decks/{deck_id}/slides/1/apply_edit",
            data={"decision": "accept"},
        )
        assert resp2.status_code == 200

        # Verify persisted slide updated
        slide = await mem_store.get_slide(deck_id, 1)
        assert slide is not None
        assert slide.get("html_content") == "<p>new</p>"
        assert slide.get("version") == 2
        assert "pending_html" not in slide
    # (no-op outside patched context)


async def test_deck_ui_edit_review_reject(client):
    mem_store = InMemoryDeckStore()
    with patch("app.api.v1.ui.get_deck_store", return_value=mem_store):
        deck_id = await _seed_deck_with_slide(mem_store)
        with patch(
            "app.api.v1.ui.edit_slide_content",
            new=AsyncMock(return_value="<p>new</p>"),
        ):
            await client.post(
                f"/api/v1/ui/decks/{deck_id}/slides/1/edit",
                data={"edit_prompt": "make it new"},
            )

        # Reject -> keep original html
        resp = await client.post(
            f"/api/v1/ui/decks/{deck_id}/slides/1/apply_edit",
            data={"decision": "reject"},
        )
        assert resp.status_code == 200

        slide = await mem_store.get_slide(deck_id, 1)
        assert slide is not None
        assert slide.get("html_content") == "<p>old</p>"
        assert slide.get("version") == 1
        assert "pending_html" not in slide


async def test_inmemory_ui_edit_review_accept(client):
    # seed in-memory slides_db
    from app.core.infra import state

    state.slides_db.append(
        {
            "id": 1,
            "title": "S1",
            "html_content": "<p>old</p>",
            "version": 1,
            "status": "complete",
        }
    )

    with patch(
        "app.api.v1.ui.edit_slide_content", new=AsyncMock(return_value="<p>new</p>")
    ):
        resp = await client.post(
            "/api/v1/ui/slides/1/edit", data={"edit_prompt": "change it"}
        )
        assert resp.status_code == 200

    resp2 = await client.post(
        "/api/v1/ui/slides/1/apply_edit", data={"decision": "accept"}
    )
    assert resp2.status_code == 200

    slide = next((s for s in state.slides_db if s.get("id") == 1), None)
    assert slide is not None
    assert slide.get("html_content") == "<p>new</p>"
    assert slide.get("version") == 2
    assert "pending_html" not in slide

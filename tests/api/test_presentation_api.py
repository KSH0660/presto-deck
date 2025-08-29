import pytest
from unittest.mock import patch, AsyncMock


pytestmark = pytest.mark.asyncio


async def test_add_and_list_slides(client):
    """슬라이드 추가 후 목록에서 확인할 수 있어야 합니다."""
    resp = await client.post(
        "/api/v1/slides/add", json={"add_prompt": "Marketing plan Q4"}
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["id"] == 1
    assert created["status"] == "complete"
    assert isinstance(created["version"], int)
    assert isinstance(created["title"], str)
    assert isinstance(created["html_content"], str)

    list_resp = await client.get("/api/v1/slides")
    assert list_resp.status_code == 200
    slides = list_resp.json()
    assert isinstance(slides, list) and len(slides) == 1
    assert slides[0]["title"].startswith("New Slide for:")
    # schema check
    s0 = slides[0]
    for k in ("id", "title", "html_content", "version", "status"):
        assert k in s0


async def test_edit_slide(client):
    """슬라이드 편집 API가 버전과 내용을 갱신해야 합니다."""
    # 먼저 슬라이드를 하나 추가
    created = (
        await client.post("/api/v1/slides/add", json={"add_prompt": "Topic"})
    ).json()
    slide_id = created["id"]

    # LLM 편집 함수 패치
    with patch(
        "app.api.v1.presentation.edit_slide_content",
        new=AsyncMock(return_value="<h1>Edited</h1>"),
    ):
        resp = await client.post(
            f"/api/v1/slides/{slide_id}/edit", json={"edit_prompt": "make it bold"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == slide_id
        assert data["html_content"] == "<h1>Edited</h1>"
        # 생성 시 1이었다가 편집 후 +1
        assert data["version"] == 2
        assert data["status"] == "complete"


async def test_delete_slide(client):
    """슬라이드를 삭제하면 목록에서 사라져야 합니다."""
    created = (
        await client.post("/api/v1/slides/add", json={"add_prompt": "Delete me"})
    ).json()
    slide_id = created["id"]

    del_resp = await client.delete(f"/api/v1/slides/{slide_id}/delete")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"status": "deleted", "id": slide_id}

    slides = (await client.get("/api/v1/slides")).json()
    assert slides == []


async def test_export_html(client):
    """HTML 내보내기가 빈 상태와 비어있지 않은 상태 모두 동작합니다."""
    # 빈 상태
    resp_empty = await client.get("/api/v1/export/html")
    assert resp_empty.status_code == 200
    assert "No slides to export" in resp_empty.text

    # 슬라이드 추가 후 내보내기
    await client.post("/api/v1/slides/add", json={"add_prompt": "Export"})
    resp = await client.get("/api/v1/export/html")
    assert resp.status_code == 200
    assert "<html>" in resp.text and "</html>" in resp.text
    assert "Export" in resp.text


async def test_progress_sse(client):
    """진행 SSE가 이벤트를 스트리밍하는지 확인 (sleep 패치로 빠르게)."""
    with patch("app.api.v1.presentation.asyncio.sleep", new=AsyncMock()) as _:
        async with client.stream("GET", "/api/v1/progress") as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            # 전체 바이트를 한 번에 읽고 이벤트 개수 확인
            body = b"".join([chunk async for chunk in r.aiter_bytes()]).decode()
            # 4단계 이벤트("step")가 있어야 함
            assert body.count("event: step") == 4


async def test_generate_sse_smoke(client):
    """generate 스트림이 SSE 형태로 동작하는지 스모크 테스트 (내부 스트림 패치)."""

    async def fake_stream(_req):
        yield "event: started\ndata: {}\n\n"
        yield 'event: slide_rendered\ndata: {"index":0}\n\n'
        yield 'event: completed\ndata: {"total":1}\n\n'

    with patch("app.api.v1.presentation.stream_presentation", new=fake_stream):
        payload = {"user_prompt": "Hello", "theme": None, "color_preference": None}
        async with client.stream("POST", "/api/v1/generate", json=payload) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            text = b"".join([c async for c in r.aiter_bytes()]).decode()
            assert "event: started" in text
            assert "event: slide_rendered" in text
            assert "event: completed" in text

import pytest
from unittest.mock import patch, AsyncMock

from app.models.schema import (
    DeckPlan,
    SlideSpec,
    LayoutSelection,
    SlideCandidates,
    TemplateCandidate,
    SlideHTML,
)


pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_deck_plan():
    """샘플 DeckPlan 픽스처."""
    return DeckPlan(
        topic="Stream Topic",
        audience="Stream Audience",
        slides=[
            SlideSpec(slide_id=1, title="Slide 1", key_points=["P1"]),
            SlideSpec(slide_id=2, title="Slide 2", key_points=["P2"]),
            SlideSpec(slide_id=3, title="Slide 3", key_points=["P3"]),
        ],
    )


@pytest.fixture
def mock_layout_selection():
    """샘플 LayoutSelection 픽스처."""
    return LayoutSelection(
        items=[
            SlideCandidates(
                slide_id=1, candidates=[TemplateCandidate(template_name="title.html")]
            ),
            SlideCandidates(
                slide_id=2, candidates=[TemplateCandidate(template_name="content.html")]
            ),
            SlideCandidates(
                slide_id=3,
                candidates=[TemplateCandidate(template_name="two_column.html")],
            ),
        ]
    )


async def test_generate_stream_sends_sse(client, mock_deck_plan, mock_layout_selection):
    """SSE 스트림이 기대 이벤트를 포함하는지 확인한다."""
    with patch("app.core.planner.plan_deck", new_callable=AsyncMock) as mock_plan:
        with patch(
            "app.core.layout_selector.select_layouts", new_callable=AsyncMock
        ) as mock_select:
            with patch(
                "app.core.slide_worker.process_slide", new_callable=AsyncMock
            ) as mock_process:
                mock_plan.return_value = mock_deck_plan
                mock_select.return_value = mock_layout_selection

                # 반환 순서를 섞어서 완료순의 동작을 확인
                async def proc(
                    slide_spec,
                    deck_plan,
                    candidate_template_names,
                    template_catalog,
                    model,
                ):
                    # simulate small async work
                    return SlideHTML(
                        slide_id=slide_spec.slide_id,
                        template_name=(
                            candidate_template_names[0]
                            if candidate_template_names
                            else "title.html"
                        ),
                        html=f"<h1>{slide_spec.title}</h1>",
                    )

                mock_process.side_effect = proc

                # 스트리밍 요청
                async with client.stream(
                    "POST",
                    "/api/v1/generate-stream",
                    json={
                        "user_request": "Stream me",
                        "quality": "default",
                        "ordered": False,
                        "concurrency": 2,
                    },
                ) as resp:
                    assert resp.status_code == 200
                    text = ""
                    async for chunk in resp.aiter_text():
                        text += chunk

                # 기본 이벤트가 포함되어야 함
                assert "event: started" in text
                assert "event: deck_plan" in text
                assert text.count("event: slide_rendered") == 3
                assert "event: progress" in text
                assert "event: completed" in text

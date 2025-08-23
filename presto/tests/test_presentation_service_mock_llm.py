import pytest
from unittest.mock import AsyncMock, patch, Mock
from presto.app.services.presentation import PresentationService
from presto.app.models.presentation import (
    PresentationRequest,
    PresentationOutline,
    SlideOutline,
)
from presto.app.services.template import TemplateService
from presto.app.services.resource import ResourceService


@pytest.fixture
def mock_template_service():
    mock = Mock(spec=TemplateService)
    # Ensure get_prompt_template returns a mock object that has a 'render' method
    mock.get_prompt_template.return_value.render.return_value = "mocked outline prompt"
    return mock


@pytest.fixture
def mock_resource_service():
    mock = AsyncMock(spec=ResourceService)
    return mock


@pytest.fixture
def presentation_service(mock_template_service, mock_resource_service):
    return PresentationService(mock_template_service, mock_resource_service)


@pytest.mark.asyncio
async def test_generate_outline_with_mock_llm(
    presentation_service, mock_template_service
):
    """Mock LLM을 사용하여 _generate_outline 메서드를 테스트합니다."""
    mock_request = PresentationRequest(
        topic="Test Topic",
        slide_count=3,
        theme="classic",
        model="gpt-4o",
        user_provided_urls=[],
        user_provided_text="",
        perform_web_search=False,
    )
    mock_available_layouts = ["title", "list"]
    mock_enriched_context = "Mocked enriched context summary."

    # Mock the generate_content_openai function
    with patch(
        "presto.app.services.presentation.generate_content_openai",
        new_callable=AsyncMock,
    ) as mock_generate_content_openai:
        # Configure the mock's return value
        mock_generate_content_openai.return_value = PresentationOutline(
            slides=[
                SlideOutline(title="Intro", layout="title"),
                SlideOutline(title="Body", layout="list"),
                SlideOutline(title="Conclusion", layout="list"),
            ]
        )

        outline = await presentation_service._generate_outline(
            mock_request, mock_available_layouts, mock_enriched_context
        )

        # Assert that generate_content_openai was called with the correct arguments
        mock_generate_content_openai.assert_called_once_with(
            "mocked outline prompt",
            model=mock_request.model,
            response_model=PresentationOutline,
        )

        # Assert the returned outline
        assert isinstance(outline, PresentationOutline)
        assert len(outline.slides) == 3
        assert outline.slides[0].title == "Intro"
        assert outline.slides[1].layout == "list"

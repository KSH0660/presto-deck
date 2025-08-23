import pytest
from unittest.mock import AsyncMock, Mock
from presto.app.services.presentation import PresentationService
from presto.app.services.template import TemplateService
from presto.app.services.resource import ResourceService


@pytest.fixture
def mock_template_service():
    mock = Mock(spec=TemplateService)
    mock.get_prompt_template.return_value.render.return_value = "mocked outline prompt"
    return mock


@pytest.fixture
def mock_resource_service():
    mock = AsyncMock(spec=ResourceService)
    return mock


@pytest.fixture
def presentation_service(mock_template_service, mock_resource_service):
    return PresentationService(mock_template_service, mock_resource_service)

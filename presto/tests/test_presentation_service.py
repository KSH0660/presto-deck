import pytest
import json
from presto.app.services.presentation import PresentationService
from unittest.mock import Mock


# Mock dependencies for PresentationService
@pytest.fixture
def mock_template_service():
    return Mock()


@pytest.fixture
def mock_resource_service():
    return Mock()


@pytest.fixture
def presentation_service(mock_template_service, mock_resource_service):
    return PresentationService(mock_template_service, mock_resource_service)


def test_normalize_content_string(presentation_service):
    """문자열 입력이 올바르게 정규화되는지 테스트합니다."""
    content = "Hello World"
    expected = ["Hello World"]
    assert presentation_service._normalize_content(content) == expected


def test_normalize_content_json_string(presentation_service):
    """JSON 문자열 입력이 올바르게 정규화되는지 테스트합니다."""
    content = json.dumps({"text": "Hello JSON"})
    expected = ["{'text': 'Hello JSON'}"]
    assert presentation_service._normalize_content(content) == expected


def test_normalize_content_list_of_strings(presentation_service):
    """문자열 리스트 입력이 올바르게 정규화되는지 테스트합니다."""
    content = ["Item 1", "Item 2"]
    expected = ["Item 1", "Item 2"]
    assert presentation_service._normalize_content(content) == expected


def test_normalize_content_list_of_dicts(presentation_service):
    """딕셔너리 리스트 입력이 올바르게 문자열화되어 정규화되는지 테스트합니다."""
    content = [{"key": "value"}, {"number": 123}]
    expected = ["{'key': 'value'}", "{'number': 123}"]
    assert presentation_service._normalize_content(content) == expected


def test_normalize_content_empty_string(presentation_service):
    """빈 문자열 입력이 올바르게 정규화되는지 테스트합니다."""
    content = ""
    expected = [""]
    assert presentation_service._normalize_content(content) == expected


def test_normalize_content_none(presentation_service):
    """None 입력이 올바르게 정규화되는지 테스트합니다."""
    content = None
    expected = ["None"]
    assert presentation_service._normalize_content(content) == expected


def test_normalize_content_mixed_types(presentation_service):
    """혼합된 타입의 리스트 입력이 올바르게 정규화되는지 테스트합니다."""
    content = ["string", 123, {"key": "value"}, None]
    expected = ["string", "123", "{'key': 'value'}", "None"]
    assert presentation_service._normalize_content(content) == expected

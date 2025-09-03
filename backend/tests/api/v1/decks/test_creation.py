"""
Tests for deck creation endpoint.
"""

import pytest
from unittest.mock import AsyncMock
from uuid import UUID


class TestDeckCreation:
    """Test deck creation endpoint POST /api/v1/decks."""

    def test_create_deck_success(
        self, client, mock_dependencies, auth_headers, sample_deck_create_request
    ):
        """Test successful deck creation with all optional fields."""
        # Setup mocks
        mock_use_case_result = {
            "deck_id": "12345678-1234-5678-9012-123456789012",
            "status": "pending",
        }

        # Mock the use case execution
        with pytest.MonkeyPatch().context() as m:
            mock_use_case = AsyncMock()
            mock_use_case.execute.return_value = mock_use_case_result
            m.setattr(
                "app.api.v1.decks.creation.CreateDeckPlanUseCase",
                lambda **kwargs: mock_use_case,
            )

            # Make request
            response = client.post(
                "/api/v1/decks", json=sample_deck_create_request, headers=auth_headers
            )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "deck_id" in data
        assert data["status"] == "pending"
        assert "message" in data

        # Verify use case was called with correct parameters
        mock_use_case.execute.assert_called_once()
        call_args = mock_use_case.execute.call_args
        assert call_args.kwargs["prompt"] == sample_deck_create_request["prompt"]
        assert (
            call_args.kwargs["style_preferences"]
            == sample_deck_create_request["style_preferences"]
        )

    def test_create_deck_minimal_request(self, client, mock_dependencies, auth_headers):
        """Test deck creation with minimal required fields only."""
        minimal_request = {"prompt": "Create a simple presentation about Python basics"}

        mock_use_case_result = {
            "deck_id": "12345678-1234-5678-9012-123456789012",
            "status": "pending",
        }

        with pytest.MonkeyPatch().context() as m:
            mock_use_case = AsyncMock()
            mock_use_case.execute.return_value = mock_use_case_result
            m.setattr(
                "app.api.v1.decks.creation.CreateDeckPlanUseCase",
                lambda **kwargs: mock_use_case,
            )

            response = client.post(
                "/api/v1/decks", json=minimal_request, headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert UUID(data["deck_id"])  # Valid UUID
        assert data["status"] == "pending"

    def test_create_deck_validation_errors(
        self, client, mock_dependencies, auth_headers
    ):
        """Test validation errors for invalid deck creation requests."""

        # Test missing prompt
        response = client.post("/api/v1/decks", json={}, headers=auth_headers)
        assert response.status_code == 422

        # Test prompt too short
        response = client.post(
            "/api/v1/decks", json={"prompt": "short"}, headers=auth_headers
        )
        assert response.status_code == 422

        # Test invalid slide count
        response = client.post(
            "/api/v1/decks",
            json={
                "prompt": "Valid prompt for testing validation",
                "slide_count": 0,  # Invalid: must be >= 1
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_deck_unauthorized(self, client, mock_dependencies):
        """Test deck creation without authentication."""
        response = client.post(
            "/api/v1/decks", json={"prompt": "Test prompt without auth"}
        )
        assert response.status_code == 401

    def test_create_deck_use_case_error(
        self, client, mock_dependencies, auth_headers, sample_deck_create_request
    ):
        """Test handling of use case errors."""

        with pytest.MonkeyPatch().context() as m:
            mock_use_case = AsyncMock()
            mock_use_case.execute.side_effect = ValueError("Invalid prompt format")
            m.setattr(
                "app.api.v1.decks.creation.CreateDeckPlanUseCase",
                lambda **kwargs: mock_use_case,
            )

            response = client.post(
                "/api/v1/decks", json=sample_deck_create_request, headers=auth_headers
            )

        assert response.status_code == 400
        assert "Invalid prompt format" in response.json()["detail"]

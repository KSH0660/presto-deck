"""
Application ports - abstract interfaces for external dependencies.

These interfaces define the contracts that the application layer needs
from external systems, following the Dependency Inversion Principle.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import UUID

from app.domain.entities.deck import Deck
from app.domain.entities.slide import Slide


class DeckRepositoryPort(ABC):
    """Abstract repository interface for Deck operations."""

    @abstractmethod
    async def create(self, deck: Deck) -> Deck:
        """Create a new deck."""
        pass

    @abstractmethod
    async def get_by_id(self, deck_id: UUID) -> Optional[Deck]:
        """Get deck by ID."""
        pass

    @abstractmethod
    async def get_by_user_id(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> List[Deck]:
        """Get decks by user ID with pagination."""
        pass

    @abstractmethod
    async def update(self, deck: Deck) -> Deck:
        """Update an existing deck."""
        pass

    @abstractmethod
    async def delete(self, deck_id: UUID) -> bool:
        """Delete a deck."""
        pass


class SlideRepositoryPort(ABC):
    """Abstract repository interface for Slide operations."""

    @abstractmethod
    async def create(self, slide: Slide) -> Slide:
        """Create a new slide."""
        pass

    @abstractmethod
    async def get_by_deck_id(self, deck_id: UUID) -> List[Slide]:
        """Get all slides for a deck."""
        pass

    @abstractmethod
    async def get_by_id(self, slide_id: UUID) -> Optional[Slide]:
        """Get slide by ID."""
        pass

    @abstractmethod
    async def update(self, slide: Slide) -> Slide:
        """Update an existing slide."""
        pass

    @abstractmethod
    async def delete(self, slide_id: UUID) -> bool:
        """Delete a slide."""
        pass

    @abstractmethod
    async def reorder_slides(
        self, deck_id: UUID, slide_orders: Dict[UUID, int]
    ) -> List[Slide]:
        """Reorder slides in a deck."""
        pass


class EventRepositoryPort(ABC):
    """Abstract repository interface for Event operations."""

    @abstractmethod
    async def store_event(self, deck_id: UUID, event_data: Dict[str, Any]) -> None:
        """Store an event."""
        pass

    @abstractmethod
    async def get_events_by_deck_id(
        self, deck_id: UUID, from_version: int = 0
    ) -> List[Dict[str, Any]]:
        """Get events for a deck from a specific version."""
        pass


class LLMServicePort(ABC):
    """Abstract interface for LLM operations."""

    @abstractmethod
    async def generate_deck_plan(
        self, prompt: str, style_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a deck plan from a prompt."""
        pass

    @abstractmethod
    async def generate_slide_content(
        self, slide_outline: str, deck_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate content for a specific slide."""
        pass

    @abstractmethod
    async def refine_slide_content(
        self, current_content: str, refinement_request: str
    ) -> Dict[str, Any]:
        """Refine existing slide content based on feedback."""
        pass


class MessageBrokerPort(ABC):
    """Abstract interface for message broker operations."""

    @abstractmethod
    async def enqueue_job(self, job_name: str, **kwargs) -> str:
        """Enqueue a background job."""
        pass

    @abstractmethod
    async def publish_event(self, channel: str, event_data: Dict[str, Any]) -> None:
        """Publish an event to a channel."""
        pass


class WebSocketBroadcasterPort(ABC):
    """Abstract interface for WebSocket broadcasting."""

    @abstractmethod
    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]) -> None:
        """Broadcast message to a specific user."""
        pass

    @abstractmethod
    async def broadcast_to_deck(self, deck_id: str, message: Dict[str, Any]) -> None:
        """Broadcast message to all users subscribed to a deck."""
        pass


class TemplateServicePort(ABC):
    """Abstract interface for template operations."""

    @abstractmethod
    async def get_available_templates(
        self, template_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get available slide templates."""
        pass

    @abstractmethod
    async def render_slide(
        self, template_filename: str, content_data: Dict[str, Any]
    ) -> str:
        """Render slide content using a template."""
        pass

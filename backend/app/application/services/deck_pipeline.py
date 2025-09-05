"""
Deck Pipeline Service - Orchestrates the entire deck generation pipeline.

This service coordinates the complex workflow of deck generation:
Planning → Selection → Rendering → Editing
"""

from typing import Dict, Any, List
from uuid import UUID

from app.domain.entities.deck import Deck
from app.domain.entities.slide import Slide
from app.domain.services.deck_orchestration import DeckOrchestrationService
from app.application.ports import (
    LLMServicePort,
    TemplateServicePort,
    MessageBrokerPort,
    WebSocketBroadcasterPort,
)


class DeckPipelineService:
    """
    Application service that orchestrates the deck generation pipeline.

    This service coordinates multiple domain services and external adapters
    to implement the complete deck generation workflow.
    """

    def __init__(
        self,
        llm_service: LLMServicePort,
        template_service: TemplateServicePort,
        message_broker: MessageBrokerPort,
        ws_broadcaster: WebSocketBroadcasterPort,
    ):
        self.llm_service = llm_service
        self.template_service = template_service
        self.message_broker = message_broker
        self.ws_broadcaster = ws_broadcaster
        self.orchestration_service = DeckOrchestrationService()

    async def initiate_deck_generation(self, deck: Deck, user_id: UUID) -> None:
        """
        Initiate the deck generation pipeline.

        Args:
            deck: The deck to generate
            user_id: ID of the user who owns the deck
        """
        # Enqueue planning phase
        await self.message_broker.enqueue_job(
            "generate_deck_plan",
            deck_id=str(deck.id),
            user_id=str(user_id),
            prompt=deck.prompt,
            style_preferences=deck.style_preferences,
        )

        # Notify user that generation has started
        await self.ws_broadcaster.broadcast_to_user(
            user_id=str(user_id),
            message={
                "type": "DeckStarted",
                "deck_id": str(deck.id),
                "status": deck.status.value,
                "message": "Deck generation pipeline initiated",
            },
        )

    async def execute_planning_phase(self, deck: Deck, user_id: UUID) -> Dict[str, Any]:
        """
        Execute the planning phase of deck generation.

        This phase analyzes the prompt and creates a structured plan.

        Args:
            deck: The deck being planned
            user_id: ID of the user who owns the deck

        Returns:
            Dict[str, Any]: Planning results with slide outlines
        """
        # Generate deck plan using LLM
        plan_result = await self.llm_service.generate_deck_plan(
            prompt=deck.prompt, style_preferences=deck.style_preferences
        )

        # Notify planning progress
        await self.ws_broadcaster.broadcast_to_user(
            user_id=str(user_id),
            message={
                "type": "PlanUpdated",
                "deck_id": str(deck.id),
                "plan": plan_result,
                "message": "Deck plan generated successfully",
            },
        )

        return plan_result

    async def execute_generation_phase(
        self, deck: Deck, slides: List[Slide], user_id: UUID
    ) -> List[Slide]:
        """
        Execute the generation phase for all slides.

        Args:
            deck: The deck being generated
            slides: List of slides to generate content for
            user_id: ID of the user who owns the deck

        Returns:
            List[Slide]: Updated slides with generated content
        """
        updated_slides = []

        for slide in slides:
            # Generate content for each slide
            content_result = await self.llm_service.generate_slide_content(
                slide_outline=slide.content_outline,
                deck_context={
                    "prompt": deck.prompt,
                    "style_preferences": deck.style_preferences,
                    "template_type": (
                        deck.template_type.value if deck.template_type else None
                    ),
                    "slide_position": slide.order,
                    "total_slides": len(slides),
                },
            )

            # Update slide with generated content
            slide.update_content(
                html_content=content_result.get("html_content", ""),
                presenter_notes=content_result.get("presenter_notes", ""),
            )

            updated_slides.append(slide)

            # Notify progress for each slide
            await self.ws_broadcaster.broadcast_to_user(
                user_id=str(user_id),
                message={
                    "type": "SlideUpdated",
                    "deck_id": str(deck.id),
                    "slide_id": str(slide.id),
                    "slide_order": slide.order,
                    "progress": (slide.order / len(slides)) * 100,
                    "message": f"Generated slide {slide.order} of {len(slides)}",
                },
            )

        return updated_slides

    async def finalize_deck(
        self, deck: Deck, slides: List[Slide], user_id: UUID
    ) -> bool:
        """
        Finalize the deck generation process.

        Args:
            deck: The deck to finalize
            slides: All slides in the deck
            user_id: ID of the user who owns the deck

        Returns:
            bool: True if deck can be finalized
        """
        # Check if deck can be completed using domain service
        can_complete, reason = self.orchestration_service.can_mark_deck_complete(
            deck, slides
        )

        if not can_complete:
            # Notify user of the issue
            await self.ws_broadcaster.broadcast_to_user(
                user_id=str(user_id),
                message={
                    "type": "DeckFailed",
                    "deck_id": str(deck.id),
                    "reason": reason,
                    "message": f"Cannot complete deck: {reason}",
                },
            )
            return False

        # Notify successful completion
        await self.ws_broadcaster.broadcast_to_user(
            user_id=str(user_id),
            message={
                "type": "DeckCompleted",
                "deck_id": str(deck.id),
                "slide_count": len(slides),
                "message": "Deck generation completed successfully",
            },
        )

        return True

    async def handle_generation_error(
        self, deck_id: UUID, user_id: UUID, error_message: str, phase: str = "unknown"
    ) -> None:
        """
        Handle errors during deck generation.

        Args:
            deck_id: ID of the deck where error occurred
            user_id: ID of the user who owns the deck
            error_message: Description of the error
            phase: Which phase the error occurred in
        """
        await self.ws_broadcaster.broadcast_to_user(
            user_id=str(user_id),
            message={
                "type": "DeckFailed",
                "deck_id": str(deck_id),
                "phase": phase,
                "error": error_message,
                "message": f"Deck generation failed during {phase} phase",
            },
        )

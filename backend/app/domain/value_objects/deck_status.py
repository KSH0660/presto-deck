"""
Deck status value object - core business states.
"""

from enum import Enum


class DeckStatus(str, Enum):
    """
    Deck lifecycle status with business rules.

    This enum defines the core states a deck can be in during its lifecycle.
    Each status represents a distinct business state with specific rules and transitions.
    """

    PENDING = "pending"  # Just created, waiting to start processing
    PLANNING = "planning"  # AI is analyzing prompt and creating outline
    GENERATING = "generating"  # AI is creating slide content
    EDITING = "editing"  # Post-generation refinement and editing
    COMPLETED = "completed"  # Deck is finished and ready for use
    FAILED = "failed"  # Generation failed due to error
    CANCELLED = "cancelled"  # User cancelled the generation

    def can_transition_to(self, new_status: "DeckStatus") -> bool:
        """
        Business rule: Define valid status transitions.

        Args:
            new_status: The status to transition to

        Returns:
            bool: Whether the transition is valid
        """
        valid_transitions = {
            self.PENDING: [self.PLANNING, self.CANCELLED, self.FAILED],
            self.PLANNING: [self.GENERATING, self.CANCELLED, self.FAILED],
            self.GENERATING: [
                self.EDITING,
                self.COMPLETED,
                self.CANCELLED,
                self.FAILED,
            ],
            self.EDITING: [self.COMPLETED, self.FAILED],
            self.COMPLETED: [self.EDITING],  # Allow re-editing completed decks
            self.FAILED: [self.PENDING],  # Allow retry from failed state
            self.CANCELLED: [self.PENDING],  # Allow restart from cancelled state
        }

        return new_status in valid_transitions.get(self, [])

    def is_terminal(self) -> bool:
        """
        Business rule: Check if this is a terminal state.

        Returns:
            bool: True if this status cannot transition to other states
        """
        return self in [self.COMPLETED, self.FAILED, self.CANCELLED]

    def is_processing(self) -> bool:
        """
        Business rule: Check if deck is actively being processed.

        Returns:
            bool: True if deck is in an active processing state
        """
        return self in [self.PLANNING, self.GENERATING, self.EDITING]

    def can_be_cancelled(self) -> bool:
        """
        Business rule: Check if deck can be cancelled.

        Returns:
            bool: True if deck can be cancelled from this status
        """
        return self in [self.PENDING, self.PLANNING, self.GENERATING]

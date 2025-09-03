"""
SQLAlchemy model for Slide Version Management.
Tracks all changes to slides for editing, collaboration, and rollback support.
"""

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from enum import Enum
import uuid

from app.data.models.base import Base


class SlideVersionReason(str, Enum):
    """Enumeration of slide version change reasons."""

    AI_GENERATED = "ai_generated"  # Initial AI generation
    AI_REGENERATED = "ai_regenerated"  # AI re-generation with different prompt
    USER_EDIT = "user_edit"  # Manual user editing
    TEMPLATE_CHANGE = "template_change"  # Template switched
    REORDER = "reorder"  # Slide order changed
    INSERT = "insert"  # New slide inserted
    DELETE = "delete"  # Slide deleted (soft delete)
    COLLABORATION = "collaboration"  # Multi-user editing
    ROLLBACK = "rollback"  # Reverted to previous version


class SlideVersionModel(Base):
    """
    Version history for slides supporting editing, collaboration, and rollback.

    Each version captures a complete snapshot of slide state at that point in time.
    This enables:
    - Full edit history tracking
    - Rollback to any previous version
    - Collaboration with conflict resolution
    - AI vs user edit differentiation
    - Analytics on editing patterns
    """

    __tablename__ = "slide_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key relationships
    slide_id = Column(
        UUID(as_uuid=True),
        ForeignKey("slides.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    deck_id = Column(
        UUID(as_uuid=True),
        ForeignKey("decks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Version metadata
    version_no = Column(Integer, nullable=False)  # 1, 2, 3, ...
    reason = Column(String(50), nullable=False)  # See SlideVersionReason enum

    # Complete slide state snapshot
    snapshot = Column(JSON, nullable=False)  # Full slide data at this version

    # Change metadata
    created_by = Column(UUID(as_uuid=True), nullable=True)  # User who made the change
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)

    # Optional: Change description for complex edits
    change_description = Column(Text, nullable=True)

    # Optional: Parent version for branching/merging scenarios
    parent_version = Column(Integer, nullable=True)

    # Relationships
    slide = relationship("SlideModel", back_populates="versions")
    deck = relationship("DeckModel")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("slide_id", "version_no", name="unique_slide_version"),
        Index("idx_slide_versions_created_at", "slide_id", "created_at"),
        Index("idx_slide_versions_reason", "reason"),
        Index("idx_slide_versions_user", "created_by", "created_at"),
    )

    @property
    def snapshot_data(self) -> dict:
        """Parse snapshot JSON data."""
        return self.snapshot or {}

    def get_slide_state(self) -> dict:
        """Get the slide state from this version's snapshot."""
        return {
            "title": self.snapshot_data.get("title", ""),
            "content_outline": self.snapshot_data.get("content_outline", ""),
            "html_content": self.snapshot_data.get("html_content"),
            "presenter_notes": self.snapshot_data.get("presenter_notes", ""),
            "template_filename": self.snapshot_data.get("template_filename", ""),
            "order": self.snapshot_data.get("order", 1),
        }

    @classmethod
    def create_snapshot(
        cls,
        title: str,
        content_outline: str,
        html_content: str = None,
        presenter_notes: str = "",
        template_filename: str = "",
        order: int = 1,
        **extra_data,
    ) -> dict:
        """Helper method to create a standardized snapshot."""
        snapshot = {
            "title": title,
            "content_outline": content_outline,
            "html_content": html_content,
            "presenter_notes": presenter_notes,
            "template_filename": template_filename,
            "order": order,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        snapshot.update(extra_data)
        return snapshot

    def __repr__(self):
        return f"<SlideVersionModel(slide_id={self.slide_id}, version={self.version_no}, reason={self.reason})>"

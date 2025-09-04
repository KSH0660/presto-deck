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
    UniqueConstraint,
    Index,
)

# JSONB 타입을 추가하기 위해 postgresql dialect에서 import합니다.
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from enum import Enum
import uuid

from app.data.models.base import Base


class SlideVersionReason(str, Enum):
    """Enumeration of slide version change reasons."""

    AI_GENERATED = "ai_generated"
    AI_REGENERATED = "ai_regenerated"
    USER_EDIT = "user_edit"
    TEMPLATE_CHANGE = "template_change"
    REORDER = "reorder"
    INSERT = "insert"
    DELETE = "delete"
    COLLABORATION = "collaboration"
    ROLLBACK = "rollback"


class SlideVersionModel(Base):
    """
    Version history for slides supporting editing, collaboration, and rollback.
    """

    __tablename__ = "slide_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

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

    version_no = Column(Integer, nullable=False)
    reason = Column(String(50), nullable=False)

    # JSON 대신 JSONB를 사용하여 효율성과 인덱싱 성능을 높입니다.
    snapshot = Column(JSONB, nullable=False)

    created_by = Column(UUID(as_uuid=True), nullable=True)
    # created_at 필드를 UTC를 사용하도록 수정합니다.
    created_at = Column(
        DateTime(timezone=True), default=datetime.now(UTC), index=True, nullable=False
    )

    change_description = Column(Text, nullable=True)
    parent_version = Column(Integer, nullable=True)

    slide = relationship("SlideModel", back_populates="versions")
    deck = relationship("DeckModel")

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

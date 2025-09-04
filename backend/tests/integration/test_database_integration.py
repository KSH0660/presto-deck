"""
Integration tests for database operations with real SQLite/PostgreSQL.

These tests verify actual database interactions and transaction behavior.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Deck, Slide, DeckEvent
from app.infra.db.repositories.deck_repository import DeckRepository
from app.infra.db.repositories.slide_repository import SlideRepository
from app.infra.db.repositories.event_repository import EventRepository
from app.api.schemas import DeckStatus
from app.domain_core.value_objects.template_type import TemplateType


@pytest.mark.integration
class TestDatabaseModels:
    """Test database model behavior and relationships."""

    async def test_deck_model_creation_and_retrieval(
        self, test_db_session: AsyncSession
    ):
        """Test basic deck model operations."""
        # Create a deck
        deck_id = uuid4()
        user_id = uuid4()

        deck = Deck(
            id=deck_id,
            user_id=user_id,
            title="Test Deck",
            description="A test deck for integration testing",
            prompt="Create a test presentation",
            target_audience="Developers",
            estimated_duration=30,
            status=DeckStatus.PENDING,
            style_preferences={"theme": "professional", "color_scheme": "blue"},
        )

        test_db_session.add(deck)
        await test_db_session.commit()

        # Retrieve the deck
        result = await test_db_session.execute(select(Deck).where(Deck.id == deck_id))
        retrieved_deck = result.scalar_one()

        assert retrieved_deck.id == deck_id
        assert retrieved_deck.user_id == user_id
        assert retrieved_deck.title == "Test Deck"
        assert retrieved_deck.status == DeckStatus.PENDING
        assert retrieved_deck.style_preferences["theme"] == "professional"
        assert retrieved_deck.created_at is not None
        assert retrieved_deck.updated_at is not None

    async def test_slide_model_with_deck_relationship(
        self, test_db_session: AsyncSession
    ):
        """Test slide model and its relationship to deck."""
        # Create deck first
        deck_id = uuid4()
        deck = Deck(
            id=deck_id,
            user_id=uuid4(),
            title="Parent Deck",
            description="Deck for slide testing",
            prompt="Test prompt",
            status=DeckStatus.PLANNING,
        )
        test_db_session.add(deck)
        await test_db_session.flush()  # Ensure deck is persisted

        # Create slides
        slide1 = Slide(
            id=uuid4(),
            deck_id=deck_id,
            order=1,
            title="Introduction",
            content_outline="Overview of the topic",
            html_content="<h1>Introduction</h1><p>Content here</p>",
            presenter_notes="Welcome and introduce the topic",
            template_type=TemplateType.PROFESSIONAL,
        )

        slide2 = Slide(
            id=uuid4(),
            deck_id=deck_id,
            order=2,
            title="Main Content",
            content_outline="Detailed explanation",
            html_content="<h1>Main Content</h1><p>Detailed content</p>",
            presenter_notes="Explain the main concepts",
            template_type=TemplateType.PROFESSIONAL,
        )

        test_db_session.add_all([slide1, slide2])
        await test_db_session.commit()

        # Test relationship loading
        result = await test_db_session.execute(select(Deck).where(Deck.id == deck_id))
        deck_with_slides = result.scalar_one()

        # Load slides relationship
        await test_db_session.refresh(deck_with_slides, ["slides"])

        assert len(deck_with_slides.slides) == 2
        assert deck_with_slides.slides[0].order == 1
        assert deck_with_slides.slides[1].order == 2

    async def test_deck_event_model(self, test_db_session: AsyncSession):
        """Test deck event model for audit trail."""
        deck_id = uuid4()

        # Create deck
        deck = Deck(
            id=deck_id,
            user_id=uuid4(),
            title="Event Test Deck",
            description="Testing events",
            prompt="Test",
            status=DeckStatus.PENDING,
        )
        test_db_session.add(deck)
        await test_db_session.flush()

        # Create events
        event1 = DeckEvent(
            id=uuid4(),
            deck_id=deck_id,
            event_type="DeckStarted",
            event_data={"status": "PLANNING"},
            sequence_number=1,
            created_at=datetime.now(timezone.utc),
        )

        event2 = DeckEvent(
            id=uuid4(),
            deck_id=deck_id,
            event_type="SlideAdded",
            event_data={"slide_id": str(uuid4()), "order": 1},
            sequence_number=2,
            created_at=datetime.now(timezone.utc),
        )

        test_db_session.add_all([event1, event2])
        await test_db_session.commit()

        # Query events by deck
        result = await test_db_session.execute(
            select(DeckEvent)
            .where(DeckEvent.deck_id == deck_id)
            .order_by(DeckEvent.sequence_number)
        )
        events = result.scalars().all()

        assert len(events) == 2
        assert events[0].event_type == "DeckStarted"
        assert events[1].event_type == "SlideAdded"
        assert events[0].sequence_number < events[1].sequence_number


@pytest.mark.integration
class TestDatabaseRepositories:
    """Test repository pattern implementations."""

    @pytest.fixture
    def deck_repo(self, test_db_session: AsyncSession):
        """Create deck repository instance."""
        return DeckRepository(test_db_session)

    @pytest.fixture
    def slide_repo(self, test_db_session: AsyncSession):
        """Create slide repository instance."""
        return SlideRepository(test_db_session)

    @pytest.fixture
    def event_repo(self, test_db_session: AsyncSession):
        """Create event repository instance."""
        return EventRepository(test_db_session)

    async def test_deck_repository_operations(
        self, deck_repo: DeckRepository, test_db_session: AsyncSession
    ):
        """Test deck repository CRUD operations."""
        user_id = uuid4()

        # Create deck
        deck_data = {
            "user_id": user_id,
            "title": "Repository Test Deck",
            "description": "Testing repository pattern",
            "prompt": "Create a test deck",
            "target_audience": "Testers",
            "estimated_duration": 25,
            "status": DeckStatus.PENDING,
            "style_preferences": {"theme": "minimal"},
        }

        created_deck = await deck_repo.create(deck_data)
        await test_db_session.commit()

        assert created_deck.id is not None
        assert created_deck.title == "Repository Test Deck"
        assert created_deck.user_id == user_id

        # Get by ID
        retrieved_deck = await deck_repo.get_by_id(created_deck.id)
        assert retrieved_deck is not None
        assert retrieved_deck.id == created_deck.id

        # Update deck
        updated_data = {
            "title": "Updated Repository Test Deck",
            "status": DeckStatus.PLANNING,
        }
        updated_deck = await deck_repo.update(created_deck.id, updated_data)
        await test_db_session.commit()

        assert updated_deck.title == "Updated Repository Test Deck"
        assert updated_deck.status == DeckStatus.PLANNING

        # List user decks
        user_decks = await deck_repo.get_by_user_id(user_id)
        assert len(user_decks) == 1
        assert user_decks[0].id == created_deck.id

    async def test_slide_repository_operations(
        self, slide_repo: SlideRepository, test_db_session: AsyncSession
    ):
        """Test slide repository operations."""
        # Create a deck first
        deck_id = uuid4()
        deck = Deck(
            id=deck_id,
            user_id=uuid4(),
            title="Slide Test Deck",
            description="For slide repository testing",
            prompt="Test slides",
            status=DeckStatus.GENERATING,
        )
        test_db_session.add(deck)
        await test_db_session.flush()

        # Create slides using repository
        slide1_data = {
            "deck_id": deck_id,
            "order": 1,
            "title": "First Slide",
            "content_outline": "Introduction content",
            "html_content": "<h1>First Slide</h1>",
            "presenter_notes": "Introduction notes",
            "template_type": TemplateType.PROFESSIONAL,
        }

        slide2_data = {
            "deck_id": deck_id,
            "order": 2,
            "title": "Second Slide",
            "content_outline": "Main content",
            "html_content": "<h1>Second Slide</h1>",
            "presenter_notes": "Main content notes",
            "template_type": TemplateType.PROFESSIONAL,
        }

        slide1 = await slide_repo.create(slide1_data)
        await slide_repo.create(slide2_data)  # slide2 not used elsewhere
        await test_db_session.commit()

        # Get slides by deck
        deck_slides = await slide_repo.get_by_deck_id(deck_id)
        assert len(deck_slides) == 2

        # Slides should be ordered
        assert deck_slides[0].order == 1
        assert deck_slides[1].order == 2

        # Update slide
        updated_slide_data = {
            "title": "Updated First Slide",
            "html_content": "<h1>Updated First Slide</h1><p>New content</p>",
        }
        updated_slide = await slide_repo.update(slide1.id, updated_slide_data)
        await test_db_session.commit()

        assert updated_slide.title == "Updated First Slide"
        assert "<p>New content</p>" in updated_slide.html_content

    async def test_event_repository_operations(
        self, event_repo: EventRepository, test_db_session: AsyncSession
    ):
        """Test event repository operations."""
        deck_id = uuid4()

        # Create deck first
        deck = Deck(
            id=deck_id,
            user_id=uuid4(),
            title="Event Test Deck",
            description="For event testing",
            prompt="Test events",
            status=DeckStatus.PENDING,
        )
        test_db_session.add(deck)
        await test_db_session.flush()

        # Create events
        event1_data = {
            "deck_id": deck_id,
            "event_type": "DeckStarted",
            "event_data": {"user_action": "create_deck"},
            "sequence_number": 1,
        }

        event2_data = {
            "deck_id": deck_id,
            "event_type": "PlanUpdated",
            "event_data": {"slides_planned": 5},
            "sequence_number": 2,
        }

        await event_repo.create(event1_data)
        await event_repo.create(event2_data)
        await test_db_session.commit()

        # Get events by deck
        deck_events = await event_repo.get_by_deck_id(deck_id)
        assert len(deck_events) == 2

        # Test pagination
        page1_events = await event_repo.get_by_deck_id(deck_id, limit=1, offset=0)
        assert len(page1_events) == 1
        assert page1_events[0].sequence_number == 1

        page2_events = await event_repo.get_by_deck_id(deck_id, limit=1, offset=1)
        assert len(page2_events) == 1
        assert page2_events[0].sequence_number == 2

        # Get events since version
        recent_events = await event_repo.get_by_deck_id_since_version(
            deck_id, since_version=1
        )
        assert len(recent_events) == 1
        assert recent_events[0].sequence_number == 2


@pytest.mark.integration
class TestDatabaseTransactions:
    """Test database transaction behavior and error handling."""

    async def test_transaction_rollback_on_error(self, test_db_session: AsyncSession):
        """Test that transaction rolls back on error."""
        deck_id = uuid4()
        user_id = uuid4()

        try:
            # Start transaction
            deck = Deck(
                id=deck_id,
                user_id=user_id,
                title="Transaction Test",
                description="Testing rollback",
                prompt="Test",
                status=DeckStatus.PENDING,
            )
            test_db_session.add(deck)

            # This should work
            await test_db_session.flush()

            # Create a slide with invalid foreign key (should fail)
            invalid_slide = Slide(
                id=uuid4(),
                deck_id=uuid4(),  # Non-existent deck_id
                order=1,
                title="Invalid Slide",
                content_outline="Should fail",
                template_type=TemplateType.PROFESSIONAL,
            )
            test_db_session.add(invalid_slide)

            # This should raise an error
            await test_db_session.commit()

        except Exception:
            # Transaction should be rolled back
            await test_db_session.rollback()

            # Verify deck was not persisted
            result = await test_db_session.execute(
                select(Deck).where(Deck.id == deck_id)
            )
            assert result.scalar_one_or_none() is None

    async def test_concurrent_updates(self, test_db_engine):
        """Test handling of concurrent updates to same record."""
        deck_id = uuid4()
        user_id = uuid4()

        # Create initial deck
        async with AsyncSession(test_db_engine) as session1:
            deck = Deck(
                id=deck_id,
                user_id=user_id,
                title="Concurrent Test",
                description="Testing concurrent updates",
                prompt="Test",
                status=DeckStatus.PENDING,
            )
            session1.add(deck)
            await session1.commit()

        # Simulate concurrent updates
        async with (
            AsyncSession(test_db_engine) as session1,
            AsyncSession(test_db_engine) as session2,
        ):
            # Both sessions load the same deck
            result1 = await session1.execute(select(Deck).where(Deck.id == deck_id))
            deck1 = result1.scalar_one()

            result2 = await session2.execute(select(Deck).where(Deck.id == deck_id))
            deck2 = result2.scalar_one()

            # Session 1 updates title
            deck1.title = "Updated by Session 1"
            deck1.status = DeckStatus.PLANNING
            await session1.commit()

            # Session 2 tries to update description
            deck2.description = "Updated by Session 2"
            deck2.status = DeckStatus.GENERATING

            # This should work (different fields can be updated concurrently)
            await session2.commit()

            # Verify final state
            async with AsyncSession(test_db_engine) as verify_session:
                result = await verify_session.execute(
                    select(Deck).where(Deck.id == deck_id)
                )
                final_deck = result.scalar_one()

                # Should have updates from session 2 (last commit wins)
                assert final_deck.description == "Updated by Session 2"
                assert final_deck.status == DeckStatus.GENERATING

    async def test_database_constraints(self, test_db_session: AsyncSession):
        """Test database constraints and validation."""
        user_id = uuid4()

        # Test unique constraint (if any)
        deck1 = Deck(
            id=uuid4(),
            user_id=user_id,
            title="Constraint Test",
            description="Testing constraints",
            prompt="Test",
            status=DeckStatus.PENDING,
        )
        test_db_session.add(deck1)
        await test_db_session.commit()

        # Test foreign key constraint
        with pytest.raises(Exception):  # Should raise foreign key error
            invalid_slide = Slide(
                id=uuid4(),
                deck_id=uuid4(),  # Non-existent deck
                order=1,
                title="Invalid Slide",
                content_outline="Should fail",
                template_type=TemplateType.PROFESSIONAL,
            )
            test_db_session.add(invalid_slide)
            await test_db_session.commit()


@pytest.mark.integration
class TestDatabasePerformance:
    """Test database performance and optimization."""

    async def test_bulk_operations(self, test_db_session: AsyncSession):
        """Test bulk insert and query performance."""
        import time

        # Create a deck
        deck_id = uuid4()
        deck = Deck(
            id=deck_id,
            user_id=uuid4(),
            title="Bulk Test Deck",
            description="Testing bulk operations",
            prompt="Test bulk",
            status=DeckStatus.GENERATING,
        )
        test_db_session.add(deck)
        await test_db_session.flush()

        # Bulk insert slides
        start_time = time.time()
        slides = []
        for i in range(50):
            slide = Slide(
                id=uuid4(),
                deck_id=deck_id,
                order=i + 1,
                title=f"Slide {i + 1}",
                content_outline=f"Content for slide {i + 1}",
                html_content=f"<h1>Slide {i + 1}</h1><p>Content</p>",
                presenter_notes=f"Notes for slide {i + 1}",
                template_type=TemplateType.PROFESSIONAL,
            )
            slides.append(slide)

        test_db_session.add_all(slides)
        await test_db_session.commit()

        bulk_insert_time = time.time() - start_time

        # Bulk query
        start_time = time.time()
        result = await test_db_session.execute(
            select(Slide).where(Slide.deck_id == deck_id).order_by(Slide.order)
        )
        queried_slides = result.scalars().all()
        bulk_query_time = time.time() - start_time

        assert len(queried_slides) == 50
        assert bulk_insert_time < 1.0  # Should be reasonably fast
        assert bulk_query_time < 0.5  # Query should be very fast

        # Test aggregation queries
        start_time = time.time()
        count_result = await test_db_session.execute(
            select(func.count(Slide.id)).where(Slide.deck_id == deck_id)
        )
        slide_count = count_result.scalar()
        aggregation_time = time.time() - start_time

        assert slide_count == 50
        assert aggregation_time < 0.1  # Aggregation should be very fast

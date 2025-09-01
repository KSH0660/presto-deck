"""Integration tests for database layer."""

import pytest
from datetime import datetime, timedelta, UTC
from uuid import uuid4

from app.domain.entities import Deck, DeckStatus, Slide, DeckEvent
from app.infrastructure.db.repositories import (
    PostgresDeckRepository,
    PostgresSlideRepository,
    PostgresEventRepository,
)


class TestPostgresDeckRepositoryIntegration:
    """Integration tests for PostgresDeckRepository with real database."""

    @pytest.mark.asyncio
    async def test_deck_crud_operations(self, db_session, test_user_id):
        """Test complete CRUD operations for decks."""
        repository = PostgresDeckRepository(db_session)
        
        # Create deck
        deck = Deck(
            id=uuid4(),
            user_id=test_user_id,
            title="Integration Test Deck",
            status=DeckStatus.PENDING,
            version=1,
            deck_plan={"title": "Test", "slides": []},
        )
        
        # Test create
        created_deck = await repository.create(deck)
        await db_session.commit()
        
        assert created_deck.id == deck.id
        assert created_deck.title == "Integration Test Deck"
        assert created_deck.status == DeckStatus.PENDING
        
        # Test get by ID
        retrieved_deck = await repository.get_by_id(deck.id)
        assert retrieved_deck is not None
        assert retrieved_deck.id == deck.id
        assert retrieved_deck.title == "Integration Test Deck"
        assert retrieved_deck.user_id == test_user_id
        
        # Test exists
        exists = await repository.exists(deck.id)
        assert exists is True
        
        # Test ownership
        is_owned = await repository.is_owned_by_user(deck.id, test_user_id)
        assert is_owned is True
        
        is_owned_by_other = await repository.is_owned_by_user(deck.id, "other-user")
        assert is_owned_by_other is False
        
        # Test update
        deck.title = "Updated Test Deck"
        deck.status = DeckStatus.COMPLETED
        deck.version = 2
        deck.deck_plan = {"title": "Updated", "slides": ["slide1", "slide2"]}
        
        updated_deck = await repository.update(deck)
        await db_session.commit()
        
        assert updated_deck.title == "Updated Test Deck"
        assert updated_deck.status == DeckStatus.COMPLETED
        assert updated_deck.version == 2
        
        # Verify update in database
        retrieved_updated = await repository.get_by_id(deck.id)
        assert retrieved_updated.title == "Updated Test Deck"
        assert retrieved_updated.status == DeckStatus.COMPLETED
        assert retrieved_updated.deck_plan == {"title": "Updated", "slides": ["slide1", "slide2"]}
        
        # Test delete
        deleted = await repository.delete(deck.id)
        await db_session.commit()
        
        assert deleted is True
        
        # Verify deletion
        deleted_deck = await repository.get_by_id(deck.id)
        assert deleted_deck is None
        
        exists_after_delete = await repository.exists(deck.id)
        assert exists_after_delete is False

    @pytest.mark.asyncio
    async def test_get_by_user_id_with_pagination(self, db_session, test_user_id, another_user_id):
        """Test getting decks by user ID with pagination."""
        repository = PostgresDeckRepository(db_session)
        
        # Create multiple decks for test user
        test_decks = []
        for i in range(5):
            deck = Deck(
                id=uuid4(),
                user_id=test_user_id,
                title=f"Test Deck {i+1}",
                status=DeckStatus.PENDING,
                version=1,
                created_at=datetime.now(UTC) - timedelta(days=i),
            )
            await repository.create(deck)
            test_decks.append(deck)
        
        # Create deck for another user
        other_deck = Deck(
            id=uuid4(),
            user_id=another_user_id,
            title="Other User Deck",
            status=DeckStatus.PENDING,
            version=1,
        )
        await repository.create(other_deck)
        await db_session.commit()
        
        # Test get all decks for user
        all_decks = await repository.get_by_user_id(test_user_id, limit=10, offset=0)
        assert len(all_decks) == 5
        
        # Should be ordered by created_at desc (newest first)
        assert all_decks[0].title == "Test Deck 1"  # Created most recently
        assert all_decks[-1].title == "Test Deck 5"  # Created earliest
        
        # Test pagination
        first_page = await repository.get_by_user_id(test_user_id, limit=2, offset=0)
        assert len(first_page) == 2
        assert first_page[0].title == "Test Deck 1"
        assert first_page[1].title == "Test Deck 2"
        
        second_page = await repository.get_by_user_id(test_user_id, limit=2, offset=2)
        assert len(second_page) == 2
        assert second_page[0].title == "Test Deck 3"
        assert second_page[1].title == "Test Deck 4"
        
        # Test limit beyond available
        beyond_limit = await repository.get_by_user_id(test_user_id, limit=10, offset=3)
        assert len(beyond_limit) == 2
        
        # Test with different user
        other_user_decks = await repository.get_by_user_id(another_user_id)
        assert len(other_user_decks) == 1
        assert other_user_decks[0].title == "Other User Deck"

    @pytest.mark.asyncio
    async def test_deck_not_found_operations(self, db_session, test_user_id):
        """Test operations on non-existent decks."""
        repository = PostgresDeckRepository(db_session)
        nonexistent_id = uuid4()
        
        # Test get by ID
        deck = await repository.get_by_id(nonexistent_id)
        assert deck is None
        
        # Test exists
        exists = await repository.exists(nonexistent_id)
        assert exists is False
        
        # Test ownership
        is_owned = await repository.is_owned_by_user(nonexistent_id, test_user_id)
        assert is_owned is False
        
        # Test delete
        deleted = await repository.delete(nonexistent_id)
        assert deleted is False
        
        # Test update should raise ValueError
        nonexistent_deck = Deck(
            id=nonexistent_id,
            user_id=test_user_id,
            title="Nonexistent",
            status=DeckStatus.PENDING,
            version=1,
        )
        
        with pytest.raises(ValueError) as exc:
            await repository.update(nonexistent_deck)
        
        assert "not found" in str(exc.value)


class TestPostgresSlideRepositoryIntegration:
    """Integration tests for PostgresSlideRepository with real database."""

    @pytest.mark.asyncio
    async def test_slide_crud_operations(self, db_session, sample_deck):
        """Test complete CRUD operations for slides."""
        # First create the deck
        deck_repository = PostgresDeckRepository(db_session)
        await deck_repository.create(sample_deck)
        
        slide_repository = PostgresSlideRepository(db_session)
        
        # Create slide
        slide = Slide(
            id=uuid4(),
            deck_id=sample_deck.id,
            slide_order=1,
            html_content="<h1>Integration Test Slide</h1><p>Content</p>",
            presenter_notes="Test presenter notes",
        )
        
        # Test create
        created_slide = await slide_repository.create(slide)
        await db_session.commit()
        
        assert created_slide.id == slide.id
        assert created_slide.deck_id == sample_deck.id
        assert created_slide.slide_order == 1
        assert created_slide.html_content == "<h1>Integration Test Slide</h1><p>Content</p>"
        
        # Test get by ID
        retrieved_slide = await slide_repository.get_by_id(slide.id)
        assert retrieved_slide is not None
        assert retrieved_slide.id == slide.id
        assert retrieved_slide.html_content == "<h1>Integration Test Slide</h1><p>Content</p>"
        assert retrieved_slide.presenter_notes == "Test presenter notes"
        
        # Test update
        slide.html_content = "<h1>Updated Slide</h1><p>Updated content</p>"
        slide.presenter_notes = "Updated notes"
        slide.slide_order = 2
        
        updated_slide = await slide_repository.update(slide)
        await db_session.commit()
        
        assert updated_slide.html_content == "<h1>Updated Slide</h1><p>Updated content</p>"
        assert updated_slide.presenter_notes == "Updated notes"
        assert updated_slide.slide_order == 2
        
        # Verify update in database
        retrieved_updated = await slide_repository.get_by_id(slide.id)
        assert retrieved_updated.html_content == "<h1>Updated Slide</h1><p>Updated content</p>"
        assert retrieved_updated.slide_order == 2
        
        # Test delete
        deleted = await slide_repository.delete(slide.id)
        await db_session.commit()
        
        assert deleted is True
        
        # Verify deletion
        deleted_slide = await slide_repository.get_by_id(slide.id)
        assert deleted_slide is None

    @pytest.mark.asyncio
    async def test_get_by_deck_id_ordering(self, db_session, sample_deck):
        """Test getting slides by deck ID with correct ordering."""
        # First create the deck
        deck_repository = PostgresDeckRepository(db_session)
        await deck_repository.create(sample_deck)
        
        slide_repository = PostgresSlideRepository(db_session)
        
        # Create slides in non-sequential order
        slides = []
        for order in [3, 1, 4, 2]:
            slide = Slide(
                id=uuid4(),
                deck_id=sample_deck.id,
                slide_order=order,
                html_content=f"<h1>Slide {order}</h1>",
                presenter_notes=f"Notes for slide {order}",
            )
            await slide_repository.create(slide)
            slides.append(slide)
        
        await db_session.commit()
        
        # Test get by deck ID
        retrieved_slides = await slide_repository.get_by_deck_id(sample_deck.id)
        assert len(retrieved_slides) == 4
        
        # Should be ordered by slide_order
        assert retrieved_slides[0].slide_order == 1
        assert retrieved_slides[1].slide_order == 2
        assert retrieved_slides[2].slide_order == 3
        assert retrieved_slides[3].slide_order == 4
        
        # Verify content matches order
        assert retrieved_slides[0].html_content == "<h1>Slide 1</h1>"
        assert retrieved_slides[3].html_content == "<h1>Slide 4</h1>"

    @pytest.mark.asyncio
    async def test_delete_by_deck_id(self, db_session, sample_deck):
        """Test deleting all slides for a deck."""
        # First create the deck
        deck_repository = PostgresDeckRepository(db_session)
        await deck_repository.create(sample_deck)
        
        slide_repository = PostgresSlideRepository(db_session)
        
        # Create multiple slides
        slides = []
        for i in range(3):
            slide = Slide(
                id=uuid4(),
                deck_id=sample_deck.id,
                slide_order=i + 1,
                html_content=f"<h1>Slide {i+1}</h1>",
                presenter_notes=f"Notes {i+1}",
            )
            await slide_repository.create(slide)
            slides.append(slide)
        
        await db_session.commit()
        
        # Verify slides exist
        existing_slides = await slide_repository.get_by_deck_id(sample_deck.id)
        assert len(existing_slides) == 3
        
        # Test delete by deck ID
        deleted_count = await slide_repository.delete_by_deck_id(sample_deck.id)
        await db_session.commit()
        
        assert deleted_count == 3
        
        # Verify all slides deleted
        remaining_slides = await slide_repository.get_by_deck_id(sample_deck.id)
        assert len(remaining_slides) == 0
        
        # Verify individual slides don't exist
        for slide in slides:
            individual_slide = await slide_repository.get_by_id(slide.id)
            assert individual_slide is None

    @pytest.mark.asyncio
    async def test_get_max_order(self, db_session, sample_deck):
        """Test getting maximum slide order."""
        # First create the deck
        deck_repository = PostgresDeckRepository(db_session)
        await deck_repository.create(sample_deck)
        
        slide_repository = PostgresSlideRepository(db_session)
        
        # Test with no slides
        max_order = await slide_repository.get_max_order(sample_deck.id)
        assert max_order == 0
        
        # Create slides with different orders
        orders = [1, 3, 7, 2]
        for order in orders:
            slide = Slide(
                id=uuid4(),
                deck_id=sample_deck.id,
                slide_order=order,
                html_content=f"<h1>Slide {order}</h1>",
            )
            await slide_repository.create(slide)
        
        await db_session.commit()
        
        # Test max order
        max_order = await slide_repository.get_max_order(sample_deck.id)
        assert max_order == 7

    @pytest.mark.asyncio
    async def test_slide_not_found_operations(self, db_session):
        """Test operations on non-existent slides."""
        slide_repository = PostgresSlideRepository(db_session)
        nonexistent_id = uuid4()
        
        # Test get by ID
        slide = await slide_repository.get_by_id(nonexistent_id)
        assert slide is None
        
        # Test delete
        deleted = await slide_repository.delete(nonexistent_id)
        assert deleted is False
        
        # Test update should raise ValueError
        nonexistent_slide = Slide(
            id=nonexistent_id,
            deck_id=uuid4(),
            slide_order=1,
            html_content="<h1>Nonexistent</h1>",
        )
        
        with pytest.raises(ValueError) as exc:
            await slide_repository.update(nonexistent_slide)
        
        assert "not found" in str(exc.value)


class TestPostgresEventRepositoryIntegration:
    """Integration tests for PostgresEventRepository with real database."""

    @pytest.mark.asyncio
    async def test_event_creation_and_retrieval(self, db_session, sample_deck):
        """Test event creation and retrieval operations."""
        # First create the deck
        deck_repository = PostgresDeckRepository(db_session)
        await deck_repository.create(sample_deck)
        
        event_repository = PostgresEventRepository(db_session)
        
        # Create events
        events = []
        for i in range(3):
            event = DeckEvent(
                deck_id=sample_deck.id,
                version=i + 1,
                event_type=f"TestEvent{i+1}",
                payload={"data": f"event{i+1}", "order": i + 1},
                created_at=datetime.now(UTC) + timedelta(seconds=i),
            )
            created_event = await event_repository.create(event)
            events.append(created_event)
        
        await db_session.commit()
        
        # Verify events have IDs
        for event in events:
            assert event.id is not None
            assert isinstance(event.id, int)
        
        # Test get by deck ID
        retrieved_events = await event_repository.get_by_deck_id(sample_deck.id)
        assert len(retrieved_events) == 3
        
        # Should be ordered by version
        assert retrieved_events[0].version == 1
        assert retrieved_events[1].version == 2
        assert retrieved_events[2].version == 3
        
        # Verify content
        assert retrieved_events[0].event_type == "TestEvent1"
        assert retrieved_events[0].payload == {"data": "event1", "order": 1}
        assert retrieved_events[2].event_type == "TestEvent3"

    @pytest.mark.asyncio
    async def test_get_by_deck_id_with_from_version(self, db_session, sample_deck):
        """Test getting events with from_version filter."""
        # First create the deck
        deck_repository = PostgresDeckRepository(db_session)
        await deck_repository.create(sample_deck)
        
        event_repository = PostgresEventRepository(db_session)
        
        # Create events with versions 1-5
        for version in range(1, 6):
            event = DeckEvent(
                deck_id=sample_deck.id,
                version=version,
                event_type=f"Event{version}",
                payload={"version": version},
            )
            await event_repository.create(event)
        
        await db_session.commit()
        
        # Test with from_version = 0 (get all)
        all_events = await event_repository.get_by_deck_id(sample_deck.id, from_version=0)
        assert len(all_events) == 5
        
        # Test with from_version = 2 (get versions > 2)
        filtered_events = await event_repository.get_by_deck_id(sample_deck.id, from_version=2)
        assert len(filtered_events) == 3
        assert filtered_events[0].version == 3
        assert filtered_events[1].version == 4
        assert filtered_events[2].version == 5
        
        # Test with from_version = 5 (get no events)
        no_events = await event_repository.get_by_deck_id(sample_deck.id, from_version=5)
        assert len(no_events) == 0
        
        # Test with from_version beyond max
        beyond_events = await event_repository.get_by_deck_id(sample_deck.id, from_version=10)
        assert len(beyond_events) == 0

    @pytest.mark.asyncio
    async def test_get_latest_version(self, db_session, sample_deck):
        """Test getting latest event version."""
        # First create the deck
        deck_repository = PostgresDeckRepository(db_session)
        await deck_repository.create(sample_deck)
        
        event_repository = PostgresEventRepository(db_session)
        
        # Test with no events
        latest_version = await event_repository.get_latest_version(sample_deck.id)
        assert latest_version == 0
        
        # Create events with non-sequential versions
        versions = [1, 3, 7, 2, 5]
        for version in versions:
            event = DeckEvent(
                deck_id=sample_deck.id,
                version=version,
                event_type=f"Event{version}",
                payload={"version": version},
            )
            await event_repository.create(event)
        
        await db_session.commit()
        
        # Test latest version
        latest_version = await event_repository.get_latest_version(sample_deck.id)
        assert latest_version == 7

    @pytest.mark.asyncio
    async def test_events_for_different_decks(self, db_session, test_user_id):
        """Test events isolation between different decks."""
        deck_repository = PostgresDeckRepository(db_session)
        event_repository = PostgresEventRepository(db_session)
        
        # Create two decks
        deck1 = Deck(
            id=uuid4(),
            user_id=test_user_id,
            title="Deck 1",
            status=DeckStatus.PENDING,
            version=1,
        )
        
        deck2 = Deck(
            id=uuid4(),
            user_id=test_user_id,
            title="Deck 2",
            status=DeckStatus.PENDING,
            version=1,
        )
        
        await deck_repository.create(deck1)
        await deck_repository.create(deck2)
        
        # Create events for deck1
        for i in range(3):
            event = DeckEvent(
                deck_id=deck1.id,
                version=i + 1,
                event_type=f"Deck1Event{i+1}",
                payload={"deck": "deck1"},
            )
            await event_repository.create(event)
        
        # Create events for deck2
        for i in range(2):
            event = DeckEvent(
                deck_id=deck2.id,
                version=i + 1,
                event_type=f"Deck2Event{i+1}",
                payload={"deck": "deck2"},
            )
            await event_repository.create(event)
        
        await db_session.commit()
        
        # Test events for deck1
        deck1_events = await event_repository.get_by_deck_id(deck1.id)
        assert len(deck1_events) == 3
        for event in deck1_events:
            assert event.deck_id == deck1.id
            assert event.payload["deck"] == "deck1"
        
        # Test events for deck2
        deck2_events = await event_repository.get_by_deck_id(deck2.id)
        assert len(deck2_events) == 2
        for event in deck2_events:
            assert event.deck_id == deck2.id
            assert event.payload["deck"] == "deck2"
        
        # Test latest versions
        deck1_latest = await event_repository.get_latest_version(deck1.id)
        deck2_latest = await event_repository.get_latest_version(deck2.id)
        assert deck1_latest == 3
        assert deck2_latest == 2

    @pytest.mark.asyncio
    async def test_event_timestamp_ordering(self, db_session, sample_deck):
        """Test that events maintain creation timestamp ordering."""
        # First create the deck
        deck_repository = PostgresDeckRepository(db_session)
        await deck_repository.create(sample_deck)
        
        event_repository = PostgresEventRepository(db_session)
        
        # Create events with specific timestamps
        timestamps = [
            datetime(2024, 1, 1, 10, 0, 0),
            datetime(2024, 1, 1, 10, 1, 0),
            datetime(2024, 1, 1, 10, 2, 0),
        ]
        
        for i, timestamp in enumerate(timestamps):
            event = DeckEvent(
                deck_id=sample_deck.id,
                version=i + 1,
                event_type=f"TimestampEvent{i+1}",
                payload={"timestamp": timestamp.isoformat()},
                created_at=timestamp,
            )
            await event_repository.create(event)
        
        await db_session.commit()
        
        # Retrieve events
        events = await event_repository.get_by_deck_id(sample_deck.id)
        
        # Verify timestamp ordering (should be ordered by version, not timestamp)
        assert events[0].version == 1
        assert events[1].version == 2
        assert events[2].version == 3
        
        # But verify timestamps are preserved
        assert events[0].created_at == timestamps[0]
        assert events[1].created_at == timestamps[1]
        assert events[2].created_at == timestamps[2]
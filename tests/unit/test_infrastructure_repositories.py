"""Unit tests for database repository implementations."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from app.domain.entities import Deck, DeckStatus, Slide, DeckEvent
from app.infrastructure.db.repositories import (
    PostgresDeckRepository,
    PostgresSlideRepository,
    PostgresEventRepository,
)
from app.infrastructure.db.models import DeckModel, SlideModel, DeckEventModel


class TestPostgresDeckRepository:
    """Test cases for PostgresDeckRepository."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def deck_repository(self, mock_session):
        """Create deck repository with mock session."""
        return PostgresDeckRepository(mock_session)

    @pytest.fixture
    def sample_deck(self, test_user_id):
        """Create sample deck entity."""
        return Deck(
            id=uuid4(),
            user_id=test_user_id,
            title="Test Presentation",
            status=DeckStatus.PENDING,
            version=1,
            deck_plan={"title": "Test", "slides": []},
        )

    @pytest.mark.asyncio
    async def test_create_success(self, deck_repository, mock_session, sample_deck):
        """Test successful deck creation."""
        mock_session.add = Mock()
        mock_session.flush = AsyncMock()

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await deck_repository.create(sample_deck)

        assert result == sample_deck
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_metrics.assert_called_with("create", "decks", "success")

        # Verify the model was created correctly
        call_args = mock_session.add.call_args[0][0]
        assert isinstance(call_args, DeckModel)
        assert call_args.id == sample_deck.id
        assert call_args.user_id == sample_deck.user_id
        assert call_args.title == sample_deck.title
        assert call_args.status == sample_deck.status.value

    @pytest.mark.asyncio
    async def test_create_database_error(
        self, deck_repository, mock_session, sample_deck
    ):
        """Test deck creation with database error."""
        mock_session.add = Mock()
        mock_session.flush = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            with pytest.raises(SQLAlchemyError):
                await deck_repository.create(sample_deck)

        mock_metrics.assert_called_with("create", "decks", "error")

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, deck_repository, mock_session, sample_deck):
        """Test getting deck by ID when found."""
        # Create mock database model
        mock_db_deck = Mock(spec=DeckModel)
        mock_db_deck.id = sample_deck.id
        mock_db_deck.user_id = sample_deck.user_id
        mock_db_deck.title = sample_deck.title
        mock_db_deck.status = DeckStatus.PENDING
        mock_db_deck.version = sample_deck.version
        mock_db_deck.deck_plan = sample_deck.deck_plan
        mock_db_deck.created_at = sample_deck.created_at
        mock_db_deck.updated_at = sample_deck.updated_at

        # Mock query result
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_db_deck
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await deck_repository.get_by_id(sample_deck.id)

        assert result is not None
        assert result.id == sample_deck.id
        assert result.user_id == sample_deck.user_id
        assert result.title == sample_deck.title
        assert result.status == DeckStatus.PENDING
        mock_metrics.assert_called_with("get", "decks", "success")

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, deck_repository, mock_session):
        """Test getting deck by ID when not found."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await deck_repository.get_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_database_error(self, deck_repository, mock_session):
        """Test getting deck by ID with database error."""
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            with pytest.raises(SQLAlchemyError):
                await deck_repository.get_by_id(uuid4())

        mock_metrics.assert_called_with("get", "decks", "error")

    @pytest.mark.asyncio
    async def test_get_by_user_id_success(
        self, deck_repository, mock_session, test_user_id
    ):
        """Test getting decks by user ID."""
        # Create mock database models
        mock_decks = []
        for i in range(3):
            mock_deck = Mock(spec=DeckModel)
            mock_deck.id = uuid4()
            mock_deck.user_id = test_user_id
            mock_deck.title = f"Deck {i+1}"
            mock_deck.status = DeckStatus.PENDING
            mock_deck.version = 1
            mock_deck.deck_plan = {}
            mock_deck.created_at = datetime.now()
            mock_deck.updated_at = datetime.now()
            mock_decks.append(mock_deck)

        # Mock query result
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_decks
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await deck_repository.get_by_user_id(
                test_user_id, limit=5, offset=0
            )

        assert len(result) == 3
        for i, deck in enumerate(result):
            assert deck.title == f"Deck {i+1}"
            assert deck.user_id == test_user_id

        mock_metrics.assert_called_with("list", "decks", "success")

    @pytest.mark.asyncio
    async def test_get_by_user_id_database_error(
        self, deck_repository, mock_session, test_user_id
    ):
        """Test getting decks by user ID with database error."""
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            with pytest.raises(SQLAlchemyError):
                await deck_repository.get_by_user_id(test_user_id)

        mock_metrics.assert_called_with("list", "decks", "error")

    @pytest.mark.asyncio
    async def test_update_success(self, deck_repository, mock_session, sample_deck):
        """Test successful deck update."""
        # Create mock database model
        mock_db_deck = Mock(spec=DeckModel)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_db_deck
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()

        # Update deck properties
        sample_deck.title = "Updated Title"
        sample_deck.status = DeckStatus.COMPLETED
        sample_deck.version = 2

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await deck_repository.update(sample_deck)

        assert result == sample_deck
        assert mock_db_deck.title == "Updated Title"
        assert mock_db_deck.status == DeckStatus.COMPLETED.value
        assert mock_db_deck.version == 2
        mock_session.flush.assert_called_once()
        mock_metrics.assert_called_with("update", "decks", "success")

    @pytest.mark.asyncio
    async def test_update_not_found(self, deck_repository, mock_session, sample_deck):
        """Test updating deck that doesn't exist."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            with pytest.raises(ValueError) as exc:
                await deck_repository.update(sample_deck)

        assert f"Deck with ID {sample_deck.id} not found" in str(exc.value)
        mock_metrics.assert_called_with("update", "decks", "not_found")

    @pytest.mark.asyncio
    async def test_update_database_error(
        self, deck_repository, mock_session, sample_deck
    ):
        """Test deck update with database error."""
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            with pytest.raises(SQLAlchemyError):
                await deck_repository.update(sample_deck)

        mock_metrics.assert_called_with("update", "decks", "error")

    @pytest.mark.asyncio
    async def test_delete_success(self, deck_repository, mock_session):
        """Test successful deck deletion."""
        deck_id = uuid4()
        mock_db_deck = Mock(spec=DeckModel)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_db_deck
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_session.flush = AsyncMock()

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await deck_repository.delete(deck_id)

        assert result is True
        mock_session.delete.assert_called_once_with(mock_db_deck)
        mock_session.flush.assert_called_once()
        mock_metrics.assert_called_with("delete", "decks", "success")

    @pytest.mark.asyncio
    async def test_delete_not_found(self, deck_repository, mock_session):
        """Test deleting deck that doesn't exist."""
        deck_id = uuid4()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await deck_repository.delete(deck_id)

        assert result is False
        mock_metrics.assert_called_with("delete", "decks", "not_found")

    @pytest.mark.asyncio
    async def test_delete_database_error(self, deck_repository, mock_session):
        """Test deck deletion with database error."""
        deck_id = uuid4()
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            with pytest.raises(SQLAlchemyError):
                await deck_repository.delete(deck_id)

        mock_metrics.assert_called_with("delete", "decks", "error")

    @pytest.mark.asyncio
    async def test_exists_true(self, deck_repository, mock_session):
        """Test deck existence check when deck exists."""
        deck_id = uuid4()
        mock_result = Mock()
        mock_result.scalar.return_value = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await deck_repository.exists(deck_id)

        assert result is True
        mock_metrics.assert_called_with("exists", "decks", "success")

    @pytest.mark.asyncio
    async def test_exists_false(self, deck_repository, mock_session):
        """Test deck existence check when deck doesn't exist."""
        deck_id = uuid4()
        mock_result = Mock()
        mock_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await deck_repository.exists(deck_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_database_error(self, deck_repository, mock_session):
        """Test deck existence check with database error."""
        deck_id = uuid4()
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            with pytest.raises(SQLAlchemyError):
                await deck_repository.exists(deck_id)

        mock_metrics.assert_called_with("exists", "decks", "error")

    @pytest.mark.asyncio
    async def test_is_owned_by_user_true(
        self, deck_repository, mock_session, test_user_id
    ):
        """Test ownership check when user owns deck."""
        deck_id = uuid4()
        mock_result = Mock()
        mock_result.scalar.return_value = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await deck_repository.is_owned_by_user(deck_id, test_user_id)

        assert result is True
        mock_metrics.assert_called_with("ownership_check", "decks", "success")

    @pytest.mark.asyncio
    async def test_is_owned_by_user_false(
        self, deck_repository, mock_session, test_user_id
    ):
        """Test ownership check when user doesn't own deck."""
        deck_id = uuid4()
        mock_result = Mock()
        mock_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await deck_repository.is_owned_by_user(deck_id, test_user_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_owned_by_user_database_error(
        self, deck_repository, mock_session, test_user_id
    ):
        """Test ownership check with database error."""
        deck_id = uuid4()
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            with pytest.raises(SQLAlchemyError):
                await deck_repository.is_owned_by_user(deck_id, test_user_id)

        mock_metrics.assert_called_with("ownership_check", "decks", "error")


class TestPostgresSlideRepository:
    """Test cases for PostgresSlideRepository."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def slide_repository(self, mock_session):
        """Create slide repository with mock session."""
        return PostgresSlideRepository(mock_session)

    @pytest.fixture
    def sample_slide(self):
        """Create sample slide entity."""
        return Slide(
            id=uuid4(),
            deck_id=uuid4(),
            slide_order=1,
            html_content="<h1>Test Slide</h1>",
            presenter_notes="Test notes",
        )

    @pytest.mark.asyncio
    async def test_create_success(self, slide_repository, mock_session, sample_slide):
        """Test successful slide creation."""
        mock_session.add = Mock()
        mock_session.flush = AsyncMock()

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await slide_repository.create(sample_slide)

        assert result == sample_slide
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_metrics.assert_called_with("create", "slides", "success")

        # Verify the model was created correctly
        call_args = mock_session.add.call_args[0][0]
        assert isinstance(call_args, SlideModel)
        assert call_args.id == sample_slide.id
        assert call_args.deck_id == sample_slide.deck_id
        assert call_args.slide_order == sample_slide.slide_order
        assert call_args.html_content == sample_slide.html_content

    @pytest.mark.asyncio
    async def test_create_database_error(
        self, slide_repository, mock_session, sample_slide
    ):
        """Test slide creation with database error."""
        mock_session.add = Mock()
        mock_session.flush = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            with pytest.raises(SQLAlchemyError):
                await slide_repository.create(sample_slide)

        mock_metrics.assert_called_with("create", "slides", "error")

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, slide_repository, mock_session, sample_slide):
        """Test getting slide by ID when found."""
        # Create mock database model
        mock_db_slide = Mock(spec=SlideModel)
        mock_db_slide.id = sample_slide.id
        mock_db_slide.deck_id = sample_slide.deck_id
        mock_db_slide.slide_order = sample_slide.slide_order
        mock_db_slide.html_content = sample_slide.html_content
        mock_db_slide.presenter_notes = sample_slide.presenter_notes
        mock_db_slide.created_at = sample_slide.created_at
        mock_db_slide.updated_at = sample_slide.updated_at

        # Mock query result
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_db_slide
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await slide_repository.get_by_id(sample_slide.id)

        assert result is not None
        assert result.id == sample_slide.id
        assert result.deck_id == sample_slide.deck_id
        assert result.slide_order == sample_slide.slide_order
        assert result.html_content == sample_slide.html_content
        mock_metrics.assert_called_with("get", "slides", "success")

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, slide_repository, mock_session):
        """Test getting slide by ID when not found."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await slide_repository.get_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_deck_id_success(self, slide_repository, mock_session):
        """Test getting slides by deck ID."""
        deck_id = uuid4()

        # Create mock database models
        mock_slides = []
        for i in range(3):
            mock_slide = Mock(spec=SlideModel)
            mock_slide.id = uuid4()
            mock_slide.deck_id = deck_id
            mock_slide.slide_order = i + 1
            mock_slide.html_content = f"<h1>Slide {i+1}</h1>"
            mock_slide.presenter_notes = f"Notes {i+1}"
            mock_slide.created_at = datetime.now()
            mock_slide.updated_at = datetime.now()
            mock_slides.append(mock_slide)

        # Mock query result
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_slides
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await slide_repository.get_by_deck_id(deck_id)

        assert len(result) == 3
        for i, slide in enumerate(result):
            assert slide.slide_order == i + 1
            assert slide.deck_id == deck_id

        mock_metrics.assert_called_with("list", "slides", "success")

    @pytest.mark.asyncio
    async def test_update_success(self, slide_repository, mock_session, sample_slide):
        """Test successful slide update."""
        # Create mock database model
        mock_db_slide = Mock(spec=SlideModel)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_db_slide
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()

        # Update slide properties
        sample_slide.html_content = "<h1>Updated Content</h1>"
        sample_slide.presenter_notes = "Updated notes"

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await slide_repository.update(sample_slide)

        assert result == sample_slide
        assert mock_db_slide.html_content == "<h1>Updated Content</h1>"
        assert mock_db_slide.presenter_notes == "Updated notes"
        mock_session.flush.assert_called_once()
        mock_metrics.assert_called_with("update", "slides", "success")

    @pytest.mark.asyncio
    async def test_update_not_found(self, slide_repository, mock_session, sample_slide):
        """Test updating slide that doesn't exist."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            with pytest.raises(ValueError) as exc:
                await slide_repository.update(sample_slide)

        assert f"Slide with ID {sample_slide.id} not found" in str(exc.value)
        mock_metrics.assert_called_with("update", "slides", "not_found")

    @pytest.mark.asyncio
    async def test_delete_success(self, slide_repository, mock_session):
        """Test successful slide deletion."""
        slide_id = uuid4()
        mock_db_slide = Mock(spec=SlideModel)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_db_slide
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_session.flush = AsyncMock()

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await slide_repository.delete(slide_id)

        assert result is True
        mock_session.delete.assert_called_once_with(mock_db_slide)
        mock_session.flush.assert_called_once()
        mock_metrics.assert_called_with("delete", "slides", "success")

    @pytest.mark.asyncio
    async def test_delete_not_found(self, slide_repository, mock_session):
        """Test deleting slide that doesn't exist."""
        slide_id = uuid4()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await slide_repository.delete(slide_id)

        assert result is False
        mock_metrics.assert_called_with("delete", "slides", "not_found")

    @pytest.mark.asyncio
    async def test_delete_by_deck_id_success(self, slide_repository, mock_session):
        """Test deleting all slides for a deck."""
        deck_id = uuid4()

        # Create mock slides
        mock_slides = [Mock(spec=SlideModel) for _ in range(3)]
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_slides
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_session.flush = AsyncMock()

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await slide_repository.delete_by_deck_id(deck_id)

        assert result == 3  # Number of deleted slides
        assert mock_session.delete.call_count == 3
        mock_session.flush.assert_called_once()
        mock_metrics.assert_called_with("delete_by_deck", "slides", "success")

    @pytest.mark.asyncio
    async def test_get_max_order_with_slides(self, slide_repository, mock_session):
        """Test getting max slide order when slides exist."""
        deck_id = uuid4()
        mock_result = Mock()
        mock_result.scalar.return_value = 5
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await slide_repository.get_max_order(deck_id)

        assert result == 5
        mock_metrics.assert_called_with("max_order", "slides", "success")

    @pytest.mark.asyncio
    async def test_get_max_order_no_slides(self, slide_repository, mock_session):
        """Test getting max slide order when no slides exist."""
        deck_id = uuid4()
        mock_result = Mock()
        mock_result.scalar.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await slide_repository.get_max_order(deck_id)

        assert result == 0


class TestPostgresEventRepository:
    """Test cases for PostgresEventRepository."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def event_repository(self, mock_session):
        """Create event repository with mock session."""
        return PostgresEventRepository(mock_session)

    @pytest.fixture
    def sample_event(self):
        """Create sample deck event entity."""
        return DeckEvent(
            deck_id=uuid4(),
            version=1,
            event_type="DeckStarted",
            payload={"title": "Test Deck"},
        )

    @pytest.mark.asyncio
    async def test_create_success(self, event_repository, mock_session, sample_event):
        """Test successful event creation."""
        # Create mock database model with generated ID
        mock_db_event = Mock(spec=DeckEventModel)
        mock_db_event.id = 123

        mock_session.add = Mock()
        mock_session.flush = AsyncMock()

        # Mock the add method to set the db model
        def mock_add(obj):
            obj.id = 123

        mock_session.add.side_effect = mock_add

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await event_repository.create(sample_event)

        assert result.id == 123  # ID should be set from database
        assert result.deck_id == sample_event.deck_id
        assert result.version == sample_event.version
        assert result.event_type == sample_event.event_type
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_metrics.assert_called_with("create", "deck_events", "success")

    @pytest.mark.asyncio
    async def test_create_database_error(
        self, event_repository, mock_session, sample_event
    ):
        """Test event creation with database error."""
        mock_session.add = Mock()
        mock_session.flush = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            with pytest.raises(SQLAlchemyError):
                await event_repository.create(sample_event)

        mock_metrics.assert_called_with("create", "deck_events", "error")

    @pytest.mark.asyncio
    async def test_get_by_deck_id_success(self, event_repository, mock_session):
        """Test getting events by deck ID."""
        deck_id = uuid4()

        # Create mock database models
        mock_events = []
        for i in range(3):
            mock_event = Mock(spec=DeckEventModel)
            mock_event.id = i + 1
            mock_event.deck_id = deck_id
            mock_event.version = i + 1
            mock_event.event_type = f"Event{i+1}"
            mock_event.payload = {"data": f"event{i+1}"}
            mock_event.created_at = datetime.now()
            mock_events.append(mock_event)

        # Mock query result
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_events
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await event_repository.get_by_deck_id(deck_id, from_version=0)

        assert len(result) == 3
        for i, event in enumerate(result):
            assert event.id == i + 1
            assert event.deck_id == deck_id
            assert event.version == i + 1

        mock_metrics.assert_called_with("list", "deck_events", "success")

    @pytest.mark.asyncio
    async def test_get_by_deck_id_with_from_version(
        self, event_repository, mock_session
    ):
        """Test getting events by deck ID with from_version filter."""
        deck_id = uuid4()

        # Should only return events with version > 2
        mock_events = []
        for i in range(2, 5):  # versions 3, 4, 5
            mock_event = Mock(spec=DeckEventModel)
            mock_event.id = i + 1
            mock_event.deck_id = deck_id
            mock_event.version = i + 1
            mock_event.event_type = f"Event{i+1}"
            mock_event.payload = {"data": f"event{i+1}"}
            mock_event.created_at = datetime.now()
            mock_events.append(mock_event)

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_events
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await event_repository.get_by_deck_id(deck_id, from_version=2)

        assert len(result) == 3
        for i, event in enumerate(result):
            assert event.version >= 3  # Should only have versions > 2

    @pytest.mark.asyncio
    async def test_get_by_deck_id_database_error(self, event_repository, mock_session):
        """Test getting events with database error."""
        deck_id = uuid4()
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            with pytest.raises(SQLAlchemyError):
                await event_repository.get_by_deck_id(deck_id)

        mock_metrics.assert_called_with("list", "deck_events", "error")

    @pytest.mark.asyncio
    async def test_get_latest_version_with_events(self, event_repository, mock_session):
        """Test getting latest version when events exist."""
        deck_id = uuid4()
        mock_result = Mock()
        mock_result.scalar.return_value = 5
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            result = await event_repository.get_latest_version(deck_id)

        assert result == 5
        mock_metrics.assert_called_with("latest_version", "deck_events", "success")

    @pytest.mark.asyncio
    async def test_get_latest_version_no_events(self, event_repository, mock_session):
        """Test getting latest version when no events exist."""
        deck_id = uuid4()
        mock_result = Mock()
        mock_result.scalar.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await event_repository.get_latest_version(deck_id)

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_latest_version_database_error(
        self, event_repository, mock_session
    ):
        """Test getting latest version with database error."""
        deck_id = uuid4()
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Database error"))

        with patch(
            "app.core.observability.metrics.record_database_operation"
        ) as mock_metrics:
            with pytest.raises(SQLAlchemyError):
                await event_repository.get_latest_version(deck_id)

        mock_metrics.assert_called_with("latest_version", "deck_events", "error")

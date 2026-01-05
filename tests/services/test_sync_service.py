"""Tests for sync service."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from kindle_sync.models import Book, Highlight, HighlightColor
from kindle_sync.services.sync_service import BookSyncDetail, SyncResult, SyncService


@pytest.fixture
def mock_auth_manager():
    """Create a mock auth manager."""
    auth = Mock()
    auth.is_authenticated.return_value = True
    auth.get_session.return_value = Mock()
    return auth


@pytest.fixture
def sample_books():
    """Create sample books for testing."""
    return [
        Book(
            asin="BOOK1",
            title="Test Book 1",
            author="Author 1",
            url="https://example.com/book1",
            image_url="https://example.com/img1.jpg",
            last_annotated_date=datetime(2023, 1, 1),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
        Book(
            asin="BOOK2",
            title="Test Book 2",
            author="Author 2",
            url="https://example.com/book2",
            image_url="https://example.com/img2.jpg",
            last_annotated_date=datetime(2023, 1, 2),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
    ]


@pytest.fixture
def sample_highlights_book1():
    """Create sample highlights for book 1."""
    return [
        Highlight(
            id="h1",
            book_asin="BOOK1",
            text="First highlight",
            location="100-110",
            page="10",
            color=HighlightColor.YELLOW,
            created_date=datetime(2023, 1, 1),
            created_at=datetime.now(),
        ),
        Highlight(
            id="h2",
            book_asin="BOOK1",
            text="Second highlight",
            location="200-210",
            page="20",
            color=HighlightColor.BLUE,
            created_date=datetime(2023, 1, 1),
            created_at=datetime.now(),
        ),
    ]


class TestSyncServiceNotAuthenticated:
    """Tests for sync when not authenticated."""

    def test_sync_not_authenticated(self, temp_db_path):
        """Test sync fails when not authenticated."""
        with patch("kindle_sync.services.sync_service.AuthManager") as MockAuth:
            mock_auth = Mock()
            mock_auth.is_authenticated.return_value = False
            MockAuth.return_value = mock_auth

            result = SyncService.sync(temp_db_path)

            assert result.success is False
            assert "Not authenticated" in result.message
            assert result.error is not None
            assert "Please login first" in result.error


class TestSyncServiceFullSync:
    """Tests for full sync operations."""

    def test_full_sync_success(
        self, temp_db_path, mock_auth_manager, sample_books, sample_highlights_book1
    ):
        """Test successful full sync."""
        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.KindleScraper") as MockScraper,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_scraper = Mock()
            mock_scraper.scrape_books.return_value = sample_books
            mock_scraper.scrape_highlights.side_effect = [
                sample_highlights_book1,
                [],  # No highlights for book 2
            ]
            MockScraper.return_value = mock_scraper

            result = SyncService.sync(temp_db_path)

            assert result.success is True
            assert result.books_synced == 2
            assert result.new_highlights == 2
            assert result.deleted_highlights == 0
            assert len(result.book_details) == 2
            assert result.book_details[0].new_highlights == 2
            assert result.book_details[0].total_highlights == 2

    def test_full_sync_no_books_found(self, temp_db_path, mock_auth_manager):
        """Test full sync when no books are found."""
        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.KindleScraper") as MockScraper,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_scraper = Mock()
            mock_scraper.scrape_books.return_value = []
            MockScraper.return_value = mock_scraper

            result = SyncService.sync(temp_db_path)

            assert result.success is True
            assert result.message == "No books found"
            assert result.books_synced == 0

    def test_full_sync_scraper_error(self, temp_db_path, mock_auth_manager):
        """Test full sync when scraper encounters an error."""
        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.KindleScraper") as MockScraper,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_scraper = Mock()
            mock_scraper.scrape_books.side_effect = Exception("Scraper error")
            MockScraper.return_value = mock_scraper

            result = SyncService.sync(temp_db_path)

            assert result.success is False
            assert "Sync failed" in result.message
            assert result.error is not None
            assert "Scraper error" in result.error

    def test_full_sync_with_progress_callback(
        self, temp_db_path, mock_auth_manager, sample_books, sample_highlights_book1
    ):
        """Test full sync with progress callback."""
        progress_messages = []

        def progress_callback(message: str):
            progress_messages.append(message)

        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.KindleScraper") as MockScraper,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_scraper = Mock()
            mock_scraper.scrape_books.return_value = sample_books
            mock_scraper.scrape_highlights.side_effect = [sample_highlights_book1, []]
            MockScraper.return_value = mock_scraper

            result = SyncService.sync(temp_db_path, progress_callback=progress_callback)

            assert result.success is True
            assert len(progress_messages) > 0
            assert "Fetching books from Amazon" in progress_messages[0]
            assert "Sync complete" in progress_messages[-1]


class TestSyncServiceSingleBook:
    """Tests for single book sync operations."""

    def test_sync_single_book_success(
        self, temp_db, mock_auth_manager, sample_books, sample_highlights_book1
    ):
        """Test successful single book sync."""
        # Pre-populate database with books
        for book in sample_books:
            temp_db.insert_book(book)

        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.KindleScraper") as MockScraper,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_scraper = Mock()
            mock_scraper.scrape_single_book.return_value = sample_books[0]
            mock_scraper.scrape_highlights.return_value = sample_highlights_book1
            MockScraper.return_value = mock_scraper

            result = SyncService.sync_single_book(temp_db.db_path, "BOOK1")

            assert result.success is True
            assert result.books_synced == 1
            assert result.book_details[0].asin == "BOOK1"

    def test_sync_single_book_not_found_on_amazon(self, temp_db, mock_auth_manager, sample_books):
        """Test single book sync when book is not found on Amazon."""
        for book in sample_books:
            temp_db.insert_book(book)

        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.KindleScraper") as MockScraper,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_scraper = Mock()
            mock_scraper.scrape_single_book.return_value = None
            MockScraper.return_value = mock_scraper

            result = SyncService.sync_single_book(temp_db.db_path, "NONEXISTENT")

            assert result.success is False
            assert "Book not found" in result.message

    def test_sync_single_book_not_in_database(
        self, temp_db, mock_auth_manager, sample_books, sample_highlights_book1
    ):
        """Test single book sync when book is not in database (adds it)."""
        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.KindleScraper") as MockScraper,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_scraper = Mock()
            mock_scraper.scrape_single_book.return_value = sample_books[0]
            mock_scraper.scrape_highlights.return_value = sample_highlights_book1
            MockScraper.return_value = mock_scraper

            result = SyncService.sync_single_book(temp_db.db_path, "BOOK1")

            assert result.success is True
            assert result.books_synced == 1
            assert result.new_highlights == 2

    def test_sync_single_book_with_progress_callback(
        self, temp_db, mock_auth_manager, sample_books, sample_highlights_book1
    ):
        """Test single book sync with progress callback."""
        progress_messages = []

        def progress_callback(message: str):
            progress_messages.append(message)

        for book in sample_books:
            temp_db.insert_book(book)

        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.KindleScraper") as MockScraper,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_scraper = Mock()
            mock_scraper.scrape_single_book.return_value = sample_books[0]
            mock_scraper.scrape_highlights.return_value = sample_highlights_book1
            MockScraper.return_value = mock_scraper

            result = SyncService.sync_single_book(
                temp_db.db_path, "BOOK1", progress_callback=progress_callback
            )

            assert result.success is True
            assert len(progress_messages) > 0


class TestSyncServiceHighlightUpdates:
    """Tests for highlight update operations during sync."""

    def test_sync_adds_new_highlights(
        self, temp_db, mock_auth_manager, sample_books, sample_highlights_book1
    ):
        """Test that new highlights are added during sync."""
        # Pre-populate with book and one highlight
        temp_db.insert_book(sample_books[0])
        temp_db.insert_highlight(sample_highlights_book1[0])

        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.KindleScraper") as MockScraper,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_scraper = Mock()
            mock_scraper.scrape_single_book.return_value = sample_books[0]
            # Return both highlights (one existing, one new)
            mock_scraper.scrape_highlights.return_value = sample_highlights_book1
            MockScraper.return_value = mock_scraper

            result = SyncService.sync_single_book(temp_db.db_path, "BOOK1")

            assert result.success is True
            assert result.new_highlights == 1  # Only one new highlight
            assert result.book_details[0].new_highlights == 1
            assert result.book_details[0].total_highlights == 2

    def test_sync_deletes_removed_highlights(
        self, temp_db, mock_auth_manager, sample_books, sample_highlights_book1
    ):
        """Test that deleted highlights are removed during sync."""
        # Pre-populate with book and both highlights
        temp_db.insert_book(sample_books[0])
        for highlight in sample_highlights_book1:
            temp_db.insert_highlight(highlight)

        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.KindleScraper") as MockScraper,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_scraper = Mock()
            mock_scraper.scrape_single_book.return_value = sample_books[0]
            # Return only first highlight (second was deleted)
            mock_scraper.scrape_highlights.return_value = [sample_highlights_book1[0]]
            MockScraper.return_value = mock_scraper

            result = SyncService.sync_single_book(temp_db.db_path, "BOOK1")

            assert result.success is True
            assert result.deleted_highlights == 1
            assert result.book_details[0].deleted_highlights == 1
            assert result.book_details[0].total_highlights == 1

    def test_sync_updates_existing_highlights(
        self, temp_db, mock_auth_manager, sample_books, sample_highlights_book1
    ):
        """Test that existing highlights are updated during sync (UPSERT)."""
        # Pre-populate with book and highlights
        temp_db.insert_book(sample_books[0])
        for highlight in sample_highlights_book1:
            temp_db.insert_highlight(highlight)

        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.KindleScraper") as MockScraper,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_scraper = Mock()
            mock_scraper.scrape_single_book.return_value = sample_books[0]
            # Return same highlights (no new, no deleted)
            mock_scraper.scrape_highlights.return_value = sample_highlights_book1
            MockScraper.return_value = mock_scraper

            result = SyncService.sync_single_book(temp_db.db_path, "BOOK1")

            assert result.success is True
            assert result.new_highlights == 0
            assert result.deleted_highlights == 0
            assert result.book_details[0].total_highlights == 2


class TestSyncServiceErrors:
    """Tests for error handling in sync service."""

    def test_sync_handles_scraper_errors(self, temp_db, mock_auth_manager, sample_books):
        """Test sync handles scraper errors gracefully."""
        temp_db.insert_book(sample_books[0])

        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.KindleScraper") as MockScraper,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_scraper = Mock()
            mock_scraper.scrape_single_book.return_value = sample_books[0]
            mock_scraper.scrape_highlights.side_effect = Exception("Network error")
            MockScraper.return_value = mock_scraper

            result = SyncService.sync_single_book(temp_db.db_path, "BOOK1")

            assert result.success is False
            assert "Sync failed" in result.message
            assert result.error is not None
            assert "Network error" in result.error

    def test_sync_handles_database_errors(self, temp_db_path, mock_auth_manager):
        """Test sync handles database errors gracefully."""
        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.DatabaseManager") as MockDB,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_db = Mock()
            mock_db.get_session.side_effect = Exception("Database error")
            MockDB.return_value = mock_db

            result = SyncService.sync(temp_db_path)

            assert result.success is False
            assert "Sync failed" in result.message


class TestSyncServiceMetadata:
    """Tests for sync metadata updates."""

    def test_sync_updates_last_sync_time(
        self, temp_db, mock_auth_manager, sample_books, sample_highlights_book1
    ):
        """Test that sync updates last sync timestamp."""
        temp_db.insert_book(sample_books[0])

        with (
            patch("kindle_sync.services.sync_service.AuthManager") as MockAuth,
            patch("kindle_sync.services.sync_service.KindleScraper") as MockScraper,
        ):
            MockAuth.return_value = mock_auth_manager

            mock_scraper = Mock()
            mock_scraper.scrape_single_book.return_value = sample_books[0]
            mock_scraper.scrape_highlights.return_value = sample_highlights_book1
            MockScraper.return_value = mock_scraper

            before_sync = datetime.now()
            result = SyncService.sync_single_book(temp_db.db_path, "BOOK1")
            after_sync = datetime.now()

            assert result.success is True

            # Verify last sync was updated
            last_sync = temp_db.get_last_sync()
            assert last_sync is not None
            assert before_sync <= last_sync <= after_sync


class TestBookSyncDetail:
    """Tests for BookSyncDetail dataclass."""

    def test_book_sync_detail_creation(self):
        """Test creating a BookSyncDetail."""
        detail = BookSyncDetail(
            asin="TEST123",
            title="Test Book",
            author="Test Author",
            new_highlights=5,
            deleted_highlights=2,
            total_highlights=10,
        )

        assert detail.asin == "TEST123"
        assert detail.title == "Test Book"
        assert detail.author == "Test Author"
        assert detail.new_highlights == 5
        assert detail.deleted_highlights == 2
        assert detail.total_highlights == 10


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_sync_result_defaults(self):
        """Test SyncResult default values."""
        result = SyncResult(success=True, message="Done")

        assert result.success is True
        assert result.message == "Done"
        assert result.books_synced == 0
        assert result.new_highlights == 0
        assert result.deleted_highlights == 0
        assert result.error is None
        assert result.book_details == []

    def test_sync_result_with_details(self):
        """Test SyncResult with book details."""
        details = [
            BookSyncDetail(
                asin="BOOK1",
                title="Book 1",
                author="Author 1",
                new_highlights=3,
                deleted_highlights=1,
                total_highlights=5,
            )
        ]

        result = SyncResult(
            success=True,
            message="Complete",
            books_synced=1,
            new_highlights=3,
            deleted_highlights=1,
            book_details=details,
        )

        assert result.books_synced == 1
        assert result.new_highlights == 3
        assert result.deleted_highlights == 1
        assert len(result.book_details) == 1
        assert result.book_details[0].asin == "BOOK1"

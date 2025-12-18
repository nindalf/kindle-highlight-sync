"""Tests for database operations."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from kindle_sync.database import DatabaseError, DatabaseManager
from kindle_sync.models import Book, Highlight, HighlightColor


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = DatabaseManager(db_path)
    db.init_schema()
    yield db
    db.close()

    # Clean up
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_book():
    """Create a sample book for testing."""
    return Book(
        asin="B01N5AX61W",
        title="Atomic Habits",
        author="James Clear",
        url="https://www.amazon.com/dp/B01N5AX61W",
        image_url="https://example.com/image.jpg",
        last_annotated_date=datetime(2023, 10, 15),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def sample_highlight():
    """Create a sample highlight for testing."""
    return Highlight(
        id="9f2e",
        book_asin="B01N5AX61W",
        text="You do not rise to the level of your goals.",
        location="254-267",
        page="12",
        note="Important concept",
        color=HighlightColor.YELLOW,
        created_date=datetime(2023, 10, 15),
        created_at=datetime.now(),
    )


class TestDatabaseManager:
    """Tests for DatabaseManager class."""

    def test_init_creates_directory(self):
        """Test that init creates parent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "subdir" / "test.db"
            db = DatabaseManager(str(db_path))
            db.init_schema()

            assert db_path.exists()
            assert db_path.parent.exists()
            db.close()

    def test_init_schema_creates_tables(self, temp_db):
        """Test that schema initialization creates all tables."""
        # Query sqlite_master to check tables exist
        cursor = temp_db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        assert "books" in tables
        assert "highlights" in tables
        assert "session" in tables
        assert "sync_metadata" in tables

    def test_foreign_keys_enabled(self, temp_db):
        """Test that foreign keys are enabled."""
        cursor = temp_db.conn.execute("PRAGMA foreign_keys")
        result = cursor.fetchone()
        assert result[0] == 1  # Foreign keys enabled


class TestSessionOperations:
    """Tests for session operations."""

    def test_save_and_get_session(self, temp_db):
        """Test saving and retrieving session data."""
        temp_db.save_session("test_key", "test_value")
        result = temp_db.get_session("test_key")
        assert result == "test_value"

    def test_get_nonexistent_session(self, temp_db):
        """Test getting non-existent session returns None."""
        result = temp_db.get_session("nonexistent")
        assert result is None

    def test_update_session(self, temp_db):
        """Test updating existing session value."""
        temp_db.save_session("key", "value1")
        temp_db.save_session("key", "value2")
        result = temp_db.get_session("key")
        assert result == "value2"

    def test_clear_session(self, temp_db):
        """Test clearing all session data."""
        temp_db.save_session("key1", "value1")
        temp_db.save_session("key2", "value2")
        temp_db.clear_session()

        assert temp_db.get_session("key1") is None
        assert temp_db.get_session("key2") is None


class TestBookOperations:
    """Tests for book CRUD operations."""

    def test_insert_book(self, temp_db, sample_book):
        """Test inserting a book."""
        temp_db.insert_book(sample_book)
        retrieved = temp_db.get_book(sample_book.asin)

        assert retrieved is not None
        assert retrieved.asin == sample_book.asin
        assert retrieved.title == sample_book.title
        assert retrieved.author == sample_book.author

    def test_insert_book_upsert(self, temp_db, sample_book):
        """Test that inserting same book updates it."""
        temp_db.insert_book(sample_book)

        # Update the book
        sample_book.title = "Updated Title"
        temp_db.insert_book(sample_book)

        retrieved = temp_db.get_book(sample_book.asin)
        assert retrieved.title == "Updated Title"

    def test_get_nonexistent_book(self, temp_db):
        """Test getting non-existent book returns None."""
        result = temp_db.get_book("NONEXISTENT")
        assert result is None

    def test_get_all_books(self, temp_db):
        """Test getting all books."""
        book1 = Book(
            asin="ASIN1",
            title="Book A",
            author="Author A",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        book2 = Book(
            asin="ASIN2",
            title="Book B",
            author="Author B",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        temp_db.insert_book(book1)
        temp_db.insert_book(book2)

        books = temp_db.get_all_books()
        assert len(books) == 2
        assert books[0].title == "Book A"  # Sorted by title
        assert books[1].title == "Book B"

    def test_book_exists(self, temp_db, sample_book):
        """Test checking if book exists."""
        assert not temp_db.book_exists(sample_book.asin)
        temp_db.insert_book(sample_book)
        assert temp_db.book_exists(sample_book.asin)

    def test_book_with_none_values(self, temp_db):
        """Test inserting book with None optional fields."""
        book = Book(
            asin="TEST123",
            title="Test Book",
            author="Test Author",
            url=None,
            image_url=None,
            last_annotated_date=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        temp_db.insert_book(book)
        retrieved = temp_db.get_book("TEST123")

        assert retrieved is not None
        assert retrieved.url is None
        assert retrieved.image_url is None
        assert retrieved.last_annotated_date is None


class TestHighlightOperations:
    """Tests for highlight CRUD operations."""

    def test_insert_highlight(self, temp_db, sample_book, sample_highlight):
        """Test inserting a highlight."""
        # Must insert book first due to foreign key
        temp_db.insert_book(sample_book)
        temp_db.insert_highlight(sample_highlight)

        highlights = temp_db.get_highlights(sample_book.asin)
        assert len(highlights) == 1
        assert highlights[0].id == sample_highlight.id
        assert highlights[0].text == sample_highlight.text

    def test_insert_highlight_upsert(self, temp_db, sample_book, sample_highlight):
        """Test that inserting same highlight updates it."""
        temp_db.insert_book(sample_book)
        temp_db.insert_highlight(sample_highlight)

        # Update the highlight
        sample_highlight.note = "Updated note"
        temp_db.insert_highlight(sample_highlight)

        highlights = temp_db.get_highlights(sample_book.asin)
        assert len(highlights) == 1
        assert highlights[0].note == "Updated note"

    def test_insert_highlight_without_book_fails(self, temp_db, sample_highlight):
        """Test that inserting highlight without book fails."""
        with pytest.raises(DatabaseError, match="Failed to insert highlight"):
            temp_db.insert_highlight(sample_highlight)

    def test_get_highlights_empty(self, temp_db, sample_book):
        """Test getting highlights for book with no highlights."""
        temp_db.insert_book(sample_book)
        highlights = temp_db.get_highlights(sample_book.asin)
        assert len(highlights) == 0

    def test_get_highlights_sorted_by_location(self, temp_db, sample_book):
        """Test that highlights are sorted by location."""
        temp_db.insert_book(sample_book)

        h1 = Highlight(
            id="id1",
            book_asin=sample_book.asin,
            text="Text 1",
            location="100-110",
            created_at=datetime.now(),
        )
        h2 = Highlight(
            id="id2",
            book_asin=sample_book.asin,
            text="Text 2",
            location="50-60",
            created_at=datetime.now(),
        )
        h3 = Highlight(
            id="id3",
            book_asin=sample_book.asin,
            text="Text 3",
            location="200-210",
            created_at=datetime.now(),
        )

        # Insert in random order
        temp_db.insert_highlight(h1)
        temp_db.insert_highlight(h3)
        temp_db.insert_highlight(h2)

        highlights = temp_db.get_highlights(sample_book.asin)
        assert len(highlights) == 3
        assert highlights[0].location == "50-60"
        assert highlights[1].location == "100-110"
        assert highlights[2].location == "200-210"

    def test_get_highlight_count(self, temp_db, sample_book, sample_highlight):
        """Test getting highlight count."""
        temp_db.insert_book(sample_book)
        assert temp_db.get_highlight_count(sample_book.asin) == 0

        temp_db.insert_highlight(sample_highlight)
        assert temp_db.get_highlight_count(sample_book.asin) == 1

    def test_highlight_exists(self, temp_db, sample_book, sample_highlight):
        """Test checking if highlight exists."""
        temp_db.insert_book(sample_book)
        assert not temp_db.highlight_exists(sample_highlight.id)

        temp_db.insert_highlight(sample_highlight)
        assert temp_db.highlight_exists(sample_highlight.id)

    def test_delete_highlights(self, temp_db, sample_book):
        """Test deleting highlights by IDs."""
        temp_db.insert_book(sample_book)

        h1 = Highlight(
            id="id1", book_asin=sample_book.asin, text="Text 1", created_at=datetime.now()
        )
        h2 = Highlight(
            id="id2", book_asin=sample_book.asin, text="Text 2", created_at=datetime.now()
        )
        h3 = Highlight(
            id="id3", book_asin=sample_book.asin, text="Text 3", created_at=datetime.now()
        )

        temp_db.insert_highlight(h1)
        temp_db.insert_highlight(h2)
        temp_db.insert_highlight(h3)

        # Delete two highlights
        temp_db.delete_highlights(["id1", "id3"])

        highlights = temp_db.get_highlights(sample_book.asin)
        assert len(highlights) == 1
        assert highlights[0].id == "id2"

    def test_delete_highlights_empty_list(self, temp_db):
        """Test that deleting empty list doesn't fail."""
        temp_db.delete_highlights([])  # Should not raise

    def test_cascade_delete_on_book_removal(self, temp_db, sample_book, sample_highlight):
        """Test that deleting book cascades to highlights."""
        temp_db.insert_book(sample_book)
        temp_db.insert_highlight(sample_highlight)

        # Manually delete book (not exposed in API, but testing FK constraint)
        temp_db.conn.execute("DELETE FROM books WHERE asin = ?", (sample_book.asin,))
        temp_db.conn.commit()

        # Highlight should be deleted too
        assert not temp_db.highlight_exists(sample_highlight.id)

    def test_highlight_with_none_values(self, temp_db, sample_book):
        """Test inserting highlight with None optional fields."""
        highlight = Highlight(
            id="test123",
            book_asin=sample_book.asin,
            text="Test text",
            location=None,
            page=None,
            note=None,
            color=None,
            created_date=None,
            created_at=datetime.now(),
        )

        temp_db.insert_book(sample_book)
        temp_db.insert_highlight(highlight)

        highlights = temp_db.get_highlights(sample_book.asin)
        assert len(highlights) == 1
        assert highlights[0].location is None
        assert highlights[0].color is None


class TestSyncMetadata:
    """Tests for sync metadata operations."""

    def test_get_last_sync_none(self, temp_db):
        """Test getting last sync when never synced."""
        result = temp_db.get_last_sync()
        assert result is None

    def test_set_and_get_last_sync(self, temp_db):
        """Test setting and getting last sync timestamp."""
        now = datetime.now()
        temp_db.set_last_sync(now)

        result = temp_db.get_last_sync()
        assert result is not None
        # Compare with some tolerance for datetime precision
        assert abs((result - now).total_seconds()) < 1


class TestSearchHighlights:
    """Tests for search functionality."""

    def test_search_empty_query(self, temp_db):
        """Test search with empty query."""
        results = temp_db.search_highlights("")
        assert results == []

    def test_search_in_text(self, temp_db, sample_book):
        """Test search matches highlight text."""
        temp_db.insert_book(sample_book)

        h1 = Highlight(
            id="h1",
            book_asin=sample_book.asin,
            text="The quick brown fox",
            created_at=datetime.now(),
        )
        h2 = Highlight(
            id="h2", book_asin=sample_book.asin, text="The lazy dog", created_at=datetime.now()
        )
        temp_db.insert_highlight(h1)
        temp_db.insert_highlight(h2)

        results = temp_db.search_highlights("fox")
        assert len(results) == 1
        assert results[0][0].text == "The quick brown fox"
        assert results[0][1].asin == sample_book.asin

    def test_search_in_notes(self, temp_db, sample_book):
        """Test search matches notes."""
        temp_db.insert_book(sample_book)

        h1 = Highlight(
            id="h1",
            book_asin=sample_book.asin,
            text="Some text",
            note="Important concept",
            created_at=datetime.now(),
        )
        temp_db.insert_highlight(h1)

        results = temp_db.search_highlights("concept")
        assert len(results) == 1
        assert results[0][0].note == "Important concept"

    def test_search_case_insensitive(self, temp_db, sample_book):
        """Test search is case insensitive."""
        temp_db.insert_book(sample_book)

        h1 = Highlight(
            id="h1",
            book_asin=sample_book.asin,
            text="The Quick Brown Fox",
            created_at=datetime.now(),
        )
        temp_db.insert_highlight(h1)

        results_lower = temp_db.search_highlights("fox")
        results_upper = temp_db.search_highlights("FOX")
        results_mixed = temp_db.search_highlights("Fox")

        assert len(results_lower) == 1
        assert len(results_upper) == 1
        assert len(results_mixed) == 1

    def test_search_with_book_filter(self, temp_db):
        """Test search filtered by book."""
        book1 = Book(
            asin="BOOK1",
            title="Book One",
            author="Author One",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        book2 = Book(
            asin="BOOK2",
            title="Book Two",
            author="Author Two",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        temp_db.insert_book(book1)
        temp_db.insert_book(book2)

        h1 = Highlight(
            id="h1", book_asin="BOOK1", text="Searchable text", created_at=datetime.now()
        )
        h2 = Highlight(
            id="h2", book_asin="BOOK2", text="Searchable text", created_at=datetime.now()
        )
        temp_db.insert_highlight(h1)
        temp_db.insert_highlight(h2)

        # Search all books
        results_all = temp_db.search_highlights("searchable")
        assert len(results_all) == 2

        # Search only book1
        results_book1 = temp_db.search_highlights("searchable", book_asin="BOOK1")
        assert len(results_book1) == 1
        assert results_book1[0][1].asin == "BOOK1"

    def test_search_no_results(self, temp_db, sample_book):
        """Test search with no matching results."""
        temp_db.insert_book(sample_book)

        h1 = Highlight(
            id="h1", book_asin=sample_book.asin, text="Some text", created_at=datetime.now()
        )
        temp_db.insert_highlight(h1)

        results = temp_db.search_highlights("nonexistent")
        assert results == []

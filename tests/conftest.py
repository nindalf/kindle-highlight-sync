"""Shared pytest fixtures for all tests."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from kindle_sync.database import DatabaseManager
from kindle_sync.models import Book, Highlight, HighlightColor


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Clean up
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_db(temp_db_path):
    """Create a temporary database for testing."""
    db = DatabaseManager(temp_db_path)
    db.init_schema()
    yield db
    db.close()


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
        color=HighlightColor.YELLOW,
        created_date=datetime(2023, 10, 15),
        note="Important concept about systems vs goals",
        created_at=datetime.now(),
    )

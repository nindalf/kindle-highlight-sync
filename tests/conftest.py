"""Shared pytest fixtures for all tests."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from kindle_sync.models import AmazonRegion, Book, Highlight, HighlightColor
from kindle_sync.services.database_service import DatabaseManager
from kindle_sync.services.scraper_service import KindleScraper


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_db(temp_db_path):
    """Create a temporary database for testing."""
    db = DatabaseManager(temp_db_path)
    db.init_schema()
    yield db
    db.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


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


@pytest.fixture
def sample_highlights():
    """Create sample highlights for testing."""
    return [
        Highlight(
            id="9f2e",
            book_asin="B01N5AX61W",
            text="You do not rise to the level of your goals.",
            location="254-267",
            page="12",
            note="Important concept",
            color=HighlightColor.YELLOW,
            created_date=datetime(2023, 10, 15),
            created_at=datetime.now(),
        ),
        Highlight(
            id="abc1",
            book_asin="B01N5AX61W",
            text="Habits are the compound interest of self-improvement.",
            location="300-310",
            page="15",
            note=None,
            color=HighlightColor.BLUE,
            created_date=datetime(2023, 10, 16),
            created_at=datetime.now(),
        ),
    ]


@pytest.fixture
def mock_db():
    """Create a mock database for testing."""
    return Mock()


@pytest.fixture
def mock_session():
    """Create a mock requests session for testing."""
    return Mock(spec=requests.Session)


@pytest.fixture
def scraper(mock_session):
    """Create a scraper with mock session for testing."""
    return KindleScraper(mock_session, AmazonRegion.GLOBAL)

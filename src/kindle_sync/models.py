"""Data models for Kindle Highlights Sync."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class HighlightColor(StrEnum):
    """Kindle highlight colors."""

    YELLOW = "yellow"
    BLUE = "blue"
    PINK = "pink"
    ORANGE = "orange"


class AmazonRegion(StrEnum):
    """Supported Amazon regions."""

    GLOBAL = "global"
    UK = "uk"
    GERMANY = "germany"
    JAPAN = "japan"
    INDIA = "india"
    SPAIN = "spain"
    ITALY = "italy"
    FRANCE = "france"


class ExportFormat(StrEnum):
    """Supported export formats."""

    MARKDOWN = "markdown"
    JSON = "json"
    CSV = "csv"


@dataclass
class Book:
    """Represents a Kindle book."""

    asin: str
    title: str
    author: str
    url: str | None = None
    image_url: str | None = None
    last_annotated_date: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Extended metadata fields
    purchase_date: datetime | None = None
    status: str | None = None  # Done, Started, Not Started, Abandoned
    format: str | None = None  # Paperback, eBook, Hardcover, Audiobook
    notes: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    reading_time: str | None = None  # Format: "HH:MM"
    genres: str | None = None  # Comma-separated genres
    shop_link: str | None = None  # Amazon or other shop link
    isbn: str | None = None
    classification: str | None = None  # Dewey decimal classification
    goodreads_link: str | None = None
    price_gbp: str | None = None  # Format: "£X.XX"
    price_inr: str | None = None  # Format: "₹X.XX"
    review: str | None = None  # User's review of the book
    star_rating: float | None = None  # Rating out of 5.0


@dataclass
class Highlight:
    """Represents a Kindle highlight."""

    id: str
    book_asin: str
    text: str
    location: str | None = None
    page: str | None = None
    note: str | None = None
    color: HighlightColor | None = None
    created_date: datetime | None = None
    created_at: datetime | None = None
    is_hidden: bool = False


@dataclass
class BookHighlights:
    """Combines a book with its highlights."""

    book: Book
    highlights: list[Highlight]


@dataclass
class RegionConfig:
    """Configuration for an Amazon region."""

    name: str
    hostname: str
    kindle_reader_url: str
    notebook_url: str


@dataclass
class BookWithHighlightCount:
    """Book with highlight count."""

    book: Book
    highlight_count: int


@dataclass
class SearchResult:
    """Search result with highlight and book."""

    highlight: Highlight
    book: Book

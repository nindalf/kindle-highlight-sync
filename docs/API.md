# API Documentation

## Overview

This document describes the public APIs of all modules in the Kindle Highlights Sync application. Each module is designed to be independently testable and composable.

## Table of Contents

1. [Models](#models)
2. [Database Module](#database-module)
3. [Authentication Module](#authentication-module)
4. [Scraper Module](#scraper-module)
5. [Exporter Module](#exporter-module)
6. [Configuration Module](#configuration-module)
7. [Utilities Module](#utilities-module)
8. [CLI Module](#cli-module)

---

## Models

**Module**: `kindle_sync.models`

### Data Classes

#### `Book`

Represents a Kindle book.

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Book:
    """Represents a Kindle book."""
    
    id: str
    """Fletcher-16 hash of lowercase title."""
    
    title: str
    """Book title."""
    
    author: str
    """Book author(s)."""
    
    asin: Optional[str] = None
    """Amazon Standard Identification Number."""
    
    url: Optional[str] = None
    """Amazon product page URL."""
    
    image_url: Optional[str] = None
    """Book cover image URL."""
    
    last_annotated_date: Optional[datetime] = None
    """Timestamp of last annotation."""
    
    created_at: Optional[datetime] = None
    """Database record creation timestamp."""
    
    updated_at: Optional[datetime] = None
    """Database record last update timestamp."""
```

**Example**:
```python
book = Book(
    id="3a7f",
    title="Atomic Habits",
    author="James Clear",
    asin="B01N5AX61W",
    url="https://www.amazon.com/dp/B01N5AX61W",
    last_annotated_date=datetime(2023, 10, 15, 14, 30)
)
```

---

#### `Highlight`

Represents a Kindle highlight/annotation.

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Highlight:
    """Represents a Kindle highlight."""
    
    id: str
    """Fletcher-16 hash of lowercase text."""
    
    book_id: str
    """Foreign key to Book.id."""
    
    text: str
    """The highlighted text content."""
    
    location: Optional[str] = None
    """Kindle location (e.g., '1234-1456')."""
    
    page: Optional[str] = None
    """Page number if available."""
    
    note: Optional[str] = None
    """User's note attached to highlight."""
    
    color: Optional[HighlightColor] = None
    """Highlight color."""
    
    created_date: Optional[datetime] = None
    """Timestamp when highlight was created."""
    
    created_at: Optional[datetime] = None
    """Database record creation timestamp."""
```

**Example**:
```python
highlight = Highlight(
    id="9f2e",
    book_id="3a7f",
    text="You do not rise to the level of your goals...",
    location="254-267",
    page="12",
    color=HighlightColor.YELLOW
)
```

---

#### `BookHighlights`

Combines a book with its highlights.

```python
from dataclasses import dataclass

@dataclass
class BookHighlights:
    """Combines a book with its highlights."""
    
    book: Book
    """The book object."""
    
    highlights: list[Highlight]
    """List of highlights for this book."""
```

---

### Enums

#### `HighlightColor`

Available highlight colors.

```python
from enum import Enum

class HighlightColor(Enum):
    """Kindle highlight colors."""
    
    YELLOW = "yellow"
    BLUE = "blue"
    PINK = "pink"
    ORANGE = "orange"
```

---

#### `AmazonRegion`

Supported Amazon regions.

```python
from enum import Enum

class AmazonRegion(Enum):
    """Supported Amazon regions."""
    
    GLOBAL = "global"
    UK = "uk"
    GERMANY = "germany"
    JAPAN = "japan"
    INDIA = "india"
    SPAIN = "spain"
    ITALY = "italy"
    FRANCE = "france"
```

---

#### `ExportFormat`

Supported export formats.

```python
from enum import Enum

class ExportFormat(Enum):
    """Supported export formats."""
    
    MARKDOWN = "markdown"
    JSON = "json"
    CSV = "csv"
```

---

### Configuration Types

#### `RegionConfig`

Configuration for an Amazon region.

```python
from dataclasses import dataclass

@dataclass
class RegionConfig:
    """Configuration for an Amazon region."""
    
    name: str
    """Human-readable region name."""
    
    hostname: str
    """Amazon hostname (e.g., 'amazon.com')."""
    
    kindle_reader_url: str
    """Kindle reader base URL."""
    
    notebook_url: str
    """Kindle notebook URL for scraping."""
```

---

## Database Module

**Module**: `kindle_sync.database`

### `DatabaseManager`

Main class for database operations.

```python
class DatabaseManager:
    """Manages SQLite database operations."""
    
    def __init__(self, db_path: str) -> None:
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
    
    def init_schema(self) -> None:
        """Create database schema if it doesn't exist."""
    
    def close(self) -> None:
        """Close database connection."""
```

---

### Book Operations

```python
class DatabaseManager:
    
    def insert_book(self, book: Book) -> None:
        """
        Insert or update a book.
        
        Uses UPSERT logic - if book exists, updates it.
        
        Args:
            book: Book object to insert
            
        Raises:
            DatabaseError: If insertion fails
        """
    
    def get_book(self, book_id: str) -> Optional[Book]:
        """
        Get a book by ID.
        
        Args:
            book_id: Book ID (Fletcher-16 hash)
            
        Returns:
            Book object if found, None otherwise
        """
    
    def get_all_books(self) -> list[Book]:
        """
        Get all books from database.
        
        Returns:
            List of Book objects, ordered by title
        """
    
    def delete_book(self, book_id: str) -> None:
        """
        Delete a book and all its highlights (CASCADE).
        
        Args:
            book_id: Book ID to delete
        """
    
    def book_exists(self, book_id: str) -> bool:
        """
        Check if a book exists.
        
        Args:
            book_id: Book ID to check
            
        Returns:
            True if book exists, False otherwise
        """
```

**Example Usage**:
```python
db = DatabaseManager("~/.kindle-sync/highlights.db")
db.init_schema()

# Insert a book
book = Book(id="3a7f", title="Atomic Habits", author="James Clear")
db.insert_book(book)

# Get a book
book = db.get_book("3a7f")

# Get all books
books = db.get_all_books()
```

---

### Highlight Operations

```python
class DatabaseManager:
    
    def insert_highlights(self, highlights: list[Highlight]) -> int:
        """
        Batch insert highlights.
        
        Ignores duplicates (based on highlight ID).
        
        Args:
            highlights: List of Highlight objects
            
        Returns:
            Number of highlights inserted (excluding duplicates)
        """
    
    def get_highlights(self, book_id: str) -> list[Highlight]:
        """
        Get all highlights for a book.
        
        Args:
            book_id: Book ID
            
        Returns:
            List of Highlight objects, ordered by location
        """
    
    def get_all_highlights(self) -> list[Highlight]:
        """
        Get all highlights from database.
        
        Returns:
            List of Highlight objects
        """
    
    def get_book_with_highlights(self, book_id: str) -> Optional[BookHighlights]:
        """
        Get a book with all its highlights.
        
        Args:
            book_id: Book ID
            
        Returns:
            BookHighlights object if book found, None otherwise
        """
    
    def delete_highlights(self, book_id: str) -> None:
        """
        Delete all highlights for a book.
        
        Args:
            book_id: Book ID
        """
```

**Example Usage**:
```python
# Insert highlights
highlights = [
    Highlight(id="h1", book_id="3a7f", text="First highlight"),
    Highlight(id="h2", book_id="3a7f", text="Second highlight")
]
count = db.insert_highlights(highlights)
print(f"Inserted {count} highlights")

# Get highlights for a book
highlights = db.get_highlights("3a7f")

# Get book with highlights
book_highlights = db.get_book_with_highlights("3a7f")
```

---

### Session Operations

```python
class DatabaseManager:
    
    def save_session(self, key: str, value: str) -> None:
        """
        Save session data.
        
        Args:
            key: Session key
            value: Session value (typically JSON string)
        """
    
    def get_session(self, key: str) -> Optional[str]:
        """
        Get session data.
        
        Args:
            key: Session key
            
        Returns:
            Session value if found, None otherwise
        """
    
    def clear_session(self) -> None:
        """Clear all session data."""
```

**Example Usage**:
```python
# Save cookies
cookies_json = json.dumps({"cookies": [...]})
db.save_session("cookies", cookies_json)

# Load cookies
cookies_json = db.get_session("cookies")
cookies = json.loads(cookies_json) if cookies_json else None

# Clear session (logout)
db.clear_session()
```

---

### Sync Metadata Operations

```python
class DatabaseManager:
    
    def get_last_sync(self) -> Optional[datetime]:
        """
        Get last successful sync timestamp.
        
        Returns:
            Datetime of last sync, or None if never synced
        """
    
    def set_last_sync(self, timestamp: datetime) -> None:
        """
        Set last sync timestamp.
        
        Args:
            timestamp: Sync timestamp
        """
    
    def get_sync_metadata(self, key: str) -> Optional[str]:
        """
        Get sync metadata value.
        
        Args:
            key: Metadata key
            
        Returns:
            Metadata value if found, None otherwise
        """
    
    def set_sync_metadata(self, key: str, value: str) -> None:
        """
        Set sync metadata value.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
```

---

## Authentication Module

**Module**: `kindle_sync.auth`

### `AuthManager`

Manages Amazon authentication and session cookies.

```python
class AuthManager:
    """Manages Amazon authentication and session management."""
    
    def __init__(self, db: DatabaseManager, region: AmazonRegion) -> None:
        """
        Initialize auth manager.
        
        Args:
            db: Database manager instance
            region: Amazon region to authenticate with
        """
    
    def is_authenticated(self) -> bool:
        """
        Check if user has valid session.
        
        Returns:
            True if authenticated, False otherwise
        """
    
    def login(self, headless: bool = False, timeout: int = 60) -> bool:
        """
        Perform Amazon login using Selenium.
        
        Opens a browser window for user to log in. Waits for successful
        login by detecting URL change to Kindle reader.
        
        Args:
            headless: Run browser in headless mode
            timeout: Login timeout in seconds
            
        Returns:
            True if login successful, False otherwise
            
        Raises:
            AuthenticationError: If login fails or times out
        """
    
    def logout(self) -> None:
        """Clear stored session cookies."""
    
    def get_session(self) -> requests.Session:
        """
        Get requests.Session with stored cookies.
        
        Returns:
            Configured requests.Session
            
        Raises:
            AuthenticationError: If not authenticated
        """
    
    def validate_session(self) -> bool:
        """
        Validate that stored session is still active.
        
        Makes a test request to notebook URL.
        
        Returns:
            True if session valid, False otherwise
        """
```

**Example Usage**:
```python
from kindle_sync.auth import AuthManager
from kindle_sync.database import DatabaseManager
from kindle_sync.models import AmazonRegion

db = DatabaseManager("~/.kindle-sync/highlights.db")
auth = AuthManager(db, AmazonRegion.GLOBAL)

# Check if already authenticated
if not auth.is_authenticated():
    # Perform login
    success = auth.login(headless=False)
    if not success:
        print("Login failed")
        exit(1)

# Get authenticated session
session = auth.get_session()

# Use session for scraping
response = session.get("https://read.amazon.com/notebook")
```

---

### Internal Methods

```python
class AuthManager:
    
    def _launch_browser_login(self, headless: bool, timeout: int) -> dict:
        """
        Launch Selenium browser for login.
        
        Returns:
            Dictionary of cookies
        """
    
    def _save_cookies(self, cookies: dict) -> None:
        """Save cookies to database."""
    
    def _load_cookies(self) -> Optional[dict]:
        """Load cookies from database."""
    
    def _cookies_to_session(self, cookies: dict, session: requests.Session) -> None:
        """Add cookies to requests.Session."""
```

---

## Scraper Module

**Module**: `kindle_sync.scraper`

### `KindleScraper`

Scrapes books and highlights from Amazon.

```python
class KindleScraper:
    """Scrapes Kindle books and highlights from Amazon."""
    
    def __init__(self, session: requests.Session, region: AmazonRegion) -> None:
        """
        Initialize scraper.
        
        Args:
            session: Authenticated requests.Session
            region: Amazon region for scraping
        """
    
    def scrape_books(self) -> list[Book]:
        """
        Scrape all books from notebook page.
        
        Returns:
            List of Book objects
            
        Raises:
            ScraperError: If scraping fails
            AuthenticationError: If session expired
        """
    
    def scrape_highlights(self, book: Book) -> list[Highlight]:
        """
        Scrape all highlights for a book.
        
        Handles pagination automatically.
        
        Args:
            book: Book to scrape highlights for
            
        Returns:
            List of Highlight objects
            
        Raises:
            ScraperError: If scraping fails
        """
    
    def scrape_all(self) -> list[BookHighlights]:
        """
        Scrape all books and their highlights.
        
        Convenience method that calls scrape_books() then
        scrape_highlights() for each book.
        
        Returns:
            List of BookHighlights objects
        """
```

**Example Usage**:
```python
from kindle_sync.scraper import KindleScraper
from kindle_sync.auth import AuthManager

# Get authenticated session
auth = AuthManager(db, AmazonRegion.GLOBAL)
session = auth.get_session()

# Create scraper
scraper = KindleScraper(session, AmazonRegion.GLOBAL)

# Scrape all books
books = scraper.scrape_books()
print(f"Found {len(books)} books")

# Scrape highlights for a specific book
highlights = scraper.scrape_highlights(books[0])
print(f"Found {len(highlights)} highlights")

# Scrape everything
all_data = scraper.scrape_all()
for book_highlights in all_data:
    print(f"{book_highlights.book.title}: {len(book_highlights.highlights)} highlights")
```

---

### Internal Methods

```python
class KindleScraper:
    
    def _fetch_page(self, url: str) -> BeautifulSoup:
        """Fetch and parse a page."""
    
    def _parse_book_element(self, element: BeautifulSoup) -> Book:
        """Parse a single book HTML element."""
    
    def _parse_highlight_element(self, element: BeautifulSoup, book_id: str) -> Highlight:
        """Parse a single highlight HTML element."""
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse Amazon date string (region-aware)."""
    
    def _extract_pagination_token(self, soup: BeautifulSoup) -> Optional[tuple[str, str]]:
        """Extract next page token and state."""
```

---

## Exporter Module

**Module**: `kindle_sync.exporter`

### `Exporter`

Exports highlights to various formats.

```python
class Exporter:
    """Exports highlights to various formats."""
    
    def __init__(
        self,
        db: DatabaseManager,
        templates_dir: Optional[str] = None
    ) -> None:
        """
        Initialize exporter.
        
        Args:
            db: Database manager instance
            templates_dir: Custom templates directory (optional)
        """
    
    def export_all(
        self,
        output_dir: str,
        format: ExportFormat = ExportFormat.MARKDOWN,
        template_name: str = "default",
        overwrite: bool = False
    ) -> list[str]:
        """
        Export all books to files.
        
        Args:
            output_dir: Directory to write files to
            format: Export format
            template_name: Template name (for Markdown)
            overwrite: Overwrite existing files
            
        Returns:
            List of created file paths
            
        Raises:
            ExportError: If export fails
        """
    
    def export_book(
        self,
        book_id: str,
        output_path: str,
        format: ExportFormat = ExportFormat.MARKDOWN,
        template_name: str = "default"
    ) -> str:
        """
        Export a single book.
        
        Args:
            book_id: Book ID to export
            output_path: Output file path
            format: Export format
            template_name: Template name (for Markdown)
            
        Returns:
            Created file path
            
        Raises:
            ExportError: If export fails
            ValueError: If book not found
        """
```

**Example Usage**:
```python
from kindle_sync.exporter import Exporter, ExportFormat

exporter = Exporter(db)

# Export all books to Markdown
files = exporter.export_all(
    output_dir="./my-highlights",
    format=ExportFormat.MARKDOWN,
    template_name="default"
)
print(f"Exported {len(files)} files")

# Export specific book to JSON
exporter.export_book(
    book_id="3a7f",
    output_path="./atomic-habits.json",
    format=ExportFormat.JSON
)
```

---

### Template Rendering

```python
class Exporter:
    
    def _render_markdown(
        self,
        book: Book,
        highlights: list[Highlight],
        template_name: str
    ) -> str:
        """
        Render book to Markdown using Jinja2.
        
        Args:
            book: Book object
            highlights: List of highlights
            template_name: Template name
            
        Returns:
            Rendered Markdown string
        """
    
    def _render_json(
        self,
        book: Book,
        highlights: list[Highlight]
    ) -> str:
        """
        Render book to JSON.
        
        Returns:
            JSON string
        """
    
    def _render_csv(
        self,
        book: Book,
        highlights: list[Highlight]
    ) -> str:
        """
        Render book to CSV.
        
        Returns:
            CSV string
        """
```

---

### Filename Generation

```python
class Exporter:
    
    def _generate_filename(
        self,
        book: Book,
        format: ExportFormat
    ) -> str:
        """
        Generate filename for book export.
        
        Format: {author_last_name}-{title_slug}.{ext}
        
        Args:
            book: Book object
            format: Export format
            
        Returns:
            Filename string
        """
```

---

## Configuration Module

**Module**: `kindle_sync.config`

### `Config`

Application configuration constants.

```python
class Config:
    """Application configuration."""
    
    # Region configurations
    REGIONS: dict[AmazonRegion, RegionConfig]
    
    # Default settings
    DEFAULT_REGION: AmazonRegion = AmazonRegion.GLOBAL
    DEFAULT_DB_PATH: str = "~/.kindle-sync/highlights.db"
    DEFAULT_EXPORT_DIR: str = "~/.kindle-sync/exports"
    DEFAULT_TEMPLATE: str = "default"
    
    # Browser settings
    BROWSER_TIMEOUT: int = 60
    BROWSER_IMPLICIT_WAIT: int = 10
    BROWSER_HEADLESS: bool = False
    
    # Scraping settings
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 2
    RETRY_BACKOFF: int = 2
    
    # User agent
    USER_AGENT: str = "Mozilla/5.0 ..."
    
    @classmethod
    def get_region_config(cls, region: AmazonRegion) -> RegionConfig:
        """Get configuration for a region."""
    
    @classmethod
    def expand_path(cls, path: str) -> str:
        """Expand ~ in paths."""
```

**Example Usage**:
```python
from kindle_sync.config import Config
from kindle_sync.models import AmazonRegion

# Get region config
region_config = Config.get_region_config(AmazonRegion.UK)
print(region_config.notebook_url)  # https://read.amazon.co.uk/notebook

# Get default paths
db_path = Config.expand_path(Config.DEFAULT_DB_PATH)
```

---

## Utilities Module

**Module**: `kindle_sync.utils`

### Hash Functions

```python
def fletcher16(text: str) -> str:
    """
    Generate Fletcher-16 checksum for text.
    
    Args:
        text: Input text (will be lowercased)
        
    Returns:
        4-character hexadecimal string
        
    Example:
        >>> fletcher16("Atomic Habits")
        "3a7f"
    """
```

---

### String Utilities

```python
def slugify(text: str, max_length: int = 50) -> str:
    """
    Convert text to URL-safe slug.
    
    Args:
        text: Input text
        max_length: Maximum slug length
        
    Returns:
        Slugified string
        
    Example:
        >>> slugify("The Pragmatic Programmer")
        "the-pragmatic-programmer"
    """

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.
    
    Args:
        filename: Input filename
        
    Returns:
        Sanitized filename
    """

def extract_author_last_name(author: str) -> str:
    """
    Extract last name from author string.
    
    Handles multiple authors and various formats.
    
    Args:
        author: Author string (e.g., "James Clear" or "Hunt & Thomas")
        
    Returns:
        Last name (e.g., "Clear" or "Hunt-Thomas")
    """
```

---

### Date Utilities

```python
def parse_amazon_date(
    date_str: str,
    region: AmazonRegion
) -> datetime:
    """
    Parse Amazon date string (region-aware).
    
    Args:
        date_str: Date string from Amazon
        region: Amazon region for locale
        
    Returns:
        Parsed datetime object
        
    Example:
        >>> parse_amazon_date("Sunday October 24, 2021", AmazonRegion.GLOBAL)
        datetime(2021, 10, 24, 0, 0)
    """

def format_date(dt: datetime, format: str = "iso") -> str:
    """
    Format datetime for display.
    
    Args:
        dt: Datetime to format
        format: Format type ("iso", "human", "short")
        
    Returns:
        Formatted string
    """
```

---

### Retry Decorator

```python
from typing import Callable, TypeVar

T = TypeVar('T')

def retry(
    max_attempts: int = 3,
    delay: int = 2,
    backoff: int = 2,
    exceptions: tuple = (Exception,)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum retry attempts
        delay: Initial delay in seconds
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch
        
    Returns:
        Decorated function
        
    Example:
        @retry(max_attempts=3, delay=1, backoff=2)
        def fetch_data():
            return requests.get(url)
    """
```

---

## CLI Module

**Module**: `kindle_sync.cli`

### Main CLI Function

```python
import click

@click.group()
@click.option("--db", default=None, help="Database path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode")
@click.version_option(version="0.1.0")
@click.pass_context
def main(ctx: click.Context, db: str, verbose: bool, quiet: bool) -> None:
    """Kindle Highlights Sync - Sync and export Kindle highlights."""
```

---

### Commands

#### `login`

```python
@main.command()
@click.option("--region", default="global", help="Amazon region")
@click.option("--headless/--no-headless", default=False, help="Headless browser")
@click.pass_context
def login(ctx: click.Context, region: str, headless: bool) -> None:
    """Authenticate with Amazon and save session."""
```

#### `sync`

```python
@main.command()
@click.option("--full", is_flag=True, help="Full sync (all books)")
@click.option("--books", default=None, help="Comma-separated book IDs")
@click.pass_context
def sync(ctx: click.Context, full: bool, books: str) -> None:
    """Sync books and highlights from Amazon."""
```

#### `export`

```python
@main.command()
@click.argument("output_dir", required=False)
@click.option("--format", default="markdown", help="Export format")
@click.option("--template", default="default", help="Template name")
@click.option("--books", default=None, help="Comma-separated book IDs")
@click.pass_context
def export(
    ctx: click.Context,
    output_dir: str,
    format: str,
    template: str,
    books: str
) -> None:
    """Export highlights to files."""
```

#### `list`

```python
@main.command()
@click.option("--format", default="table", help="Output format")
@click.option("--sort", default="title", help="Sort by (title, author, date)")
@click.pass_context
def list_books(ctx: click.Context, format: str, sort: str) -> None:
    """List all books in database."""
```

#### `show`

```python
@main.command()
@click.argument("book_id")
@click.pass_context
def show(ctx: click.Context, book_id: str) -> None:
    """Show details of a specific book."""
```

#### `logout`

```python
@main.command()
@click.pass_context
def logout(ctx: click.Context) -> None:
    """Clear stored session."""
```

#### `status`

```python
@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show sync status and statistics."""
```

---

## Error Handling

### Exception Hierarchy

```python
class KindleSyncError(Exception):
    """Base exception for all kindle-sync errors."""
    
    def __init__(
        self,
        message: str,
        code: str,
        details: Optional[dict] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(KindleSyncError):
    """Authentication-related errors."""
    pass


class ScraperError(KindleSyncError):
    """Scraping-related errors."""
    pass


class DatabaseError(KindleSyncError):
    """Database-related errors."""
    pass


class ExportError(KindleSyncError):
    """Export-related errors."""
    pass


class ConfigurationError(KindleSyncError):
    """Configuration-related errors."""
    pass
```

---

## Type Hints

All modules use comprehensive type hints:

```python
from typing import Optional, List, Dict, Union, Callable
from datetime import datetime
import requests

def scrape_books(session: requests.Session, region: AmazonRegion) -> List[Book]:
    """Type-hinted function signature."""
    pass
```

Run type checking with:
```bash
mypy src/kindle_sync
```

---

## Testing Support

### Test Fixtures

```python
# tests/conftest.py

import pytest
from kindle_sync.database import DatabaseManager
from kindle_sync.models import Book, Highlight

@pytest.fixture
def temp_db() -> DatabaseManager:
    """Temporary test database."""
    pass

@pytest.fixture
def sample_book() -> Book:
    """Sample book for testing."""
    pass

@pytest.fixture
def sample_highlights() -> List[Highlight]:
    """Sample highlights for testing."""
    pass
```

---

## Best Practices

### Context Managers

Use context managers for resources:

```python
from contextlib import contextmanager

@contextmanager
def database_connection(db_path: str):
    """Context manager for database connection."""
    db = DatabaseManager(db_path)
    db.init_schema()
    try:
        yield db
    finally:
        db.close()


# Usage
with database_connection("highlights.db") as db:
    books = db.get_all_books()
```

---

## Performance Considerations

### Batch Operations

Prefer batch operations over individual inserts:

```python
# Good - batch insert
db.insert_highlights(all_highlights)

# Bad - individual inserts
for highlight in all_highlights:
    db.insert_highlight(highlight)
```

### Connection Pooling

Reuse database connections:

```python
# Create once
db = DatabaseManager(db_path)

# Use multiple times
db.insert_book(book1)
db.insert_book(book2)

# Close when done
db.close()
```

---

**End of API Documentation**

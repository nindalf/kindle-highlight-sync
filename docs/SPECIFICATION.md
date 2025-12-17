# Kindle Highlights Sync - Technical Specification

**Version:** 0.1.0  
**Status:** Draft  
**Last Updated:** 2025-12-17

## Table of Contents

1. [Overview](#overview)
2. [Goals and Non-Goals](#goals-and-non-goals)
3. [Architecture](#architecture)
4. [Data Models](#data-models)
5. [Module Specifications](#module-specifications)
6. [Database Schema](#database-schema)
7. [Authentication Flow](#authentication-flow)
8. [Scraping Strategy](#scraping-strategy)
9. [Export Formats](#export-formats)
10. [CLI Interface](#cli-interface)
11. [Error Handling](#error-handling)
12. [Security Considerations](#security-considerations)
13. [Testing Strategy](#testing-strategy)
14. [Development Workflow](#development-workflow)

---

## Overview

**Kindle Highlights Sync** is a Python-based command-line tool that automates the process of downloading Kindle highlights from Amazon's website and storing them in a local SQLite database. It provides export functionality to various formats including Markdown, JSON, and CSV.

### Problem Statement

Amazon Kindle users accumulate highlights across many books, but accessing them requires:
- Logging into Amazon's website
- Navigating through a web interface
- No offline access
- Limited export options
- No programmatic access

This tool solves these problems by providing:
- One-time authentication with session persistence
- Automatic sync of all books and highlights
- Local database storage for offline access
- Multiple export formats
- Simple CLI interface

### Inspiration

This project is inspired by [obsidian-kindle-plugin](https://github.com/hadynz/obsidian-kindle-plugin), which provides similar functionality for Obsidian users. This implementation creates a standalone, simpler version focused on core sync and export functionality.

---

## Goals and Non-Goals

### Goals

1. **Authentication**: Securely authenticate with Amazon and persist session cookies
2. **Data Collection**: Scrape all books and highlights from Amazon Kindle notebook
3. **Local Storage**: Store data in SQLite database with proper schema
4. **Export**: Export highlights to multiple formats (Markdown, JSON, CSV)
5. **Incremental Sync**: Support syncing only new/updated books
6. **Multi-Region**: Support Amazon regions (US, UK, Germany, Japan, etc.)
7. **CLI Interface**: Provide intuitive command-line interface
8. **Robustness**: Handle network errors, pagination, and session expiration

### Non-Goals

1. **GUI**: No graphical user interface (CLI only for MVP)
2. **Cloud Sync**: No cloud storage integration
3. **Mobile App**: No mobile application
4. **Book Purchase**: No integration with book purchasing
5. **Annotation Editing**: No editing of highlights (read-only)
6. **Social Features**: No sharing or collaboration features
7. **My Clippings Import**: Not supporting offline `My Clippings.txt` in MVP

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                           │
│                      (click commands)                       │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────┴───────────────────────────────────────────┐
│                    Application Layer                        │
│  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   Auth    │  │ Scraper  │  │ Database │  │ Exporter │  │
│  │  Manager  │  │          │  │  Manager │  │          │  │
│  └───────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────┴───────────────────────────────────────────┐
│                     Data Layer                              │
│  ┌──────────────────┐         ┌────────────────────────┐   │
│  │  SQLite Database │         │   File System          │   │
│  │  - Books         │         │   - Exports            │   │
│  │  - Highlights    │         │   - Templates          │   │
│  │  - Sessions      │         │   - Config             │   │
│  └──────────────────┘         └────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Module Structure

```
kindle_sync/
├── __init__.py           # Package initialization
├── cli.py                # CLI commands and entry point
├── auth.py               # Authentication and session management
├── scraper.py            # Web scraping logic
├── database.py           # Database operations
├── exporter.py           # Export functionality
├── models.py             # Data models and types
├── config.py             # Configuration management
├── utils.py              # Utility functions
└── templates/            # Export templates
    ├── default.md.j2     # Default Markdown template
    ├── simple.md.j2      # Simple Markdown template
    └── detailed.md.j2    # Detailed Markdown template
```

### Technology Stack

- **Language**: Python 3.10+
- **Package Manager**: uv
- **Web Automation**: Selenium 4.x
- **HTML Parsing**: BeautifulSoup4
- **Database**: SQLite (built-in)
- **Templating**: Jinja2
- **CLI**: Click
- **HTTP**: Requests
- **Linting**: Ruff
- **Testing**: pytest

---

## Data Models

### Core Data Structures

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class HighlightColor(Enum):
    """Kindle highlight colors."""
    YELLOW = "yellow"
    BLUE = "blue"
    PINK = "pink"
    ORANGE = "orange"


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


@dataclass
class Book:
    """Represents a Kindle book."""
    id: str                           # Fletcher-16 hash of title
    title: str
    author: str
    asin: Optional[str] = None        # Amazon Standard Identification Number
    url: Optional[str] = None
    image_url: Optional[str] = None
    last_annotated_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Highlight:
    """Represents a Kindle highlight."""
    id: str                           # Fletcher-16 hash of text
    book_id: str
    text: str
    location: Optional[str] = None    # Kindle location (e.g., "1234-1456")
    page: Optional[str] = None
    note: Optional[str] = None        # User's note attached to highlight
    color: Optional[HighlightColor] = None
    created_date: Optional[datetime] = None
    created_at: Optional[datetime] = None


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
```

### ID Generation Strategy

Uses **Fletcher-16 checksum** algorithm for generating IDs:
- **Book ID**: Hash of lowercase title
- **Highlight ID**: Hash of lowercase highlight text

**Rationale**: Fast, non-cryptographic, collision-resistant for this use case.

```python
def fletcher16(text: str) -> str:
    """Generate Fletcher-16 checksum for text."""
    data = text.lower().encode('utf-8')
    sum1 = sum2 = 0
    for byte in data:
        sum1 = (sum1 + byte) % 255
        sum2 = (sum2 + sum1) % 255
    checksum = (sum2 << 8) | sum1
    return f"{checksum:04x}"
```

---

## Module Specifications

### 1. Authentication Module (`auth.py`)

**Purpose**: Handle Amazon authentication and session management.

**Key Classes**:

```python
class AuthManager:
    """Manages Amazon authentication and session cookies."""
    
    def __init__(self, db: DatabaseManager, region: AmazonRegion):
        """Initialize auth manager."""
        
    def is_authenticated(self) -> bool:
        """Check if valid session exists."""
        
    def login(self, headless: bool = False) -> bool:
        """Perform Amazon login using Selenium."""
        
    def logout(self) -> None:
        """Clear session cookies."""
        
    def get_session(self) -> requests.Session:
        """Get requests.Session with stored cookies."""
        
    def _launch_browser_login(self, headless: bool) -> dict:
        """Launch Selenium browser for login."""
        
    def _save_cookies(self, cookies: dict) -> None:
        """Save cookies to database."""
        
    def _load_cookies(self) -> Optional[dict]:
        """Load cookies from database."""
```

**Authentication Flow**:
1. Check if cookies exist in database
2. If not, launch Selenium browser
3. Navigate to Amazon Kindle notebook URL
4. Wait for user to log in
5. Detect successful login (URL changes to kindle reader)
6. Extract all cookies
7. Store cookies in database
8. Return session

**Session Validation**:
- Test session by making request to notebook URL
- Check for successful response (200) and valid HTML
- If validation fails, trigger re-authentication

### 2. Scraper Module (`scraper.py`)

**Purpose**: Scrape books and highlights from Amazon.

**Key Classes**:

```python
class KindleScraper:
    """Scrapes Kindle books and highlights from Amazon."""
    
    def __init__(self, session: requests.Session, region: AmazonRegion):
        """Initialize scraper with authenticated session."""
        
    def scrape_books(self) -> list[Book]:
        """Scrape all books from notebook page."""
        
    def scrape_highlights(self, book: Book) -> list[Highlight]:
        """Scrape all highlights for a book (with pagination)."""
        
    def _parse_book_element(self, element: BeautifulSoup) -> Book:
        """Parse a single book HTML element."""
        
    def _parse_highlight_element(self, element: BeautifulSoup) -> Highlight:
        """Parse a single highlight HTML element."""
        
    def _parse_date(self, date_str: str) -> datetime:
        """Parse Amazon date string (region-aware)."""
```

**Scraping Strategy**:

1. **Books List**:
   - URL: `https://read.amazon.com/notebook`
   - Selector: `.kp-notebook-library-each-book`
   - Extract: title (h2), author (p), ASIN (element ID), image, date

2. **Highlights** (per book):
   - URL: `https://read.amazon.com/notebook?asin={asin}&contentLimitState={state}&token={token}`
   - Selector: `.a-row.a-spacing-base`
   - Extract: text (#highlight), color (CSS class), location, page, note
   - Handle pagination via `.kp-notebook-annotations-next-page-start`

### 3. Database Module (`database.py`)

**Purpose**: Manage SQLite database operations.

**Key Classes**:

```python
class DatabaseManager:
    """Manages SQLite database operations."""
    
    def __init__(self, db_path: str):
        """Initialize database connection."""
        
    def init_schema(self) -> None:
        """Create database schema if not exists."""
        
    # Book operations
    def insert_book(self, book: Book) -> None:
        """Insert or update a book."""
        
    def get_book(self, book_id: str) -> Optional[Book]:
        """Get book by ID."""
        
    def get_all_books(self) -> list[Book]:
        """Get all books."""
        
    def delete_book(self, book_id: str) -> None:
        """Delete a book and its highlights."""
        
    # Highlight operations
    def insert_highlights(self, highlights: list[Highlight]) -> None:
        """Batch insert highlights."""
        
    def get_highlights(self, book_id: str) -> list[Highlight]:
        """Get all highlights for a book."""
        
    def get_all_highlights(self) -> list[Highlight]:
        """Get all highlights."""
        
    # Session operations
    def save_session(self, key: str, value: str) -> None:
        """Save session data."""
        
    def get_session(self, key: str) -> Optional[str]:
        """Get session data."""
        
    def clear_session(self) -> None:
        """Clear all session data."""
        
    # Sync operations
    def get_last_sync(self) -> Optional[datetime]:
        """Get last successful sync timestamp."""
        
    def set_last_sync(self, timestamp: datetime) -> None:
        """Set last sync timestamp."""
```

### 4. Exporter Module (`exporter.py`)

**Purpose**: Export highlights to various formats.

**Key Classes**:

```python
class ExportFormat(Enum):
    """Supported export formats."""
    MARKDOWN = "markdown"
    JSON = "json"
    CSV = "csv"


class Exporter:
    """Exports highlights to various formats."""
    
    def __init__(self, db: DatabaseManager, templates_dir: str):
        """Initialize exporter."""
        
    def export_all(
        self,
        output_dir: str,
        format: ExportFormat = ExportFormat.MARKDOWN,
        template_name: str = "default"
    ) -> list[str]:
        """Export all books to files."""
        
    def export_book(
        self,
        book_id: str,
        output_path: str,
        format: ExportFormat = ExportFormat.MARKDOWN,
        template_name: str = "default"
    ) -> str:
        """Export a single book."""
        
    def _render_markdown(
        self,
        book: Book,
        highlights: list[Highlight],
        template_name: str
    ) -> str:
        """Render book to Markdown using Jinja2."""
        
    def _render_json(
        self,
        book: Book,
        highlights: list[Highlight]
    ) -> str:
        """Render book to JSON."""
        
    def _render_csv(
        self,
        book: Book,
        highlights: list[Highlight]
    ) -> str:
        """Render book to CSV."""
```

### 5. Configuration Module (`config.py`)

**Purpose**: Manage application configuration.

```python
class Config:
    """Application configuration."""
    
    # Region configurations
    REGIONS: dict[AmazonRegion, RegionConfig] = {...}
    
    # Default settings
    DEFAULT_REGION: AmazonRegion = AmazonRegion.GLOBAL
    DEFAULT_DB_PATH: str = "~/.kindle-sync/highlights.db"
    DEFAULT_EXPORT_DIR: str = "~/.kindle-sync/exports"
    DEFAULT_TEMPLATE: str = "default"
    
    # Browser settings
    BROWSER_TIMEOUT: int = 60
    BROWSER_IMPLICIT_WAIT: int = 10
    
    # Scraping settings
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 2
```

---

## Database Schema

### SQL Schema

```sql
-- Books table
CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,                    -- Fletcher-16 hash of title
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    asin TEXT,
    url TEXT,
    image_url TEXT,
    last_annotated_date TEXT,               -- ISO 8601 format
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_books_author ON books(author);
CREATE INDEX idx_books_title ON books(title);
CREATE INDEX idx_books_asin ON books(asin);

-- Highlights table
CREATE TABLE IF NOT EXISTS highlights (
    id TEXT PRIMARY KEY,                    -- Fletcher-16 hash of text
    book_id TEXT NOT NULL,
    text TEXT NOT NULL,
    location TEXT,
    page TEXT,
    note TEXT,
    color TEXT,
    created_date TEXT,                      -- ISO 8601 format
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE INDEX idx_highlights_book_id ON highlights(book_id);
CREATE INDEX idx_highlights_color ON highlights(color);

-- Session table (for authentication cookies and state)
CREATE TABLE IF NOT EXISTS session (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Sync metadata table
CREATE TABLE IF NOT EXISTS sync_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Database File Location

Default: `~/.kindle-sync/highlights.db`

### Data Types

- All dates stored as ISO 8601 strings (e.g., "2023-10-15T14:30:00")
- All text stored as UTF-8
- Foreign key constraints enabled

---

## Authentication Flow

### Detailed Authentication Sequence

```
┌─────────┐                  ┌──────────┐                ┌─────────────┐
│   CLI   │                  │   Auth   │                │   Browser   │
│         │                  │  Manager │                │  (Selenium) │
└────┬────┘                  └────┬─────┘                └──────┬──────┘
     │                            │                              │
     │  login()                   │                              │
     ├───────────────────────────>│                              │
     │                            │                              │
     │                            │  Check DB for cookies        │
     │                            ├──────────────────────┐       │
     │                            │                      │       │
     │                            │<─────────────────────┘       │
     │                            │                              │
     │                            │  Launch browser              │
     │                            ├─────────────────────────────>│
     │                            │                              │
     │                            │  Navigate to notebook URL    │
     │                            ├─────────────────────────────>│
     │                            │                              │
     │                            │                              │  User logs in
     │                            │                              ├───────────┐
     │                            │                              │           │
     │                            │                              │<──────────┘
     │                            │                              │
     │                            │  Detect URL change           │
     │                            │<─────────────────────────────┤
     │                            │                              │
     │                            │  Extract cookies             │
     │                            │<─────────────────────────────┤
     │                            │                              │
     │                            │  Close browser               │
     │                            ├─────────────────────────────>│
     │                            │                              │
     │                            │  Save cookies to DB          │
     │                            ├──────────────────────┐       │
     │                            │                      │       │
     │                            │<─────────────────────┘       │
     │                            │                              │
     │  Success                   │                              │
     │<───────────────────────────┤                              │
     │                            │                              │
```

### Cookie Management

**Stored Cookies**:
- `session-id`
- `session-id-time`
- `ubid-main`
- `at-main`
- `x-main`
- All other Amazon cookies

**Cookie Storage Format** (in session table):
```json
{
  "cookies": [
    {
      "name": "session-id",
      "value": "...",
      "domain": ".amazon.com",
      "path": "/",
      "expiry": 1234567890
    },
    ...
  ]
}
```

### Session Validation

Before each scraping operation:
1. Load cookies from database
2. Create requests.Session
3. Add cookies to session
4. Make test request to notebook URL
5. Check response status and content
6. If validation fails, trigger re-authentication

---

## Scraping Strategy

### HTML Structure (as of 2023)

**Books List** (`/notebook`):
```html
<div class="kp-notebook-library-each-book" id="{ASIN}">
    <img class="kp-notebook-cover-image" src="{image_url}" />
    <h2 class="kp-notebook-searchable">{title}</h2>
    <p class="kp-notebook-searchable">Author: {author}</p>
    <input id="kp-notebook-annotated-date-{ASIN}" value="{date}" />
</div>
```

**Highlights** (`/notebook?asin={ASIN}`):
```html
<div class="a-row a-spacing-base">
    <span class="kp-notebook-highlight kp-notebook-highlight-{color}" id="highlight">
        {highlight_text}
    </span>
    <input id="kp-annotation-location" value="{location}" />
    <div id="annotationNoteHeader">Page {page}</div>
    <span id="note">{note_text}</span>
</div>

<!-- Pagination -->
<input class="kp-notebook-annotations-next-page-start" value="{token}" />
<input class="kp-notebook-content-limit-state" value="{state}" />
```

### Pagination Handling

Highlights are paginated. Next page URL format:
```
/notebook?asin={ASIN}&contentLimitState={state}&token={token}
```

Algorithm:
1. Parse highlights from current page
2. Check for `.kp-notebook-annotations-next-page-start`
3. If exists, extract token and state
4. Build next page URL
5. Repeat until no next page token

### Date Parsing (Region-Aware)

Different regions use different date formats:

| Region  | Format                        | Example                     |
|---------|-------------------------------|------------------------------|
| Global  | Weekday Month DD, YYYY        | Sunday October 24, 2021     |
| Japan   | YYYY MM DD                    | 2021 10 24                  |
| France  | MMMM D, YYYY (French locale)  | octobre 24, 2021            |

### Error Handling

**Network Errors**:
- Retry up to 3 times with exponential backoff
- Log failures for manual inspection

**Parsing Errors**:
- Log warning and skip malformed elements
- Continue processing remaining elements

**Session Expiration**:
- Detect 302 redirects to login page
- Clear stored cookies
- Prompt user to re-authenticate

---

## Export Formats

### Markdown Format

**Default Template** (`default.md.j2`):
```markdown
# {{ book.title }}

**Author:** {{ book.author }}  
**ASIN:** {{ book.asin }}  
{% if book.last_annotated_date %}**Last Annotated:** {{ book.last_annotated_date | date }}{% endif %}

---

## Highlights

{% for highlight in highlights %}
### Location {{ highlight.location }}{% if highlight.page %} (Page {{ highlight.page }}){% endif %}

> {{ highlight.text }}

{% if highlight.note %}**Note:** {{ highlight.note }}{% endif %}

{% if highlight.color %}*Color: {{ highlight.color.value }}*{% endif %}

---
{% endfor %}

**Total Highlights:** {{ highlights | length }}
```

**Output Filename**: `{author_last_name}-{title_slug}.md`

### JSON Format

```json
{
  "book": {
    "id": "abc123",
    "title": "Example Book",
    "author": "John Doe",
    "asin": "B0123456789",
    "url": "https://www.amazon.com/dp/B0123456789",
    "image_url": "https://...",
    "last_annotated_date": "2023-10-15T14:30:00"
  },
  "highlights": [
    {
      "id": "def456",
      "book_id": "abc123",
      "text": "This is a highlight",
      "location": "1234-1456",
      "page": "42",
      "note": "This is my note",
      "color": "yellow",
      "created_date": "2023-10-15T14:30:00"
    }
  ]
}
```

### CSV Format

```csv
Book Title,Author,ASIN,Highlight,Location,Page,Note,Color,Date
"Example Book","John Doe","B0123456789","This is a highlight","1234-1456","42","This is my note","yellow","2023-10-15"
```

---

## CLI Interface

### Command Structure

```bash
kindle-sync [OPTIONS] COMMAND [ARGS]...
```

### Commands

#### 1. `login`
Authenticate with Amazon and save session.

```bash
kindle-sync login [OPTIONS]

Options:
  --region TEXT          Amazon region (global, uk, germany, etc.) [default: global]
  --headless/--no-headless  Run browser in headless mode [default: no-headless]
```

**Example**:
```bash
$ kindle-sync login --region uk
Opening browser for Amazon login...
Please log in to your Amazon account.
✓ Login successful! Session saved.
```

#### 2. `sync`
Sync books and highlights from Amazon.

```bash
kindle-sync sync [OPTIONS]

Options:
  --full                 Full sync (all books) vs incremental [default: incremental]
  --books TEXT           Comma-separated list of book IDs to sync
```

**Example**:
```bash
$ kindle-sync sync
Syncing highlights from Amazon...
✓ Found 23 books
✓ Synced 156 new highlights
✓ Database updated
```

#### 3. `export`
Export highlights to files.

```bash
kindle-sync export [OPTIONS] [OUTPUT_DIR]

Options:
  --format TEXT          Export format (markdown, json, csv) [default: markdown]
  --template TEXT        Template name (default, simple, detailed) [default: default]
  --books TEXT           Comma-separated list of book IDs to export
```

**Example**:
```bash
$ kindle-sync export ./my-highlights --format markdown
Exporting highlights...
✓ Exported 23 books to ./my-highlights
```

#### 4. `list`
List all books in database.

```bash
kindle-sync list [OPTIONS]

Options:
  --format TEXT          Output format (table, json) [default: table]
  --sort TEXT            Sort by (title, author, date) [default: title]
```

**Example**:
```bash
$ kindle-sync list
┌──────────────────────────────────┬─────────────────┬────────────┐
│ Title                            │ Author          │ Highlights │
├──────────────────────────────────┼─────────────────┼────────────┤
│ Atomic Habits                    │ James Clear     │ 42         │
│ The Pragmatic Programmer         │ Hunt & Thomas   │ 78         │
└──────────────────────────────────┴─────────────────┴────────────┘
```

#### 5. `show`
Show details of a specific book.

```bash
kindle-sync show BOOK_ID
```

**Example**:
```bash
$ kindle-sync show abc123
Title: Atomic Habits
Author: James Clear
ASIN: B01N5AX61W
Highlights: 42
Last Annotated: 2023-10-15

Recent highlights:
1. "You do not rise to the level of your goals..."
2. "Habits are the compound interest of self-improvement..."
```

#### 6. `logout`
Clear stored session.

```bash
kindle-sync logout
```

**Example**:
```bash
$ kindle-sync logout
✓ Session cleared. You'll need to login again.
```

#### 7. `status`
Show sync status and statistics.

```bash
kindle-sync status
```

**Example**:
```bash
$ kindle-sync status
Database: ~/.kindle-sync/highlights.db
Last Sync: 2023-10-15 14:30:00
Total Books: 23
Total Highlights: 456
Session: Active (expires in 7 days)
```

### Global Options

```bash
Options:
  --db PATH              Database path [default: ~/.kindle-sync/highlights.db]
  --verbose, -v          Verbose output
  --quiet, -q            Quiet mode (errors only)
  --help                 Show help message
  --version              Show version
```

---

## Error Handling

### Error Categories

1. **Authentication Errors**
   - Invalid credentials
   - Session expired
   - Two-factor authentication required
   - Region mismatch

2. **Network Errors**
   - Connection timeout
   - DNS resolution failure
   - Server error (5xx)
   - Rate limiting

3. **Parsing Errors**
   - Unexpected HTML structure
   - Missing required fields
   - Invalid data format

4. **Database Errors**
   - Database locked
   - Disk full
   - Corrupted database
   - Schema mismatch

5. **File System Errors**
   - Permission denied
   - Disk full
   - Invalid path

### Error Handling Strategy

```python
from enum import Enum
from typing import Optional

class ErrorCode(Enum):
    AUTH_FAILED = "AUTH_001"
    SESSION_EXPIRED = "AUTH_002"
    NETWORK_TIMEOUT = "NET_001"
    PARSE_ERROR = "PARSE_001"
    DB_ERROR = "DB_001"
    FS_ERROR = "FS_001"

class KindleSyncError(Exception):
    """Base exception for kindle-sync errors."""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode,
        details: Optional[dict] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)
```

### Retry Logic

```python
from functools import wraps
import time

def retry(max_attempts: int = 3, delay: int = 2, backoff: int = 2):
    """Retry decorator with exponential backoff."""
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except (NetworkError, TimeoutError) as e:
                    attempt += 1
                    if attempt == max_attempts:
                        raise
                    time.sleep(current_delay)
                    current_delay *= backoff
                    
        return wrapper
    return decorator
```

---

## Security Considerations

### Authentication Security

1. **Cookie Storage**
   - Store cookies in SQLite database (not plain text files)
   - Database should have restricted permissions (600)
   - Consider encryption for cookie values

2. **Session Management**
   - Never log cookie values
   - Clear cookies on logout
   - Implement session timeout

3. **Browser Security**
   - Run Selenium with minimal permissions
   - Disable unnecessary browser features
   - Clear browser cache after login

### Data Security

1. **Database**
   - Restrict file permissions (600)
   - Consider SQLCipher for encryption
   - Regular backups recommended

2. **Exports**
   - Default export directory in user home
   - Warn if exporting to shared locations
   - Sanitize filenames to prevent path traversal

### Network Security

1. **HTTPS Only**
   - All Amazon requests over HTTPS
   - Verify SSL certificates
   - No insecure fallbacks

2. **Request Headers**
   - Use standard User-Agent
   - Include appropriate referers
   - No sensitive data in URLs

---

## Testing Strategy

### Unit Tests

**Coverage Target**: 80%+

**Test Categories**:

1. **Model Tests** (`tests/test_models.py`)
   - Data class creation
   - Validation logic
   - Serialization/deserialization

2. **Utility Tests** (`tests/test_utils.py`)
   - Fletcher-16 hash generation
   - Date parsing
   - String sanitization

3. **Database Tests** (`tests/test_database.py`)
   - CRUD operations
   - Foreign key constraints
   - Transaction handling

4. **Scraper Tests** (`tests/test_scraper.py`)
   - HTML parsing with mock data
   - Pagination logic
   - Error handling

5. **Exporter Tests** (`tests/test_exporter.py`)
   - Template rendering
   - Format conversion
   - Filename generation

### Integration Tests

1. **Auth Flow** (`tests/integration/test_auth.py`)
   - Mock browser interaction
   - Cookie persistence
   - Session validation

2. **End-to-End Sync** (`tests/integration/test_sync.py`)
   - Mock Amazon responses
   - Full sync workflow
   - Database updates

3. **Export Workflow** (`tests/integration/test_export.py`)
   - Database to file export
   - Template rendering
   - File creation

### Test Fixtures

```python
# tests/conftest.py

@pytest.fixture
def temp_db():
    """Create temporary test database."""
    db_path = tempfile.mktemp(suffix=".db")
    db = DatabaseManager(db_path)
    db.init_schema()
    yield db
    os.unlink(db_path)

@pytest.fixture
def sample_book():
    """Sample book for testing."""
    return Book(
        id="test123",
        title="Test Book",
        author="Test Author",
        asin="B0123456789"
    )

@pytest.fixture
def sample_highlights():
    """Sample highlights for testing."""
    return [
        Highlight(
            id="h1",
            book_id="test123",
            text="Test highlight 1"
        ),
        Highlight(
            id="h2",
            book_id="test123",
            text="Test highlight 2"
        )
    ]
```

---

## Development Workflow

### Setup Development Environment

```bash
# Clone repository
git clone <repo_url>
cd kindle-highlights-sync

# Create virtual environment with uv
uv venv

# Activate virtual environment
source .venv/bin/activate  # Unix
# or
.venv\Scripts\activate     # Windows

# Install dependencies
uv pip install -e ".[dev]"

# Verify installation
kindle-sync --version
```

### Code Quality Checks

**Linting with Ruff**:
```bash
# Check code
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

**Type Checking with mypy**:
```bash
mypy src/kindle_sync
```

**Run Tests**:
```bash
# All tests
pytest

# With coverage
pytest --cov=kindle_sync --cov-report=html

# Specific test file
pytest tests/test_database.py

# Specific test
pytest tests/test_database.py::test_insert_book
```

### Pre-commit Workflow

Recommended workflow before committing:

```bash
# 1. Format code
ruff format .

# 2. Fix linting issues
ruff check --fix .

# 3. Run type checker
mypy src/kindle_sync

# 4. Run tests
pytest

# 5. Check coverage
pytest --cov=kindle_sync --cov-report=term-missing

# 6. Commit
git add .
git commit -m "Your commit message"
```

### Git Workflow

**Branch Strategy**:
- `main`: Stable releases
- `develop`: Integration branch
- `feature/*`: New features
- `fix/*`: Bug fixes

**Commit Convention**:
```
type(scope): subject

body (optional)

footer (optional)
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Example:
```
feat(scraper): add support for Japanese date format

- Parse dates in YYYY MM DD format
- Add locale-aware date parsing
- Update tests

Closes #42
```

### Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Run full test suite
4. Build package: `uv build`
5. Tag release: `git tag v0.1.0`
6. Push tags: `git push --tags`

---

## Appendix

### A. Amazon Region URLs

| Region       | Hostname      | Notebook URL                          |
|--------------|---------------|---------------------------------------|
| Global (US)  | amazon.com    | https://read.amazon.com/notebook      |
| UK           | amazon.co.uk  | https://read.amazon.co.uk/notebook    |
| Germany      | amazon.de     | https://lesen.amazon.de/notebook      |
| Japan        | amazon.co.jp  | https://read.amazon.co.jp/notebook    |
| India        | amazon.in     | https://read.amazon.in/notebook       |
| Spain        | amazon.es     | https://leer.amazon.es/notebook       |
| Italy        | amazon.it     | https://leggi.amazon.it/notebook      |
| France       | amazon.fr     | https://lire.amazon.fr/notebook       |

### B. Dependencies Rationale

| Package            | Purpose                              | Why This Choice?                  |
|--------------------|--------------------------------------|-----------------------------------|
| selenium           | Browser automation                   | Industry standard, well-maintained|
| beautifulsoup4     | HTML parsing                         | Simple API, robust                |
| requests           | HTTP client                          | De facto standard                 |
| click              | CLI framework                        | Feature-rich, popular             |
| jinja2             | Templating                           | Powerful, flexible                |
| webdriver-manager  | Auto-manage browser drivers          | Reduces setup friction            |
| rich               | Terminal formatting                  | Beautiful CLI output              |
| ruff               | Linting & formatting                 | Fast, modern, all-in-one          |

### C. Future Enhancements

**Version 0.2.0**:
- Incremental sync optimization
- Search within highlights
- Custom templates support
- Export to Notion/Obsidian

**Version 0.3.0**:
- Web UI for browsing
- Statistics and analytics
- Tagging system
- Highlight annotations

**Version 0.4.0**:
- My Clippings.txt import
- Multiple account support
- Cloud backup integration
- Mobile companion app

---

## Document History

| Version | Date       | Author  | Changes                    |
|---------|------------|---------|----------------------------|
| 0.1.0   | 2025-12-17 | Krishna | Initial specification      |

---

**End of Specification Document**

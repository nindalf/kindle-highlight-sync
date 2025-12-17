# Kindle Highlights Sync - Technical Specification

**Version:** 0.1.0  
**Last Updated:** 2025-12-17

## Overview

Python CLI tool to sync Kindle highlights from Amazon to a local SQLite database and export to Markdown/JSON/CSV.

**Inspired by**: [obsidian-kindle-plugin](https://github.com/hadynz/obsidian-kindle-plugin)

### Core Features

- One-time authentication via Selenium
- Multi-region Amazon support (8 regions)
- Local SQLite storage with ASIN-based schema
- Export to Markdown, JSON, CSV
- Incremental sync support

---

## Architecture

```
CLI (Click) → Auth (Selenium) → Scraper (BeautifulSoup) → Database (SQLite) → Exporter (Jinja2)
```

### Module Structure

```
src/kindle_sync/
├── models.py      # Data models (Book, Highlight, enums)
├── config.py      # Configuration & region definitions
├── utils.py       # Utilities (fletcher16, slugify, retry)
├── database.py    # SQLite operations
├── auth.py        # Selenium authentication
├── scraper.py     # Amazon scraping
├── exporter.py    # File export
└── cli.py         # CLI commands
```

---

## Data Models

### Book
```python
@dataclass
class Book:
    asin: str                         # Amazon ID (Primary Key)
    title: str
    author: str
    url: str | None
    image_url: str | None
    last_annotated_date: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
```

### Highlight
```python
@dataclass
class Highlight:
    id: str                           # Fletcher-16 hash
    book_asin: str                    # Foreign key to Book
    text: str
    location: str | None              # e.g., "1234-1456"
    page: str | None
    note: str | None
    color: HighlightColor | None      # yellow, blue, pink, orange
    created_date: datetime | None
```

### ID Strategy
- **Books**: Use ASIN (10-char Amazon identifier, e.g., `B01N5AX61W`)
- **Highlights**: Fletcher-16 hash of text (4-char hex, e.g., `9f2e`)

---

## Database Schema

### Tables

**books**
```sql
CREATE TABLE books (
    asin TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    url TEXT,
    image_url TEXT,
    last_annotated_date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_books_author ON books(author);
CREATE INDEX idx_books_title ON books(title);
```

**highlights**
```sql
CREATE TABLE highlights (
    id TEXT PRIMARY KEY,
    book_asin TEXT NOT NULL,
    text TEXT NOT NULL,
    location TEXT,
    page TEXT,
    note TEXT,
    color TEXT,
    created_date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_asin) REFERENCES books(asin) ON DELETE CASCADE
);
CREATE INDEX idx_highlights_book_asin ON highlights(book_asin);
```

**session** - Stores authentication cookies (JSON)  
**sync_metadata** - Stores sync timestamps

### Key Queries

```sql
-- Get book with highlights
SELECT * FROM books WHERE asin = ?;
SELECT * FROM highlights WHERE book_asin = ? ORDER BY location;

-- Search highlights
SELECT h.text, b.title FROM highlights h 
JOIN books b ON h.book_asin = b.asin 
WHERE h.text LIKE ?;
```

---

## Authentication

### Flow
1. Launch Chrome via Selenium
2. Navigate to `https://read.amazon.com/notebook`
3. Wait for user login (detect URL change to `read.amazon.com`)
4. Extract cookies
5. Store cookies in SQLite
6. Reuse for ~7 days

### Region Support

| Region | URL |
|--------|-----|
| Global | `read.amazon.com/notebook` |
| UK | `read.amazon.co.uk/notebook` |
| Germany | `lesen.amazon.de/notebook` |
| Japan | `read.amazon.co.jp/notebook` |
| India | `read.amazon.in/notebook` |
| Spain | `leer.amazon.es/notebook` |
| Italy | `leggi.amazon.it/notebook` |
| France | `lire.amazon.fr/notebook` |

---

## Scraping

### Books List
- **URL**: `https://read.amazon.com/notebook`
- **Selector**: `.kp-notebook-library-each-book`
- **Extract**: title, author, ASIN (element ID), image, last annotated date

### Highlights (per book)
- **URL**: `/notebook?asin={asin}&contentLimitState={state}&token={token}`
- **Selector**: `.a-row.a-spacing-base`
- **Extract**: text, color (CSS class), location, page, note
- **Pagination**: Follow `.kp-notebook-annotations-next-page-start`

### Date Parsing (Region-Aware)

| Region | Format | Example |
|--------|--------|---------|
| Global | `Weekday Month DD, YYYY` | `Sunday October 24, 2021` |
| Japan | `YYYY MM DD` | `2021 10 24` |
| France | `MMMM D, YYYY` (French) | `octobre 24, 2021` |

---

## Export

### Markdown (Default)
```markdown
# {{title}}
**Author:** {{author}}
**ASIN:** {{asin}}

## Highlights
### Location {{location}}
> {{text}}
**Note:** {{note}}
---
```

### JSON
```json
{
  "book": {"asin": "...", "title": "...", "author": "..."},
  "highlights": [{"id": "...", "book_asin": "...", "text": "..."}]
}
```

### CSV
```csv
Book Title,Author,ASIN,Highlight,Location,Page,Note,Color,Date
```

**Template Engine**: Jinja2  
**Filename Format**: `{author_last_name}-{title_slug}.md`

---

## CLI Commands

```bash
# Authentication
kindle-sync login [--region REGION] [--headless]
kindle-sync logout

# Sync
kindle-sync sync [--full] [--books ASINS]

# Export
kindle-sync export OUTPUT_DIR [--format FORMAT] [--template NAME]

# Info
kindle-sync list [--sort FIELD]
kindle-sync show ASIN
kindle-sync status
```

### Global Options
```
--db PATH          Database path [default: ~/.kindle-sync/highlights.db]
--verbose, -v      Verbose output
--quiet, -q        Quiet mode
```

---

## Module APIs

### DatabaseManager
```python
db = DatabaseManager(db_path)
db.init_schema()
db.insert_book(book)
db.get_book(asin) -> Book | None
db.get_all_books() -> list[Book]
db.save_session(key, value)
db.get_session(key) -> str | None
```

### AuthManager
```python
auth = AuthManager(db, region)
auth.login(headless=False) -> bool
auth.is_authenticated() -> bool
auth.get_session() -> requests.Session
auth.logout()
```

### KindleScraper
```python
scraper = KindleScraper(session, region)
scraper.scrape_books() -> list[Book]
scraper.scrape_highlights(book) -> list[Highlight]
```

### Exporter
```python
exporter = Exporter(db, templates_dir)
exporter.export_all(output_dir, format) -> list[str]
exporter.export_book(asin, output_path, format)
```

---

## Error Handling

### Exception Hierarchy
```python
class KindleSyncError(Exception): pass
class AuthenticationError(KindleSyncError): pass
class ScraperError(KindleSyncError): pass
class DatabaseError(KindleSyncError): pass
class ExportError(KindleSyncError): pass
```

### Retry Strategy
```python
@retry(max_attempts=3, delay=2, backoff=2)
def fetch_page(url):
    return requests.get(url)
```

---

## Security

- **No credentials stored** - Only session cookies
- **Database permissions** - Set to `600` (owner only)
- **SQL injection** - Parameterized queries only
- **Session expiration** - Validate before each use
- **HTTPS only** - All Amazon requests

---

## Testing

### Unit Tests
```bash
uv run pytest tests/test_models.py
uv run pytest tests/test_utils.py
uv run pytest tests/test_database.py
```

### Coverage Target
```bash
uv run pytest --cov=kindle_sync --cov-report=html
```
**Target**: 80%+

### Test Fixtures
```python
@pytest.fixture
def temp_db():
    db_path = tempfile.mktemp(suffix=".db")
    db = DatabaseManager(db_path)
    db.init_schema()
    yield db
    os.unlink(db_path)
```

---

## Development

### Setup
```bash
uv sync
```

### Code Quality
```bash
uv run ruff format .              # Format
uv run ruff check --fix .         # Lint
uv run mypy src/kindle_sync       # Type check
uv run pytest                     # Test
```

### Dependencies
- **Core**: selenium, beautifulsoup4, requests, jinja2, click, rich
- **Dev**: ruff, pytest, mypy

---

## Configuration

### Config Class
```python
Config.DEFAULT_REGION = AmazonRegion.GLOBAL
Config.DEFAULT_DB_PATH = "~/.kindle-sync/highlights.db"
Config.BROWSER_TIMEOUT = 60
Config.REQUEST_TIMEOUT = 30
Config.MAX_RETRIES = 3
```

---

## Utilities

### Fletcher-16 Hash
```python
def fletcher16(text: str) -> str:
    data = text.lower().encode('utf-8')
    sum1 = sum2 = 0
    for byte in data:
        sum1 = (sum1 + byte) % 255
        sum2 = (sum2 + sum1) % 255
    return f"{(sum2 << 8) | sum1:04x}"
```

### String Utilities
```python
slugify(text)                    # URL-safe slug
sanitize_filename(filename)      # Remove invalid chars
extract_author_last_name(author) # Handle multiple authors
```

---

## Implementation Status

### ✅ Completed (Phase 1)
- models.py - Data models
- config.py - Configuration
- utils.py - Utilities
- database.py - Database operations
- auth.py - Authentication
- cli.py - Basic CLI (login, logout, status)

### 🚧 To Implement (Phase 2)
- scraper.py - Web scraping
- exporter.py - Export functionality
- CLI commands: sync, export, list, show

---

## Roadmap

### v0.2.0
- Incremental sync optimization
- Search within highlights
- Custom template support

### v0.3.0
- Web UI for browsing
- Statistics and analytics
- Tagging system

### v0.4.0
- My Clippings.txt import
- Multiple account support
- Cloud backup integration

---

**End of Specification**

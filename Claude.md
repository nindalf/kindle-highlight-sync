# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

After you make a change:
- Run tests with `uv run pytest`
- Run the formatter with `uv run ruff format .`
- Run the linter with `uv run ruff check --fix .`
- Run the type checker with `uvx ty check`. If there are any errors fix them.

### Running Tests
```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/test_database.py

# Single test
uv run pytest tests/test_database.py::TestDatabaseManager::test_insert_book

# With coverage
uv run pytest --cov=kindle_sync --cov-report=term-missing
```

### Running the Application

```bash
# CLI commands
uv run kindle-sync login
uv run kindle-sync sync
uv run kindle-sync export ./output
uv run kindle-sync web
```

## Architecture Overview

This is a Kindle highlights sync tool with two user interfaces (CLI and web) sharing a common service layer.

### Layered Architecture

```
┌─────────────────────────────────────────────────────┐
│  User Interfaces                                    │
│  cli.py | web.py                                    │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────┐
│  Service Layer (services/)                          │
│  AuthService | SyncService | ExportService          │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────┐
│  Data Access Layer                                  │
│  DatabaseManager | KindleScraper                    │
└─────────────────────────────────────────────────────┘
```

### Service Layer Pattern

All business logic lives in `services/`. Services return dataclass Results with consistent structure:

```python
@dataclass
class SyncResult:
    success: bool
    message: str
    error: str | None = None
    data: dict | None = None  # Contains stats, books_synced, etc.
```

This enables both CLI and web interfaces to call the same methods and handle results uniformly.

**Key Services:**
- `AuthService` (`auth_service.py`) - Amazon login via Selenium, session management
- `SyncService` (`sync_service.py`) - Orchestrates scraping and database updates
- `ExportService` (`export_service.py`) - Exports to Markdown/JSON/CSV using Jinja2 templates
- `DatabaseManager` (`database_service.py`) - All SQLite operations (619 lines)
- `KindleScraper` (`scraper_service.py`) - Scrapes Amazon with API-first, HTML fallback strategy

### Database Management

**Thread-Safety:** DatabaseManager uses connection pooling. In Flask, connections are per-request via `g` object:

```python
def get_db():
    if "db" not in g:
        g.db = DatabaseManager(current_app.config["DATABASE"])
    return g.db
```

**UPSERT Pattern:** All sync operations use `INSERT ... ON CONFLICT DO UPDATE` to handle incremental syncs safely.

**Schema:** 4 tables - `books`, `highlights`, `session`, `sync_metadata`

### Web Scraping Strategy

`KindleScraper` uses a dual-method approach:
1. **API-based (primary):** Fetches from `/kindle-library/search` endpoint with pagination tokens
2. **HTML-based (fallback):** Parses notebook page with BeautifulSoup if API fails

All scraping methods wrapped with `@retry` decorator for network resilience.

### Flask Web Interface

`web.py` provides both HTML routes (for browser UI) and API routes (JSON responses):

**Web UI Routes:**
- `/` - Book grid
- `/book/<asin>` - Book details with highlights
- `/search` - Full-text search

**API Routes:**
- `/api/status` - Auth and sync status
- `/api/sync` - Trigger sync
- `/api/export` - Trigger export
- `/api/books/<asin>/metadata` - Update book metadata
- `/api/highlights/<id>/toggle-visibility` - Hide/show highlights

## Important Patterns

### Highlight ID Generation
Uses SHA-256 hash of highlight content to generate stable, unique IDs:
```python
def fletcher16(text: str) -> str:
    # Returns first 8 hex characters of SHA-256 like "a1b2c3d4"
```

This allows detecting when highlights change between syncs.

### Export Templates

Markdown export uses Jinja2 templates in `templates/export/`:
- `simple.md.j2` - Minimal
- `astro.md.j2` - Metadata in frontmatter, highlights and review in the main body. 

- `astro.md.j2` - Astro-compatible frontmatter

Custom templates can be added and referenced by name.

### Multi-Region Support
8 Amazon regions configured in `config.py`. Each has specific URLs and date formats. Region selected during login:
```bash
uv run kindle-sync login --region uk
```

### Incremental Sync Algorithm
1. Fetch all books from Amazon
2. For each book, fetch all highlights
3. Compare with database using highlight IDs
4. UPSERT new/changed highlights
5. DELETE highlights no longer present
6. Update last sync timestamp

## Key Files

- `cli.py` (370 lines) - Click-based CLI with 8 commands
- `web.py` (450 lines) - Flask app with web UI and API routes
- `services/database_service.py` (619 lines) - All database operations
- `services/scraper_service.py` (387 lines) - Amazon scraping logic
- `services/auth_service.py` (260 lines) - Authentication and session management
- `services/export_service.py` (332 lines) - Export to multiple formats
- `services/sync_service.py` (139 lines) - Sync orchestration
- `models.py` (110 lines) - Dataclasses for Book, Highlight, results
- `utils.py` (220 lines) - Fletcher-16 hash, retry decorator, filename sanitization

## Common Development Scenarios

### Adding a New Export Format
1. Create template in `templates/export/` (if template-based)
2. Add format to `ExportFormat` enum in `models.py`
3. Add export logic in `ExportService._export_single()`
4. Add tests in `tests/test_export_service.py`

### Adding a New Database Field
1. Update `Book` or `Highlight` dataclass in `models.py`
2. Add migration in `DatabaseManager._initialize_db()`
3. Update INSERT/UPDATE queries in `DatabaseManager`
4. Update scraper if field comes from Amazon
5. Update templates if field should appear in exports

### Adding a New CLI Command
1. Add `@cli.command()` in `cli.py`
2. Call service layer methods (don't duplicate business logic)
3. Use Rich library for terminal output
4. Add tests in `tests/test_cli.py`

### Adding a New Web Route
1. Add route in `web.py`
2. For API routes, return JSON with consistent structure
3. For web routes, render template from `templates/web/`
4. Use `get_db()` for database access (per-request connection)
5. Add tests in `tests/test_web.py`

## Testing Notes

- **Fixtures:** Shared fixtures in `tests/conftest.py` (temp databases, sample data)
- **Coverage:** Currently ~62% (1,722 lines of test code)
- **Mock strategy:** Services are tested with real SQLite (in-memory), scraper uses mocked responses

## Python Version

Requires Python 3.14+ (specified in pyproject.toml). Uses modern type hints including `|` union syntax.

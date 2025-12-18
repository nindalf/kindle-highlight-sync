# Kindle Highlights Sync

Sync your Kindle highlights from Amazon to a local SQLite database. Export to Markdown, JSON, or CSV. Browse via CLI or web interface.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- 🔐 **One-time authentication** - Browser-based login, session persistence
- 📦 **Local SQLite storage** - All data stored locally, offline access
- 📄 **Multiple export formats** - Markdown, JSON, CSV with Jinja2 templates
- 🌍 **Multi-region support** - US, UK, Germany, Japan, India, Spain, Italy, France
- 💻 **CLI interface** - 8 commands for all operations
- 🌐 **Web interface** - Browse and search highlights in your browser
- 🔍 **Full-text search** - Search across all highlights and notes
- 🎨 **Highlight colors** - Preserves yellow, blue, pink, orange colors
- 🔄 **Smart sync** - Incremental updates, note editing, deletion tracking

## Installation

**Prerequisites:** Python 3.10+, Chrome/Firefox

```bash
git clone <repo-url>
cd kindle-highlights-sync
uv sync
```

## Quick Start

```bash
# Login to Amazon
uv run kindle-sync login

# Sync all highlights
uv run kindle-sync sync

# Export to Markdown
uv run kindle-sync export ./highlights

# Start web interface
uv run kindle-sync web
```

## CLI Commands

### Authentication

```bash
kindle-sync login [--region uk] [--headless]
kindle-sync logout
kindle-sync status
```

Supported regions: `global` (US), `uk`, `germany`, `japan`, `india`, `spain`, `italy`, `france`

### Syncing

```bash
# Incremental sync (default)
kindle-sync sync

# Full sync (re-download everything)
kindle-sync sync --full

# Sync specific books
kindle-sync sync --books "ASIN1,ASIN2"
```

The sync command:
- Downloads new highlights
- Updates modified notes
- Removes deleted highlights
- Tracks last sync time

### Export

```bash
# Export all books to Markdown (default)
kindle-sync export ./output

# Export to JSON or CSV
kindle-sync export ./output --format json
kindle-sync export ./output --format csv

# Use custom template
kindle-sync export ./output --template detailed

# Export specific books
kindle-sync export ./output --books "ASIN1,ASIN2"
```

**Built-in templates:**
- `default` - Comprehensive with all metadata
- `simple` - Minimal, just highlights
- `detailed` - Full export with notes and colors

### Browsing

```bash
# List all books
kindle-sync list [--sort author|date] [--format table|json]

# Show book details
kindle-sync show <ASIN>
```

### Web Interface

```bash
# Start server (default: localhost:5000)
kindle-sync web

# Custom host/port
kindle-sync web --host 0.0.0.0 --port 8080

# Debug mode
kindle-sync web --debug
```

**Web features:**
- Grid view of all books
- Individual book pages with all highlights
- Full-text search across highlights and notes
- Color-coded highlights
- Responsive design
- Thread-safe SQLite connections

## Configuration

### Database Location

Default: `~/.kindle-sync/highlights.db`

Override with `--db` flag:
```bash
kindle-sync --db /path/to/custom.db sync
```

### Custom Templates

Place templates in `~/.kindle-sync/templates/`:
```jinja2
# mytemplate.md.j2
# {{ book.title }} by {{ book.author }}

{% for highlight in highlights %}
> {{ highlight.text }}
{% if highlight.note %}**Note:** {{ highlight.note }}{% endif %}
{% endfor %}
```

Use with `--template mytemplate`

## How It Works

### Authentication

1. Opens browser to Amazon login page
2. You log in through Amazon's interface
3. Extracts and stores session cookies
4. Reuses cookies for future requests (session expires ~7 days)

### Scraping

1. Loads `read.amazon.com/notebook` with stored cookies
2. Parses HTML for books (title, author, ASIN)
3. Iterates through book pages with pagination
4. Extracts highlights (text, location, page, note, color)
5. Generates unique IDs using Fletcher-16 hash

### Storage

- **Books table**: ASIN (primary key), title, author, metadata
- **Highlights table**: Fletcher-16 ID, book_asin (foreign key), text, location, page, note, color
- **Session table**: Encrypted cookies, region, expiry
- **Sync metadata**: Last sync timestamp

### Sync Algorithm

```python
for book in scraped_books:
    existing_highlights = get_from_db(book.asin)
    new_highlights = scrape_from_amazon(book.asin)
    
    # Insert/update highlights (UPSERT)
    for highlight in new_highlights:
        db.insert_highlight(highlight)  # ON CONFLICT DO UPDATE
    
    # Delete removed highlights
    deleted = existing_highlights - new_highlights
    db.delete_highlights(deleted)
```

## Export Examples

### Markdown

```markdown
# Atomic Habits

**Author:** James Clear  
**ASIN:** B01N5AX61W

## Highlights

### Location 254-267 (Page 12)

> You do not rise to the level of your goals. You fall to the level of your systems.

**Note:** Important concept about systems vs goals  
*Color: yellow*
```

### JSON

```json
{
  "book": {
    "asin": "B01N5AX61W",
    "title": "Atomic Habits",
    "author": "James Clear"
  },
  "highlights": [
    {
      "id": "9f2e",
      "text": "You do not rise to the level of your goals...",
      "location": "254-267",
      "page": "12",
      "color": "yellow",
      "note": "Important concept"
    }
  ]
}
```

## Development

### Running Tests

```bash
uv sync --extra dev

# All tests (115 tests, 62% coverage)
uv run pytest

# Specific test file
uv run pytest tests/test_database.py

# With coverage report
uv run pytest --cov=kindle_sync --cov-report=html
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint
uv run ruff check .

# Auto-fix
uv run ruff check --fix .

# Type checking
uvx ty check
```

## Architecture

### Project Structure

```
kindle-highlights-sync/
├── src/kindle_sync/
│   ├── cli.py              # CLI commands (8 commands)
│   ├── auth.py             # Authentication & cookies
│   ├── scraper.py          # HTML parsing & pagination
│   ├── database.py         # SQLite operations & search
│   ├── exporter.py         # Markdown/JSON/CSV export
│   ├── web.py              # Flask web interface
│   ├── models.py           # Data models (Book, Highlight)
│   ├── config.py           # Region configs
│   ├── utils.py            # Fletcher-16 hash, retry logic
│   └── templates/
│       ├── default.md.j2   # Export templates
│       ├── simple.md.j2
│       ├── detailed.md.j2
│       └── web/            # Web UI templates
│           ├── base.html
│           ├── index.html
│           ├── book.html
│           └── search.html
├── tests/                  # 115 unit tests
└── pyproject.toml          # Project config
```

### Tech Stack

- **CLI:** Click + Rich
- **Web:** Flask 3.0+
- **Database:** SQLite3
- **Scraping:** Selenium + BeautifulSoup4
- **Templates:** Jinja2
- **HTTP:** Requests
- **Testing:** pytest

### Database Schema

```sql
CREATE TABLE books (
    asin TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    url TEXT,
    image_url TEXT,
    last_annotated_date TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE highlights (
    id TEXT PRIMARY KEY,              -- Fletcher-16 hash
    book_asin TEXT NOT NULL,
    text TEXT NOT NULL,
    location TEXT,
    page TEXT,
    note TEXT,
    color TEXT,
    created_date TEXT,
    created_at TEXT,
    FOREIGN KEY (book_asin) REFERENCES books(asin) ON DELETE CASCADE
);

CREATE TABLE session (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE sync_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT
);
```

## Troubleshooting

### Login Issues

- Ensure correct region: `kindle-sync login --region uk`
- Try non-headless: `kindle-sync login --no-headless`
- Check 2FA settings (may require manual intervention)

### Session Expired

```bash
kindle-sync logout
kindle-sync login
```

### No Books Found

- Verify highlights exist on read.amazon.com
- Check region matches your account
- Try `kindle-sync sync --full`

### Database Locked

- Close other instances
- Check file permissions: `chmod 600 ~/.kindle-sync/highlights.db`

### Web Interface Threading Error

Fixed in current version. Uses per-request database connections via Flask's `g` object.

### Search Not Finding Results

- Search is case-insensitive
- Searches both highlight text and notes
- Uses SQL LIKE pattern matching
- For large collections (>10k highlights), consider SQLite FTS5

## Limitations

- **Manual login required** - No credential storage for security
- **Session expiry** - ~7 days, requires re-login
- **HTML parsing dependency** - May break if Amazon changes site structure
- **Single platform** - Only syncs from Amazon (no Kobo, Apple Books, etc.)
- **No My Clippings.txt import** - Planned for future
- **Basic search** - SQL LIKE (not full-text index)

## Security

- **No credentials stored** - Only session cookies
- **Local data** - Everything stored on your machine
- **Secure deletion** - Use `logout` to clear session
- **File permissions** - Database should be 600 (user read/write only)

### Best Practices

1. Use `logout` when done syncing
2. Don't share database file (contains session data)
3. Keep system secure (database not encrypted by default)
4. Consider encrypting the database file

## Stats

- **Lines of code:** ~1,850 production code
- **Modules:** 9 core modules
- **CLI commands:** 8
- **Export formats:** 3 (Markdown, JSON, CSV)
- **Templates:** 3 export + 4 web
- **Regions:** 8 Amazon regions
- **Tests:** 115 tests, 62% coverage
- **Dependencies:** 10 packages

## Inspiration

Inspired by [obsidian-kindle-plugin](https://github.com/hadynz/obsidian-kindle-plugin). This project provides a standalone CLI/web alternative with more export options and local storage.

## License

MIT License - see LICENSE file

## Roadmap

- [x] Consider cli.py and web.py holistically. They both need to call some of the same code. For example, I want to be able to login, sync and export from within the web interface. What's the best way to share this functionality.
- [x] Export location.
- [ ] Add more details to the book: Purchase date,Book,Author,Status,Format,Start date,End date,Reading time,Genres,Amazon link,ISBN,Classification,Goodreads link,price in GBP, price in INR
- [ ] Fetch some of these details from Goodreads.
- [ ] Add an option in the web interface to edit details to the book.
- [ ] Add a pre-commit hook that runs `ruff` and `ty`
- [ ] Explore packaging this project into an app that could be launched on a mac, without needing to be launched from the command line.
- [ ] Option to hide a highlight
- [ ] Export in an Astro friendly format.

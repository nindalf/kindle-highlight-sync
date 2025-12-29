# Kindle Highlights Sync

Manage your Kindle highlights, reviews, and ratings locally. Sync from Amazon, store in SQLite, and export to your preferred format.

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What is this?

A local-first tool for managing your Kindle reading data. It syncs your highlights, notes, and annotations from Amazon's Kindle service to a SQLite database on your machine. You can then browse, search, edit metadata, add reviews and ratings, and export everything to Markdown, JSON, or CSV.

**Key capabilities:**

- Sync highlights and notes from Amazon Kindle
- Add your own reviews, ratings, and metadata (reading dates, genres, prices)
- Download book cover images
- Search across all highlights and notes
- Export to multiple formats with customizable templates
- Three interfaces: CLI, web browser, macOS menu bar

## Installation

**Prerequisites:** Python 3.14+, Chrome or Firefox

```bash
git clone https://github.com/nindalf/kindle-highlights-sync.git
cd kindle-highlights-sync
uv sync
```

## Quick Start

```bash
# Login to Amazon (one-time setup)
uv run kindle-sync login

# Sync your highlights
uv run kindle-sync sync

# Download book cover images
uv run kindle-sync sync-images

# Export to Markdown
uv run kindle-sync export ./output

# Start web interface
uv run kindle-sync web
```

Open `http://localhost:5000` in your browser.

## Usage

### Command Line Interface

**Authentication:**
```bash
uv run kindle-sync login              # Login to Amazon
uv run kindle-sync login --region uk  # Specify region
uv run kindle-sync logout             # Clear session
uv run kindle-sync status             # Check login status
```

Supported regions: global (US), uk, germany, japan, india, spain, italy, france

**Syncing:**
```bash
uv run kindle-sync sync                    # Incremental sync (recommended)
uv run kindle-sync sync --full             # Full re-sync
uv run kindle-sync sync-images             # Download book covers
uv run kindle-sync sync-images --size 600  # Higher resolution (160, 300, 400, 600)
```

**Browsing:**
```bash
uv run kindle-sync list                      # Show all books
uv run kindle-sync list --sort author       # Sort by author or date
uv run kindle-sync show <ASIN>              # Show book details
```

**Exporting:**
```bash
uv run kindle-sync export ./output                    # Export to Markdown
uv run kindle-sync export ./output --format json      # Export to JSON
uv run kindle-sync export ./output --template simple  # Use simple template
```

Available templates: simple, astro

**Web Interface:**
```bash
uv run kindle-sync web                  # Start on localhost:5000
uv run kindle-sync web --port 8080      # Custom port
```

### Web Interface

The web interface provides:
- Grid view of all books with cover images
- Individual book pages with all highlights
- Full-text search across highlights and notes
- Edit book metadata (ISBN, genres, reading dates, prices)
- Add reviews and star ratings
- Hide highlights you don't want to export
- Configure export and image directories
- Trigger sync and export operations

Access settings at `http://localhost:5000/settings`

### macOS Menu Bar App

Run as a native macOS app with a menu bar icon:

```bash
uv run kindle-sync-app
```

Features:
- Background Flask server for web interface
- Quick access to sync, export, and settings
- Desktop notifications for operations
- Open web interface from menu

To build a standalone .app bundle:
```bash
uv run --extra app python setup.py py2app
```

## Features

### Highlight Management
- Incremental sync (only downloads new/changed highlights)
- Preserves highlight colors (yellow, blue, pink, orange)
- Track highlight locations and page numbers
- Add personal notes to highlights
- Hide highlights from exports

### Book Metadata
- Extended metadata beyond Kindle data: ISBN, genres, reading dates, prices (GBP/INR)
- Purchase and reading time tracking
- Goodreads and shop links
- Reading status (Done, Started, Not Started, Abandoned)
- Book format (eBook, Paperback, Hardcover, Audiobook)

### Reviews and Ratings
- Write reviews for books
- Add star ratings (out of 5.0)
- Edit metadata through web interface

### Export Options
- Multiple formats: Markdown, JSON, CSV
- Customizable Jinja2 templates
- Four built-in templates:
  - **simple**: Minimal, just highlights
  - **astro**: Metadata in frontmatter, highlights and review in the main body. 

  - **astro**: Astro-compatible with frontmatter
- Custom templates supported

### Image Management
- Download book cover images
- Configurable image sizes (160px to 600px)
- Parallel downloads for speed
- Automatic URL cleanup for original images

### Multi-Region Support
Eight Amazon regions with region-specific date formats and URLs.

## Configuration

**Database:** `~/.kindle-sync/highlights.db` (override with `--db` flag)

**Directories:**
- Export: `~/.kindle-sync/exports` (configurable in web settings)
- Images: `~/.kindle-sync/images` (configurable in web settings)
- Custom templates: `~/.kindle-sync/templates/`

## Authentication

Uses browser-based login for security. No credentials are stored, only session cookies. Sessions expire after a year.

## Data Storage

All data stored locally in SQLite:
- **Books**: Title, author, ASIN, metadata, review, rating
- **Highlights**: Text, location, page, note, color, visibility
- **Session**: Amazon cookies and region
- **Metadata**: Last sync time, export/image directories

## Development

See [Claude.md](Claude.md) for architecture details and development workflows.

**Quick commands:**
```bash
uv run pytest                 # Run tests
uv run ruff format .          # Format code
uv run ruff check --fix .     # Lint and fix
uvx ty check                  # Type checking
```

## Troubleshooting

**Login fails:** Ensure region matches your Amazon account. Try `--no-headless` flag to see browser.

**Session expired:** Run `kindle-sync logout` then `kindle-sync login` to refresh.

**No highlights found:** Verify highlights exist at read.amazon.com. Try `--full` sync.

**Database locked:** Close other instances. Check file permissions: `chmod 600 ~/.kindle-sync/highlights.db`

## Limitations

- Only supports Amazon Kindle (no Kobo, Apple Books, etc.)
- Depends on Amazon's HTML structure (may break if they change it)
- Search uses SQL LIKE (not full-text index)

## License

MIT License

## Acknowledgments

Inspired by [obsidian-kindle-plugin](https://github.com/hadynz/obsidian-kindle-plugin).

## Future Features

- [x] Migrate prices to floats
- [x] Show images locally.
- [x] Use ISBN to fetch genres and page count from Goodreads.
- [ ] Figure out why Dopamine nation and Project Hail Mary aren't being parsed.
- [ ] Figure out why highlights are being misclassified. Like the ones at the end of Circe. Or Circe in the middle of A Little Hatred.
- [ ] Add a pre-commit hook that runs `ruff` and `ty`
- [ ] Explore htmx in the frontend.

# Kindle Highlights Sync

A Python tool to sync your Kindle highlights from Amazon to a local SQLite database and export them to various formats.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

## Features

- **One-time authentication**: Log in once, reuse session for future syncs
- **Automatic sync**: Download all your Kindle books and highlights
- **Local storage**: SQLite database for offline access
- **Multiple export formats**: Markdown, JSON, CSV
- **Customizable templates**: Jinja2-based Markdown templates
- **Multi-region support**: Works with Amazon.com, .co.uk, .de, .jp, and more
- **CLI interface**: Simple command-line interface

## Installation

### Prerequisites

- Python 3.10 or higher
- Chrome or Firefox browser (for authentication)

### Using uv (Recommended)

```bash
# Clone the repository
git clone <repo-url>
cd kindle-highlights-sync

# Install dependencies (creates .venv automatically)
uv sync

# Verify installation
uv run kindle-sync --version
```

### Using pip

```bash
# Clone the repository
git clone <repo-url>
cd kindle-highlights-sync

# Install
pip install -e .

# Verify installation
kindle-sync --version
```

## Quick Start

### 1. Authenticate with Amazon

```bash
uv run kindle-sync login
```

This opens a browser window where you log in to your Amazon account. Once authenticated, your session is saved locally.

### 2. Sync Your Highlights

```bash
uv run kindle-sync sync
```

This downloads all your books and highlights to a local SQLite database.

### 3. Export Your Highlights

```bash
uv run kindle-sync export ./my-highlights
```

This exports all your highlights to Markdown files in the `./my-highlights` directory.

## Usage

### Authentication

```bash
# Login with default region (amazon.com)
uv run kindle-sync login

# Login with specific region
uv run kindle-sync login --region uk

# Run browser in headless mode (no window)
uv run kindle-sync login --headless
```

### Syncing

```bash
# Incremental sync (default) - only new highlights
uv run kindle-sync sync

# Full sync - all books and highlights
uv run kindle-sync sync --full

# Sync specific books only
uv run kindle-sync sync --books abc123,def456
```

### Exporting

```bash
# Export all books to Markdown (default)
uv run kindle-sync export ./output

# Export to JSON
uv run kindle-sync export ./output --format json

# Export to CSV
uv run kindle-sync export ./output --format csv

# Use custom template
uv run kindle-sync export ./output --template detailed

# Export specific books only
uv run kindle-sync export ./output --books abc123,def456
```

### Listing Books

```bash
# List all books in database
uv run kindle-sync list

# Output as JSON
uv run kindle-sync list --format json

# Sort by author
uv run kindle-sync list --sort author
```

### Show Book Details

```bash
# Show details for a specific book
uv run kindle-sync show abc123
```

### Check Status

```bash
# Show sync status and statistics
uv run kindle-sync status
```

### Logout

```bash
# Clear stored session
uv run kindle-sync logout
```

## Configuration

### Database Location

Default: `~/.kindle-sync/highlights.db`

Override with `--db` flag:
```bash
uv run kindle-sync --db /path/to/custom.db sync
```

### Supported Regions

| Region          | Code      | Amazon Site         |
|-----------------|-----------|---------------------|
| Global (US)     | `global`  | amazon.com          |
| United Kingdom  | `uk`      | amazon.co.uk        |
| Germany         | `germany` | amazon.de           |
| Japan           | `japan`   | amazon.co.jp        |
| India           | `india`   | amazon.in           |
| Spain           | `spain`   | amazon.es           |
| Italy           | `italy`   | amazon.it           |
| France          | `france`  | amazon.fr           |

### Export Templates

Built-in Markdown templates:

- **default**: Comprehensive export with all metadata
- **simple**: Minimal export with just highlights
- **detailed**: Full export with notes and colors

Custom templates can be placed in `~/.kindle-sync/templates/`.

## Example Workflow

```bash
# Initial setup
uv run kindle-sync login --region uk
uv run kindle-sync sync --full

# Daily workflow
uv run kindle-sync sync
uv run kindle-sync export ~/Documents/highlights

# Export specific book to JSON
uv run kindle-sync list  # Find book ID
uv run kindle-sync export ./output --books abc123 --format json
```

## Output Examples

### Markdown Export

```markdown
# Atomic Habits

**Author:** James Clear  
**ASIN:** B01N5AX61W  
**Last Annotated:** 2023-10-15

---

## Highlights

### Location 254-267 (Page 12)

> You do not rise to the level of your goals. You fall to the level of your systems.

**Note:** Important concept about systems vs goals

*Color: yellow*

---

**Total Highlights:** 42
```

### JSON Export

```json
{
  "book": {
    "id": "3a7f",
    "title": "Atomic Habits",
    "author": "James Clear",
    "asin": "B01N5AX61W"
  },
  "highlights": [
    {
      "id": "9f2e",
      "text": "You do not rise to the level of your goals...",
      "location": "254-267",
      "page": "12",
      "color": "yellow"
    }
  ]
}
```

## Project Structure

```
kindle-highlights-sync/
├── src/
│   └── kindle_sync/
│       ├── __init__.py         # Package initialization
│       ├── cli.py              # CLI commands
│       ├── auth.py             # Authentication
│       ├── scraper.py          # Web scraping
│       ├── database.py         # Database operations
│       ├── exporter.py         # Export functionality
│       ├── models.py           # Data models
│       ├── config.py           # Configuration
│       ├── utils.py            # Utilities
│       └── templates/          # Export templates
├── tests/                      # Test suite
├── docs/                       # Documentation
│   ├── SPECIFICATION.md        # Technical specification
│   ├── DATABASE.md             # Database schema
│   └── API.md                  # API documentation
├── pyproject.toml              # Project configuration
└── README.md                   # This file
```

## Development

### Setup Development Environment

```bash
# Clone repository
git clone <repo-url>
cd kindle-highlights-sync

# Install with dev dependencies
uv sync
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=kindle_sync --cov-report=html

# Run specific test
uv run pytest tests/test_database.py
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Type checking
uv run mypy src/kindle_sync
```

### Pre-commit Checklist

Before committing:

```bash
uv run ruff format .
uv run ruff check --fix .
uv run mypy src/kindle_sync
uv run pytest
```

## Documentation

- [Getting Started](docs/Getting-Started.md) - Installation and usage guide
- [Technical Specification](docs/Specification.md) - Complete technical reference

## How It Works

### Authentication

1. Opens a browser window with Amazon login page
2. User logs in through Amazon's standard interface
3. After successful login, extracts session cookies
4. Stores cookies in local SQLite database
5. Reuses cookies for future requests

### Scraping

1. Loads `https://read.amazon.com/notebook` with stored cookies
2. Parses HTML to extract books (title, author, ASIN, etc.)
3. For each book, loads highlights page with pagination
4. Extracts highlights (text, location, page, note, color)
5. Generates unique IDs using Fletcher-16 hash

### Storage

- SQLite database with three main tables: `books`, `highlights`, `session`
- Book ID: Hash of lowercase title
- Highlight ID: Hash of lowercase text
- Foreign key relationship: highlights → books (cascade delete)

### Export

- Jinja2 templates for Markdown rendering
- JSON export with structured data
- CSV export for spreadsheet import
- Configurable output format and location

## Troubleshooting

### "Login failed"

- Ensure you're using the correct region
- Try non-headless mode: `uv run kindle-sync login --no-headless`
- Check if two-factor authentication is enabled (may require manual intervention)

### "Session expired"

- Run `uv run kindle-sync logout` and then `uv run kindle-sync login` again
- Amazon sessions typically expire after a week

### "No books found"

- Ensure you have highlights in your Amazon Kindle account
- Check that you're using the correct region
- Try `uv run kindle-sync sync --full` for a complete refresh

### "Database locked"

- Ensure no other instances are running
- Check file permissions on database file
- Try closing any database browser tools

## Limitations

- Requires manual login (no credential storage for security)
- Session expires after ~7 days (requires re-login)
- Depends on Amazon's HTML structure (may break if Amazon changes their site)
- Cannot sync highlights from books purchased on other platforms
- No support for "My Clippings.txt" import (planned for future)

## Security

- **No credentials stored**: Only session cookies are saved
- **Local database**: All data stored on your machine
- **Secure deletion**: Use `logout` to clear session
- **File permissions**: Database file should be readable only by you (600)

### Security Best Practices

1. Use `logout` when done syncing
2. Don't share your database file (contains session data)
3. Keep your system secure (database is not encrypted by default)
4. Consider encrypting the database file for additional security

## Inspiration

This project is inspired by [obsidian-kindle-plugin](https://github.com/hadynz/obsidian-kindle-plugin), which provides similar functionality for Obsidian users. This implementation provides a standalone, CLI-focused alternative.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run code quality checks (`ruff`, `mypy`, `pytest`)
5. Submit a pull request

## Roadmap

### Version 0.2.0
- [ ] Incremental sync optimization
- [ ] Search within highlights
- [ ] Custom template support
- [ ] Export to Notion/Obsidian formats

### Version 0.3.0
- [ ] Web UI for browsing highlights
- [ ] Statistics and analytics
- [ ] Tagging system
- [ ] Highlight annotations

### Version 0.4.0
- [ ] My Clippings.txt import
- [ ] Multiple account support
- [ ] Cloud backup integration
- [ ] Mobile companion app

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Inspired by [obsidian-kindle-plugin](https://github.com/hadynz/obsidian-kindle-plugin)
- Built with [Selenium](https://www.selenium.dev/), [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/), and [Click](https://click.palletsprojects.com/)

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/kindle-highlights-sync/issues)
- **Documentation**: See `docs/` directory
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/kindle-highlights-sync/discussions)

---

**Happy highlighting!** 📚✨

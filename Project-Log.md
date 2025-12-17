# Kindle Highlights Sync - Project Summary

## Setup & Infrastructure

- Project initialized with `uv`, `pyproject.toml`, ruff configuration

## Next Tasks to Implement

### 1. **scraper.py** - Web scraping module
   - Scrape books list from Amazon notebook
   - Scrape highlights for each book with pagination
   - Parse HTML with BeautifulSoup
   - Handle region-specific date formats
   - Error handling for network issues

### 2. **exporter.py** - Export functionality
   - Markdown export with Jinja2 templates
   - JSON export
   - CSV export
   - Filename generation (`author-title.md`)
   - Create default templates

### 3. **CLI completion** - Remaining commands
   - `sync` command (calls scraper + database)
   - `export` command (calls exporter)
   - `list` command (shows all books)
   - `show <asin>` command (book details)

### 4. **Templates** - Export templates
   - Create `src/kindle_sync/templates/` directory
   - `default.md.j2` - Comprehensive template
   - `simple.md.j2` - Minimal template
   - `detailed.md.j2` - Full metadata template

### 5. **Testing** - Test suite
   - Unit tests for utils, database, models
   - Integration tests for scraper
   - Mock fixtures for testing
   - Achieve 80%+ coverage

---

**Current Status**: Authentication and database infrastructure complete. Ready to implement scraping → export → CLI integration.

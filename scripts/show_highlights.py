"""Script to scrape and display all highlights for a single book from Amazon."""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from kindle_sync.models import AmazonRegion, Book
from kindle_sync.services.auth_service import AuthManager
from kindle_sync.services.database_service import DatabaseManager
from kindle_sync.services.scraper_service import KindleScraper


def main():
    """Scrape and display all highlights for a book from Amazon."""
    if len(sys.argv) < 2:
        print("Usage: python show_highlights.py <ASIN>")
        print("\nExample: python show_highlights.py B00H25FCSQ")
        sys.exit(1)

    asin = sys.argv[1]

    # Get database path to retrieve session
    db_path = Path.home() / ".kindle-sync" / "highlights.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("Please run 'kindle-sync login' first")
        sys.exit(1)

    db = DatabaseManager(str(db_path))
    db.init_schema()

    # Get region and authenticate
    region = AmazonRegion(db.get_session("region") or "global")
    auth = AuthManager(db, region)

    if not auth.is_authenticated():
        print("Not authenticated. Please run 'kindle-sync login' first")
        db.close()
        sys.exit(1)

    # Create scraper
    scraper = KindleScraper(auth.get_session(), region)

    print(f"Scraping highlights for ASIN: {asin}")
    print("This will fetch fresh data from Amazon...")
    print()

    # Create a minimal book object for scraping
    book = Book(
        asin=asin,
        title="Unknown",
        author="Unknown",
    )

    try:
        # Scrape highlights directly from Amazon
        highlights = scraper.scrape_highlights(book)
    except Exception as e:
        print(f"Error scraping highlights: {e}")
        db.close()
        sys.exit(1)

    print("=" * 80)
    print(f"ASIN: {asin}")
    print("=" * 80)
    print()

    print(f"Total highlights scraped: {len(highlights)}")
    print()

    # Display each highlight
    for i, highlight in enumerate(highlights, 1):
        print(f"[{i}] " + "=" * 75)
        print(f"ID: {highlight.id}")

        if highlight.location:
            print(f"Location: {highlight.location}")
        if highlight.page:
            print(f"Page: {highlight.page}")
        if highlight.color:
            print(f"Color: {highlight.color}")
        if highlight.created_date:
            print(f"Created: {highlight.created_date}")

        print()
        print("Text:")
        print(f"  {highlight.text}")
        print()

        if highlight.note:
            print("Note:")
            print(f"  {highlight.note}")
            print()

        print()

    db.close()


if __name__ == "__main__":
    main()

"""Sync service for both CLI and web interfaces."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from kindle_sync.models import AmazonRegion
from kindle_sync.services.auth_service import AuthManager
from kindle_sync.services.database_service import DatabaseManager
from kindle_sync.services.scraper_service import KindleScraper


@dataclass
class BookSyncDetail:
    """Details about a single book's sync."""

    asin: str
    title: str
    author: str
    new_highlights: int
    deleted_highlights: int
    total_highlights: int


@dataclass
class SyncResult:
    """Result of sync operation."""

    success: bool
    message: str
    books_synced: int = 0
    new_highlights: int = 0
    deleted_highlights: int = 0
    error: str | None = None
    book_details: list[BookSyncDetail] = field(default_factory=list)


class SyncService:
    """Service for sync operations."""

    @staticmethod
    def sync(
        db_path: str,
        full: bool = False,
        book_asins: list[str] | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> SyncResult:
        """Sync books and highlights from Amazon."""
        db = DatabaseManager(db_path)
        db.init_schema()

        try:
            region = AmazonRegion(db.get_session("region") or "global")
            auth = AuthManager(db, region)
            if not auth.is_authenticated():
                db.close()
                return SyncResult(
                    success=False, message="Not authenticated", error="Please login first"
                )

            scraper = KindleScraper(auth.get_session(), region)

            if progress_callback:
                progress_callback("Fetching books from Amazon...")

            scraped_books = scraper.scrape_books()
            if not scraped_books:
                db.close()
                return SyncResult(success=True, message="No books found", books_synced=0)

            if book_asins:
                scraped_books = [b for b in scraped_books if b.asin in book_asins]
                if not scraped_books:
                    db.close()
                    return SyncResult(
                        success=False,
                        message="None of the specified books found",
                        error=f"Books not found: {', '.join(book_asins)}",
                    )

            for book in scraped_books:
                # Fetch Goodreads data if we have an ISBN
                if book.isbn:
                    try:
                        genres, page_count = scraper.scrape_goodreads_metadata(book.isbn)
                        if genres:
                            book.genres = genres
                        if page_count:
                            book.page_count = page_count
                    except Exception as e:
                        print(f"Failed to fetch Goodreads data for {book.title}: {e}")

                db.insert_book(book)

            total_new = 0
            total_deleted = 0
            book_details = []

            for i, book in enumerate(scraped_books, 1):
                if progress_callback:
                    progress_callback(
                        f"Syncing '{book.title}' by {book.author} ({i}/{len(scraped_books)})"
                    )

                highlights = scraper.scrape_highlights(book)
                existing_highlights = db.get_highlights(book.asin)
                existing_ids = {h.id for h in existing_highlights}
                scraped_ids = {h.id for h in highlights}

                new_count = 0
                for highlight in highlights:
                    if highlight.id not in existing_ids:
                        new_count += 1
                    db.insert_highlight(highlight)

                deleted_ids = existing_ids - scraped_ids
                if deleted_ids:
                    db.delete_highlights(list(deleted_ids))

                total_new += new_count
                total_deleted += len(deleted_ids)

                book_details.append(
                    BookSyncDetail(
                        asin=book.asin,
                        title=book.title,
                        author=book.author,
                        new_highlights=new_count,
                        deleted_highlights=len(deleted_ids),
                        total_highlights=len(highlights),
                    )
                )

            db.set_last_sync(datetime.now())
            db.close()

            if progress_callback:
                progress_callback("Sync complete!")

            return SyncResult(
                success=True,
                message="Sync complete",
                books_synced=len(scraped_books),
                new_highlights=total_new,
                deleted_highlights=total_deleted,
                book_details=book_details,
            )
        except Exception as e:
            db.close()
            return SyncResult(success=False, message="Sync failed", error=str(e))

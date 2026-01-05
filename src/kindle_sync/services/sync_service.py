"""Sync service for both CLI and web interfaces."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from kindle_sync.models import AmazonRegion, Book
from kindle_sync.services.auth_service import AuthManager
from kindle_sync.services.database_service import DatabaseManager
from kindle_sync.services.scraper_service import KindleScraper, ScraperError


@dataclass
class AddPhysicalBookResult:
    """Result of adding a physical book."""

    success: bool
    message: str
    book: Book | None = None
    error: str | None = None


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
        progress_callback: Callable[[str], None] | None = None,
    ) -> SyncResult:
        """Full sync: scrape all books from Amazon and sync their highlights.

        Args:
            db_path: Path to the database
            progress_callback: Optional callback for progress updates

        Returns:
            SyncResult with sync statistics
        """
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

            # Full sync: scrape all books from Amazon
            if progress_callback:
                progress_callback("Fetching books from Amazon...")

            scraped_books = scraper.scrape_books()
            if not scraped_books:
                db.close()
                return SyncResult(success=True, message="No books found", books_synced=0)

            # Insert/update books in database
            for book in scraped_books:
                db.insert_book(book)

            books_to_sync = scraped_books

            total_new = 0
            total_deleted = 0
            book_details = []

            for i, book in enumerate(books_to_sync, 1):
                if progress_callback:
                    progress_callback(
                        f"Syncing '{book.title}' by {book.author} ({i}/{len(books_to_sync)})"
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
                books_synced=len(books_to_sync),
                new_highlights=total_new,
                deleted_highlights=total_deleted,
                book_details=book_details,
            )
        except Exception as e:
            db.close()
            return SyncResult(success=False, message="Sync failed", error=str(e))

    @staticmethod
    def sync_single_book(
        db_path: str,
        asin: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> SyncResult:
        """
        Sync a single book by ASIN.

        This method fetches the book metadata from Amazon and syncs its highlights.
        If the book doesn't exist in the database, it will be added.

        Args:
            db_path: Path to the database
            asin: Amazon Standard Identification Number
            progress_callback: Optional callback for progress updates

        Returns:
            SyncResult with sync statistics
        """
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
                progress_callback(f"Fetching book {asin} from Amazon...")

            # Fetch the book from Amazon
            book = scraper.scrape_single_book(asin)
            if not book:
                db.close()
                return SyncResult(
                    success=False,
                    message="Book not found",
                    error=f"Book with ASIN {asin} not found in your Kindle library",
                )

            print(book.title)
            print(book.goodreads_link)
            print(book.genres)
            # Insert/update book in database (upsert to update metadata if book exists)
            db.upsert_book(book)

            if progress_callback:
                progress_callback(f"Syncing highlights for '{book.title}'...")

            # Sync highlights
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

            book_detail = BookSyncDetail(
                asin=book.asin,
                title=book.title,
                author=book.author,
                new_highlights=new_count,
                deleted_highlights=len(deleted_ids),
                total_highlights=len(highlights),
            )

            db.set_last_sync(datetime.now())
            db.close()

            if progress_callback:
                progress_callback("Sync complete!")

            return SyncResult(
                success=True,
                message=f"Synced '{book.title}'",
                books_synced=1,
                new_highlights=new_count,
                deleted_highlights=len(deleted_ids),
                book_details=[book_detail],
            )
        except Exception as e:
            db.close()
            return SyncResult(success=False, message="Sync failed", error=str(e))

    @staticmethod
    def sync_new_books(
        db_path: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> SyncResult:
        """
        Scan for and sync new books that aren't in the database.

        This method efficiently scans through the Kindle library and only
        syncs books that haven't been seen before.

        Args:
            db_path: Path to the database
            progress_callback: Optional callback for progress updates

        Returns:
            SyncResult with sync statistics
        """
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
                progress_callback("Scanning for new books...")

            # Get existing ASINs from database
            existing_books = db.get_all_books()
            existing_asins = {book.asin for book in existing_books}

            # Fetch new books from Amazon
            new_books = scraper.scrape_new_books(existing_asins)

            if not new_books:
                db.close()
                return SyncResult(
                    success=True,
                    message="No new books found",
                    books_synced=0,
                )

            if progress_callback:
                progress_callback(f"Found {len(new_books)} new book(s)")

            # Insert new books and sync their highlights
            total_new = 0
            book_details = []

            for i, book in enumerate(new_books, 1):
                if progress_callback:
                    progress_callback(
                        f"Syncing '{book.title}' by {book.author} ({i}/{len(new_books)})"
                    )

                # Insert book
                db.insert_book(book)

                # Sync highlights
                highlights = scraper.scrape_highlights(book)
                for highlight in highlights:
                    db.insert_highlight(highlight)

                total_new += len(highlights)

                book_details.append(
                    BookSyncDetail(
                        asin=book.asin,
                        title=book.title,
                        author=book.author,
                        new_highlights=len(highlights),
                        deleted_highlights=0,
                        total_highlights=len(highlights),
                    )
                )

            db.set_last_sync(datetime.now())
            db.close()

            if progress_callback:
                progress_callback("Sync complete!")

            return SyncResult(
                success=True,
                message=f"Synced {len(new_books)} new book(s)",
                books_synced=len(new_books),
                new_highlights=total_new,
                deleted_highlights=0,
                book_details=book_details,
            )
        except Exception as e:
            db.close()
            return SyncResult(success=False, message="Sync failed", error=str(e))

    @staticmethod
    def add_physical_book(
        db_path: str, asin: str, isbn: str | None = None
    ) -> AddPhysicalBookResult:
        """
        Add a physical book by scraping metadata from Amazon and Goodreads.

        Args:
            db_path: Path to the database
            asin: Amazon Standard Identification Number
            isbn: International Standard Book Number (optional)

        Returns:
            AddPhysicalBookResult with the scraped book data
        """
        db = DatabaseManager(db_path)
        db.init_schema()

        try:
            region = AmazonRegion(db.get_session("region") or "global")
            auth = AuthManager(db, region)
            if not auth.is_authenticated():
                db.close()
                return AddPhysicalBookResult(
                    success=False, message="Not authenticated", error="Please login first"
                )

            scraper = KindleScraper(auth.get_session(), region)

            # Scrape physical book metadata
            book = scraper.scrape_physical_book(asin, isbn)

            # Insert book into database
            db.insert_book(book)
            db.close()

            # Download book cover image if available
            if book.image_url:
                from kindle_sync.models import ImageSize
                from kindle_sync.services.image_service import ImageService

                # Use ImageService to download the image
                image_result = ImageService.sync_book_image(
                    db_path, book.asin, size=ImageSize.ORIGINAL
                )
                if not image_result.success:
                    # Log warning but don't fail the entire operation
                    print(
                        f"Warning: Failed to download image for book '{book.title}': {image_result.error}"
                    )

            return AddPhysicalBookResult(
                success=True, message="Physical book added successfully", book=book
            )

        except ScraperError as e:
            db.close()
            return AddPhysicalBookResult(
                success=False, message="Failed to scrape book data", error=str(e)
            )
        except Exception as e:
            db.close()
            return AddPhysicalBookResult(
                success=False, message="Failed to add physical book", error=str(e)
            )

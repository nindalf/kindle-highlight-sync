"""Database operations for Kindle Highlights Sync."""

import sqlite3
from datetime import datetime
from pathlib import Path

from kindle_sync.models import Book, BookWithHighlightCount, Highlight, HighlightColor, SearchResult


class DatabaseError(Exception):
    """Raised when database operations fail."""

    pass


class DatabaseManager:
    """Manages SQLite database operations."""

    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def init_schema(self) -> None:
        """Create database schema if it doesn't exist."""
        self.connect()
        assert self.conn is not None

        # Create books table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS books (
                asin TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                url TEXT,
                image_url TEXT,
                last_annotated_date TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                purchase_date TEXT,
                status TEXT,
                format TEXT,
                notes TEXT,
                start_date TEXT,
                end_date TEXT,
                reading_time TEXT,
                genres TEXT,
                shop_link TEXT,
                isbn TEXT,
                classification TEXT,
                goodreads_link TEXT,
                price_gbp TEXT,
                price_inr TEXT,
                review TEXT,
                star_rating REAL
            )
        """)

        # Create indexes for books
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_books_author ON books(author)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)")

        # Create highlights table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS highlights (
                id TEXT PRIMARY KEY,
                book_asin TEXT NOT NULL,
                text TEXT NOT NULL,
                location TEXT,
                page TEXT,
                note TEXT,
                color TEXT,
                created_date TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_hidden INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (book_asin) REFERENCES books(asin) ON DELETE CASCADE
            )
        """)

        # Create indexes for highlights
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_highlights_book_asin ON highlights(book_asin)"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_highlights_color ON highlights(color)")

        # Create session table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS session (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create sync_metadata table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def save_session(self, key: str, value: str) -> None:
        self.connect()
        assert self.conn is not None
        self.conn.execute(
            """
            INSERT INTO session (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        self.conn.commit()

    def get_session(self, key: str) -> str | None:
        self.connect()
        assert self.conn is not None
        cursor = self.conn.execute("SELECT value FROM session WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

    def clear_session(self) -> None:
        self.connect()
        assert self.conn is not None
        self.conn.execute("DELETE FROM session")
        self.conn.commit()

    def insert_book(self, book: Book) -> None:
        """Insert a book only if it doesn't exist (no update on conflict)."""
        self.connect()
        assert self.conn is not None
        try:
            self.conn.execute(
                """
                INSERT INTO books (
                    asin, title, author, url, image_url,
                    last_annotated_date, updated_at,
                    purchase_date, status, format, notes,
                    start_date, end_date, reading_time, genres,
                    shop_link, isbn, classification, goodreads_link,
                    price_gbp, price_inr, review, star_rating
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asin) DO NOTHING
                """,
                (
                    book.asin,
                    book.title,
                    book.author,
                    book.url,
                    book.image_url,
                    book.last_annotated_date.isoformat() if book.last_annotated_date else None,
                    book.purchase_date.isoformat() if book.purchase_date else None,
                    book.status,
                    book.format,
                    book.notes,
                    book.start_date.isoformat() if book.start_date else None,
                    book.end_date.isoformat() if book.end_date else None,
                    book.reading_time,
                    book.genres,
                    book.shop_link,
                    book.isbn,
                    book.classification,
                    book.goodreads_link,
                    book.price_gbp,
                    book.price_inr,
                    book.review,
                    book.star_rating,
                ),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to insert book: {e}") from e

    def get_book(self, asin: str) -> Book | None:
        self.connect()
        assert self.conn is not None
        cursor = self.conn.execute(
            """
            SELECT asin, title, author, url, image_url, last_annotated_date,
                   created_at, updated_at,
                   purchase_date, status, format, notes,
                   start_date, end_date, reading_time, genres,
                   shop_link, isbn, classification, goodreads_link,
                   price_gbp, price_inr, review, star_rating
            FROM books WHERE asin = ?
            """,
            (asin,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return Book(
            asin=row[0],
            title=row[1],
            author=row[2],
            url=row[3],
            image_url=row[4],
            last_annotated_date=datetime.fromisoformat(row[5]) if row[5] else None,
            created_at=datetime.fromisoformat(row[6]) if row[6] else None,
            updated_at=datetime.fromisoformat(row[7]) if row[7] else None,
            purchase_date=datetime.fromisoformat(row[8]) if row[8] else None,
            status=row[9],
            format=row[10],
            notes=row[11],
            start_date=datetime.fromisoformat(row[12]) if row[12] else None,
            end_date=datetime.fromisoformat(row[13]) if row[13] else None,
            reading_time=row[14],
            genres=row[15],
            shop_link=row[16],
            isbn=row[17],
            classification=row[18],
            goodreads_link=row[19],
            price_gbp=row[20],
            price_inr=row[21],
            review=row[22],
            star_rating=row[23],
        )

    def get_all_books(self, sort_by: str = "title") -> list[Book]:
        self.connect()
        assert self.conn is not None
        cursor = self.conn.execute(
            """
            SELECT asin, title, author, url, image_url, last_annotated_date,
                   created_at, updated_at,
                   purchase_date, status, format, notes,
                   start_date, end_date, reading_time, genres,
                   shop_link, isbn, classification, goodreads_link,
                   price_gbp, price_inr, review, star_rating
            FROM books
            ORDER BY title
            """
        )

        books = [
            Book(
                asin=row[0],
                title=row[1],
                author=row[2],
                url=row[3],
                image_url=row[4],
                last_annotated_date=datetime.fromisoformat(row[5]) if row[5] else None,
                created_at=datetime.fromisoformat(row[6]) if row[6] else None,
                updated_at=datetime.fromisoformat(row[7]) if row[7] else None,
                purchase_date=datetime.fromisoformat(row[8]) if row[8] else None,
                status=row[9],
                format=row[10],
                notes=row[11],
                start_date=datetime.fromisoformat(row[12]) if row[12] else None,
                end_date=datetime.fromisoformat(row[13]) if row[13] else None,
                reading_time=row[14],
                genres=row[15],
                shop_link=row[16],
                isbn=row[17],
                classification=row[18],
                goodreads_link=row[19],
                price_gbp=row[20],
                price_inr=row[21],
                review=row[22],
                star_rating=row[23],
            )
            for row in cursor.fetchall()
        ]

        if sort_by == "author":
            books.sort(key=lambda b: b.author)
        elif sort_by == "date":
            books.sort(key=lambda b: b.last_annotated_date or datetime.min, reverse=True)

        return books

    def book_exists(self, asin: str) -> bool:
        self.connect()
        assert self.conn is not None
        cursor = self.conn.execute("SELECT 1 FROM books WHERE asin = ?", (asin,))
        return cursor.fetchone() is not None

    def update_book_metadata(self, asin: str, **kwargs) -> None:
        """Update specific fields of a book's metadata."""
        self.connect()
        assert self.conn is not None

        # Build update query dynamically based on provided fields
        allowed_fields = {
            "title",
            "purchase_date",
            "status",
            "format",
            "notes",
            "start_date",
            "end_date",
            "reading_time",
            "genres",
            "shop_link",
            "isbn",
            "classification",
            "goodreads_link",
            "price_gbp",
            "price_inr",
            "review",
            "star_rating",
        }

        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not update_fields:
            return

        # Convert datetime objects to ISO format strings
        for field in ["purchase_date", "start_date", "end_date"]:
            if field in update_fields and update_fields[field] is not None:
                if isinstance(update_fields[field], datetime):
                    update_fields[field] = update_fields[field].isoformat()

        set_clause = ", ".join(f"{field} = ?" for field in update_fields.keys())
        query = f"UPDATE books SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE asin = ?"

        try:
            self.conn.execute(query, (*update_fields.values(), asin))
            self.conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to update book metadata: {e}") from e

    def get_last_sync(self) -> datetime | None:
        self.connect()
        assert self.conn is not None
        cursor = self.conn.execute("SELECT value FROM sync_metadata WHERE key = 'last_sync'")
        if row := cursor.fetchone():
            try:
                return datetime.fromisoformat(row[0])
            except ValueError:
                return None
        return None

    def set_last_sync(self, timestamp: datetime) -> None:
        self.connect()
        assert self.conn is not None
        self.conn.execute(
            """
            INSERT INTO sync_metadata (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            ("last_sync", timestamp.isoformat()),
        )
        self.conn.commit()

    def insert_highlight(self, highlight: Highlight) -> None:
        """Insert or update a highlight (UPSERT)."""
        self.connect()
        assert self.conn is not None
        try:
            self.conn.execute(
                """
                INSERT INTO highlights (
                    id, book_asin, text, location, page, note, color, created_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    text = excluded.text,
                    location = excluded.location,
                    page = excluded.page,
                    note = excluded.note,
                    color = excluded.color,
                    created_date = excluded.created_date
                """,
                (
                    highlight.id,
                    highlight.book_asin,
                    highlight.text,
                    highlight.location,
                    highlight.page,
                    highlight.note,
                    highlight.color.value if highlight.color else None,
                    highlight.created_date.isoformat() if highlight.created_date else None,
                ),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to insert highlight: {e}") from e

    def get_highlights(self, book_asin: str) -> list[Highlight]:
        """Get all highlights for a book, ordered by location."""
        self.connect()
        assert self.conn is not None
        cursor = self.conn.execute(
            """
            SELECT id, book_asin, text, location, page, note, color,
                   created_date, created_at, is_hidden
            FROM highlights
            WHERE book_asin = ?
            ORDER BY
                CASE
                    WHEN location IS NOT NULL THEN
                        CAST(substr(location, 1, instr(location || '-', '-') - 1) AS INTEGER)
                    ELSE 999999
                END
            """,
            (book_asin,),
        )

        return [
            Highlight(
                id=row[0],
                book_asin=row[1],
                text=row[2],
                location=row[3],
                page=row[4],
                note=row[5],
                color=HighlightColor(row[6]) if row[6] else None,
                created_date=datetime.fromisoformat(row[7]) if row[7] else None,
                created_at=datetime.fromisoformat(row[8]) if row[8] else None,
                is_hidden=bool(row[9]),
            )
            for row in cursor.fetchall()
        ]

    def get_highlight_count(self, book_asin: str) -> int:
        self.connect()
        assert self.conn is not None
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM highlights WHERE book_asin = ?", (book_asin,)
        )
        row = cursor.fetchone()
        return row[0] if row else 0

    def highlight_exists(self, highlight_id: str) -> bool:
        self.connect()
        assert self.conn is not None
        cursor = self.conn.execute("SELECT 1 FROM highlights WHERE id = ?", (highlight_id,))
        return cursor.fetchone() is not None

    def delete_highlights(self, highlight_ids: list[str]) -> None:
        if not highlight_ids:
            return
        self.connect()
        assert self.conn is not None
        try:
            placeholders = ",".join("?" * len(highlight_ids))
            self.conn.execute(f"DELETE FROM highlights WHERE id IN ({placeholders})", highlight_ids)
            self.conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to delete highlights: {e}") from e

    def search_highlights(self, query: str, book_asin: str | None = None) -> list[SearchResult]:
        """Search highlights by text content."""
        if not query:
            return []

        self.connect()
        assert self.conn is not None

        search_pattern = f"%{query}%"
        sql = """
            SELECT
                h.id, h.book_asin, h.text, h.location, h.page, h.note,
                h.color, h.created_date, h.created_at, h.is_hidden,
                b.asin, b.title, b.author, b.url, b.image_url,
                b.last_annotated_date, b.created_at, b.updated_at
            FROM highlights h
            JOIN books b ON h.book_asin = b.asin
            WHERE (h.text LIKE ? OR h.note LIKE ?)
        """

        if book_asin:
            sql += " AND h.book_asin = ?"
            sql += " ORDER BY b.title, h.page, h.location"
            cursor = self.conn.execute(sql, (search_pattern, search_pattern, book_asin))
        else:
            sql += " ORDER BY b.title, h.page, h.location"
            cursor = self.conn.execute(sql, (search_pattern, search_pattern))

        return [
            SearchResult(
                highlight=Highlight(
                    id=row[0],
                    book_asin=row[1],
                    text=row[2],
                    location=row[3],
                    page=row[4],
                    note=row[5],
                    color=HighlightColor(row[6]) if row[6] else None,
                    created_date=datetime.fromisoformat(row[7]) if row[7] else None,
                    created_at=datetime.fromisoformat(row[8]) if row[8] else None,
                    is_hidden=bool(row[9]),
                ),
                book=Book(
                    asin=row[10],
                    title=row[11],
                    author=row[12],
                    url=row[13],
                    image_url=row[14],
                    last_annotated_date=datetime.fromisoformat(row[15]) if row[15] else None,
                    created_at=datetime.fromisoformat(row[16]) if row[16] else None,
                    updated_at=datetime.fromisoformat(row[17]) if row[17] else None,
                ),
            )
            for row in cursor.fetchall()
        ]

    def get_all_books_with_counts(self, sort_by: str = "title") -> list[BookWithHighlightCount]:
        """Get all books with their highlight counts."""
        books = self.get_all_books(sort_by="title")  # Get unsorted first
        books_with_counts = [
            BookWithHighlightCount(book=book, highlight_count=self.get_highlight_count(book.asin))
            for book in books
        ]

        if sort_by == "author":
            books_with_counts.sort(key=lambda b: b.book.author)
        elif sort_by == "date":
            books_with_counts.sort(
                key=lambda b: b.book.last_annotated_date or datetime.min, reverse=True
            )

        return books_with_counts

    def get_statistics(self) -> dict:
        """Get database statistics."""
        books = self.get_all_books()
        total_highlights = sum(self.get_highlight_count(book.asin) for book in books)
        last_sync = self.get_last_sync()

        return {
            "total_books": len(books),
            "total_highlights": total_highlights,
            "last_sync": last_sync.isoformat() if last_sync else None,
        }

    def get_export_directory(self) -> str | None:
        """Get the configured export directory."""
        self.connect()
        assert self.conn is not None
        cursor = self.conn.execute("SELECT value FROM sync_metadata WHERE key = 'export_directory'")
        if row := cursor.fetchone():
            return row[0]
        return None

    def set_export_directory(self, directory: str) -> None:
        """Set the export directory."""
        self.connect()
        assert self.conn is not None
        self.conn.execute(
            """
            INSERT INTO sync_metadata (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            ("export_directory", directory),
        )
        self.conn.commit()

    def get_images_directory(self) -> str | None:
        """Get the configured images directory."""
        self.connect()
        assert self.conn is not None
        cursor = self.conn.execute("SELECT value FROM sync_metadata WHERE key = 'images_directory'")
        if row := cursor.fetchone():
            return row[0]
        return None

    def set_images_directory(self, directory: str) -> None:
        """Set the images directory."""
        self.connect()
        assert self.conn is not None
        self.conn.execute(
            """
            INSERT INTO sync_metadata (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            ("images_directory", directory),
        )
        self.conn.commit()

    def toggle_highlight_visibility(self, highlight_id: str) -> bool:
        """Toggle the visibility of a highlight. Returns the new is_hidden state."""
        self.connect()
        assert self.conn is not None
        try:
            # Get current state
            cursor = self.conn.execute(
                "SELECT is_hidden FROM highlights WHERE id = ?", (highlight_id,)
            )
            row = cursor.fetchone()
            if row is None:
                raise DatabaseError(f"Highlight {highlight_id} not found")

            current_state = bool(row[0])
            new_state = not current_state

            # Update state
            self.conn.execute(
                "UPDATE highlights SET is_hidden = ? WHERE id = ?",
                (int(new_state), highlight_id),
            )
            self.conn.commit()
            return new_state
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to toggle highlight visibility: {e}") from e

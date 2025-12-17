"""Database operations for Kindle Highlights Sync."""

import sqlite3
from datetime import datetime
from pathlib import Path

from kindle_sync.models import Book


class DatabaseError(Exception):
    """Raised when database operations fail."""

    pass


class DatabaseManager:
    """Manages SQLite database operations."""

    def __init__(self, db_path: str) -> None:
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Establish database connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        """Close database connection."""
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
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

    # Session operations
    def save_session(self, key: str, value: str) -> None:
        """
        Save session data.

        Args:
            key: Session key
            value: Session value (typically JSON string)
        """
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
        """
        Get session data.

        Args:
            key: Session key

        Returns:
            Session value if found, None otherwise
        """
        self.connect()
        assert self.conn is not None

        cursor = self.conn.execute("SELECT value FROM session WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

    def clear_session(self) -> None:
        """Clear all session data."""
        self.connect()
        assert self.conn is not None

        self.conn.execute("DELETE FROM session")
        self.conn.commit()

    # Book operations
    def insert_book(self, book: Book) -> None:
        """
        Insert or update a book.

        Uses UPSERT logic - if book exists, updates it.

        Args:
            book: Book object to insert

        Raises:
            DatabaseError: If insertion fails
        """
        self.connect()
        assert self.conn is not None

        try:
            self.conn.execute(
                """
                INSERT INTO books (
                    asin, title, author, url, image_url,
                    last_annotated_date, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(asin) DO UPDATE SET
                    title = excluded.title,
                    author = excluded.author,
                    url = excluded.url,
                    image_url = excluded.image_url,
                    last_annotated_date = excluded.last_annotated_date,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    book.asin,
                    book.title,
                    book.author,
                    book.url,
                    book.image_url,
                    book.last_annotated_date.isoformat() if book.last_annotated_date else None,
                ),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to insert book: {e}") from e

    def get_book(self, asin: str) -> Book | None:
        """
        Get a book by ASIN.

        Args:
            asin: Book ASIN

        Returns:
            Book object if found, None otherwise
        """
        self.connect()
        assert self.conn is not None

        cursor = self.conn.execute(
            """
            SELECT asin, title, author, url, image_url, last_annotated_date,
                   created_at, updated_at
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
        )

    def get_all_books(self) -> list[Book]:
        """
        Get all books from database.

        Returns:
            List of Book objects, ordered by title
        """
        self.connect()
        assert self.conn is not None

        cursor = self.conn.execute(
            """
            SELECT asin, title, author, url, image_url, last_annotated_date,
                   created_at, updated_at
            FROM books
            ORDER BY title
            """
        )

        books = []
        for row in cursor.fetchall():
            books.append(
                Book(
                    asin=row[0],
                    title=row[1],
                    author=row[2],
                    url=row[3],
                    image_url=row[4],
                    last_annotated_date=datetime.fromisoformat(row[5]) if row[5] else None,
                    created_at=datetime.fromisoformat(row[6]) if row[6] else None,
                    updated_at=datetime.fromisoformat(row[7]) if row[7] else None,
                )
            )

        return books

    def book_exists(self, asin: str) -> bool:
        """
        Check if a book exists.

        Args:
            asin: Book ASIN to check

        Returns:
            True if book exists, False otherwise
        """
        self.connect()
        assert self.conn is not None

        cursor = self.conn.execute("SELECT 1 FROM books WHERE asin = ?", (asin,))
        return cursor.fetchone() is not None

    # Sync metadata operations
    def get_last_sync(self) -> datetime | None:
        """
        Get last successful sync timestamp.

        Returns:
            Datetime of last sync, or None if never synced
        """
        self.connect()
        assert self.conn is not None

        cursor = self.conn.execute("SELECT value FROM sync_metadata WHERE key = 'last_sync'")
        row = cursor.fetchone()

        if row:
            try:
                return datetime.fromisoformat(row[0])
            except ValueError:
                return None

        return None

    def set_last_sync(self, timestamp: datetime) -> None:
        """
        Set last sync timestamp.

        Args:
            timestamp: Sync timestamp
        """
        self.save_session("last_sync", timestamp.isoformat())

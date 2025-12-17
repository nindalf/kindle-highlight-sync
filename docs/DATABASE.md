# Database Schema Documentation

## Overview

The Kindle Highlights Sync application uses SQLite as its local database. This document describes the complete database schema, relationships, and usage patterns.

## Database Location

**Default Path**: `~/.kindle-sync/highlights.db`

**File Permissions**: Should be set to `600` (read/write for owner only) for security.

## Schema Diagram

```
┌─────────────────────────────────────┐
│             books                   │
├─────────────────────────────────────┤
│ id (PK)                TEXT         │
│ title                  TEXT         │
│ author                 TEXT         │
│ asin                   TEXT         │
│ url                    TEXT         │
│ image_url              TEXT         │
│ last_annotated_date    TEXT         │
│ created_at             TEXT         │
│ updated_at             TEXT         │
└──────────────┬──────────────────────┘
               │
               │ 1:N
               │
┌──────────────┴──────────────────────┐
│          highlights                 │
├─────────────────────────────────────┤
│ id (PK)                TEXT         │
│ book_id (FK)           TEXT         │────┐
│ text                   TEXT         │    │
│ location               TEXT         │    │
│ page                   TEXT         │    │
│ note                   TEXT         │    │
│ color                  TEXT         │    │
│ created_date           TEXT         │    │
│ created_at             TEXT         │    │
└─────────────────────────────────────┘    │
                                           │
                                           │
                    FOREIGN KEY ───────────┘
```

## Table Definitions

### 1. `books` Table

Stores metadata about Kindle books.

```sql
CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    asin TEXT,
    url TEXT,
    image_url TEXT,
    last_annotated_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_books_author ON books(author);
CREATE INDEX idx_books_title ON books(title);
CREATE INDEX idx_books_asin ON books(asin);
```

#### Columns

| Column               | Type | Nullable | Description                                           |
|----------------------|------|----------|-------------------------------------------------------|
| `id`                 | TEXT | No       | Fletcher-16 hash of lowercase title (Primary Key)     |
| `title`              | TEXT | No       | Book title                                            |
| `author`             | TEXT | No       | Book author(s)                                        |
| `asin`               | TEXT | Yes      | Amazon Standard Identification Number                 |
| `url`                | TEXT | Yes      | Amazon product page URL                               |
| `image_url`          | TEXT | Yes      | Book cover image URL                                  |
| `last_annotated_date`| TEXT | Yes      | ISO 8601 timestamp of last annotation                 |
| `created_at`         | TEXT | No       | ISO 8601 timestamp of record creation                 |
| `updated_at`         | TEXT | No       | ISO 8601 timestamp of last update                     |

#### Sample Data

```sql
INSERT INTO books VALUES (
    '3a7f',                                    -- id
    'Atomic Habits',                           -- title
    'James Clear',                             -- author
    'B01N5AX61W',                              -- asin
    'https://www.amazon.com/dp/B01N5AX61W',    -- url
    'https://m.media-amazon.com/images/...',   -- image_url
    '2023-10-15T14:30:00',                     -- last_annotated_date
    '2023-10-15T10:00:00',                     -- created_at
    '2023-10-15T14:30:00'                      -- updated_at
);
```

#### Notes

- **ID Generation**: Generated using Fletcher-16 checksum of lowercase title
- **Timestamps**: All timestamps stored in ISO 8601 format (UTC)
- **ASIN**: Unique identifier used by Amazon; may be null for some books
- **Updates**: `updated_at` should be updated whenever the record changes

---

### 2. `highlights` Table

Stores individual highlights/annotations from books.

```sql
CREATE TABLE IF NOT EXISTS highlights (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    text TEXT NOT NULL,
    location TEXT,
    page TEXT,
    note TEXT,
    color TEXT,
    created_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_highlights_book_id ON highlights(book_id);
CREATE INDEX idx_highlights_color ON highlights(color);
```

#### Columns

| Column         | Type | Nullable | Description                                      |
|----------------|------|----------|--------------------------------------------------|
| `id`           | TEXT | No       | Fletcher-16 hash of lowercase text (Primary Key) |
| `book_id`      | TEXT | No       | Foreign key to books.id                          |
| `text`         | TEXT | No       | The highlighted text content                     |
| `location`     | TEXT | Yes      | Kindle location (e.g., "1234-1456")              |
| `page`         | TEXT | Yes      | Page number (if available)                       |
| `note`         | TEXT | Yes      | User's note attached to highlight                |
| `color`        | TEXT | Yes      | Highlight color (yellow, blue, pink, orange)     |
| `created_date` | TEXT | Yes      | ISO 8601 timestamp when highlight was created    |
| `created_at`   | TEXT | No       | ISO 8601 timestamp of record creation            |

#### Sample Data

```sql
INSERT INTO highlights VALUES (
    '9f2e',                                                      -- id
    '3a7f',                                                      -- book_id
    'You do not rise to the level of your goals. You fall...',  -- text
    '254-267',                                                   -- location
    '12',                                                        -- page
    'Important concept about systems vs goals',                 -- note
    'yellow',                                                    -- color
    '2023-10-15T14:30:00',                                       -- created_date
    '2023-10-15T14:30:00'                                        -- created_at
);
```

#### Notes

- **ID Generation**: Generated using Fletcher-16 checksum of lowercase text
- **Foreign Key**: Cascade delete - deleting a book deletes all its highlights
- **Color Values**: Must be one of: `yellow`, `blue`, `pink`, `orange`, or null
- **Location Format**: Kindle location ranges (e.g., "1234-1456")

---

### 3. `session` Table

Stores authentication session data including cookies.

```sql
CREATE TABLE IF NOT EXISTS session (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

#### Columns

| Column       | Type | Nullable | Description                           |
|--------------|------|----------|---------------------------------------|
| `key`        | TEXT | No       | Session data key (Primary Key)        |
| `value`      | TEXT | No       | Session data value (JSON string)      |
| `updated_at` | TEXT | No       | ISO 8601 timestamp of last update     |

#### Sample Data

```sql
INSERT INTO session VALUES (
    'cookies',                                         -- key
    '{"cookies": [{"name": "session-id", ...}]}',      -- value (JSON)
    '2023-10-15T10:00:00'                              -- updated_at
);
```

#### Standard Keys

| Key          | Description                           | Value Format    |
|--------------|---------------------------------------|-----------------|
| `cookies`    | Amazon session cookies                | JSON array      |
| `region`     | Selected Amazon region                | String          |
| `user_agent` | Browser user agent used for scraping  | String          |

#### Notes

- **Security**: This table contains sensitive authentication data
- **Encryption**: Consider encrypting values in production
- **Cleanup**: Clear this table on logout

---

### 4. `sync_metadata` Table

Stores metadata about sync operations.

```sql
CREATE TABLE IF NOT EXISTS sync_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

#### Columns

| Column       | Type | Nullable | Description                           |
|--------------|------|----------|---------------------------------------|
| `key`        | TEXT | No       | Metadata key (Primary Key)            |
| `value`      | TEXT | No       | Metadata value                        |
| `updated_at` | TEXT | No       | ISO 8601 timestamp of last update     |

#### Sample Data

```sql
INSERT INTO sync_metadata VALUES (
    'last_sync',                    -- key
    '2023-10-15T14:30:00',          -- value (timestamp)
    '2023-10-15T14:30:00'           -- updated_at
);
```

#### Standard Keys

| Key                | Description                        | Value Format    |
|--------------------|------------------------------------|-----------------|
| `last_sync`        | Timestamp of last successful sync  | ISO 8601 string |
| `last_full_sync`   | Timestamp of last full sync        | ISO 8601 string |
| `sync_count`       | Total number of syncs performed    | Integer string  |
| `last_sync_status` | Status of last sync (success/fail) | String          |
| `error_count`      | Number of consecutive errors       | Integer string  |

---

## Relationships

### One-to-Many: Books to Highlights

- One book can have many highlights
- Each highlight belongs to exactly one book
- Foreign key: `highlights.book_id` → `books.id`
- Cascade delete: Deleting a book deletes all its highlights

```sql
-- Get all highlights for a book
SELECT h.* 
FROM highlights h
WHERE h.book_id = '3a7f'
ORDER BY h.location;

-- Get book with highlight count
SELECT b.*, COUNT(h.id) as highlight_count
FROM books b
LEFT JOIN highlights h ON b.id = h.book_id
GROUP BY b.id;
```

---

## Common Queries

### Query Examples

#### 1. Get All Books with Highlight Counts

```sql
SELECT 
    b.id,
    b.title,
    b.author,
    b.last_annotated_date,
    COUNT(h.id) as highlight_count
FROM books b
LEFT JOIN highlights h ON b.id = h.book_id
GROUP BY b.id
ORDER BY b.last_annotated_date DESC;
```

#### 2. Get Recent Highlights Across All Books

```sql
SELECT 
    h.text,
    h.location,
    h.note,
    b.title,
    b.author,
    h.created_date
FROM highlights h
JOIN books b ON h.book_id = b.id
ORDER BY h.created_date DESC
LIMIT 20;
```

#### 3. Search Highlights by Text

```sql
SELECT 
    h.text,
    h.note,
    b.title,
    b.author
FROM highlights h
JOIN books b ON h.book_id = b.id
WHERE h.text LIKE '%productivity%'
   OR h.note LIKE '%productivity%'
ORDER BY b.title;
```

#### 4. Get Highlights by Color

```sql
SELECT 
    h.text,
    h.location,
    b.title
FROM highlights h
JOIN books b ON h.book_id = b.id
WHERE h.color = 'yellow'
ORDER BY h.created_date DESC;
```

#### 5. Get Books Without Highlights

```sql
SELECT b.*
FROM books b
LEFT JOIN highlights h ON b.id = h.book_id
WHERE h.id IS NULL;
```

#### 6. Get Statistics

```sql
SELECT 
    COUNT(DISTINCT b.id) as total_books,
    COUNT(h.id) as total_highlights,
    AVG(highlight_count) as avg_highlights_per_book
FROM books b
LEFT JOIN highlights h ON b.id = h.book_id
LEFT JOIN (
    SELECT book_id, COUNT(*) as highlight_count
    FROM highlights
    GROUP BY book_id
) hc ON b.id = hc.book_id;
```

---

## Database Operations

### Initialization

```python
def init_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema."""
    
    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Create books table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            asin TEXT,
            url TEXT,
            image_url TEXT,
            last_annotated_date TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_books_author ON books(author)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_books_asin ON books(asin)")
    
    # Create highlights table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS highlights (
            id TEXT PRIMARY KEY,
            book_id TEXT NOT NULL,
            text TEXT NOT NULL,
            location TEXT,
            page TEXT,
            note TEXT,
            color TEXT,
            created_date TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_highlights_book_id ON highlights(book_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_highlights_color ON highlights(color)")
    
    # Create session table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create sync_metadata table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
```

### Insert or Update Book

```python
def upsert_book(conn: sqlite3.Connection, book: Book) -> None:
    """Insert or update a book."""
    
    conn.execute("""
        INSERT INTO books (
            id, title, author, asin, url, image_url, 
            last_annotated_date, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            author = excluded.author,
            asin = excluded.asin,
            url = excluded.url,
            image_url = excluded.image_url,
            last_annotated_date = excluded.last_annotated_date,
            updated_at = CURRENT_TIMESTAMP
    """, (
        book.id,
        book.title,
        book.author,
        book.asin,
        book.url,
        book.image_url,
        book.last_annotated_date.isoformat() if book.last_annotated_date else None
    ))
    
    conn.commit()
```

### Batch Insert Highlights

```python
def insert_highlights(conn: sqlite3.Connection, highlights: list[Highlight]) -> None:
    """Insert multiple highlights (ignore duplicates)."""
    
    conn.executemany("""
        INSERT OR IGNORE INTO highlights (
            id, book_id, text, location, page, note, color, created_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (
            h.id,
            h.book_id,
            h.text,
            h.location,
            h.page,
            h.note,
            h.color.value if h.color else None,
            h.created_date.isoformat() if h.created_date else None
        )
        for h in highlights
    ])
    
    conn.commit()
```

---

## Data Integrity

### Foreign Key Constraints

```sql
-- Enable foreign key constraints
PRAGMA foreign_keys = ON;
```

Always enable foreign key constraints when opening the database to ensure referential integrity.

### Constraints

1. **Primary Keys**: All tables have primary keys
2. **Foreign Keys**: Highlights reference books with CASCADE DELETE
3. **NOT NULL**: Critical fields like book title, author, highlight text
4. **Unique**: IDs are unique (enforced by PRIMARY KEY)

### Validation

Before inserting data, validate:

1. **Book ID**: Must be valid Fletcher-16 hash
2. **Highlight Color**: Must be one of: yellow, blue, pink, orange, or null
3. **Dates**: Must be valid ISO 8601 format
4. **Foreign Keys**: Book must exist before inserting highlights

---

## Performance Considerations

### Indexes

Indexes are created on frequently queried columns:

- `books.author` - For filtering by author
- `books.title` - For searching by title
- `books.asin` - For lookup by ASIN
- `highlights.book_id` - For joining with books
- `highlights.color` - For filtering by color

### Query Optimization

1. **Use Indexes**: Queries should use indexed columns in WHERE clauses
2. **Limit Results**: Use LIMIT for pagination
3. **Avoid SELECT ***: Select only needed columns
4. **Use Prepared Statements**: Prevent SQL injection and improve performance

### Database Size

Estimated size for typical usage:

- **Books**: ~1 KB per book
- **Highlights**: ~500 bytes per highlight
- **Session**: ~5 KB
- **Metadata**: ~1 KB

Example: 100 books with 50 highlights each = ~2.6 MB

---

## Backup and Recovery

### Backup Strategy

```python
import shutil
from datetime import datetime

def backup_database(db_path: str, backup_dir: str) -> str:
    """Create a backup of the database."""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{backup_dir}/highlights_backup_{timestamp}.db"
    
    shutil.copy2(db_path, backup_path)
    
    return backup_path
```

### Recovery

```python
def restore_database(backup_path: str, db_path: str) -> None:
    """Restore database from backup."""
    
    shutil.copy2(backup_path, db_path)
```

### Recommended Backup Schedule

- **Before sync**: Automatic backup before major operations
- **Weekly**: Scheduled backups
- **Before upgrades**: Before schema migrations

---

## Migrations

### Version 0.1.0 (Initial Schema)

Initial database schema creation.

### Future Migrations

When schema changes are needed:

1. Add migration script in `migrations/` directory
2. Version migrations (e.g., `001_add_tags_table.sql`)
3. Track applied migrations in database
4. Apply migrations automatically on startup

Example migration table:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

## Security

### File Permissions

Set restrictive permissions on database file:

```bash
chmod 600 ~/.kindle-sync/highlights.db
```

### Sensitive Data

The `session` table contains sensitive authentication data:

1. Encrypt cookie values before storage
2. Clear session table on logout
3. Use secure deletion methods

### SQL Injection Prevention

Always use parameterized queries:

```python
# Good - parameterized
conn.execute("SELECT * FROM books WHERE id = ?", (book_id,))

# Bad - vulnerable to SQL injection
conn.execute(f"SELECT * FROM books WHERE id = '{book_id}'")
```

---

## Troubleshooting

### Common Issues

#### 1. Foreign Key Constraint Violation

**Error**: `FOREIGN KEY constraint failed`

**Solution**: Ensure book exists before inserting highlights

```python
# Check if book exists
cursor = conn.execute("SELECT id FROM books WHERE id = ?", (book_id,))
if cursor.fetchone() is None:
    # Insert book first
    insert_book(conn, book)
```

#### 2. Database Locked

**Error**: `database is locked`

**Solution**: Ensure only one connection writes at a time

```python
# Set timeout for lock
conn = sqlite3.connect(db_path, timeout=10.0)
```

#### 3. Corrupted Database

**Error**: `database disk image is malformed`

**Solution**: Restore from backup or rebuild

```python
# Check integrity
conn.execute("PRAGMA integrity_check")

# Rebuild database
conn.execute("VACUUM")
```

---

## Appendix

### Fletcher-16 Implementation

```python
def fletcher16(text: str) -> str:
    """
    Generate Fletcher-16 checksum for text.
    
    Args:
        text: Input text to hash
        
    Returns:
        4-character hexadecimal string
    """
    data = text.lower().encode('utf-8')
    sum1 = sum2 = 0
    
    for byte in data:
        sum1 = (sum1 + byte) % 255
        sum2 = (sum2 + sum1) % 255
    
    checksum = (sum2 << 8) | sum1
    return f"{checksum:04x}"


# Examples
assert fletcher16("Atomic Habits") == "3a7f"
assert fletcher16("The Pragmatic Programmer") == "8b2c"
```

### Date Format Utilities

```python
from datetime import datetime

def to_iso8601(dt: datetime) -> str:
    """Convert datetime to ISO 8601 string."""
    return dt.isoformat()

def from_iso8601(s: str) -> datetime:
    """Parse ISO 8601 string to datetime."""
    return datetime.fromisoformat(s)


# Example
now = datetime.now()
iso_str = to_iso8601(now)  # "2023-10-15T14:30:00"
dt = from_iso8601(iso_str)  # datetime object
```

---

**End of Database Documentation**

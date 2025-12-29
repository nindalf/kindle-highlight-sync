#!/usr/bin/env python3
"""Check which book cover images are missing from the images directory."""

import sqlite3
import sys
from pathlib import Path


def get_image_filename(image_url: str) -> str | None:
    """Extract filename from image URL."""
    if not image_url or image_url.strip() == "":
        return None
    return image_url.split("/")[-1]


def main():
    """Check for missing book cover images."""
    # Paths
    db_path = Path.home() / ".kindle-sync" / "highlights.db"

    if not db_path.exists():
        print(f"Error: Database {db_path} not found")
        print("Please run kindle-sync at least once to create the database")
        sys.exit(1)

    # Connect to database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Get images directory from database
    cursor.execute("SELECT value FROM sync_metadata WHERE key = 'images_directory'")
    result = cursor.fetchone()
    if result:
        images_dir = Path(result[0]).expanduser()
    else:
        # Use default
        images_dir = Path.home() / ".kindle-sync" / "images"

    print(f"Images directory: {images_dir}")
    print()

    # Get all books with image URLs
    cursor.execute(
        """
        SELECT asin, title, author, image_url
        FROM books
        WHERE image_url IS NOT NULL AND image_url != ''
        ORDER BY title
    """
    )

    books = cursor.fetchall()
    total_books = len(books)

    if total_books == 0:
        print("No books with image URLs found in database")
        conn.close()
        return

    missing = []
    present = []

    for asin, title, author, image_url in books:
        filename = get_image_filename(image_url)
        if not filename:
            continue

        image_path = images_dir / filename

        if image_path.exists():
            present.append((asin, title, author, filename))
        else:
            missing.append((asin, title, author, filename, image_url))

    conn.close()

    # Print results
    print("=" * 80)
    print(f"Total books with image URLs: {total_books}")
    print(f"Images downloaded: {len(present)}")
    print(f"Images missing: {len(missing)}")
    print("=" * 80)

    if missing:
        print("\nMissing images:")
        print("-" * 80)
        for asin, title, author, filename, image_url in missing:
            title_display = (title[:50] + "...") if len(title) > 50 else title
            print(f"✗ {title_display}")
            print(f"  Author: {author}")
            print(f"  ASIN: {asin}")
            print(f"  Filename: {filename}")
            print(f"  URL: {image_url}")
            print()

        print("\nTo download missing images, run:")
        print("  kindle-sync sync-images")
    else:
        print("\n✓ All book cover images have been downloaded!")


if __name__ == "__main__":
    main()

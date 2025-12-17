"""Tests for web interface."""

import pytest

from kindle_sync.web import create_app


@pytest.fixture
def app(temp_db_path):
    """Create Flask app with test database."""
    app = create_app(temp_db_path)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


class TestWebInterface:
    """Test web interface routes."""

    def test_index_empty(self, client):
        """Test index page with no books."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"No books yet" in response.data

    def test_index_with_books(self, client, temp_db, sample_book, sample_highlight):
        """Test index page with books."""
        temp_db.insert_book(sample_book)
        temp_db.insert_highlight(sample_highlight)

        response = client.get("/")
        assert response.status_code == 200
        assert sample_book.title.encode() in response.data
        assert sample_book.author.encode() in response.data
        assert b"1 highlights" in response.data

    def test_book_page(self, client, temp_db, sample_book, sample_highlight):
        """Test individual book page."""
        temp_db.insert_book(sample_book)
        temp_db.insert_highlight(sample_highlight)

        response = client.get(f"/book/{sample_book.asin}")
        assert response.status_code == 200
        assert sample_book.title.encode() in response.data
        assert sample_highlight.text.encode() in response.data

    def test_book_page_not_found(self, client):
        """Test book page with invalid ASIN."""
        response = client.get("/book/invalid")
        assert response.status_code == 404

    def test_book_page_with_note(self, client, temp_db, sample_book, sample_highlight):
        """Test book page displays notes."""
        sample_highlight.note = "This is an important concept"
        temp_db.insert_book(sample_book)
        temp_db.insert_highlight(sample_highlight)

        response = client.get(f"/book/{sample_book.asin}")
        assert response.status_code == 200
        assert b"This is an important concept" in response.data

    def test_book_page_highlight_colors(self, client, temp_db, sample_book):
        """Test highlight colors are displayed."""
        from kindle_sync.models import Highlight, HighlightColor

        highlights = [
            Highlight(
                id="h1",
                book_asin=sample_book.asin,
                text="Yellow highlight",
                color=HighlightColor.YELLOW,
            ),
            Highlight(
                id="h2",
                book_asin=sample_book.asin,
                text="Blue highlight",
                color=HighlightColor.BLUE,
            ),
            Highlight(
                id="h3",
                book_asin=sample_book.asin,
                text="Pink highlight",
                color=HighlightColor.PINK,
            ),
            Highlight(
                id="h4",
                book_asin=sample_book.asin,
                text="Orange highlight",
                color=HighlightColor.ORANGE,
            ),
        ]

        temp_db.insert_book(sample_book)
        for h in highlights:
            temp_db.insert_highlight(h)

        response = client.get(f"/book/{sample_book.asin}")
        assert response.status_code == 200
        assert b"Yellow highlight" in response.data
        assert b"Blue highlight" in response.data
        assert b"Pink highlight" in response.data
        assert b"Orange highlight" in response.data

    def test_search_page(self, client):
        """Test search page (placeholder)."""
        response = client.get("/search")
        assert response.status_code == 200
        assert b"coming soon" in response.data

    def test_template_formatting(self, client, temp_db, sample_book):
        """Test date formatting in templates."""
        from datetime import datetime

        sample_book.last_annotated_date = datetime(2023, 10, 15, 14, 30)
        temp_db.insert_book(sample_book)
        temp_db.set_last_sync(datetime(2023, 10, 16, 9, 0))

        response = client.get("/")
        assert response.status_code == 200
        # Check date formatting
        assert b"October" in response.data

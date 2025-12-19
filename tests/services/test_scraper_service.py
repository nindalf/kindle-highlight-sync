"""Tests for web scraping functionality."""

from datetime import datetime
from unittest.mock import Mock

import pytest
import requests

from kindle_sync.models import AmazonRegion, HighlightColor
from kindle_sync.services.scraper_service import KindleScraper, ScraperError


def _mock_isbn_response(isbn: str | None = None) -> Mock:
    """Create a mock response for ISBN product page requests."""
    response = Mock()
    response.status_code = 200
    response.raise_for_status = Mock()
    if isbn:
        # Mock HTML with ISBN in feature div
        response.text = f"""
        <html>
            <div id="printEditionIsbn_feature_div">
                <div class="a-row">
                    <span></span>
                    <span>{isbn}</span>
                </div>
            </div>
        </html>
        """
    else:
        # Mock HTML without ISBN
        response.text = "<html><body></body></html>"
    return response


class TestScraperInit:
    """Tests for scraper initialization."""

    def test_init(self, mock_session):
        """Test scraper initialization."""
        scraper = KindleScraper(mock_session, AmazonRegion.UK)
        assert scraper.session == mock_session
        assert scraper.region == AmazonRegion.UK
        assert scraper.region_config.hostname == "amazon.co.uk"


class TestScrapeBooks:
    """Tests for book scraping."""

    def test_scrape_books_success(self, scraper, mock_session):
        """Test successful book scraping via API."""
        # Mock API response
        api_response = Mock()
        api_response.status_code = 200
        api_response.raise_for_status = Mock()
        api_response.json.return_value = {
            "itemsList": [
                {
                    "asin": "B01N5AX61W",
                    "title": "Atomic Habits",
                    "authors": ["James Clear"],
                    "productUrl": "https://example.com/image.jpg",
                    "lastAnnotationTime": 1634966400000,  # Sunday October 24, 2021
                },
                {
                    "asin": "B07EXAMPLE",
                    "title": "Another Book",
                    "authors": ["John Doe"],
                    "productUrl": "https://example.com/another.jpg",
                },
            ],
            "paginationToken": None,
        }

        # Mock ISBN responses for each book
        isbn_response1 = _mock_isbn_response("9780735211292")
        isbn_response2 = _mock_isbn_response("9781234567890")

        # Return API response first, then ISBN responses for each book
        mock_session.get.side_effect = [api_response, isbn_response1, isbn_response2]

        books = scraper.scrape_books()

        assert len(books) == 2
        assert books[0].asin == "B01N5AX61W"
        assert books[0].title == "Atomic Habits"
        assert books[0].author == "James Clear"
        assert books[0].image_url == "https://example.com/image.jpg"
        assert books[0].isbn == "9780735211292"
        assert books[1].asin == "B07EXAMPLE"
        assert books[1].title == "Another Book"
        assert books[1].author == "John Doe"
        assert books[1].isbn == "9781234567890"

    def test_scrape_books_empty(self, scraper, mock_session):
        """Test scraping with no books via API."""
        # Mock API response with empty list
        api_response = Mock()
        api_response.status_code = 200
        api_response.raise_for_status = Mock()
        api_response.json.return_value = {
            "itemsList": [],
            "paginationToken": None,
        }
        mock_session.get.return_value = api_response

        books = scraper.scrape_books()
        assert len(books) == 0

    def test_scrape_books_network_error(self, scraper, mock_session, monkeypatch):
        """Test scraping with network error (both API and HTML fallback fail)."""
        # Speed up test by mocking time.sleep
        import time

        monkeypatch.setattr(time, "sleep", lambda x: None)

        mock_session.get.side_effect = requests.RequestException("Network error")

        with pytest.raises(ScraperError, match="Failed to fetch"):
            scraper.scrape_books()

    def test_scrape_books_missing_title(self, scraper, mock_session):
        """Test scraping book with missing title via API."""
        # Mock API response with book missing title (should use default)
        api_response = Mock()
        api_response.status_code = 200
        api_response.raise_for_status = Mock()
        api_response.json.return_value = {
            "itemsList": [
                {
                    "asin": "B01TEST",
                    "authors": ["Author"],
                    # No title field
                },
            ],
            "paginationToken": None,
        }

        # Mock ISBN response
        isbn_response = _mock_isbn_response()
        mock_session.get.side_effect = [api_response, isbn_response]

        books = scraper.scrape_books()
        assert len(books) == 1
        assert books[0].title == "Unknown Title"  # Default value

    def test_parse_book_author_prefixes(self, scraper, mock_session):
        """Test that API returns authors correctly."""
        # API returns clean author names without prefixes
        api_response = Mock()
        api_response.status_code = 200
        api_response.raise_for_status = Mock()
        api_response.json.return_value = {
            "itemsList": [
                {
                    "asin": "TEST1",
                    "title": "Book 1",
                    "authors": ["Author One"],
                },
                {
                    "asin": "TEST2",
                    "title": "Book 2",
                    "authors": ["Author Two"],
                },
                {
                    "asin": "TEST3",
                    "title": "Book 3",
                    "authors": ["Author Three"],
                },
            ],
            "paginationToken": None,
        }

        # Mock ISBN responses for each book
        isbn_responses = [_mock_isbn_response() for _ in range(3)]
        mock_session.get.side_effect = [api_response] + isbn_responses

        books = scraper.scrape_books()
        assert books[0].author == "Author One"
        assert books[1].author == "Author Two"
        assert books[2].author == "Author Three"

    def test_scrape_books_image_url_processing(self, scraper, mock_session):
        """Test that image URLs have size markers removed."""
        # Mock API response with various image URL formats
        api_response = Mock()
        api_response.status_code = 200
        api_response.raise_for_status = Mock()
        api_response.json.return_value = {
            "itemsList": [
                {
                    "asin": "BOOK1",
                    "title": "Book 1",
                    "authors": ["Author 1"],
                    "productUrl": "https://m.media-amazon.com/images/I/71z10uQJnqL._SY160.jpg",
                },
                {
                    "asin": "BOOK2",
                    "title": "Book 2",
                    "authors": ["Author 2"],
                    "productUrl": "https://m.media-amazon.com/images/I/513iWXWubiL._SY400_.jpg",
                },
                {
                    "asin": "BOOK3",
                    "title": "Book 3",
                    "authors": ["Author 3"],
                    "productUrl": "https://m.media-amazon.com/images/I/41abc._SY300_.png",
                },
                {
                    "asin": "BOOK4",
                    "title": "Book 4",
                    "authors": ["Author 4"],
                    "productUrl": "https://m.media-amazon.com/images/I/normal.jpg",
                },
            ],
            "paginationToken": None,
        }

        # Mock ISBN responses for each book
        isbn_responses = [_mock_isbn_response() for _ in range(4)]
        mock_session.get.side_effect = [api_response] + isbn_responses

        books = scraper.scrape_books()

        # Verify size markers are removed
        assert books[0].image_url == "https://m.media-amazon.com/images/I/71z10uQJnqL.jpg"
        assert books[1].image_url == "https://m.media-amazon.com/images/I/513iWXWubiL.jpg"
        assert books[2].image_url == "https://m.media-amazon.com/images/I/41abc.png"
        # URL without size marker should remain unchanged
        assert books[3].image_url == "https://m.media-amazon.com/images/I/normal.jpg"


class TestScrapeHighlights:
    """Tests for highlight scraping."""

    def test_scrape_highlights_single_page(self, scraper, mock_session):
        """Test scraping highlights from single page."""
        html = """
        <html>
            <div class="a-row a-spacing-base">
                <div id="annotationNoteHeader">Highlight on page 42</div>
                <div class="kp-notebook-highlight kp-notebook-highlight-yellow">
                    <span id="highlight">First highlight text</span>
                </div>
                <input id="kp-annotation-location" value="100-110"/>
                <div id="note">This is a note</div>
            </div>
            <div class="a-row a-spacing-base">
                <div id="annotationNoteHeader">Page 50</div>
                <div class="kp-notebook-highlight kp-notebook-highlight-blue">
                    <span id="highlight">Second highlight text</span>
                </div>
                <input id="kp-annotation-location" value="200-210"/>
            </div>
        </html>
        """

        mock_response = Mock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        highlights = scraper.scrape_highlights(Mock(asin="TEST123"))

        assert len(highlights) == 2
        assert highlights[0].text == "First highlight text"
        assert highlights[0].location == "100-110"
        assert highlights[0].page == "42"
        assert highlights[0].note == "This is a note"
        assert highlights[0].color == HighlightColor.YELLOW
        assert highlights[1].text == "Second highlight text"
        assert highlights[1].color == HighlightColor.BLUE

    def test_scrape_highlights_pagination(self, scraper, mock_session):
        """Test scraping highlights with pagination."""
        html_page1 = """
        <html>
            <div class="a-row a-spacing-base">
                <div class="kp-notebook-highlight">
                    <span id="highlight">Highlight 1</span>
                </div>
            </div>
            <input class="kp-notebook-content-limit-state" value="state123"/>
            <input class="kp-notebook-annotations-next-page-start" value="token456"/>
        </html>
        """

        html_page2 = """
        <html>
            <div class="a-row a-spacing-base">
                <div class="kp-notebook-highlight">
                    <span id="highlight">Highlight 2</span>
                </div>
            </div>
            <input class="kp-notebook-content-limit-state" value="state789"/>
        </html>
        """

        mock_response1 = Mock()
        mock_response1.text = html_page1
        mock_response1.status_code = 200
        mock_response1.raise_for_status = Mock()

        mock_response2 = Mock()
        mock_response2.text = html_page2
        mock_response2.status_code = 200
        mock_response2.raise_for_status = Mock()

        mock_session.get.side_effect = [mock_response1, mock_response2]

        highlights = scraper.scrape_highlights(Mock(asin="TEST123"))

        assert len(highlights) == 2
        assert highlights[0].text == "Highlight 1"
        assert highlights[1].text == "Highlight 2"
        assert mock_session.get.call_count == 2

    def test_scrape_highlights_empty_text_filtered(self, scraper, mock_session):
        """Test that highlights with empty text are filtered out."""
        html = """
        <html>
            <div class="a-row a-spacing-base">
                <div class="kp-notebook-highlight">
                    <span id="highlight"></span>
                </div>
            </div>
            <div class="a-row a-spacing-base">
                <div class="kp-notebook-highlight">
                    <span id="highlight">Valid highlight</span>
                </div>
            </div>
        </html>
        """

        mock_response = Mock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        highlights = scraper.scrape_highlights(Mock(asin="TEST123"))

        assert len(highlights) == 1
        assert highlights[0].text == "Valid highlight"

    def test_scrape_highlights_colors(self, scraper, mock_session):
        """Test parsing different highlight colors."""
        html = """
        <html>
            <div class="a-row a-spacing-base">
                <div class="kp-notebook-highlight kp-notebook-highlight-yellow">
                    <span id="highlight">Yellow highlight</span>
                </div>
            </div>
            <div class="a-row a-spacing-base">
                <div class="kp-notebook-highlight kp-notebook-highlight-blue">
                    <span id="highlight">Blue highlight</span>
                </div>
            </div>
            <div class="a-row a-spacing-base">
                <div class="kp-notebook-highlight kp-notebook-highlight-pink">
                    <span id="highlight">Pink highlight</span>
                </div>
            </div>
            <div class="a-row a-spacing-base">
                <div class="kp-notebook-highlight kp-notebook-highlight-orange">
                    <span id="highlight">Orange highlight</span>
                </div>
            </div>
        </html>
        """

        mock_response = Mock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        highlights = scraper.scrape_highlights(Mock(asin="TEST123"))

        assert len(highlights) == 4
        assert highlights[0].color == HighlightColor.YELLOW
        assert highlights[1].color == HighlightColor.BLUE
        assert highlights[2].color == HighlightColor.PINK
        assert highlights[3].color == HighlightColor.ORANGE

    def test_scrape_highlights_note_with_br_tags(self, scraper, mock_session):
        """Test that <br> tags in notes are converted to newlines."""
        html = """
        <html>
            <div class="a-row a-spacing-base">
                <div class="kp-notebook-highlight">
                    <span id="highlight">Test highlight</span>
                </div>
                <div id="note">Line 1<br/>Line 2<br>Line 3</div>
            </div>
        </html>
        """

        mock_response = Mock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        highlights = scraper.scrape_highlights(Mock(asin="TEST123"))

        assert len(highlights) == 1
        assert "Line 1\nLine 2\nLine 3" in highlights[0].note

    def test_scrape_highlights_network_error(self, scraper, mock_session, monkeypatch):
        """Test highlight scraping with network error."""
        # Speed up test by mocking time.sleep
        import time

        monkeypatch.setattr(time, "sleep", lambda x: None)

        mock_session.get.side_effect = requests.RequestException("Network error")

        with pytest.raises(ScraperError, match="Failed to fetch highlights page"):
            scraper.scrape_highlights(Mock(asin="TEST123"))


class TestDateParsing:
    """Tests for date parsing."""

    def test_parse_date_global_format(self):
        """Test parsing dates in global format."""
        scraper = KindleScraper(Mock(), AmazonRegion.GLOBAL)

        date = scraper._parse_date("Sunday October 24, 2021")
        assert date == datetime(2021, 10, 24)

        date = scraper._parse_date("October 24, 2021")
        assert date == datetime(2021, 10, 24)

    def test_parse_date_empty_string(self):
        """Test parsing empty date string."""
        scraper = KindleScraper(Mock(), AmazonRegion.GLOBAL)
        date = scraper._parse_date("")
        assert date is None

    def test_parse_date_invalid_format(self):
        """Test parsing invalid date format."""
        scraper = KindleScraper(Mock(), AmazonRegion.GLOBAL)
        date = scraper._parse_date("Invalid Date")
        assert date is None

    def test_parse_date_common_formats(self):
        """Test parsing common date formats."""
        scraper = KindleScraper(Mock(), AmazonRegion.GLOBAL)

        date = scraper._parse_date("2021-10-24")
        assert date == datetime(2021, 10, 24)

        date = scraper._parse_date("10/24/2021")
        assert date == datetime(2021, 10, 24)


class TestRetryDecorator:
    """Tests for retry functionality in scraper."""

    def test_scrape_books_retries_on_failure(self, scraper, mock_session, monkeypatch):
        """Test that scrape_books retries on failure."""
        # Speed up test by mocking time.sleep
        import time

        monkeypatch.setattr(time, "sleep", lambda x: None)

        # First 3 calls fail (API tries), then HTML fallback succeeds with empty response
        empty_json_response = Mock()
        empty_json_response.status_code = 200
        empty_json_response.raise_for_status = Mock()
        empty_json_response.json.return_value = {"itemsList": [], "paginationToken": None}

        mock_session.get.side_effect = [
            requests.RequestException("Error 1"),
            requests.RequestException("Error 2"),
            empty_json_response,
        ]

        books = scraper.scrape_books()

        assert mock_session.get.call_count == 3
        assert books == []

    def test_scrape_books_fails_after_max_retries(self, scraper, mock_session, monkeypatch):
        """Test that scrape_books fails after max retries (both API and HTML fallback)."""
        # Speed up test by mocking time.sleep
        import time

        monkeypatch.setattr(time, "sleep", lambda x: None)

        mock_session.get.side_effect = requests.RequestException("Persistent error")

        with pytest.raises(ScraperError):
            scraper.scrape_books()

        # API tries 3 times, then HTML fallback tries 3 times = 6 total
        assert mock_session.get.call_count == 6

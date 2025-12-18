"""Tests for web scraping functionality."""

from datetime import datetime
from unittest.mock import Mock

import pytest
import requests

from kindle_sync.models import AmazonRegion, HighlightColor
from kindle_sync.services.scraper_service import KindleScraper, ScraperError


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
        """Test successful book scraping."""
        html = """
        <html>
            <div class="kp-notebook-library-each-book" id="B01N5AX61W">
                <h2 class="kp-notebook-searchable">Atomic Habits</h2>
                <p class="kp-notebook-searchable">By: James Clear</p>
                <img class="kp-notebook-cover-image" src="https://example.com/image.jpg"/>
                <input id="kp-notebook-annotated-date-B01N5AX61W" value="Sunday October 24, 2021"/>
            </div>
            <div class="kp-notebook-library-each-book" id="B07EXAMPLE">
                <h2 class="kp-notebook-searchable">Another Book</h2>
                <p class="kp-notebook-searchable">Par: John Doe</p>
                <img class="kp-notebook-cover-image" src="https://example.com/another.jpg"/>
            </div>
        </html>
        """

        mock_response = Mock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        books = scraper.scrape_books()

        assert len(books) == 2
        assert books[0].asin == "B01N5AX61W"
        assert books[0].title == "Atomic Habits"
        assert books[0].author == "James Clear"
        assert books[0].image_url == "https://example.com/image.jpg"
        assert books[1].asin == "B07EXAMPLE"
        assert books[1].title == "Another Book"
        assert books[1].author == "John Doe"

    def test_scrape_books_empty(self, scraper, mock_session):
        """Test scraping with no books."""
        html = "<html><body>No books here</body></html>"

        mock_response = Mock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        books = scraper.scrape_books()
        assert len(books) == 0

    def test_scrape_books_network_error(self, scraper, mock_session):
        """Test scraping with network error."""
        mock_session.get.side_effect = requests.RequestException("Network error")

        with pytest.raises(ScraperError, match="Failed to fetch notebook page"):
            scraper.scrape_books()

    def test_scrape_books_missing_title(self, scraper, mock_session):
        """Test scraping book with missing title."""
        html = """
        <html>
            <div class="kp-notebook-library-each-book" id="B01TEST">
                <p class="kp-notebook-searchable">By: Author</p>
            </div>
        </html>
        """

        mock_response = Mock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        books = scraper.scrape_books()
        assert len(books) == 0

    def test_parse_book_author_prefixes(self, scraper, mock_session):
        """Test that various author prefixes are removed."""
        html = """
        <html>
            <div class="kp-notebook-library-each-book" id="TEST1">
                <h2 class="kp-notebook-searchable">Book 1</h2>
                <p class="kp-notebook-searchable">By: Author One</p>
            </div>
            <div class="kp-notebook-library-each-book" id="TEST2">
                <h2 class="kp-notebook-searchable">Book 2</h2>
                <p class="kp-notebook-searchable">De: Author Two</p>
            </div>
            <div class="kp-notebook-library-each-book" id="TEST3">
                <h2 class="kp-notebook-searchable">Book 3</h2>
                <p class="kp-notebook-searchable">Di: Author Three</p>
            </div>
        </html>
        """

        mock_response = Mock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        books = scraper.scrape_books()
        assert books[0].author == "Author One"
        assert books[1].author == "Author Two"
        assert books[2].author == "Author Three"


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

    def test_scrape_highlights_network_error(self, scraper, mock_session):
        """Test highlight scraping with network error."""
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

    def test_scrape_books_retries_on_failure(self, scraper, mock_session):
        """Test that scrape_books retries on failure."""
        mock_session.get.side_effect = [
            requests.RequestException("Error 1"),
            requests.RequestException("Error 2"),
            Mock(text="<html></html>", status_code=200, raise_for_status=Mock()),
        ]

        books = scraper.scrape_books()

        assert mock_session.get.call_count == 3
        assert books == []

    def test_scrape_books_fails_after_max_retries(self, scraper, mock_session):
        """Test that scrape_books fails after max retries."""
        mock_session.get.side_effect = requests.RequestException("Persistent error")

        with pytest.raises(ScraperError):
            scraper.scrape_books()

        assert mock_session.get.call_count == 3

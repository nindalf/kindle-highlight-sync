"""Web scraping for Amazon Kindle highlights."""

import re
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

from kindle_sync.config import Config
from kindle_sync.models import AmazonRegion, Book, Highlight, HighlightColor
from kindle_sync.utils import fletcher16, retry


class ScraperError(Exception):
    """Raised when scraping fails."""

    pass


class KindleScraper:
    """Scrapes books and highlights from Amazon Kindle."""

    def __init__(self, session: requests.Session, region: AmazonRegion) -> None:
        """
        Initialize scraper.

        Args:
            session: Authenticated requests session
            region: Amazon region to scrape
        """
        self.session = session
        self.region = region
        self.region_config = Config.get_region_config(region)

    @retry(max_attempts=Config.MAX_RETRIES, delay=Config.RETRY_DELAY, backoff=Config.RETRY_BACKOFF)
    def scrape_books(self) -> list[Book]:
        """
        Scrape all books from notebook page.

        Returns:
            List of Book objects

        Raises:
            ScraperError: If scraping fails
        """
        try:
            response = self.session.get(
                self.region_config.notebook_url, timeout=Config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise ScraperError(f"Failed to fetch notebook page: {e}") from e

        soup = BeautifulSoup(response.text, "html.parser")
        book_elements = soup.select(".kp-notebook-library-each-book")

        if not book_elements:
            return []

        books = []
        for element in book_elements:
            try:
                book = self._parse_book_element(element)
                books.append(book)
            except Exception as e:
                # Log error but continue with other books
                print(f"Warning: Failed to parse book: {e}")
                continue

        return books

    @retry(max_attempts=Config.MAX_RETRIES, delay=Config.RETRY_DELAY, backoff=Config.RETRY_BACKOFF)
    def scrape_highlights(self, book: Book) -> list[Highlight]:
        """
        Scrape all highlights for a book.

        Args:
            book: Book to scrape highlights for

        Returns:
            List of Highlight objects

        Raises:
            ScraperError: If scraping fails
        """
        highlights = []
        content_limit_state = ""
        token = ""

        while True:
            page_highlights, content_limit_state, token = self._scrape_highlights_page(
                book.asin, content_limit_state, token
            )
            highlights.extend(page_highlights)

            # No more pages if token is empty or None
            if not token:
                break

        return highlights

    def _scrape_highlights_page(
        self, asin: str, content_limit_state: str, token: str
    ) -> tuple[list[Highlight], str, str]:
        """
        Scrape a single page of highlights.

        Args:
            asin: Book ASIN
            content_limit_state: Pagination state
            token: Pagination token

        Returns:
            Tuple of (highlights, next_content_limit_state, next_token)

        Raises:
            ScraperError: If scraping fails
        """
        # Build URL with pagination parameters
        url = (
            f"{self.region_config.notebook_url}?asin={asin}"
            f"&contentLimitState={content_limit_state}&token={token}"
        )

        try:
            response = self.session.get(url, timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as e:
            raise ScraperError(f"Failed to fetch highlights page: {e}") from e

        soup = BeautifulSoup(response.text, "html.parser")

        # Parse highlights - use the correct container selector
        highlights = []
        highlight_elements = soup.select(".a-row.a-spacing-base")

        for element in highlight_elements:
            # Skip elements that don't have a highlight
            if not element.select_one("#highlight"):
                continue

            try:
                highlight = self._parse_highlight_element(element, asin)
                if highlight.text:  # Filter out empty highlights
                    highlights.append(highlight)
            except Exception as e:
                print(f"Warning: Failed to parse highlight: {e}")
                continue

        # Extract pagination state from hidden input fields
        next_content_limit_state = ""
        next_token = ""

        content_limit_input = soup.select_one(".kp-notebook-content-limit-state")
        if content_limit_input:
            value = content_limit_input.get("value")
            next_content_limit_state = str(value) if value is not None else ""

        token_input = soup.select_one(".kp-notebook-annotations-next-page-start")
        if token_input:
            value = token_input.get("value")
            next_token = str(value) if value is not None else ""

        return highlights, next_content_limit_state, next_token

    def _parse_book_element(self, element: Any) -> Book:
        """
        Parse a book element from HTML.

        Args:
            element: BeautifulSoup element

        Returns:
            Book object

        Raises:
            ScraperError: If parsing fails
        """
        # Extract ASIN from element ID
        asin = element.get("id", "")
        if not asin:
            raise ScraperError("Could not extract ASIN from book element")

        # Extract title from h2
        title_element = element.select_one("h2.kp-notebook-searchable")
        if not title_element:
            raise ScraperError("Could not find title element")
        title = title_element.get_text(strip=True)

        # Extract author from p (remove "By: " or "Par: " prefix)
        author_element = element.select_one("p.kp-notebook-searchable")
        if author_element:
            author = author_element.get_text(strip=True)
            # Remove common author prefixes
            for prefix in ["By: ", "Par: ", "De: ", "Di: ", "Por: "]:
                if author.startswith(prefix):
                    author = author[len(prefix) :]
                    break
        else:
            author = "Unknown"

        # Extract image URL
        image_element = element.select_one(".kp-notebook-cover-image")
        image_url = image_element.get("src") if image_element else None

        # Extract last annotated date from input field
        last_annotated_date = None
        date_input = element.select_one('input[id^="kp-notebook-annotated-date"]')
        if date_input:
            date_text = date_input.get("value", "")
            if date_text:
                last_annotated_date = self._parse_date(date_text)

        # Build book URL using ASIN
        book_url = f"https://www.amazon.com/dp/{asin}"

        return Book(
            asin=asin,
            title=title,
            author=author,
            url=book_url,
            image_url=image_url,
            last_annotated_date=last_annotated_date,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def _parse_highlight_element(self, element: Any, book_asin: str) -> Highlight:
        """
        Parse a highlight element from HTML.

        Args:
            element: BeautifulSoup element
            book_asin: ASIN of the book

        Returns:
            Highlight object

        Raises:
            ScraperError: If parsing fails
        """
        # Extract highlight text from #highlight
        text_element = element.select_one("#highlight")
        if not text_element:
            raise ScraperError("Could not find highlight text")
        text = text_element.get_text(strip=True)

        # Generate ID from text
        highlight_id = fletcher16(text)

        # Extract color from parent div class
        color = None
        highlight_div = element.select_one(".kp-notebook-highlight")
        if highlight_div:
            classes = highlight_div.get("class", [])
            for cls in classes:
                if cls.startswith("kp-notebook-highlight-"):
                    color_name = cls.replace("kp-notebook-highlight-", "")
                    try:
                        color = HighlightColor(color_name)
                    except ValueError:
                        pass

        # Extract location from input field
        location = None
        location_input = element.select_one("#kp-annotation-location")
        if location_input:
            location = location_input.get("value", "")

        # Extract page number from header
        page = None
        header_element = element.select_one("#annotationNoteHeader")
        if header_element:
            header_text = header_element.get_text(strip=True)
            # Extract numeric value from end of text (e.g., "Highlight on page 42" -> "42")
            page_match = re.search(r"\d+$", header_text)
            if page_match:
                page = page_match.group(0)

        # Extract note and convert <br> to newlines
        note = None
        note_element = element.select_one("#note")
        if note_element:
            # Get HTML content and convert <br> tags to newlines
            note_html = str(note_element)
            # Replace <br> and <br/> with newlines
            note_html = re.sub(r"<br\s*/?>", "\n", note_html, flags=re.IGNORECASE)
            # Parse cleaned HTML to get text
            note_soup = BeautifulSoup(note_html, "html.parser")
            note = note_soup.get_text(strip=True)
            if note:
                note = note.strip()

        # No created date in the highlight element itself
        created_date = None

        return Highlight(
            id=highlight_id,
            book_asin=book_asin,
            text=text,
            location=location,
            page=page,
            note=note,
            color=color,
            created_date=created_date,
            created_at=datetime.now(),
        )

    def _parse_date(self, date_text: str) -> datetime | None:
        """
        Parse date string based on region.

        Args:
            date_text: Date string from HTML

        Returns:
            datetime object or None if parsing fails
        """
        # Remove leading/trailing whitespace
        date_text = date_text.strip()

        if not date_text:
            return None

        # Try different date formats based on region
        formats = []

        if self.region == AmazonRegion.GLOBAL or self.region == AmazonRegion.UK:
            # Format: "Sunday October 24, 2021"
            formats.extend(["%A %B %d, %Y", "%B %d, %Y", "%A, %B %d, %Y"])
        elif self.region == AmazonRegion.JAPAN:
            # Format: "2021年11月15日 月曜日"
            formats.extend(["%Y年%m月%d日 %A", "%Y年%m月%d日", "%Y %m %d"])
        elif self.region == AmazonRegion.FRANCE:
            # Format: "mardi août 30, 2022"
            formats.extend(["%A %B %d, %Y", "%B %d, %Y"])
        elif self.region == AmazonRegion.GERMANY:
            # Format might be similar to English
            formats.extend(["%A %B %d, %Y", "%B %d, %Y", "%d. %B %Y"])
        elif self.region == AmazonRegion.SPAIN:
            # Format might have "de" between elements
            date_text = date_text.replace(" de ", " ")
            formats.extend(["%A %B %d, %Y", "%B %d, %Y", "%d %B %Y"])
        elif self.region == AmazonRegion.ITALY:
            formats.extend(["%A %B %d, %Y", "%B %d, %Y", "%d %B %Y"])

        # Common fallback formats
        formats.extend(["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"])

        for fmt in formats:
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue

        # Could not parse date - return None instead of raising
        return None

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
        self.session = session
        self.region = region
        self.region_config = Config.get_region_config(region)

    @retry(max_attempts=Config.MAX_RETRIES, delay=Config.RETRY_DELAY, backoff=Config.RETRY_BACKOFF)
    def scrape_books(self) -> list[Book]:
        """Scrape all books from notebook page."""
        try:
            response = self.session.get(
                self.region_config.notebook_url, timeout=Config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
        except requests.RequestException as e:
            exc = ScraperError("Failed to fetch notebook page")
            exc.add_note(f"URL: {self.region_config.notebook_url}")
            exc.add_note(f"Region: {self.region}")
            raise exc from e

        book_elements = BeautifulSoup(response.text, "html.parser").select(
            ".kp-notebook-library-each-book"
        )
        if not book_elements:
            return []

        books = []
        for element in book_elements:
            try:
                books.append(self._parse_book_element(element))
            except Exception as e:
                print(f"Warning: Failed to parse book: {e}")

        return books

    @retry(max_attempts=Config.MAX_RETRIES, delay=Config.RETRY_DELAY, backoff=Config.RETRY_BACKOFF)
    def scrape_highlights(self, book: Book) -> list[Highlight]:
        """Scrape all highlights for a book."""
        highlights = []
        content_limit_state = ""
        token = ""

        while True:
            page_highlights, content_limit_state, token = self._scrape_highlights_page(
                book.asin, content_limit_state, token
            )
            highlights.extend(page_highlights)
            if not token:
                break

        return highlights

    def _scrape_highlights_page(
        self, asin: str, content_limit_state: str, token: str
    ) -> tuple[list[Highlight], str, str]:
        """Scrape a single page of highlights."""
        url = f"{self.region_config.notebook_url}?asin={asin}&contentLimitState={content_limit_state}&token={token}"

        try:
            response = self.session.get(url, timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as e:
            exc = ScraperError("Failed to fetch highlights page")
            exc.add_note(f"ASIN: {asin}")
            exc.add_note(f"URL: {url}")
            raise exc from e

        soup = BeautifulSoup(response.text, "html.parser")
        highlights = []

        for element in soup.select(".a-row.a-spacing-base"):
            if not element.select_one("#highlight"):
                continue
            try:
                highlight = self._parse_highlight_element(element, asin)
                if highlight.text:
                    highlights.append(highlight)
            except Exception as e:
                print(f"Warning: Failed to parse highlight: {e}")

        next_content_limit_state = ""
        next_token = ""

        if content_limit_input := soup.select_one(".kp-notebook-content-limit-state"):
            if value := content_limit_input.get("value"):
                next_content_limit_state = str(value)

        if token_input := soup.select_one(".kp-notebook-annotations-next-page-start"):
            if value := token_input.get("value"):
                next_token = str(value)

        return highlights, next_content_limit_state, next_token

    def _parse_book_element(self, element: Any) -> Book:
        """Parse a book element from HTML."""
        asin = element.get("id", "")
        if not asin:
            raise ScraperError("Could not extract ASIN from book element")

        title_element = element.select_one("h2.kp-notebook-searchable")
        if not title_element:
            raise ScraperError("Could not find title element")
        title = title_element.get_text(strip=True)

        author = "Unknown"
        if author_element := element.select_one("p.kp-notebook-searchable"):
            author = author_element.get_text(strip=True)
            for prefix in ["By: ", "Par: ", "De: ", "Di: ", "Por: "]:
                if author.startswith(prefix):
                    author = author[len(prefix) :]
                    break

        image_url = None
        if image_element := element.select_one(".kp-notebook-cover-image"):
            image_url = image_element.get("src")

        last_annotated_date = None
        if date_input := element.select_one('input[id^="kp-notebook-annotated-date"]'):
            if date_text := date_input.get("value", ""):
                last_annotated_date = self._parse_date(date_text)

        return Book(
            asin=asin,
            title=title,
            author=author,
            url=f"https://www.amazon.com/dp/{asin}",
            image_url=image_url,
            last_annotated_date=last_annotated_date,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def _parse_highlight_element(self, element: Any, book_asin: str) -> Highlight:
        """Parse a highlight element from HTML."""
        text_element = element.select_one("#highlight")
        if not text_element:
            raise ScraperError("Could not find highlight text")
        text = text_element.get_text(strip=True)

        color = None
        if highlight_div := element.select_one(".kp-notebook-highlight"):
            for cls in highlight_div.get("class", []):
                if cls.startswith("kp-notebook-highlight-"):
                    try:
                        color = HighlightColor(cls.replace("kp-notebook-highlight-", ""))
                    except ValueError:
                        pass

        location = None
        if location_input := element.select_one("#kp-annotation-location"):
            location = location_input.get("value", "")

        page = None
        if header_element := element.select_one("#annotationNoteHeader"):
            if page_match := re.search(r"\d+$", header_element.get_text(strip=True)):
                page = page_match.group(0)

        note = None
        if note_element := element.select_one("#note"):
            note_html = re.sub(r"<br\s*/?>", "\n", str(note_element), flags=re.IGNORECASE)
            note = BeautifulSoup(note_html, "html.parser").get_text(strip=True)

        return Highlight(
            id=fletcher16(text),
            book_asin=book_asin,
            text=text,
            location=location,
            page=page,
            note=note,
            color=color,
            created_date=None,
            created_at=datetime.now(),
        )

    def _parse_date(self, date_text: str) -> datetime | None:
        """Parse date string based on region."""
        date_text = date_text.strip()
        if not date_text:
            return None

        formats = []
        match self.region:
            case AmazonRegion.GLOBAL | AmazonRegion.UK:
                formats.extend(["%A %B %d, %Y", "%B %d, %Y", "%A, %B %d, %Y"])
            case AmazonRegion.JAPAN:
                formats.extend(["%Y年%m月%d日 %A", "%Y年%m月%d日", "%Y %m %d"])
            case AmazonRegion.FRANCE:
                formats.extend(["%A %B %d, %Y", "%B %d, %Y"])
            case AmazonRegion.GERMANY:
                formats.extend(["%A %B %d, %Y", "%B %d, %Y", "%d. %B %Y"])
            case AmazonRegion.SPAIN:
                date_text = date_text.replace(" de ", " ")
                formats.extend(["%A %B %d, %Y", "%B %d, %Y", "%d %B %Y"])
            case AmazonRegion.ITALY:
                formats.extend(["%A %B %d, %Y", "%B %d, %Y", "%d %B %Y"])
            case AmazonRegion.INDIA:
                formats.extend(["%A %B %d, %Y", "%B %d, %Y"])

        formats.extend(["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"])

        for fmt in formats:
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue

        return None

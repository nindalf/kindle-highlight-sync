"""Web scraping for Amazon Kindle highlights."""

import re
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

from kindle_sync.config import Config
from kindle_sync.models import AmazonRegion, Book, Highlight, HighlightColor
from kindle_sync.utils import retry, sha


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
        """Scrape all books using pagination API."""
        # Try API-based pagination first (more reliable for getting all books)
        try:
            return self._scrape_books_via_api()
        except (ScraperError, requests.RequestException, KeyError) as e:
            print(f"Warning: API-based scraping failed ({e}), falling back to HTML scraping")
            # Fall back to HTML scraping if API fails
            return self._scrape_books_via_html()

    def _scrape_books_via_api(self) -> list[Book]:
        """Scrape all books using the pagination API."""
        base_url = self.region_config.kindle_reader_url
        api_url = f"{base_url}/kindle-library/search"

        books = []
        pagination_token = 0
        query_size = 50

        while True:
            params = {
                "libraryType": "BOOKS",
                "paginationToken": str(pagination_token),
                "sortType": "recency",
                "querySize": str(query_size),
            }

            try:
                response = self.session.get(api_url, params=params, timeout=Config.REQUEST_TIMEOUT)
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                exc = ScraperError("Failed to fetch books via API")
                exc.add_note(f"URL: {api_url}")
                exc.add_note(f"Pagination token: {pagination_token}")
                exc.add_note(f"Region: {self.region}")
                raise exc from e

            # Parse books from API response
            items = data.get("itemsList", [])
            if not items:
                break

            for item in items:
                try:
                    book = self._parse_book_from_api(item)
                    if book:
                        books.append(book)
                except Exception as e:
                    print(f"Warning: Failed to parse book from API: {e}")

            # Check if there are more pages
            if not data.get("paginationToken"):
                break

            pagination_token = int(data["paginationToken"])

        return books

    def _scrape_books_via_html(self) -> list[Book]:
        """Scrape books from HTML notebook page (fallback method)."""
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

    def _parse_book_from_api(self, item: dict[str, Any]) -> Book | None:
        """Parse a book from API JSON response."""
        # Extract ASIN from the item
        asin = item.get("asin")
        if not asin:
            return None

        # Extract title
        title = item.get("title", "Unknown Title")

        # Extract authors - API may return as list or string
        author = "Unknown"
        authors = item.get("authors", [])
        if isinstance(authors, list) and authors:
            author = ", ".join(authors)
        elif isinstance(authors, str):
            author = authors

        # Extract image URL
        image_url = None
        if "productUrl" in item:
            image_url = item["productUrl"]
            # Remove size markers like ._SY160 or ._SY400_ before the file extension
            image_url = re.sub(r"\._SY\d+_?(?=\.\w+$)", "", image_url)

        # Extract last annotated date
        last_annotated_date = None
        if "lastAnnotationTime" in item:
            try:
                # API might return timestamp in milliseconds
                timestamp = item["lastAnnotationTime"]
                if isinstance(timestamp, int | float):
                    last_annotated_date = datetime.fromtimestamp(timestamp / 1000)
                elif isinstance(timestamp, str):
                    last_annotated_date = self._parse_date(timestamp)
            except Exception:
                pass

        # Extract ISBN from product page
        isbn = self._scrape_isbn(asin)

        return Book(
            asin=asin,
            title=title,
            author=author,
            url=f"https://www.amazon.com/dp/{asin}",
            image_url=image_url,
            last_annotated_date=last_annotated_date,
            isbn=isbn,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

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

        isbn = self._scrape_isbn(asin)
        genres, page_count, goodreads_link, _ = self._scrape_goodreads_metadata(
            isbn, include_image=False
        )

        return Book(
            asin=asin,
            title=title,
            author=author,
            url=f"https://{self.region_config.hostname}/dp/{asin}",
            image_url=image_url,
            last_annotated_date=last_annotated_date,
            isbn=isbn,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            genres=genres,
            page_count=page_count,
            goodreads_link=goodreads_link,
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
            id=sha(text),
            book_asin=book_asin,
            text=text,
            location=location,
            page=page,
            note=note,
            color=color,
            created_date=None,
            created_at=datetime.now(),
        )

    def _scrape_isbn(self, asin: str) -> str | None:
        """Scrape ISBN from Amazon product page.

        Uses three fallback methods:
        1. Extract from popover data attribute
        2. Extract from ISBN feature div
        3. Extract from product details bullets
        """
        # Construct product page URL based on region
        product_url = f"https://{self.region_config.hostname}/gp/product/{asin}"

        try:
            response = self.session.get(product_url, timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Warning: Failed to fetch product page for ISBN (ASIN: {asin}): {e}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        return self._extract_isbn_from_soup(soup)

    def _extract_isbn_from_soup(self, soup: BeautifulSoup) -> str | None:
        """Extract ISBN from BeautifulSoup parsed product page.

        Args:
            soup: BeautifulSoup object of Amazon product page

        Returns:
            ISBN string or None if not found
        """
        # Method 1: Try to extract from popover data
        popover_element = soup.select_one(
            "#rich_product_information ol.a-carousel span[data-action=a-popover]"
        )
        if popover_element:
            popover_data = popover_element.get("data-a-popover")
            if popover_data:
                isbn_match = re.search(r"\bISBN\s+(\w+)", str(popover_data))
                if isbn_match:
                    return isbn_match.group(1)

        # Method 2: Try to extract from ISBN feature div
        isbn_element = soup.select_one(
            "#printEditionIsbn_feature_div .a-row:first-child span:nth-child(2)"
        )
        if isbn_element:
            isbn_text = isbn_element.get_text(strip=True)
            if isbn_text:
                return isbn_text

        # Method 3: Try to extract from product details
        details_elements = soup.select("#detailBullets_feature_div li")
        for elem in details_elements:
            text = elem.get_text(strip=True)
            if "ISBN-13" in text or "ISBN-10" in text:
                isbn_match = re.search(r"ISBN[-\s]*(?:13|10)?[:\s]*(\d[\d\-]+\d)", text)
                if isbn_match:
                    return isbn_match.group(1).replace("-", "")

        return None

    @retry(max_attempts=3)
    def _scrape_goodreads_metadata(
        self, isbn: str, include_image: bool = False
    ) -> tuple[str | None, int | None, str | None, str | None]:
        """
        Fetch genres, page count, Goodreads link, and optionally cover image from Goodreads.

        Args:
            isbn: The ISBN of the book
            include_image: Whether to extract book cover image URL

        Returns:
            Tuple of (genres_csv, page_count, goodreads_link, image_url)
            If include_image is False, image_url will be None
        """
        try:
            clean_isbn = isbn.replace("-", "").replace(" ", "")
            url = f"https://www.goodreads.com/search?q={clean_isbn}"

            response = self.session.get(url, timeout=Config.REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()

            # Get the final URL after redirect (the actual book page)
            goodreads_link = response.url

            soup = BeautifulSoup(response.text, "html.parser")

            # Extract genres
            genres = []
            seen = set()
            genre_buttons = soup.find_all("span", class_="BookPageMetadataSection__genreButton")
            for button in genre_buttons:
                span = button.find("span")
                if span:
                    genre = span.get_text(strip=True)
                    if genre and genre != "Audiobook" and genre not in seen:
                        seen.add(genre)
                        genres.append(genre)

            genres_csv = ",".join(genres) if genres else None

            # Extract page count
            page_count = None
            pages_element = soup.find(attrs={"data-testid": "pagesFormat"})
            if pages_element:
                pages_text = pages_element.get_text(strip=True)
                match = re.search(r"(\d+)\s*pages", pages_text)
                if match:
                    page_count = int(match.group(1))

            # Extract book cover image URL if requested
            image_url = None
            if include_image:
                image_element = soup.select_one(".BookPage__bookCover img, .BookCover__image img")
                if image_element:
                    src = image_element.get("src")
                    if src and isinstance(src, str):
                        # Remove size constraints like ._SY475_ or ._SX318_
                        image_url = re.sub(r"\._S[XY]\d+_", "", src)

            return genres_csv, page_count, goodreads_link, image_url

        except Exception as e:
            print(f"Warning: Failed to fetch Goodreads data for ISBN {isbn}: {e}")
            return None, None, None, None

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

    @retry(max_attempts=Config.MAX_RETRIES, delay=Config.RETRY_DELAY, backoff=Config.RETRY_BACKOFF)
    def scrape_physical_book(self, asin: str, isbn: str | None = None) -> Book:
        """
        Scrape physical book metadata from Amazon product page and Goodreads.

        Args:
            asin: Amazon Standard Identification Number
            isbn: International Standard Book Number (optional)

        Returns:
            Book object with scraped metadata

        Raises:
            ScraperError: If scraping fails
        """
        # Construct product page URL based on region
        product_url = f"https://{self.region_config.hostname}/dp/{asin}"

        try:
            response = self.session.get(product_url, timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as e:
            exc = ScraperError(f"Failed to fetch Amazon product page for ASIN {asin}")
            exc.add_note(f"URL: {product_url}")
            raise exc from e

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title
        title = "Unknown Title"
        title_element = soup.select_one("#productTitle")
        if title_element:
            title = title_element.get_text(strip=True)

        # Extract author
        author = "Unknown"
        author_element = soup.select_one(".author .a-link-normal")
        if not author_element:
            author_element = soup.select_one("#bylineInfo .author a")
        if author_element:
            author = author_element.get_text(strip=True)

        # Extract image URL
        image_url = None
        image_element = soup.select_one("#landingImage, #imgBlkFront, #ebooksImgBlkFront")
        if image_element:
            src = image_element.get("src") or image_element.get("data-old-hires")
            if src and isinstance(src, str):
                # Remove size markers
                image_url = re.sub(r"\._SY\d+_?(?=\.\w+$)", "", src)
                image_url = re.sub(r"\._AC_.*?_\.", ".", image_url)

        # Extract or use provided ISBN
        if not isbn:
            isbn = self._extract_isbn_from_soup(soup)

        # Get metadata from Goodreads if ISBN available
        genres = None
        page_count = None
        goodreads_link = None
        goodreads_image_url = None
        if isbn:
            genres, page_count, goodreads_link, goodreads_image_url = (
                self._scrape_goodreads_metadata(isbn, include_image=True)
            )
            # Prefer Goodreads image if available and higher quality
            if goodreads_image_url:
                image_url = goodreads_image_url

        return Book(
            asin=asin,
            title=title,
            author=author,
            url=product_url,
            image_url=image_url,
            isbn=isbn,
            genres=genres,
            page_count=page_count,
            goodreads_link=goodreads_link,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

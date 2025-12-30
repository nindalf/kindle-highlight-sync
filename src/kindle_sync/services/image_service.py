"""Image service for downloading book cover images."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from kindle_sync.config import Config
from kindle_sync.models import ImageSize


class ImageError(Exception):
    """Raised when image download fails."""

    pass


@dataclass
class ImageResult:
    """Result of image sync operation."""

    success: bool
    message: str
    images_downloaded: int = 0
    total_bytes: int = 0
    error: str | None = None


class ImageService:
    @staticmethod
    def sync_book_image(
        db_path: str, asin: str, size: ImageSize = ImageSize.ORIGINAL
    ) -> ImageResult:
        """
        Download cover image for a specific book.

        Args:
            db_path: Path to the database
            asin: Book ASIN
            size: Desired image size

        Returns:
            ImageResult with download status
        """
        from kindle_sync.services.database_service import DatabaseManager

        db = DatabaseManager(db_path)
        db.init_schema()

        try:
            # Get the book
            book = db.get_book(asin)
            if not book:
                return ImageResult(
                    success=False, message="Book not found", error=f"No book with ASIN {asin}"
                )

            if not book.image_url:
                return ImageResult(
                    success=False,
                    message="No image URL",
                    error=f"Book '{book.title}' has no image URL",
                )

            # Get images directory and prepare download
            images_path = ImageService._get_images_directory(db)
            download_info = ImageService._prepare_image_download(
                book.image_url, book.asin, images_path, size
            )

            # Skip if file already exists
            if download_info is None:
                return ImageResult(
                    success=True,
                    message="Image already exists",
                    images_downloaded=0,
                    total_bytes=0,
                )

            image_url, file_path = download_info

            # Download the image
            try:
                bytes_downloaded = ImageService._download_image(image_url, file_path)
                size_str = ImageService._format_bytes(bytes_downloaded)
                return ImageResult(
                    success=True,
                    message=f"Downloaded image ({size_str})",
                    images_downloaded=1,
                    total_bytes=bytes_downloaded,
                )
            except ImageError as e:
                return ImageResult(success=False, message="Failed to download image", error=str(e))

        except Exception as e:
            return ImageResult(success=False, message="Image sync failed", error=str(e))
        finally:
            db.close()

    @staticmethod
    def sync_all_images(db_path: str, size: ImageSize = ImageSize.MEDIUM) -> ImageResult:
        from kindle_sync.services.database_service import DatabaseManager

        db = DatabaseManager(db_path)
        db.init_schema()

        try:
            # Get images directory
            images_path = ImageService._get_images_directory(db)

            # Get all books with image URLs
            books = db.get_all_books()
            if not books:
                return ImageResult(
                    success=False, message="No books found", error="Database is empty"
                )

            # Prepare download tasks (only for books that need downloading)
            download_tasks = []
            for book in books:
                if not book.image_url:
                    continue

                download_info = ImageService._prepare_image_download(
                    book.image_url, book.asin, images_path, size
                )

                # Skip if file already exists
                if download_info is None:
                    continue

                image_url, file_path = download_info
                download_tasks.append((book.title, image_url, file_path))

            # Download images in parallel
            images_downloaded = 0
            total_bytes = 0

            # Use ThreadPoolExecutor for parallel downloads (max 5 concurrent downloads)
            with ThreadPoolExecutor(max_workers=5) as executor:
                # Submit all download tasks
                future_to_task = {
                    executor.submit(ImageService._download_image, url, path): (title, url, path)
                    for title, url, path in download_tasks
                }

                # Process completed downloads
                for future in as_completed(future_to_task):
                    title, url, path = future_to_task[future]
                    try:
                        bytes_downloaded = future.result()
                        images_downloaded += 1
                        total_bytes += bytes_downloaded
                    except Exception as e:
                        # Log error but continue with other images
                        print(f"Warning: Failed to download image for '{title}': {e}")

            # Format message with size info
            size_str = ImageService._format_bytes(total_bytes)
            message = f"Downloaded {images_downloaded} image(s) ({size_str})"
            if images_downloaded == 0:
                message = "All images already downloaded"

            return ImageResult(
                success=True,
                message=message,
                images_downloaded=images_downloaded,
                total_bytes=total_bytes,
            )

        except Exception as e:
            return ImageResult(success=False, message="Image sync failed", error=str(e))
        finally:
            db.close()

    @staticmethod
    def _get_images_directory(db) -> Path:
        """
        Get and ensure images directory exists.

        Args:
            db: DatabaseManager instance

        Returns:
            Path to images directory
        """
        images_dir = db.get_images_directory()
        if not images_dir:
            images_dir = Config.DEFAULT_IMAGES_DIR

        images_path = Path(images_dir).expanduser()
        images_path.mkdir(parents=True, exist_ok=True)
        return images_path

    @staticmethod
    def _prepare_image_download(
        book_image_url: str, book_asin: str, images_path: Path, size: ImageSize
    ) -> tuple[str, Path] | None:
        """
        Prepare an image download by generating URL and checking if download is needed.

        Args:
            book_image_url: Original image URL from book
            book_asin: Book ASIN
            images_path: Directory to save images
            size: Desired image size

        Returns:
            Tuple of (image_url, file_path) if download is needed, None if file exists
        """
        # Update URL to request specified resolution
        image_url = ImageService._update_image_url(book_image_url, size)

        # Generate filename from URL
        filename = ImageService._get_filename_from_url(image_url, book_asin)
        file_path = images_path / filename

        # Skip if file already exists
        if file_path.exists():
            return None

        return image_url, file_path

    @staticmethod
    def _update_image_url(url: str, size: ImageSize) -> str:
        prefix = url.removesuffix(".jpg")
        return prefix + size + ".jpg"

    @staticmethod
    def _get_filename_from_url(url: str, asin: str) -> str:
        """
        Extract filename from URL or generate one from ASIN.

        Args:
            url: Image URL
            asin: Book ASIN

        Returns:
            Filename for the image
        """
        parsed = urlparse(url)
        path = Path(parsed.path)

        # Try to extract filename from URL
        if path.suffix in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
            # Use the last part of the path
            return path.name

        # Fallback to ASIN-based filename
        return f"{asin}.jpg"

    @staticmethod
    def _download_image(url: str, destination: Path) -> int:
        """
        Download an image from URL to destination.

        Args:
            url: Image URL
            destination: Local file path to save to

        Returns:
            Number of bytes downloaded

        Raises:
            ImageError: If download fails
        """
        try:
            response = requests.get(url, timeout=Config.REQUEST_TIMEOUT, stream=True)
            response.raise_for_status()

            total_bytes = 0
            with open(destination, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_bytes += len(chunk)

            return total_bytes

        except requests.RequestException as e:
            raise ImageError(f"Failed to download image: {e}") from e
        except OSError as e:
            raise ImageError(f"Failed to write image file: {e}") from e

    @staticmethod
    def _format_bytes(num_bytes: int) -> str:
        """
        Format bytes into human-readable string.

        Args:
            num_bytes: Number of bytes

        Returns:
            Formatted string (e.g., "1.5 MB")
        """
        if num_bytes < 1024:
            return f"{num_bytes} B"
        elif num_bytes < 1024 * 1024:
            return f"{num_bytes / 1024:.1f} KB"
        elif num_bytes < 1024 * 1024 * 1024:
            return f"{num_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{num_bytes / (1024 * 1024 * 1024):.1f} GB"

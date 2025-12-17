"""Utility functions for Kindle Highlights Sync."""

import re
import time
from collections.abc import Callable
from functools import wraps


def fletcher16(text: str) -> str:
    """
    Generate Fletcher-16 checksum for text.

    Used for generating highlight IDs.

    Args:
        text: Input text to hash (will be lowercased)

    Returns:
        4-character hexadecimal string

    Example:
        >>> fletcher16("You do not rise to the level of your goals")
        "9f2e"
    """
    data = text.lower().encode("utf-8")
    sum1 = sum2 = 0

    for byte in data:
        sum1 = (sum1 + byte) % 255
        sum2 = (sum2 + sum1) % 255

    checksum = (sum2 << 8) | sum1
    return f"{checksum:04x}"


def slugify(text: str, max_length: int = 50) -> str:
    """
    Convert text to URL-safe slug.

    Args:
        text: Input text
        max_length: Maximum slug length

    Returns:
        Slugified string

    Example:
        >>> slugify("The Pragmatic Programmer")
        "the-pragmatic-programmer"
    """
    # Convert to lowercase
    text = text.lower()

    # Replace spaces and special characters with hyphens
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)

    # Trim hyphens from ends
    text = text.strip("-")

    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length].rstrip("-")

    return text


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.

    Args:
        filename: Input filename

    Returns:
        Sanitized filename

    Example:
        >>> sanitize_filename("Book: Title/Subtitle")
        "Book Title Subtitle"
    """
    # Remove invalid filename characters
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    filename = re.sub(invalid_chars, " ", filename)

    # Replace multiple spaces with single space
    filename = re.sub(r"\s+", " ", filename)

    # Trim whitespace
    filename = filename.strip()

    return filename


def extract_author_last_name(author: str) -> str:
    """
    Extract last name from author string.

    Handles multiple authors and various formats.

    Args:
        author: Author string (e.g., "James Clear" or "Hunt & Thomas")

    Returns:
        Last name (e.g., "Clear" or "Hunt-Thomas")

    Example:
        >>> extract_author_last_name("James Clear")
        "Clear"
        >>> extract_author_last_name("Andrew Hunt & David Thomas")
        "Hunt-Thomas"
    """
    # Handle multiple authors separated by &, and, or comma
    if " & " in author or " and " in author or "," in author:
        # Split and get last names of all authors
        authors = re.split(r"[&,]|\sand\s", author)
        last_names = []
        for a in authors:
            a = a.strip()
            if a:
                # Get last word as last name
                parts = a.split()
                if parts:
                    last_names.append(parts[-1])

        return "-".join(last_names) if last_names else "Unknown"

    # Single author - get last word
    parts = author.strip().split()
    return parts[-1] if parts else "Unknown"


def retry[T](
    max_attempts: int = 3,
    delay: float = 2.0,
    backoff: int = 2,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts
        delay: Initial delay in seconds
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch

    Returns:
        Decorated function

    Example:
        @retry(max_attempts=3, delay=1, backoff=2)
        def fetch_data():
            return requests.get(url)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:  # type: ignore
            attempt = 0
            current_delay = delay

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    attempt += 1
                    if attempt == max_attempts:
                        raise
                    time.sleep(current_delay)
                    current_delay *= backoff

            # This should never be reached, but satisfies type checker
            return func(*args, **kwargs)

        return wrapper

    return decorator

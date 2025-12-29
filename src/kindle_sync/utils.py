"""Utility functions for Kindle Highlights Sync."""

import hashlib
import re
import time
from collections.abc import Callable
from functools import wraps


def sha(text: str) -> str:
    """
    Generate SHA-256 hash for text.

    Used for generating highlight IDs. Returns first 8 hex characters of SHA-256.

    Args:
        text: Input text to hash (will be lowercased)

    Returns:
        8-character hexadecimal string

    Example:
        >>> fletcher16("You do not rise to the level of your goals")
        "a1b2c3d4"
    """
    data = text.lower().encode("utf-8")
    hash_digest = hashlib.sha256(data).hexdigest()
    return hash_digest[:8]


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
    # Remove invalid filename characters
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    filename = re.sub(invalid_chars, " ", filename)

    # Replace multiple spaces with single space
    filename = re.sub(r"\s+", " ", filename)

    # Trim whitespace
    filename = filename.strip()

    return filename


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

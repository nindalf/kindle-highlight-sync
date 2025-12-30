"""Tests for utility functions."""

import time

import pytest

from kindle_sync.utils import (
    retry,
    sanitize_filename,
    sha,
    slugify,
)


class TestFletcher16:
    """Tests for fletcher16 hash function."""

    def test_basic_hash(self):
        """Test basic hash generation."""
        result = sha("Hello, World!")
        assert len(result) == 8
        assert result.isalnum()

    def test_case_insensitive(self):
        """Test that hash is case insensitive."""
        hash1 = sha("Atomic Habits")
        hash2 = sha("atomic habits")
        hash3 = sha("ATOMIC HABITS")
        assert hash1 == hash2 == hash3

    def test_deterministic(self):
        """Test that same input produces same hash."""
        text = "You do not rise to the level of your goals"
        hash1 = sha(text)
        hash2 = sha(text)
        assert hash1 == hash2

    def test_different_text_different_hash(self):
        """Test that different text produces different hash."""
        hash1 = sha("First text")
        hash2 = sha("Second text")
        assert hash1 != hash2

    def test_empty_string(self):
        """Test hash of empty string."""
        result = sha("")
        assert len(result) == 8
        assert result == "e3b0c442"

    def test_unicode(self):
        """Test hash with unicode characters."""
        result = sha("Hello 世界 🌍")
        assert len(result) == 8
        assert result.isalnum()


class TestSlugify:
    """Tests for slugify function."""

    def test_basic_slugify(self):
        """Test basic slugification."""
        assert slugify("The Pragmatic Programmer") == "the-pragmatic-programmer"

    def test_special_characters(self):
        """Test removal of special characters."""
        assert slugify("Book: Title/Subtitle!") == "book-titlesubtitle"

    def test_multiple_spaces(self):
        """Test multiple spaces collapsed to single hyphen."""
        assert slugify("Too   many    spaces") == "too-many-spaces"

    def test_leading_trailing_hyphens(self):
        """Test removal of leading/trailing hyphens."""
        assert slugify("  -Title-  ") == "title"

    def test_max_length(self):
        """Test truncation to max length."""
        long_text = "a" * 100
        result = slugify(long_text, max_length=20)
        assert len(result) == 20

    def test_max_length_no_trailing_hyphen(self):
        """Test that truncation doesn't leave trailing hyphen."""
        result = slugify("word-word-word", max_length=6)
        assert not result.endswith("-")

    def test_numbers_preserved(self):
        """Test that numbers are preserved."""
        assert slugify("Book 123") == "book-123"


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_basic_sanitization(self):
        """Test basic filename sanitization."""
        assert sanitize_filename("Book Title") == "Book Title"

    def test_invalid_characters_removed(self):
        """Test removal of invalid filename characters."""
        assert sanitize_filename("Book: Title/Subtitle") == "Book Title Subtitle"
        assert sanitize_filename('Book<>:"|?*') == "Book"

    def test_multiple_spaces_collapsed(self):
        """Test multiple spaces collapsed to single space."""
        assert sanitize_filename("Too   many    spaces") == "Too many spaces"

    def test_whitespace_trimmed(self):
        """Test leading/trailing whitespace removed."""
        assert sanitize_filename("  Title  ") == "Title"

    def test_backslash_removed(self):
        """Test backslash removed."""
        assert sanitize_filename("Path\\To\\File") == "Path To File"


class TestRetry:
    """Tests for retry decorator."""

    def test_success_on_first_try(self):
        """Test function succeeds on first try."""
        call_count = 0

        @retry(max_attempts=3, delay=0.1, backoff=2)
        def succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = succeeds()
        assert result == "success"
        assert call_count == 1

    def test_success_on_retry(self):
        """Test function succeeds after retries."""
        call_count = 0

        @retry(max_attempts=3, delay=0.1, backoff=2)
        def succeeds_on_second_try():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Not yet")
            return "success"

        result = succeeds_on_second_try()
        assert result == "success"
        assert call_count == 2

    def test_failure_after_max_attempts(self):
        """Test function fails after max attempts."""
        call_count = 0

        @retry(max_attempts=3, delay=0.1, backoff=2)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            always_fails()
        assert call_count == 3

    @pytest.mark.skip(reason="Flaky in Github Actions")
    def test_delay_increases_exponentially(self):
        """Test that delay increases with backoff."""
        call_times = []

        @retry(max_attempts=3, delay=0.1, backoff=2)
        def fails_with_timing():
            call_times.append(time.time())
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            fails_with_timing()

        # Check that delays increased (approximately 0.1s, then 0.2s)
        assert len(call_times) == 3
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        assert 0.05 < delay1 < 0.20  # ~0.1s with tolerance
        assert 0.15 < delay2 < 0.30  # ~0.2s with tolerance

    def test_specific_exception_types(self):
        """Test catching specific exception types."""
        call_count = 0

        @retry(max_attempts=3, delay=0.1, exceptions=(ValueError,))
        def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Value error")

        with pytest.raises(ValueError):
            raises_value_error()
        assert call_count == 3

    def test_unhandled_exception_not_retried(self):
        """Test that unhandled exceptions are not retried."""
        call_count = 0

        @retry(max_attempts=3, delay=0.1, exceptions=(ValueError,))
        def raises_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Type error")

        with pytest.raises(TypeError):
            raises_type_error()
        assert call_count == 1  # Should not retry

    def test_with_function_arguments(self):
        """Test retry with function arguments."""

        @retry(max_attempts=2, delay=0.1)
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_with_keyword_arguments(self):
        """Test retry with keyword arguments."""

        @retry(max_attempts=2, delay=0.1)
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = greet("World", greeting="Hi")
        assert result == "Hi, World!"

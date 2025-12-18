"""Tests for export functionality."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from kindle_sync.exporter import Exporter, ExportError
from kindle_sync.models import Book, ExportFormat, Highlight, HighlightColor


@pytest.fixture
def temp_dir():
    """Create a temporary directory for exports."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_db():
    """Create a mock database."""
    db = Mock()
    return db


@pytest.fixture
def sample_book():
    """Create a sample book."""
    return Book(
        asin="B01N5AX61W",
        title="Atomic Habits",
        author="James Clear",
        url="https://www.amazon.com/dp/B01N5AX61W",
        image_url="https://example.com/image.jpg",
        last_annotated_date=datetime(2023, 10, 15),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def sample_highlights():
    """Create sample highlights."""
    return [
        Highlight(
            id="9f2e",
            book_asin="B01N5AX61W",
            text="You do not rise to the level of your goals.",
            location="254-267",
            page="12",
            note="Important concept",
            color=HighlightColor.YELLOW,
            created_date=datetime(2023, 10, 15),
            created_at=datetime.now(),
        ),
        Highlight(
            id="abc1",
            book_asin="B01N5AX61W",
            text="Habits are the compound interest of self-improvement.",
            location="300-310",
            page="15",
            note=None,
            color=HighlightColor.BLUE,
            created_date=datetime(2023, 10, 16),
            created_at=datetime.now(),
        ),
    ]


@pytest.fixture
def exporter(mock_db, temp_dir):
    """Create an exporter with mock database."""
    return Exporter(mock_db, str(temp_dir / "templates"))


class TestExporterInit:
    """Tests for exporter initialization."""

    def test_init_with_custom_templates_dir(self, mock_db, temp_dir):
        """Test initialization with custom templates directory."""
        templates_dir = temp_dir / "custom_templates"
        exporter = Exporter(mock_db, str(templates_dir))

        assert exporter.db == mock_db
        assert templates_dir.exists()

    def test_init_creates_templates_dir(self, mock_db, temp_dir):
        """Test that initialization creates templates directory."""
        templates_dir = temp_dir / "new_templates"
        assert not templates_dir.exists()

        Exporter(mock_db, str(templates_dir))
        assert templates_dir.exists()


class TestMarkdownExport:
    """Tests for Markdown export."""

    def test_export_markdown_basic(
        self, exporter, mock_db, sample_book, sample_highlights, temp_dir
    ):
        """Test basic Markdown export."""
        mock_db.get_book.return_value = sample_book
        mock_db.get_highlights.return_value = sample_highlights

        file_path = exporter.export_book(sample_book.asin, temp_dir, ExportFormat.MARKDOWN)

        assert Path(file_path).exists()
        content = Path(file_path).read_text()

        # Check that key elements are in the output
        assert "Atomic Habits" in content
        assert "James Clear" in content
        assert "B01N5AX61W" in content
        assert "You do not rise to the level of your goals" in content
        assert "Habits are the compound interest" in content
        assert "Location 254-267" in content
        assert "Page 12" in content
        assert "Important concept" in content

    def test_export_markdown_with_template(
        self, exporter, mock_db, sample_book, sample_highlights, temp_dir
    ):
        """Test Markdown export with custom template."""
        mock_db.get_book.return_value = sample_book
        mock_db.get_highlights.return_value = sample_highlights

        # Create a simple custom template
        template_file = Path(exporter.jinja_env.loader.searchpath[0]) / "custom.md.j2"
        template_file.write_text("# {{ book.title }}\n\n{{ total_highlights }} highlights")

        file_path = exporter.export_book(
            sample_book.asin, temp_dir, ExportFormat.MARKDOWN, template="custom"
        )

        content = Path(file_path).read_text()
        assert "# Atomic Habits" in content
        assert "2 highlights" in content

    def test_export_markdown_fallback_template(
        self, exporter, mock_db, sample_book, sample_highlights, temp_dir
    ):
        """Test that fallback template is used when custom template not found."""
        mock_db.get_book.return_value = sample_book
        mock_db.get_highlights.return_value = sample_highlights

        # Request non-existent template, should use fallback
        file_path = exporter.export_book(
            sample_book.asin, temp_dir, ExportFormat.MARKDOWN, template="nonexistent"
        )

        assert Path(file_path).exists()
        content = Path(file_path).read_text()
        assert "Atomic Habits" in content


class TestJSONExport:
    """Tests for JSON export."""

    def test_export_json_basic(self, exporter, mock_db, sample_book, sample_highlights, temp_dir):
        """Test basic JSON export."""
        mock_db.get_book.return_value = sample_book
        mock_db.get_highlights.return_value = sample_highlights

        file_path = exporter.export_book(sample_book.asin, temp_dir, ExportFormat.JSON)

        assert Path(file_path).exists()
        assert file_path.endswith(".json")

        with open(file_path) as f:
            data = json.load(f)

        assert data["book"]["asin"] == "B01N5AX61W"
        assert data["book"]["title"] == "Atomic Habits"
        assert data["book"]["author"] == "James Clear"
        assert len(data["highlights"]) == 2
        assert data["highlights"][0]["text"] == "You do not rise to the level of your goals."
        assert data["highlights"][0]["color"] == "yellow"
        assert data["highlights"][1]["color"] == "blue"
        assert data["metadata"]["total_highlights"] == 2

    def test_export_json_with_none_values(self, exporter, mock_db, sample_book, temp_dir):
        """Test JSON export with None values."""
        highlight = Highlight(
            id="test",
            book_asin=sample_book.asin,
            text="Test text",
            location=None,
            page=None,
            note=None,
            color=None,
            created_date=None,
            created_at=datetime.now(),
        )
        mock_db.get_book.return_value = sample_book
        mock_db.get_highlights.return_value = [highlight]

        file_path = exporter.export_book(sample_book.asin, temp_dir, ExportFormat.JSON)

        with open(file_path) as f:
            data = json.load(f)

        assert data["highlights"][0]["location"] is None
        assert data["highlights"][0]["color"] is None


class TestCSVExport:
    """Tests for CSV export."""

    def test_export_csv_basic(self, exporter, mock_db, sample_book, sample_highlights, temp_dir):
        """Test basic CSV export."""
        mock_db.get_book.return_value = sample_book
        mock_db.get_highlights.return_value = sample_highlights

        file_path = exporter.export_book(sample_book.asin, temp_dir, ExportFormat.CSV)

        assert Path(file_path).exists()
        assert file_path.endswith(".csv")

        content = Path(file_path).read_text()

        # Check header
        assert "Book Title,Author,ASIN,Highlight,Location,Page,Note,Color,Date" in content

        # Check data rows
        assert "Atomic Habits" in content
        assert "James Clear" in content
        assert "You do not rise to the level of your goals" in content
        assert "254-267" in content
        assert "12" in content
        assert "Important concept" in content
        assert "yellow" in content

    def test_export_csv_with_empty_fields(self, exporter, mock_db, sample_book, temp_dir):
        """Test CSV export with empty fields."""
        highlight = Highlight(
            id="test",
            book_asin=sample_book.asin,
            text="Test text",
            location=None,
            page=None,
            note=None,
            color=None,
            created_date=None,
            created_at=datetime.now(),
        )
        mock_db.get_book.return_value = sample_book
        mock_db.get_highlights.return_value = [highlight]

        file_path = exporter.export_book(sample_book.asin, temp_dir, ExportFormat.CSV)

        content = Path(file_path).read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2  # Header + 1 data row

        # Check that empty fields are present
        data_row = lines[1]
        assert ",," in data_row  # Consecutive commas for empty fields


class TestFilenameGeneration:
    """Tests for filename generation."""

    def test_generate_filename_markdown(self, exporter, sample_book):
        """Test Markdown filename generation."""
        filename = exporter._generate_filename(sample_book, ExportFormat.MARKDOWN)

        assert filename == "Clear-atomic-habits.md"

    def test_generate_filename_json(self, exporter, sample_book):
        """Test JSON filename generation."""
        filename = exporter._generate_filename(sample_book, ExportFormat.JSON)

        assert filename == "Clear-atomic-habits.json"

    def test_generate_filename_csv(self, exporter, sample_book):
        """Test CSV filename generation."""
        filename = exporter._generate_filename(sample_book, ExportFormat.CSV)

        assert filename == "Clear-atomic-habits.csv"

    def test_generate_filename_special_characters(self, exporter):
        """Test filename generation with special characters."""
        book = Book(
            asin="TEST",
            title="Book: Title/Subtitle!",
            author="John O'Brien",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        filename = exporter._generate_filename(book, ExportFormat.MARKDOWN)

        # Should be sanitized
        assert "/" not in filename
        assert ":" not in filename
        assert filename.endswith(".md")

    def test_generate_filename_long_title(self, exporter):
        """Test filename generation with very long title."""
        book = Book(
            asin="TEST",
            title="A" * 100,  # Very long title
            author="Author",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        filename = exporter._generate_filename(book, ExportFormat.MARKDOWN)

        # Should be truncated
        assert len(filename) < 60  # Reasonable length


class TestExportAll:
    """Tests for exporting all books."""

    def test_export_all_multiple_books(self, exporter, mock_db, temp_dir):
        """Test exporting all books."""
        book1 = Book(
            asin="BOOK1",
            title="First Book",
            author="Author One",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        book2 = Book(
            asin="BOOK2",
            title="Second Book",
            author="Author Two",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_db.get_all_books.return_value = [book1, book2]
        mock_db.get_book.side_effect = lambda asin: book1 if asin == "BOOK1" else book2
        mock_db.get_highlights.return_value = []

        files = exporter.export_all(str(temp_dir), ExportFormat.MARKDOWN)

        assert len(files) == 2
        assert all(Path(f).exists() for f in files)

    def test_export_all_no_books(self, exporter, mock_db, temp_dir):
        """Test exporting when no books exist."""
        mock_db.get_all_books.return_value = []

        with pytest.raises(ExportError, match="No books found"):
            exporter.export_all(str(temp_dir), ExportFormat.MARKDOWN)

    def test_export_all_continues_on_error(self, exporter, mock_db, temp_dir):
        """Test that export_all continues even if one book fails."""
        book1 = Book(
            asin="BOOK1",
            title="Good Book",
            author="Author",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        book2 = Book(
            asin="BOOK2",
            title="Bad Book",
            author="Author",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_db.get_all_books.return_value = [book1, book2]

        def get_book_side_effect(asin):
            if asin == "BOOK1":
                return book1
            raise Exception("Database error")

        mock_db.get_book.side_effect = get_book_side_effect
        mock_db.get_highlights.return_value = []

        files = exporter.export_all(str(temp_dir), ExportFormat.MARKDOWN)

        # Should have exported only the successful one
        assert len(files) == 1


class TestExportErrors:
    """Tests for export error handling."""

    def test_export_book_not_found(self, exporter, mock_db, temp_dir):
        """Test exporting non-existent book."""
        mock_db.get_book.return_value = None

        with pytest.raises(ExportError, match="not found"):
            exporter.export_book("NONEXISTENT", temp_dir, ExportFormat.MARKDOWN)

    def test_export_unsupported_format(self, exporter, mock_db, sample_book, temp_dir):
        """Test exporting with invalid format."""
        mock_db.get_book.return_value = sample_book
        mock_db.get_highlights.return_value = []

        # This should not happen in practice due to enum, but test error handling
        with pytest.raises(KeyError):
            exporter.export_book(sample_book.asin, temp_dir, "invalid_format")

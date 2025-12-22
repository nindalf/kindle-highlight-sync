"""Tests for export functionality."""

import json
from datetime import datetime
from pathlib import Path

from kindle_sync.models import Book, ExportFormat, Highlight
from kindle_sync.services.export_service import ExportService


class TestMarkdownExport:
    """Tests for Markdown export."""

    def test_export_markdown_basic(self, temp_db, sample_book, sample_highlights, temp_dir):
        """Test basic Markdown export."""
        temp_db.insert_book(sample_book)
        for h in sample_highlights:
            temp_db.insert_highlight(h)

        result = ExportService.export_book(
            temp_db.db_path, sample_book.asin, str(temp_dir), ExportFormat.MARKDOWN
        )

        assert result.success
        assert len(result.files_created) == 1
        file_path = Path(result.files_created[0])
        assert file_path.exists()

        content = file_path.read_text()
        assert "Atomic Habits" in content
        assert "James Clear" in content
        assert "You do not rise to the level of your goals" in content

    def test_export_markdown_with_template(self, temp_db, sample_book, sample_highlights, temp_dir):
        """Test Markdown export with simple template."""
        temp_db.insert_book(sample_book)
        for h in sample_highlights:
            temp_db.insert_highlight(h)

        result = ExportService.export_book(
            temp_db.db_path,
            sample_book.asin,
            str(temp_dir),
            ExportFormat.MARKDOWN,
            template="simple",
        )

        assert result.success
        content = Path(result.files_created[0]).read_text()
        assert "Atomic Habits" in content

    def test_export_markdown_template_not_found(
        self, temp_db, sample_book, sample_highlights, temp_dir
    ):
        """Test that error is raised when template not found."""
        temp_db.insert_book(sample_book)
        for h in sample_highlights:
            temp_db.insert_highlight(h)

        result = ExportService.export_book(
            temp_db.db_path,
            sample_book.asin,
            str(temp_dir),
            ExportFormat.MARKDOWN,
            template="nonexistent",
        )

        assert not result.success
        assert result.error is not None
        assert "Failed to find template" in result.error


class TestJSONExport:
    """Tests for JSON export."""

    def test_export_json_basic(self, temp_db, sample_book, sample_highlights, temp_dir):
        """Test basic JSON export."""
        temp_db.insert_book(sample_book)
        for h in sample_highlights:
            temp_db.insert_highlight(h)

        result = ExportService.export_book(
            temp_db.db_path, sample_book.asin, str(temp_dir), ExportFormat.JSON
        )

        assert result.success
        file_path = Path(result.files_created[0])
        assert file_path.suffix == ".json"

        with open(file_path) as f:
            data = json.load(f)

        assert data["book"]["asin"] == "B01N5AX61W"
        assert data["book"]["title"] == "Atomic Habits"
        assert len(data["highlights"]) == 2

    def test_export_json_with_none_values(self, temp_db, sample_book, temp_dir):
        """Test JSON export with None values."""
        temp_db.insert_book(sample_book)
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
        temp_db.insert_highlight(highlight)

        result = ExportService.export_book(
            temp_db.db_path, sample_book.asin, str(temp_dir), ExportFormat.JSON
        )

        with open(result.files_created[0]) as f:
            data = json.load(f)

        assert data["highlights"][0]["location"] is None
        assert data["highlights"][0]["color"] is None


class TestCSVExport:
    """Tests for CSV export."""

    def test_export_csv_basic(self, temp_db, sample_book, sample_highlights, temp_dir):
        """Test basic CSV export."""
        temp_db.insert_book(sample_book)
        for h in sample_highlights:
            temp_db.insert_highlight(h)

        result = ExportService.export_book(
            temp_db.db_path, sample_book.asin, str(temp_dir), ExportFormat.CSV
        )

        assert result.success
        file_path = Path(result.files_created[0])
        assert file_path.suffix == ".csv"

        content = file_path.read_text()
        assert "Book Title,Author,ASIN,Highlight" in content
        assert "Atomic Habits" in content
        assert "You do not rise to the level of your goals" in content


class TestFilenameGeneration:
    """Tests for filename generation."""

    def test_generate_filename_formats(self, temp_db, sample_book, temp_dir):
        """Test filename generation for different formats."""
        temp_db.insert_book(sample_book)

        result_md = ExportService.export_book(
            temp_db.db_path, sample_book.asin, str(temp_dir), ExportFormat.MARKDOWN
        )
        result_json = ExportService.export_book(
            temp_db.db_path, sample_book.asin, str(temp_dir), ExportFormat.JSON
        )
        result_csv = ExportService.export_book(
            temp_db.db_path, sample_book.asin, str(temp_dir), ExportFormat.CSV
        )

        assert Path(result_md.files_created[0]).suffix == ".md"
        assert Path(result_json.files_created[0]).suffix == ".json"
        assert Path(result_csv.files_created[0]).suffix == ".csv"
        assert all(
            "atomic-habits" in f
            for f in [
                result_md.files_created[0],
                result_json.files_created[0],
                result_csv.files_created[0],
            ]
        )


class TestExportAll:
    """Tests for exporting all books."""

    def test_export_all_multiple_books(self, temp_db, temp_dir):
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
        temp_db.insert_book(book1)
        temp_db.insert_book(book2)

        result = ExportService.export_all(temp_db.db_path, str(temp_dir), ExportFormat.MARKDOWN)

        assert result.success
        assert len(result.files_created) == 2
        assert all(Path(f).exists() for f in result.files_created)

    def test_export_all_no_books(self, temp_db, temp_dir):
        """Test exporting when no books exist."""
        result = ExportService.export_all(temp_db.db_path, str(temp_dir), ExportFormat.MARKDOWN)

        assert not result.success
        assert "No books found" in result.message


class TestExportBooks:
    """Tests for exporting specific books."""

    def test_export_books_multiple(self, temp_db, temp_dir):
        """Test exporting multiple specific books."""
        book1 = Book(
            asin="BOOK1",
            title="First",
            author="Author",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        book2 = Book(
            asin="BOOK2",
            title="Second",
            author="Author",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        temp_db.insert_book(book1)
        temp_db.insert_book(book2)

        result = ExportService.export_books(
            temp_db.db_path, ["BOOK1", "BOOK2"], str(temp_dir), ExportFormat.MARKDOWN
        )

        assert result.success
        assert len(result.files_created) == 2

    def test_export_books_some_not_found(self, temp_db, temp_dir):
        """Test exporting when some books don't exist."""
        book1 = Book(
            asin="BOOK1",
            title="First",
            author="Author",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        temp_db.insert_book(book1)

        result = ExportService.export_books(
            temp_db.db_path, ["BOOK1", "NONEXISTENT"], str(temp_dir), ExportFormat.MARKDOWN
        )

        assert result.success
        assert len(result.files_created) == 1
        assert "1 not found" in result.message


class TestExportErrors:
    """Tests for export error handling."""

    def test_export_book_not_found(self, temp_db, temp_dir):
        """Test exporting non-existent book."""
        result = ExportService.export_book(
            temp_db.db_path, "NONEXISTENT", str(temp_dir), ExportFormat.MARKDOWN
        )

        assert not result.success
        assert "Book not found" in result.message

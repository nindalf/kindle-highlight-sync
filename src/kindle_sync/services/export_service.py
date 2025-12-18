"""Export service for both CLI and web interfaces."""

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template

from kindle_sync.models import Book, BookHighlights, ExportFormat
from kindle_sync.utils import extract_author_last_name, sanitize_filename, slugify


class ExportError(Exception):
    """Raised when export fails."""

    pass


class Exporter:
    """Exports highlights to various formats."""

    def __init__(self, db: Any, templates_dir: str | None = None) -> None:
        self.db = db
        template_path = (
            Path(templates_dir).expanduser()
            if templates_dir
            else Path(__file__).parent.parent / "templates"
        )
        template_path.mkdir(parents=True, exist_ok=True)
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_path)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def export_all(
        self,
        output_dir: str,
        format: ExportFormat = ExportFormat.MARKDOWN,
        template: str = "default",
    ) -> list[str]:
        """Export all books and highlights."""
        output_path = Path(output_dir).expanduser()
        output_path.mkdir(parents=True, exist_ok=True)

        books = self.db.get_all_books()
        if not books:
            raise ExportError("No books found in database")

        created_files = []
        for book in books:
            try:
                created_files.append(self.export_book(book.asin, output_path, format, template))
            except Exception as e:
                print(f"Warning: Failed to export book '{book.title}': {e}")

        return created_files

    def export_book(
        self,
        asin: str,
        output_path: Path | str,
        format: ExportFormat = ExportFormat.MARKDOWN,
        template: str = "default",
    ) -> str:
        """Export a single book with its highlights."""
        book = self.db.get_book(asin)
        if not book:
            raise ExportError(f"Book with ASIN {asin} not found")

        # Get all highlights and filter out hidden ones
        all_highlights = self.db.get_highlights(book.asin)
        visible_highlights = [h for h in all_highlights if not h.is_hidden]

        book_highlights = BookHighlights(book=book, highlights=visible_highlights)
        output_path = (
            Path(output_path).expanduser() if isinstance(output_path, str) else output_path
        )
        file_path = (
            output_path / self._generate_filename(book, format)
            if output_path.is_dir()
            else output_path
        )

        match format:
            case ExportFormat.MARKDOWN:
                content = self._export_markdown(book_highlights, template)
            case ExportFormat.JSON:
                content = self._export_json(book_highlights)
            case ExportFormat.CSV:
                content = self._export_csv(book_highlights)
            case _:
                raise ExportError(f"Unsupported export format: {format}")

        try:
            file_path.write_text(content, encoding="utf-8")
        except OSError as e:
            raise ExportError(f"Failed to write file: {e}") from e

        return str(file_path)

    def _export_markdown(self, book_highlights: BookHighlights, template_name: str) -> str:
        """Export to Markdown using Jinja2 template."""
        try:
            template = self.jinja_env.get_template(f"{template_name}.md.j2")
        except Exception:
            template = Template(self._get_default_markdown_template())

        try:
            return template.render(
                book=book_highlights.book,
                highlights=book_highlights.highlights,
                total_highlights=len(book_highlights.highlights),
                export_date=datetime.now().strftime("%Y-%m-%d"),
            )
        except Exception as e:
            raise ExportError(f"Failed to render template: {e}") from e

    def _export_json(self, book_highlights: BookHighlights) -> str:
        """Export to JSON format."""
        book = book_highlights.book
        return json.dumps(
            {
                "book": {
                    "asin": book.asin,
                    "title": book.title,
                    "author": book.author,
                    "url": book.url,
                    "image_url": book.image_url,
                    "last_annotated_date": book.last_annotated_date.isoformat()
                    if book.last_annotated_date
                    else None,
                },
                "highlights": [
                    {
                        "id": h.id,
                        "text": h.text,
                        "location": h.location,
                        "page": h.page,
                        "note": h.note,
                        "color": h.color.value if h.color else None,
                        "created_date": h.created_date.isoformat() if h.created_date else None,
                    }
                    for h in book_highlights.highlights
                ],
                "metadata": {
                    "total_highlights": len(book_highlights.highlights),
                    "export_date": datetime.now().isoformat(),
                },
            },
            indent=2,
            ensure_ascii=False,
        )

    def _export_csv(self, book_highlights: BookHighlights) -> str:
        """Export to CSV format."""
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Book Title",
                "Author",
                "ASIN",
                "Highlight",
                "Location",
                "Page",
                "Note",
                "Color",
                "Date",
            ]
        )

        book = book_highlights.book
        for h in book_highlights.highlights:
            writer.writerow(
                [
                    book.title,
                    book.author,
                    book.asin,
                    h.text,
                    h.location or "",
                    h.page or "",
                    h.note or "",
                    h.color.value if h.color else "",
                    h.created_date.strftime("%Y-%m-%d") if h.created_date else "",
                ]
            )

        return output.getvalue()

    def _generate_filename(self, book: Book, format: ExportFormat) -> str:
        """Generate filename for export: {author_last_name}-{title_slug}.{ext}"""
        author_name = extract_author_last_name(book.author)
        title_slug = slugify(book.title, max_length=40)
        base_name = sanitize_filename(f"{author_name}-{title_slug}")
        ext = {"md": ExportFormat.MARKDOWN, "json": ExportFormat.JSON, "csv": ExportFormat.CSV}
        ext = {v: k for k, v in ext.items()}[format]
        return f"{base_name}.{ext}"

    def _get_default_markdown_template(self) -> str:
        """Get default Markdown template."""
        return """# {{ book.title }}

**Author:** {{ book.author }}
**ASIN:** {{ book.asin }}
{% if book.last_annotated_date %}
**Last Annotated:** {{ book.last_annotated_date.strftime('%Y-%m-%d') }}
{% endif %}

---

## Highlights

{% for highlight in highlights %}
### {% if highlight.location %}Location {{ highlight.location }}{% endif %}{% if highlight.page %} (Page {{ highlight.page }}){% endif %}

> {{ highlight.text }}

{% if highlight.note %}
**Note:** {{ highlight.note }}
{% endif %}
{% if highlight.color %}
*Color: {{ highlight.color.value }}*
{% endif %}
{% if highlight.created_date %}
*Date: {{ highlight.created_date.strftime('%Y-%m-%d') }}*
{% endif %}

---

{% endfor %}

**Total Highlights:** {{ total_highlights }}
**Exported:** {{ export_date }}
"""


@dataclass
class ExportResult:
    """Result of export operation."""

    success: bool
    message: str
    files_created: list[str] = field(default_factory=list)
    error: str | None = None


class ExportService:
    """Service for export operations."""

    @staticmethod
    def export_all(
        db_path: str,
        output_dir: str,
        format: ExportFormat = ExportFormat.MARKDOWN,
        template: str = "default",
    ) -> ExportResult:
        """Export all books and highlights."""
        from kindle_sync.services.database_service import DatabaseManager

        db = DatabaseManager(db_path)
        db.init_schema()

        try:
            books = db.get_all_books()
            if not books:
                db.close()
                return ExportResult(
                    success=False, message="No books found", error="Database is empty"
                )

            created_files = Exporter(db).export_all(output_dir, format, template)
            db.close()
            return ExportResult(
                success=True,
                message=f"Exported {len(created_files)} file(s)",
                files_created=created_files,
            )
        except Exception as e:
            db.close()
            return ExportResult(success=False, message="Export failed", error=str(e))

    @staticmethod
    def export_book(
        db_path: str,
        asin: str,
        output_path: str | Path,
        format: ExportFormat = ExportFormat.MARKDOWN,
        template: str = "default",
    ) -> ExportResult:
        """Export a single book with its highlights."""
        from kindle_sync.services.database_service import DatabaseManager

        db = DatabaseManager(db_path)
        db.init_schema()

        try:
            book = db.get_book(asin)
            if not book:
                db.close()
                return ExportResult(
                    success=False, message="Book not found", error=f"No book with ASIN {asin}"
                )

            file_path = Exporter(db).export_book(asin, output_path, format, template)
            db.close()
            return ExportResult(
                success=True, message=f"Exported {book.title}", files_created=[file_path]
            )
        except Exception as e:
            db.close()
            return ExportResult(success=False, message="Export failed", error=str(e))

    @staticmethod
    def export_books(
        db_path: str,
        asins: list[str],
        output_dir: str,
        format: ExportFormat = ExportFormat.MARKDOWN,
        template: str = "default",
    ) -> ExportResult:
        """Export multiple books with their highlights."""
        from kindle_sync.services.database_service import DatabaseManager

        db = DatabaseManager(db_path)
        db.init_schema()

        try:
            exporter = Exporter(db)
            output_path = Path(output_dir).expanduser()
            output_path.mkdir(parents=True, exist_ok=True)

            created_files = []
            not_found = []

            for asin in asins:
                if not db.get_book(asin):
                    not_found.append(asin)
                    continue
                try:
                    created_files.append(exporter.export_book(asin, output_path, format, template))
                except Exception as e:
                    print(f"Warning: Failed to export book {asin}: {e}")

            db.close()

            if not created_files:
                return ExportResult(
                    success=False,
                    message="No books exported",
                    error=f"Books not found: {', '.join(not_found)}",
                )

            message = f"Exported {len(created_files)} file(s)"
            if not_found:
                message += f" ({len(not_found)} not found)"
            return ExportResult(success=True, message=message, files_created=created_files)
        except Exception as e:
            db.close()
            return ExportResult(success=False, message="Export failed", error=str(e))

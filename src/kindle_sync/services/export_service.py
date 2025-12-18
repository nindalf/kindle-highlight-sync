"""Export service for both CLI and web interfaces."""

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from kindle_sync.models import Book, BookHighlights, ExportFormat
from kindle_sync.utils import extract_author_last_name, sanitize_filename, slugify


class ExportError(Exception):
    """Raised when export fails."""

    pass


@dataclass
class ExportResult:
    """Result of export operation."""

    success: bool
    message: str
    files_created: list[str] = field(default_factory=list)
    error: str | None = None


class ExportService:
    """Service for exporting highlights to various formats."""

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
                return ExportResult(
                    success=False, message="No books found", error="Database is empty"
                )

            output_path = Path(output_dir).expanduser()
            output_path.mkdir(parents=True, exist_ok=True)

            created_files = []
            for book in books:
                try:
                    file_path = ExportService._export_single(
                        db, book.asin, output_path, format, template
                    )
                    created_files.append(file_path)
                except Exception as e:
                    print(f"Warning: Failed to export book '{book.title}': {e}")

            return ExportResult(
                success=True,
                message=f"Exported {len(created_files)} file(s)",
                files_created=created_files,
            )
        except Exception as e:
            return ExportResult(success=False, message="Export failed", error=str(e))
        finally:
            db.close()

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
                return ExportResult(
                    success=False, message="Book not found", error=f"No book with ASIN {asin}"
                )

            file_path = ExportService._export_single(db, asin, output_path, format, template)
            return ExportResult(
                success=True,
                message=f"Exported {book.title}",
                files_created=[file_path],
            )
        except Exception as e:
            return ExportResult(success=False, message="Export failed", error=str(e))
        finally:
            db.close()

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
            output_path = Path(output_dir).expanduser()
            output_path.mkdir(parents=True, exist_ok=True)

            created_files = []
            not_found = []

            for asin in asins:
                if not db.get_book(asin):
                    not_found.append(asin)
                    continue
                try:
                    file_path = ExportService._export_single(
                        db, asin, output_path, format, template
                    )
                    created_files.append(file_path)
                except Exception as e:
                    print(f"Warning: Failed to export book {asin}: {e}")

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
            return ExportResult(success=False, message="Export failed", error=str(e))
        finally:
            db.close()

    @staticmethod
    def _export_single(
        db, asin: str, output_path: Path | str, format: ExportFormat, template: str
    ) -> str:
        """Export a single book. Internal method."""
        book = db.get_book(asin)
        if not book:
            raise ExportError(f"Book with ASIN {asin} not found")

        highlights = [h for h in db.get_highlights(asin) if not h.is_hidden]
        book_highlights = BookHighlights(book=book, highlights=highlights)

        output_path = (
            Path(output_path).expanduser() if isinstance(output_path, str) else output_path
        )
        file_path = (
            output_path / ExportService._generate_filename(book, format)
            if output_path.is_dir()
            else output_path
        )

        content = ExportService._generate_content(book_highlights, format, template)

        try:
            file_path.write_text(content, encoding="utf-8")
        except OSError as e:
            raise ExportError(f"Failed to write file: {e}") from e

        return str(file_path)

    @staticmethod
    def _generate_content(
        book_highlights: BookHighlights, format: ExportFormat, template: str
    ) -> str:
        """Generate export content based on format."""
        match format:
            case ExportFormat.MARKDOWN:
                return ExportService._export_markdown(book_highlights, template)
            case ExportFormat.JSON:
                return ExportService._export_json(book_highlights)
            case ExportFormat.CSV:
                return ExportService._export_csv(book_highlights)
            case _:
                raise ExportError(f"Unsupported export format: {format}")

    @staticmethod
    def _export_markdown(book_highlights: BookHighlights, template_name: str) -> str:
        """Export to Markdown using Jinja2 template."""
        template_path = Path(__file__).parent.parent / "templates"
        env = Environment(
            loader=FileSystemLoader(str(template_path)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        try:
            template = env.get_template(f"{template_name}.md.j2")
        except Exception as e:
            raise ExportError(f"Failed to find template: {e}") from e

        try:
            return template.render(
                book=book_highlights.book,
                highlights=book_highlights.highlights,
                total_highlights=len(book_highlights.highlights),
                export_date=datetime.now().strftime("%Y-%m-%d"),
            )
        except Exception as e:
            raise ExportError(f"Failed to render template: {e}") from e

    @staticmethod
    def _export_json(book_highlights: BookHighlights) -> str:
        """Export to JSON format."""
        book = book_highlights.book

        highlights = []
        for h in book_highlights.highlights:
            highlights.append(
                {
                    "id": h.id,
                    "text": h.text,
                    "location": h.location,
                    "page": h.page,
                    "note": h.note,
                    "color": h.color.value if h.color else None,
                    "created_date": h.created_date.isoformat() if h.created_date else None,
                }
            )

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
                    "purchase_date": book.purchase_date.isoformat() if book.purchase_date else None,
                    "status": book.status,
                    "format": book.format,
                    "notes": book.notes,
                    "start_date": book.start_date.isoformat() if book.start_date else None,
                    "end_date": book.end_date.isoformat() if book.end_date else None,
                    "reading_time": book.reading_time,
                    "genres": book.genres,
                    "shop_link": book.shop_link,
                    "isbn": book.isbn,
                    "classification": book.classification,
                    "goodreads_link": book.goodreads_link,
                    "price_gbp": book.price_gbp,
                    "price_inr": book.price_inr,
                },
                "highlights": highlights,
                "metadata": {
                    "total_highlights": len(book_highlights.highlights),
                    "export_date": datetime.now().isoformat(),
                },
            },
            indent=2,
            ensure_ascii=False,
        )

    @staticmethod
    def _export_csv(book_highlights: BookHighlights) -> str:
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

    @staticmethod
    def _generate_filename(book: Book, format: ExportFormat) -> str:
        """Generate filename: {author_last_name}-{title_slug}.{ext}"""
        author_name = extract_author_last_name(book.author)
        title_slug = slugify(book.title, max_length=40)
        base_name = sanitize_filename(f"{author_name}-{title_slug}")
        ext = {ExportFormat.MARKDOWN: "md", ExportFormat.JSON: "json", ExportFormat.CSV: "csv"}[
            format
        ]
        return f"{base_name}.{ext}"

"""Export Kindle highlights to various formats."""

import csv
import json
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
        """
        Initialize exporter.

        Args:
            db: Database manager instance
            templates_dir: Custom templates directory (optional)
        """
        self.db = db

        # Setup Jinja2 environment
        if templates_dir:
            template_path = Path(templates_dir).expanduser()
        else:
            # Use default templates from package
            package_dir = Path(__file__).parent
            template_path = package_dir / "templates"

        # Create templates directory if it doesn't exist
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
        """
        Export all books and highlights.

        Args:
            output_dir: Output directory path
            format: Export format (markdown, json, csv)
            template: Template name for markdown export

        Returns:
            List of created file paths

        Raises:
            ExportError: If export fails
        """
        output_path = Path(output_dir).expanduser()
        output_path.mkdir(parents=True, exist_ok=True)

        books = self.db.get_all_books()
        if not books:
            raise ExportError("No books found in database")

        created_files = []
        for book in books:
            try:
                file_path = self.export_book(book.asin, output_path, format, template)
                created_files.append(file_path)
            except Exception as e:
                print(f"Warning: Failed to export book '{book.title}': {e}")
                continue

        return created_files

    def export_book(
        self,
        asin: str,
        output_path: Path | str,
        format: ExportFormat = ExportFormat.MARKDOWN,
        template: str = "default",
    ) -> str:
        """
        Export a single book with its highlights.

        Args:
            asin: Book ASIN
            output_path: Output directory or file path
            format: Export format
            template: Template name for markdown export

        Returns:
            Path to created file

        Raises:
            ExportError: If export fails
        """
        # Get book and highlights from database
        book = self.db.get_book(asin)
        if not book:
            raise ExportError(f"Book with ASIN {asin} not found")

        highlights = self.db.get_highlights(book.asin)
        book_highlights = BookHighlights(book=book, highlights=highlights)

        # Convert output_path to Path
        if isinstance(output_path, str):
            output_path = Path(output_path).expanduser()

        # Generate filename if output_path is a directory
        if output_path.is_dir():
            filename = self._generate_filename(book, format)
            file_path = output_path / filename
        else:
            file_path = output_path

        # Export based on format
        if format == ExportFormat.MARKDOWN:
            content = self._export_markdown(book_highlights, template)
        elif format == ExportFormat.JSON:
            content = self._export_json(book_highlights)
        elif format == ExportFormat.CSV:
            content = self._export_csv(book_highlights)
        else:
            raise ExportError(f"Unsupported export format: {format}")

        # Write to file
        try:
            file_path.write_text(content, encoding="utf-8")
        except OSError as e:
            raise ExportError(f"Failed to write file: {e}") from e

        return str(file_path)

    def _export_markdown(self, book_highlights: BookHighlights, template_name: str) -> str:
        """
        Export to Markdown using Jinja2 template.

        Args:
            book_highlights: Book with highlights
            template_name: Template name (without extension)

        Returns:
            Rendered Markdown content

        Raises:
            ExportError: If template rendering fails
        """
        try:
            # Try to load custom template
            template = self.jinja_env.get_template(f"{template_name}.md.j2")
        except Exception:
            # Fall back to inline default template
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
        """
        Export to JSON format.

        Args:
            book_highlights: Book with highlights

        Returns:
            JSON string
        """
        data: dict[str, Any] = {
            "book": {
                "asin": book_highlights.book.asin,
                "title": book_highlights.book.title,
                "author": book_highlights.book.author,
                "url": book_highlights.book.url,
                "image_url": book_highlights.book.image_url,
                "last_annotated_date": (
                    book_highlights.book.last_annotated_date.isoformat()
                    if book_highlights.book.last_annotated_date
                    else None
                ),
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
        }

        return json.dumps(data, indent=2, ensure_ascii=False)

    def _export_csv(self, book_highlights: BookHighlights) -> str:
        """
        Export to CSV format.

        Args:
            book_highlights: Book with highlights

        Returns:
            CSV string
        """
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
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

        # Write highlights
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
        """
        Generate filename for export.

        Format: {author_last_name}-{title_slug}.{ext}

        Args:
            book: Book object
            format: Export format

        Returns:
            Sanitized filename
        """
        # Get author last name
        author_name = extract_author_last_name(book.author)

        # Slugify title
        title_slug = slugify(book.title, max_length=40)

        # Combine and sanitize
        base_name = f"{author_name}-{title_slug}"
        base_name = sanitize_filename(base_name)

        # Add extension
        ext = {
            ExportFormat.MARKDOWN: "md",
            ExportFormat.JSON: "json",
            ExportFormat.CSV: "csv",
        }[format]

        return f"{base_name}.{ext}"

    def _get_default_markdown_template(self) -> str:
        """
        Get default Markdown template.

        Returns:
            Template string
        """
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

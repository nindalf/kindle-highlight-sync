"""Web interface for browsing Kindle highlights."""

from datetime import datetime
from pathlib import Path

from flask import Flask, abort, g, jsonify, render_template, request

from kindle_sync.models import ExportFormat, HighlightColor
from kindle_sync.services import AuthService, ExportService, SyncService
from kindle_sync.services.database_service import DatabaseManager


def create_app(db_path: str | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        db_path: Path to SQLite database. If None, uses default location.

    Returns:
        Configured Flask application.
    """
    app = Flask(__name__)

    # Set up template directory
    template_dir = Path(__file__).parent / "templates" / "web"
    app.template_folder = str(template_dir)

    # Store database path in app config
    if db_path is None:
        db_path = str(Path.home() / ".kindle-sync" / "highlights.db")

    app.config["DB_PATH"] = db_path

    # Initialize schema once at startup
    db = DatabaseManager(db_path)
    db.init_schema()
    db.close()

    def get_db() -> DatabaseManager:
        """Get database connection for current request."""
        if "db" not in g:
            g.db = DatabaseManager(app.config["DB_PATH"])
        return g.db

    @app.teardown_appcontext
    def close_db(error):
        """Close database connection at end of request."""
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.context_processor
    def utility_processor():
        """Add utility functions to templates."""

        def format_date(date_obj: str | datetime | None) -> str:
            """Format date to readable format."""
            if not date_obj:
                return "Unknown"
            try:
                if isinstance(date_obj, str):
                    dt = datetime.fromisoformat(date_obj)
                else:
                    dt = date_obj
                return dt.strftime("%B %d, %Y")
            except (ValueError, AttributeError, TypeError):
                return str(date_obj)

        def format_datetime(date_obj: str | datetime | None) -> str:
            """Format datetime to readable format."""
            if not date_obj:
                return "Unknown"
            try:
                if isinstance(date_obj, str):
                    dt = datetime.fromisoformat(date_obj)
                else:
                    dt = date_obj
                return dt.strftime("%B %d, %Y at %I:%M %p")
            except (ValueError, AttributeError, TypeError):
                return str(date_obj)

        def color_class(color: str) -> str:
            """Convert highlight color to CSS class."""
            color_map = {
                HighlightColor.YELLOW.value: "yellow",
                HighlightColor.BLUE.value: "blue",
                HighlightColor.PINK.value: "pink",
                HighlightColor.ORANGE.value: "orange",
            }
            return color_map.get(color, "yellow")

        return {
            "format_date": format_date,
            "format_datetime": format_datetime,
            "color_class": color_class,
        }

    # ============================================================================
    # Web UI Routes
    # ============================================================================

    @app.route("/")
    def index():
        """Show all books with highlight counts."""
        db = get_db()
        books = db.get_all_books()

        # Add highlight count to each book
        books_with_counts = []
        for book in books:
            highlights = db.get_highlights(book.asin)
            books_with_counts.append(
                {
                    "book": book,
                    "highlight_count": len(highlights),
                }
            )

        # Get last sync time
        last_sync = db.get_last_sync()

        return render_template(
            "index.html",
            books=books_with_counts,
            last_sync=last_sync,
            total_books=len(books),
        )

    @app.route("/book/<asin>")
    def book(asin: str):
        """Show highlights for a specific book."""
        db = get_db()
        book_obj = db.get_book(asin)
        if not book_obj:
            abort(404)

        highlights = db.get_highlights(asin)

        return render_template(
            "book.html",
            book=book_obj,
            highlights=highlights,
        )

    @app.route("/search")
    def search():
        """Search highlights across all books."""
        query = request.args.get("q", "").strip()
        book_filter = request.args.get("book", "").strip()

        if not query:
            # Show empty search page
            return render_template("search.html", query="", results=None)

        db = get_db()

        # Search with optional book filter
        results = db.search_highlights(query, book_asin=book_filter if book_filter else None)

        # Group results by book for better display
        books_results = {}
        for result in results:
            if result.book.asin not in books_results:
                books_results[result.book.asin] = {"book": result.book, "highlights": []}
            books_results[result.book.asin]["highlights"].append(result.highlight)

        return render_template(
            "search.html",
            query=query,
            results=list(books_results.values()),
            total_results=len(results),
            book_filter=book_filter,
        )

    @app.route("/settings")
    def settings():
        """Show settings page with sync, export, and logout options."""
        return render_template("settings.html")

    # ============================================================================
    # API Routes
    # ============================================================================

    @app.route("/api/status")
    def api_status():
        """Get authentication and sync status."""
        status = AuthService.check_status(app.config["DB_PATH"])
        return jsonify(status)

    @app.route("/api/auth/logout", methods=["POST"])
    def api_logout():
        """Clear stored session."""
        result = AuthService.logout(app.config["DB_PATH"])
        return jsonify(
            {
                "success": result.success,
                "message": result.message,
                "error": result.error,
            }
        )

    @app.route("/api/sync", methods=["POST"])
    def api_sync():
        """Trigger sync operation."""
        data = request.get_json() or {}
        full = data.get("full", False)
        book_asins = data.get("books")

        # Perform sync
        result = SyncService.sync(app.config["DB_PATH"], full=full, book_asins=book_asins)

        # Convert book details to dict
        book_details = [
            {
                "asin": detail.asin,
                "title": detail.title,
                "author": detail.author,
                "new_highlights": detail.new_highlights,
                "deleted_highlights": detail.deleted_highlights,
                "total_highlights": detail.total_highlights,
            }
            for detail in result.book_details
        ]

        return jsonify(
            {
                "success": result.success,
                "message": result.message,
                "data": {
                    "books_synced": result.books_synced,
                    "new_highlights": result.new_highlights,
                    "deleted_highlights": result.deleted_highlights,
                    "books": book_details,
                },
                "error": result.error,
            }
        )

    @app.route("/api/export", methods=["POST"])
    def api_export():
        """Export highlights."""
        data = request.get_json() or {}
        output_dir = data.get("output_dir")
        format_str = data.get("format", "markdown").upper()
        template = data.get("template", "default")
        book_asins = data.get("books")

        if not output_dir:
            return jsonify(
                {
                    "success": False,
                    "message": "output_dir is required",
                    "error": "Missing output_dir parameter",
                }
            ), 400

        try:
            export_format = ExportFormat[format_str]
        except KeyError:
            return jsonify(
                {
                    "success": False,
                    "message": "Invalid format",
                    "error": f"Format must be one of: {', '.join(f.name for f in ExportFormat)}",
                }
            ), 400

        # Perform export
        if book_asins:
            result = ExportService.export_books(
                app.config["DB_PATH"], book_asins, output_dir, export_format, template
            )
        else:
            result = ExportService.export_all(
                app.config["DB_PATH"], output_dir, export_format, template
            )

        return jsonify(
            {
                "success": result.success,
                "message": result.message,
                "data": {"files_created": result.files_created},
                "error": result.error,
            }
        )

    @app.route("/api/export-directory", methods=["GET"])
    def api_get_export_directory():
        """Get the configured export directory."""
        from kindle_sync.config import Config

        db = get_db()
        export_dir = db.get_export_directory()

        # Use default if not set
        if not export_dir:
            export_dir = Config.DEFAULT_EXPORT_DIR

        return jsonify({"success": True, "data": {"export_directory": export_dir}})

    @app.route("/api/export-directory", methods=["POST"])
    def api_set_export_directory():
        """Set the export directory."""
        data = request.get_json() or {}
        export_dir = data.get("export_directory", "").strip()

        if not export_dir:
            return jsonify(
                {
                    "success": False,
                    "message": "export_directory is required",
                    "error": "Missing export_directory parameter",
                }
            ), 400

        db = get_db()
        db.set_export_directory(export_dir)

        return jsonify(
            {
                "success": True,
                "message": "Export directory updated",
                "data": {"export_directory": export_dir},
            }
        )

    @app.route("/api/books")
    def api_books():
        """Get all books with highlight counts."""
        db = get_db()
        sort_by = request.args.get("sort", "title")
        books_with_counts = db.get_all_books_with_counts(sort_by)

        return jsonify(
            {
                "success": True,
                "data": [
                    {
                        "asin": item.book.asin,
                        "title": item.book.title,
                        "author": item.book.author,
                        "url": item.book.url,
                        "image_url": item.book.image_url,
                        "last_annotated_date": (
                            item.book.last_annotated_date.isoformat()
                            if item.book.last_annotated_date
                            else None
                        ),
                        "highlight_count": item.highlight_count,
                    }
                    for item in books_with_counts
                ],
            }
        )

    @app.route("/api/books/<asin>")
    def api_book(asin: str):
        """Get a specific book with its highlights."""
        db = get_db()
        book = db.get_book(asin)
        if not book:
            return jsonify(
                {
                    "success": False,
                    "message": "Book not found",
                    "error": f"No book with ASIN {asin}",
                }
            ), 404

        highlights = db.get_highlights(asin)

        return jsonify(
            {
                "success": True,
                "data": {
                    "book": {
                        "asin": book.asin,
                        "title": book.title,
                        "author": book.author,
                        "url": book.url,
                        "image_url": book.image_url,
                        "last_annotated_date": (
                            book.last_annotated_date.isoformat()
                            if book.last_annotated_date
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
                        for h in highlights
                    ],
                },
            }
        )

    @app.route("/api/search")
    def api_search():
        """Search highlights."""
        query = request.args.get("q", "").strip()
        book_asin = request.args.get("book")

        if not query:
            return jsonify(
                {"success": False, "message": "Query is required", "error": "Missing q parameter"}
            ), 400

        db = get_db()
        results = db.search_highlights(query, book_asin)

        return jsonify(
            {
                "success": True,
                "data": [
                    {
                        "highlight": {
                            "id": result.highlight.id,
                            "text": result.highlight.text,
                            "location": result.highlight.location,
                            "page": result.highlight.page,
                            "note": result.highlight.note,
                            "color": result.highlight.color.value
                            if result.highlight.color
                            else None,
                        },
                        "book": {
                            "asin": result.book.asin,
                            "title": result.book.title,
                            "author": result.book.author,
                        },
                    }
                    for result in results
                ],
            }
        )

    return app


def run_server(host: str = "127.0.0.1", port: int = 5000, debug: bool = False):
    """Run the Flask development server.

    Args:
        host: Host to bind to.
        port: Port to bind to.
        debug: Enable debug mode.
    """
    app = create_app()
    print(f"Starting web server at http://{host}:{port}")
    print("Press Ctrl+C to stop")
    app.run(host=host, port=port, debug=debug)

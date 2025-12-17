"""Web interface for browsing Kindle highlights."""

from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, abort, g, request

from kindle_sync.database import DatabaseManager
from kindle_sync.models import HighlightColor


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
        db_path = str(Path.home() / ".kindle-sync" / "kindle.db")

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

    @app.route("/")
    def index():
        """Show all books with highlight counts."""
        db = get_db()
        books = db.get_all_books()

        # Add highlight count to each book
        books_with_counts = []
        for book in books:
            highlights = db.get_highlights(book.asin)
            books_with_counts.append({
                "book": book,
                "highlight_count": len(highlights),
            })

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
        results = db.search_highlights(
            query,
            book_asin=book_filter if book_filter else None
        )

        # Group results by book for better display
        books_results = {}
        for highlight, book in results:
            if book.asin not in books_results:
                books_results[book.asin] = {
                    "book": book,
                    "highlights": []
                }
            books_results[book.asin]["highlights"].append(highlight)

        return render_template(
            "search.html",
            query=query,
            results=list(books_results.values()),
            total_results=len(results),
            book_filter=book_filter
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

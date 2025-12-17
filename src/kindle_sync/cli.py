"""Command-line interface for Kindle Highlights Sync."""

from datetime import datetime

import click
from rich.console import Console
from rich.table import Table

from kindle_sync.auth import AuthManager
from kindle_sync.config import Config
from kindle_sync.database import DatabaseManager
from kindle_sync.exporter import Exporter
from kindle_sync.models import AmazonRegion, ExportFormat
from kindle_sync.scraper import KindleScraper

console = Console()


@click.group()
@click.option("--db", default=None, help="Database path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode")
@click.version_option(version="0.1.0")
@click.pass_context
def main(ctx: click.Context, db: str | None, verbose: bool, quiet: bool) -> None:
    """Kindle Highlights Sync - Sync and export Kindle highlights."""
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Set database path
    db_path = db if db else Config.DEFAULT_DB_PATH
    ctx.obj["db_path"] = db_path
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet

    # Initialize database
    db_manager = DatabaseManager(db_path)
    db_manager.init_schema()
    ctx.obj["db"] = db_manager


@main.command()
@click.option(
    "--region",
    default="india",
    type=click.Choice(
        ["global", "uk", "germany", "japan", "india", "spain", "italy", "france"],
        case_sensitive=False,
    ),
    help="Amazon region",
)
@click.option("--headless/--no-headless", default=False, help="Headless browser")
@click.pass_context
def login(ctx: click.Context, region: str, headless: bool) -> None:
    """Authenticate with Amazon and save session."""
    db = ctx.obj["db"]

    # Convert region string to enum
    region_enum = AmazonRegion(region.lower())

    # Create auth manager
    auth = AuthManager(db, region_enum)

    # Check if already authenticated
    if auth.is_authenticated():
        console.print("✓ Already authenticated", style="green")
        click.confirm("Do you want to re-authenticate?", abort=True)

    # Perform login
    try:
        success = auth.login(headless=headless)
        if success:
            console.print("✓ Login successful!", style="green")
        else:
            console.print("✗ Login failed", style="red")
            raise click.Abort()
    except Exception as e:
        console.print(f"✗ Error: {e}", style="red")
        raise click.Abort() from e


@main.command()
@click.pass_context
def logout(ctx: click.Context) -> None:
    """Clear stored session."""
    db = ctx.obj["db"]

    # We don't know which region, so use default
    auth = AuthManager(db, AmazonRegion.GLOBAL)
    auth.logout()

    console.print("✓ Session cleared", style="green")


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show sync status and statistics."""
    db = ctx.obj["db"]

    # Check authentication
    auth = AuthManager(db, AmazonRegion.GLOBAL)
    is_auth = auth.is_authenticated()

    # Get stats
    books = db.get_all_books()
    last_sync = db.get_last_sync()

    # Calculate total highlights
    total_highlights = sum(db.get_highlight_count(book.asin) for book in books)

    console.print("\n[bold]Kindle Highlights Sync - Status[/bold]\n")
    console.print(f"Database: {ctx.obj['db_path']}")
    console.print(f"Authentication: {'✓ Active' if is_auth else '✗ Not authenticated'}")
    console.print(f"Total Books: {len(books)}")
    console.print(f"Total Highlights: {total_highlights}")
    console.print(
        f"Last Sync: {last_sync.strftime('%Y-%m-%d %H:%M:%S') if last_sync else 'Never'}\n"
    )


@main.command()
@click.option("--full", is_flag=True, help="Full sync (re-download everything)")
@click.option("--books", help="Comma-separated list of ASINs to sync")
@click.pass_context
def sync(ctx: click.Context, full: bool, books: str | None) -> None:
    """Sync books and highlights from Amazon."""
    db = ctx.obj["db"]

    # Get region from session
    region_str = db.get_session("region") or "global"
    region = AmazonRegion(region_str)

    # Create auth manager and get session
    auth = AuthManager(db, region)

    if not auth.is_authenticated():
        console.print("✗ Not authenticated. Please run 'login' first.", style="red")
        raise click.Abort()

    session = auth.get_session()
    scraper = KindleScraper(session, region)

    console.print("[bold]Starting sync...[/bold]\n")

    # Parse specific books if provided
    specific_asins = None
    if books:
        specific_asins = [asin.strip() for asin in books.split(",")]

    try:
        # Scrape books
        console.print("Fetching books from Amazon...")
        scraped_books = scraper.scrape_books()

        if not scraped_books:
            console.print("✗ No books found", style="yellow")
            return

        # Filter if specific books requested
        if specific_asins:
            scraped_books = [b for b in scraped_books if b.asin in specific_asins]
            if not scraped_books:
                console.print(f"✗ None of the specified books found: {books}", style="red")
                return

        console.print(f"Found {len(scraped_books)} book(s)")

        # Save books to database
        for book in scraped_books:
            db.insert_book(book)

        # Scrape highlights for each book
        total_new_highlights = 0
        for i, book in enumerate(scraped_books, 1):
            console.print(f"\n[{i}/{len(scraped_books)}] {book.title} by {book.author}")
            console.print("  Fetching highlights...")

            highlights = scraper.scrape_highlights(book)

            # Get current highlight IDs from database
            existing_highlights = db.get_highlights(book.asin)
            existing_ids = {h.id for h in existing_highlights}
            scraped_ids = {h.id for h in highlights}

            # Save/update highlights
            new_count = 0
            for highlight in highlights:
                exists = highlight.id in existing_ids
                db.insert_highlight(highlight)  # Always insert (will UPSERT)
                if not exists:
                    new_count += 1

            # Delete highlights that no longer exist on Amazon
            deleted_ids = existing_ids - scraped_ids
            deleted_count = len(deleted_ids)
            if deleted_ids:
                db.delete_highlights(list(deleted_ids))

            total_new_highlights += new_count
            status = f"  ✓ {new_count} new"
            if deleted_count > 0:
                status += f", {deleted_count} deleted"
            status += f" ({len(highlights)} total)"
            console.print(status)

        # Update last sync time
        db.set_last_sync(datetime.now())

        console.print(
            f"\n✓ Sync complete! {total_new_highlights} new highlight(s) synced.", style="green"
        )

    except Exception as e:
        console.print(f"\n✗ Sync failed: {e}", style="red")
        raise click.Abort() from e


@main.command()
@click.argument("output_dir", type=click.Path())
@click.option(
    "--format",
    type=click.Choice(["markdown", "json", "csv"], case_sensitive=False),
    default="markdown",
    help="Export format",
)
@click.option("--template", default="default", help="Template name for Markdown export")
@click.option("--books", help="Comma-separated list of ASINs to export")
@click.pass_context
def export(
    ctx: click.Context, output_dir: str, format: str, template: str, books: str | None
) -> None:
    """Export highlights to files."""
    db = ctx.obj["db"]

    # Convert format string to enum
    export_format = ExportFormat[format.upper()]

    # Create exporter
    exporter = Exporter(db)

    console.print(f"[bold]Exporting to {output_dir}...[/bold]\n")

    try:
        if books:
            # Export specific books
            asins = [asin.strip() for asin in books.split(",")]
            created_files = []
            for asin in asins:
                book = db.get_book(asin)
                if not book:
                    console.print(f"✗ Book with ASIN {asin} not found", style="yellow")
                    continue

                file_path = exporter.export_book(asin, output_dir, export_format, template)
                created_files.append(file_path)
                console.print(f"✓ {book.title} → {file_path}")
        else:
            # Export all books
            created_files = exporter.export_all(output_dir, export_format, template)
            for file_path in created_files:
                console.print(f"✓ {file_path}")

        console.print(f"\n✓ Exported {len(created_files)} file(s)", style="green")

    except Exception as e:
        console.print(f"\n✗ Export failed: {e}", style="red")
        raise click.Abort() from e


@main.command(name="list")
@click.option(
    "--sort",
    type=click.Choice(["title", "author", "date"], case_sensitive=False),
    default="title",
    help="Sort by field",
)
@click.option(
    "--format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format",
)
@click.pass_context
def list_books(ctx: click.Context, sort: str, format: str) -> None:
    """List all books in database."""
    db = ctx.obj["db"]

    books = db.get_all_books()

    if not books:
        console.print("No books found in database", style="yellow")
        return

    # Sort books
    if sort == "author":
        books.sort(key=lambda b: b.author)
    elif sort == "date":
        books.sort(key=lambda b: b.last_annotated_date or datetime.min, reverse=True)
    # Default is already sorted by title

    if format == "json":
        import json

        output = [
            {
                "asin": book.asin,
                "title": book.title,
                "author": book.author,
                "highlights": db.get_highlight_count(book.asin),
                "last_annotated": (
                    book.last_annotated_date.isoformat() if book.last_annotated_date else None
                ),
            }
            for book in books
        ]
        console.print(json.dumps(output, indent=2))
    else:
        # Table format
        table = Table(title="Books in Database")
        table.add_column("ASIN", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Author", style="yellow")
        table.add_column("Highlights", justify="right", style="green")
        table.add_column("Last Annotated", style="magenta")

        for book in books:
            highlight_count = db.get_highlight_count(book.asin)
            last_date = (
                book.last_annotated_date.strftime("%Y-%m-%d") if book.last_annotated_date else "—"
            )
            table.add_row(book.asin, book.title, book.author, str(highlight_count), last_date)

        console.print(table)


@main.command()
@click.argument("asin")
@click.pass_context
def show(ctx: click.Context, asin: str) -> None:
    """Show details for a specific book."""
    db = ctx.obj["db"]

    book = db.get_book(asin)
    if not book:
        console.print(f"✗ Book with ASIN {asin} not found", style="red")
        raise click.Abort()

    highlights = db.get_highlights(book.asin)

    console.print(f"\n[bold]{book.title}[/bold]")
    console.print(f"Author: {book.author}")
    console.print(f"ASIN: {book.asin}")
    if book.last_annotated_date:
        console.print(f"Last Annotated: {book.last_annotated_date.strftime('%Y-%m-%d')}")
    console.print(f"\nTotal Highlights: {len(highlights)}")

    if highlights:
        console.print("\n[bold]Recent Highlights:[/bold]\n")
        for i, highlight in enumerate(highlights[:5], 1):
            location = f"Location {highlight.location}" if highlight.location else ""
            page = f"Page {highlight.page}" if highlight.page else ""
            position = " • ".join(filter(None, [location, page]))

            console.print(f"[cyan]{i}. {position}[/cyan]")
            console.print(f"   {highlight.text[:100]}{'...' if len(highlight.text) > 100 else ''}")
            if highlight.note:
                console.print(f"   [yellow]Note: {highlight.note}[/yellow]")
            console.print()

        if len(highlights) > 5:
            console.print(f"... and {len(highlights) - 5} more highlight(s)")


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=5000, type=int, help="Port to bind to")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.pass_context
def web(ctx: click.Context, host: str, port: int, debug: bool) -> None:
    """Start web interface for browsing highlights."""
    from kindle_sync.web import create_app

    db_path = ctx.obj["db_path"]
    app = create_app(db_path)

    console.print("[bold]Starting web server...[/bold]")
    console.print(f"Open your browser to: [cyan]http://{host}:{port}[/cyan]")
    console.print("Press [red]Ctrl+C[/red] to stop\n")

    try:
        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        console.print("\n✓ Server stopped", style="green")


if __name__ == "__main__":
    main()

"""Command-line interface for Kindle Highlights Sync."""

import json

import click
from rich.console import Console
from rich.table import Table

from kindle_sync.config import Config
from kindle_sync.models import AmazonRegion, ExportFormat
from kindle_sync.services import AuthService, ExportService, SyncService
from kindle_sync.services.database_service import DatabaseManager

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
    db_manager.close()


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
    db_path = ctx.obj["db_path"]

    # Convert region string to enum
    region_enum = AmazonRegion(region.lower())

    # Perform login using service
    result = AuthService.login(db_path, region_enum, headless)

    if result.success:
        console.print(f"✓ {result.message}", style="green")
        if result.data and result.data.get("already_authenticated"):
            if click.confirm("Do you want to re-authenticate?"):
                # Re-login by logging out first
                AuthService.logout(db_path)
                result = AuthService.login(db_path, region_enum, headless)
                if result.success:
                    console.print("✓ Re-authentication successful!", style="green")
                else:
                    console.print(f"✗ {result.message}: {result.error}", style="red")
                    raise click.Abort()
    else:
        console.print(f"✗ {result.message}: {result.error}", style="red")
        raise click.Abort()


@main.command()
@click.pass_context
def logout(ctx: click.Context) -> None:
    """Clear stored session."""
    db_path = ctx.obj["db_path"]

    result = AuthService.logout(db_path)

    if result.success:
        console.print(f"✓ {result.message}", style="green")
    else:
        console.print(f"✗ {result.message}: {result.error}", style="red")


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show sync status and statistics."""
    db_path = ctx.obj["db_path"]

    # Get status using service
    status_data = AuthService.check_status(db_path)

    console.print("\n[bold]Kindle Highlights Sync - Status[/bold]\n")
    console.print(f"Database: {db_path}")
    console.print(
        f"Authentication: {'✓ Active' if status_data['authenticated'] else '✗ Not authenticated'}"
    )
    if status_data["region"]:
        console.print(f"Region: {status_data['region']}")
    console.print(f"Total Books: {status_data['total_books']}")
    console.print(f"Total Highlights: {status_data['total_highlights']}")

    last_sync = status_data["last_sync_datetime"]
    if last_sync:
        console.print(f"Last Sync: {last_sync.strftime('%Y-%m-%d %H:%M:%S')}\n")
    else:
        console.print("Last Sync: Never\n")


@main.command()
@click.option("--full", is_flag=True, help="Full sync (re-download everything)")
@click.option("--books", help="Comma-separated list of ASINs to sync")
@click.pass_context
def sync(ctx: click.Context, full: bool, books: str | None) -> None:
    """Sync books and highlights from Amazon."""
    db_path = ctx.obj["db_path"]

    console.print("[bold]Starting sync...[/bold]\n")

    # Parse specific books if provided
    book_asins = None
    if books:
        book_asins = [asin.strip() for asin in books.split(",")]

    # Progress callback for CLI
    def progress_callback(message: str) -> None:
        console.print(message)

    # Perform sync using service
    result = SyncService.sync(db_path, full, book_asins, progress_callback)

    if result.success:
        console.print(f"\n✓ {result.message}!", style="green")
        console.print(f"  Books synced: {result.books_synced}")
        console.print(f"  New highlights: {result.new_highlights}")
        if result.deleted_highlights > 0:
            console.print(f"  Deleted highlights: {result.deleted_highlights}")

        # Show details if verbose
        if ctx.obj.get("verbose") and result.book_details:
            console.print("\n[bold]Details:[/bold]")
            for detail in result.book_details:
                status = f"  {detail.title}: {detail.new_highlights} new"
                if detail.deleted_highlights > 0:
                    status += f", {detail.deleted_highlights} deleted"
                status += f" ({detail.total_highlights} total)"
                console.print(status)
    else:
        console.print(f"\n✗ {result.message}: {result.error}", style="red")
        raise click.Abort()


@main.command()
@click.argument("output_dir", type=click.Path(), default=Config.DEFAULT_EXPORT_DIR)
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
    db_path = ctx.obj["db_path"]

    # Convert format string to enum
    export_format = ExportFormat[format.upper()]

    console.print(f"[bold]Exporting to {output_dir}...[/bold]\n")

    # Export using service
    if books:
        # Export specific books
        asins = [asin.strip() for asin in books.split(",")]
        result = ExportService.export_books(db_path, asins, output_dir, export_format, template)
    else:
        # Export all books
        result = ExportService.export_all(db_path, output_dir, export_format, template)

    if result.success:
        for file_path in result.files_created:
            console.print(f"✓ {file_path}")
        console.print(f"\n✓ {result.message}", style="green")
    else:
        console.print(f"\n✗ {result.message}: {result.error}", style="red")
        raise click.Abort()


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
    db_path = ctx.obj["db_path"]

    db = DatabaseManager(db_path)
    db.init_schema()
    books_with_counts = db.get_all_books_with_counts(sort)
    db.close()

    if not books_with_counts:
        console.print("No books found in database", style="yellow")
        return

    if format == "json":
        output = [
            {
                "asin": item.book.asin,
                "title": item.book.title,
                "author": item.book.author,
                "highlights": item.highlight_count,
                "last_annotated": (
                    item.book.last_annotated_date.isoformat()
                    if item.book.last_annotated_date
                    else None
                ),
            }
            for item in books_with_counts
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

        for item in books_with_counts:
            last_date = (
                item.book.last_annotated_date.strftime("%Y-%m-%d")
                if item.book.last_annotated_date
                else "—"
            )
            table.add_row(
                item.book.asin,
                item.book.title,
                item.book.author,
                str(item.highlight_count),
                last_date,
            )

        console.print(table)


@main.command()
@click.argument("asin")
@click.pass_context
def show(ctx: click.Context, asin: str) -> None:
    """Show details for a specific book."""
    db_path = ctx.obj["db_path"]

    db = DatabaseManager(db_path)
    db.init_schema()
    book = db.get_book(asin)
    if not book:
        db.close()
        console.print(f"✗ Book with ASIN {asin} not found", style="red")
        raise click.Abort()

    highlights = db.get_highlights(asin)
    db.close()

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


@main.command(name="sync-images")
@click.option(
    "--size",
    type=click.Choice(["small", "medium", "large", "original"], case_sensitive=False),
    default="medium",
    help="Image size",
)
@click.pass_context
def sync_images(ctx: click.Context, size: str) -> None:
    """Download book cover images."""
    from kindle_sync.models import ImageSize
    from kindle_sync.services import ImageService

    db_path = ctx.obj["db_path"]

    # Convert size string to ImageSize enum
    image_size = ImageSize.from_name(size)

    console.print(f"[bold]Downloading book cover images {size}...[/bold]\n")

    result = ImageService.sync_all_images(db_path, image_size)

    if result.success:
        console.print(f"\n✓ {result.message}!", style="green")
        if result.images_downloaded > 0:
            console.print(f"  Images downloaded: {result.images_downloaded}")
            size_mb = result.total_bytes / (1024 * 1024)
            console.print(f"  Total size: {size_mb:.2f} MB")
    else:
        console.print(f"\n✗ {result.message}: {result.error}", style="red")
        raise click.Abort()


@main.command(name="add-physical-book")
@click.argument("asin")
@click.option("--isbn", help="ISBN for better Goodreads metadata")
@click.pass_context
def add_physical_book(ctx: click.Context, asin: str, isbn: str | None) -> None:
    """Add a physical book by ASIN."""
    db_path = ctx.obj["db_path"]

    console.print(f"[bold]Adding physical book {asin}...[/bold]\n")

    result = SyncService.add_physical_book(db_path, asin, isbn)

    if result.success and result.book:
        console.print(f"\n✓ {result.message}!", style="green")
        console.print(f"\n[bold]{result.book.title}[/bold]")
        console.print(f"Author: {result.book.author}")
        console.print(f"ASIN: {result.book.asin}")
        if result.book.isbn:
            console.print(f"ISBN: {result.book.isbn}")
        if result.book.page_count:
            console.print(f"Pages: {result.book.page_count}")
        if result.book.genres:
            console.print(f"Genres: {result.book.genres}")
        if result.book.goodreads_link:
            console.print(f"Goodreads: {result.book.goodreads_link}")
        console.print("\nYou can now add highlights and notes to this book.")
    else:
        console.print(f"\n✗ {result.message}: {result.error}", style="red")
        raise click.Abort()


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

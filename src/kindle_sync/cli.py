"""Command-line interface for Kindle Highlights Sync."""

import click
from rich.console import Console

from kindle_sync.auth import AuthManager
from kindle_sync.config import Config
from kindle_sync.database import DatabaseManager
from kindle_sync.models import AmazonRegion

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
    default="global",
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

    console.print("\n[bold]Kindle Highlights Sync - Status[/bold]\n")
    console.print(f"Database: {ctx.obj['db_path']}")
    console.print(f"Authentication: {'✓ Active' if is_auth else '✗ Not authenticated'}")
    console.print(f"Total Books: {len(books)}")
    console.print(f"Last Sync: {last_sync if last_sync else 'Never'}\n")


if __name__ == "__main__":
    main()

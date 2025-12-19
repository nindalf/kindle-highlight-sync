"""macOS menu bar application for Kindle Highlights Sync."""

import threading
import webbrowser

import rumps

from kindle_sync.config import Config
from kindle_sync.models import AmazonRegion
from kindle_sync.services import AuthService, ExportService, SyncService
from kindle_sync.services.database_service import DatabaseManager
from kindle_sync.web import create_app


class KindleSyncMenuBar(rumps.App):
    """macOS menu bar application for Kindle Highlights Sync."""

    def __init__(self):
        """Initialize the menu bar app."""
        super().__init__(
            "Kindle Sync",
            quit_button=None,
        )

        # Configuration
        self.db_path = Config.DEFAULT_DB_PATH
        self.web_host = "127.0.0.1"
        self.web_port = 5000

        # Initialize database
        db = DatabaseManager(self.db_path)
        db.init_schema()
        db.close()

        # Flask app thread
        self.flask_thread = None
        self.flask_app = None

        # Build menu
        self._build_menu()

        # Start Flask server in background
        self._start_flask_server()

    def _build_menu(self):
        """Build the menu bar menu."""
        # Check authentication status
        status = AuthService.check_status(self.db_path)
        authenticated = status["authenticated"]

        # Authentication menu items
        if authenticated:
            self.menu = [
                rumps.MenuItem("Status", callback=self.show_status),
                None,  # Separator
                rumps.MenuItem("Sync Now", callback=self.sync_highlights),
                rumps.MenuItem("Sync Images", callback=self.sync_images),
                rumps.MenuItem("Export Highlights", callback=self.export_highlights),
                None,  # Separator
                rumps.MenuItem("Open Web Interface", callback=self.open_web_interface),
                None,  # Separator
                rumps.MenuItem("Settings", callback=self.open_settings),
                rumps.MenuItem("Logout", callback=self.logout),
                None,  # Separator
                rumps.MenuItem("Quit", callback=self.quit_app),
            ]
        else:
            self.menu = [
                rumps.MenuItem("Login to Amazon", callback=self.login),
                rumps.MenuItem("Open Web Interface", callback=self.open_web_interface),
                None,  # Separator
                rumps.MenuItem("Quit", callback=self.quit_app),
            ]

    def _start_flask_server(self):
        """Start Flask server in background thread."""
        if self.flask_thread and self.flask_thread.is_alive():
            return

        self.flask_app = create_app(self.db_path)

        def run_flask():
            if self.flask_app:
                self.flask_app.run(
                    host=self.web_host, port=self.web_port, debug=False, use_reloader=False
                )

        self.flask_thread = threading.Thread(target=run_flask, daemon=True)
        self.flask_thread.start()

    def show_status(self, _):
        """Show current status."""
        status = AuthService.check_status(self.db_path)

        region = status.get("region", "Unknown")
        total_books = status.get("total_books", 0)
        total_highlights = status.get("total_highlights", 0)
        last_sync = status.get("last_sync_datetime")

        if last_sync:
            last_sync_str = last_sync.strftime("%Y-%m-%d %H:%M:%S")
        else:
            last_sync_str = "Never"

        message = (
            f"Region: {region}\n"
            f"Books: {total_books}\n"
            f"Highlights: {total_highlights}\n"
            f"Last Sync: {last_sync_str}"
        )

        rumps.alert("Kindle Sync Status", message)

    def login(self, _):
        """Perform Amazon login."""
        # Show dialog to select region
        response = rumps.Window(
            message="Select Amazon Region:",
            title="Login",
            default_text="india",
            dimensions=(280, 20),
        ).run()

        if not response.clicked:
            return

        region_str = response.text.strip().lower()

        try:
            region = AmazonRegion(region_str)
        except ValueError:
            rumps.alert(
                "Invalid Region",
                "Please enter one of: global, uk, germany, japan, india, spain, italy, france",
            )
            return

        # Show notification
        rumps.notification(
            title="Kindle Sync",
            subtitle="Login",
            message="Opening browser for Amazon login...",
        )

        # Perform login (this will open browser)
        result = AuthService.login(self.db_path, region, headless=False)

        if result.success:
            rumps.notification(
                title="Kindle Sync",
                subtitle="Login Successful",
                message="You are now authenticated with Amazon.",
            )
            # Rebuild menu to show authenticated options
            self._build_menu()
        else:
            rumps.alert("Login Failed", f"{result.message}: {result.error}")

    def logout(self, _):
        """Logout from Amazon."""
        response = rumps.alert(
            "Logout",
            "Are you sure you want to logout?",
            ok="Logout",
            cancel="Cancel",
        )

        if response == 1:  # OK clicked
            result = AuthService.logout(self.db_path)
            if result.success:
                rumps.notification(
                    title="Kindle Sync",
                    subtitle="Logged Out",
                    message="Session cleared successfully.",
                )
                # Rebuild menu to show login option
                self._build_menu()
            else:
                rumps.alert("Logout Failed", f"{result.message}: {result.error}")

    def sync_highlights(self, _):
        """Sync highlights from Amazon."""
        # Show notification
        rumps.notification(
            title="Kindle Sync",
            subtitle="Sync Started",
            message="Syncing highlights from Amazon...",
        )

        # Perform sync in background thread to avoid blocking UI
        def sync_worker():
            result = SyncService.sync(self.db_path, full=False, book_asins=None)

            if result.success:
                rumps.notification(
                    title="Kindle Sync",
                    subtitle="Sync Complete",
                    message=f"Synced {result.books_synced} books, {result.new_highlights} new highlights",
                )
            else:
                rumps.notification(
                    title="Kindle Sync",
                    subtitle="Sync Failed",
                    message=f"{result.message}: {result.error}",
                )

        sync_thread = threading.Thread(target=sync_worker, daemon=True)
        sync_thread.start()

    def export_highlights(self, _):
        """Export highlights to files."""
        # Get export directory
        db = DatabaseManager(self.db_path)
        db.init_schema()
        export_dir = db.get_export_directory()
        db.close()

        if not export_dir:
            export_dir = Config.DEFAULT_EXPORT_DIR

        # Show notification
        rumps.notification(
            title="Kindle Sync",
            subtitle="Export Started",
            message=f"Exporting highlights to {export_dir}...",
        )

        # Perform export in background thread
        def export_worker():
            from kindle_sync.models import ExportFormat

            result = ExportService.export_all(
                self.db_path, export_dir, ExportFormat.MARKDOWN, "default"
            )

            if result.success:
                rumps.notification(
                    title="Kindle Sync",
                    subtitle="Export Complete",
                    message=f"Exported {len(result.files_created)} files to {export_dir}",
                )
            else:
                rumps.notification(
                    title="Kindle Sync",
                    subtitle="Export Failed",
                    message=f"{result.message}: {result.error}",
                )

        export_thread = threading.Thread(target=export_worker, daemon=True)
        export_thread.start()

    def sync_images(self, _):
        """Sync book cover images."""
        # Show notification
        rumps.notification(
            title="Kindle Sync",
            subtitle="Image Sync Started",
            message="Downloading book cover images...",
        )

        # Perform sync in background thread
        def sync_images_worker():
            from kindle_sync.services import ImageService

            result = ImageService.sync_all_images(self.db_path)

            if result.success:
                size_mb = result.total_bytes / (1024 * 1024)
                message = (
                    f"Downloaded {result.images_downloaded} images ({size_mb:.2f} MB)"
                    if result.images_downloaded > 0
                    else "All images already downloaded"
                )
                rumps.notification(
                    title="Kindle Sync",
                    subtitle="Image Sync Complete",
                    message=message,
                )
            else:
                rumps.notification(
                    title="Kindle Sync",
                    subtitle="Image Sync Failed",
                    message=f"{result.message}: {result.error}",
                )

        sync_images_thread = threading.Thread(target=sync_images_worker, daemon=True)
        sync_images_thread.start()

    def open_web_interface(self, _):
        """Open web interface in default browser."""
        url = f"http://{self.web_host}:{self.web_port}"
        webbrowser.open(url)

        rumps.notification(
            title="Kindle Sync",
            subtitle="Web Interface",
            message="Opening web interface in your browser...",
        )

    def open_settings(self, _):
        """Open settings in web interface."""
        url = f"http://{self.web_host}:{self.web_port}/settings"
        webbrowser.open(url)

    def quit_app(self, _):
        """Quit the application."""
        rumps.quit_application()


def main():
    """Run the menu bar application."""
    app = KindleSyncMenuBar()
    app.run()


if __name__ == "__main__":
    main()

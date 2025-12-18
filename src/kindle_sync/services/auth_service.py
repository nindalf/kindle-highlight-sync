"""Authentication service for both CLI and web interfaces."""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from kindle_sync.config import Config
from kindle_sync.models import AmazonRegion


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    pass


class AuthManager:
    """Manages Amazon authentication and session cookies."""

    def __init__(self, db: Any, region: AmazonRegion) -> None:
        self.db = db
        self.region = region
        self.region_config = Config.get_region_config(region)

    def is_authenticated(self) -> bool:
        """Check if user has valid session."""
        return bool(self.db.get_session("cookies")) and self.validate_session()

    def login(self, headless: bool = False, timeout: int = 60) -> bool:
        """Perform Amazon login using Selenium. Opens browser for user to log in."""
        print(f"Opening browser for Amazon login ({self.region_config.name})...")
        print("Please log in to your Amazon account.")

        try:
            cookies = self._launch_browser_login(headless, timeout)
            cookies_json = json.dumps(cookies)
            self.db.save_session("cookies", cookies_json)
            self.db.save_session("region", self.region.value)
            print("✓ Login successful! Session saved.")
            return True
        except Exception as e:
            exc = AuthenticationError("Login failed")
            exc.add_note(f"Region: {self.region_config.name}")
            exc.add_note(f"Headless mode: {headless}")
            exc.add_note(f"Login URL: {self.region_config.kindle_reader_url}")
            raise exc from e

    def logout(self) -> None:
        """Clear stored session cookies."""
        self.db.clear_session()
        print("✓ Session cleared. You'll need to login again.")

    def get_session(self) -> requests.Session:
        """Get requests.Session with stored cookies."""
        cookies_json = self.db.get_session("cookies")
        if not cookies_json:
            raise AuthenticationError("Not authenticated. Please run 'login' first.")

        try:
            cookies_data = json.loads(cookies_json)
        except json.JSONDecodeError as e:
            raise AuthenticationError(f"Invalid cookies data: {e}") from e

        session = requests.Session()
        session.headers.update({"User-Agent": Config.USER_AGENT})

        for cookie in cookies_data.get("cookies", []):
            session.cookies.set(
                name=cookie["name"],
                value=cookie["value"],
                domain=cookie.get("domain", ""),
                path=cookie.get("path", "/"),
            )

        return session

    def validate_session(self) -> bool:
        """Validate that stored session is still active."""
        try:
            session = self.get_session()
            response = session.get(self.region_config.notebook_url, timeout=Config.REQUEST_TIMEOUT)
            return response.status_code == 200 and "signin" not in response.url.lower() and "login" not in response.url.lower()
        except (AuthenticationError, requests.RequestException):
            return False

    def _launch_browser_login(self, headless: bool, timeout: int) -> dict[str, Any]:
        """Launch Selenium browser for login."""
        chrome_options = ChromeOptions()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(f"user-agent={Config.USER_AGENT}")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        try:
            driver.get(self.region_config.notebook_url)
            start_time = time.time()

            while time.time() - start_time < timeout:
                if self.region_config.kindle_reader_url in driver.current_url:
                    cookies = driver.get_cookies()
                    driver.quit()
                    return {"cookies": cookies}
                time.sleep(1)

            driver.quit()
            raise AuthenticationError("Login timeout - please try again")
        except Exception as e:
            driver.quit()
            raise AuthenticationError(f"Browser error: {e}") from e


@dataclass
class AuthResult:
    """Result of authentication operation."""

    success: bool
    message: str
    error: str | None = None
    data: dict | None = None


class AuthService:
    """Service for authentication operations."""

    @staticmethod
    def login(db_path: str, region: AmazonRegion, headless: bool = False) -> AuthResult:
        """Perform login operation."""
        from kindle_sync.services.database_service import DatabaseManager

        db = DatabaseManager(db_path)
        db.init_schema()

        try:
            auth = AuthManager(db, region)
            if auth.is_authenticated():
                db.close()
                return AuthResult(success=True, message="Already authenticated",
                                data={"already_authenticated": True})

            success = auth.login(headless=headless)
            db.close()
            return AuthResult(
                success=success,
                message="Login successful" if success else "Login failed",
                data={"region": region.value} if success else None,
                error=None if success else "Authentication failed"
            )
        except Exception as e:
            db.close()
            return AuthResult(success=False, message="Login error", error=str(e))

    @staticmethod
    def logout(db_path: str) -> AuthResult:
        """Clear stored session."""
        from kindle_sync.services.database_service import DatabaseManager

        try:
            db = DatabaseManager(db_path)
            AuthManager(db, AmazonRegion.GLOBAL).logout()
            db.close()
            return AuthResult(success=True, message="Session cleared")
        except Exception as e:
            return AuthResult(success=False, message="Logout error", error=str(e))

    @staticmethod
    def check_status(db_path: str) -> dict:
        """Get authentication and sync status."""
        from kindle_sync.services.database_service import DatabaseManager

        db = DatabaseManager(db_path)
        db.init_schema()

        try:
            is_auth = AuthManager(db, AmazonRegion.GLOBAL).is_authenticated()
            books = db.get_all_books()
            last_sync = db.get_last_sync()
            total_highlights = sum(db.get_highlight_count(book.asin) for book in books)
            region_str = db.get_session("region")
            db.close()

            return {
                "authenticated": is_auth,
                "region": region_str,
                "total_books": len(books),
                "total_highlights": total_highlights,
                "last_sync": last_sync.isoformat() if last_sync else None,
                "last_sync_datetime": last_sync,
            }
        except Exception:
            db.close()
            return {
                "authenticated": False,
                "region": None,
                "total_books": 0,
                "total_highlights": 0,
                "last_sync": None,
                "last_sync_datetime": None,
            }

    @staticmethod
    def is_authenticated(db_path: str) -> bool:
        """Check if user is authenticated."""
        from kindle_sync.services.database_service import DatabaseManager

        try:
            db = DatabaseManager(db_path)
            db.init_schema()
            region_str = db.get_session("region") or "global"
            is_auth = AuthManager(db, AmazonRegion(region_str)).is_authenticated()
            db.close()
            return is_auth
        except Exception:
            return False

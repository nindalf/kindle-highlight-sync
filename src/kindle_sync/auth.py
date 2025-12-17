"""Authentication and session management for Amazon Kindle."""

import json
import time
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
        """
        Initialize auth manager.

        Args:
            db: Database manager instance
            region: Amazon region to authenticate with
        """
        self.db = db
        self.region = region
        self.region_config = Config.get_region_config(region)

    def is_authenticated(self) -> bool:
        """
        Check if user has valid session.

        Returns:
            True if authenticated, False otherwise
        """
        cookies_json = self.db.get_session("cookies")
        if not cookies_json:
            return False

        # Validate session by making a test request
        return self.validate_session()

    def login(self, headless: bool = False, timeout: int = 60) -> bool:
        """
        Perform Amazon login using Selenium.

        Opens a browser window for user to log in. Waits for successful
        login by detecting URL change to Kindle reader.

        Args:
            headless: Run browser in headless mode
            timeout: Login timeout in seconds

        Returns:
            True if login successful, False otherwise

        Raises:
            AuthenticationError: If login fails or times out
        """
        print(f"Opening browser for Amazon login ({self.region_config.name})...")
        print("Please log in to your Amazon account.")

        try:
            cookies = self._launch_browser_login(headless, timeout)
            self._save_cookies(cookies)
            print("✓ Login successful! Session saved.")
            return True
        except Exception as e:
            raise AuthenticationError(f"Login failed: {e}") from e

    def logout(self) -> None:
        """Clear stored session cookies."""
        self.db.clear_session()
        print("✓ Session cleared. You'll need to login again.")

    def get_session(self) -> requests.Session:
        """
        Get requests.Session with stored cookies.

        Returns:
            Configured requests.Session

        Raises:
            AuthenticationError: If not authenticated
        """
        cookies_json = self.db.get_session("cookies")
        if not cookies_json:
            raise AuthenticationError("Not authenticated. Please run 'login' first.")

        try:
            cookies_data = json.loads(cookies_json)
        except json.JSONDecodeError as e:
            raise AuthenticationError(f"Invalid cookies data: {e}") from e

        session = requests.Session()
        session.headers.update({"User-Agent": Config.USER_AGENT})

        # Add cookies to session
        self._cookies_to_session(cookies_data, session)

        return session

    def validate_session(self) -> bool:
        """
        Validate that stored session is still active.

        Makes a test request to notebook URL.

        Returns:
            True if session valid, False otherwise
        """
        try:
            session = self.get_session()
            response = session.get(self.region_config.notebook_url, timeout=Config.REQUEST_TIMEOUT)

            # Check if we're redirected to login page
            if "signin" in response.url.lower() or "login" in response.url.lower():
                return False

            # Check for successful response
            return response.status_code == 200

        except (AuthenticationError, requests.RequestException):
            return False

    def _launch_browser_login(self, headless: bool, timeout: int) -> dict[str, Any]:
        """
        Launch Selenium browser for login.

        Args:
            headless: Run in headless mode
            timeout: Timeout in seconds

        Returns:
            Dictionary of cookies

        Raises:
            AuthenticationError: If login fails
        """
        # Setup Chrome options
        chrome_options = ChromeOptions()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(f"user-agent={Config.USER_AGENT}")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Initialize driver
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        try:
            # Navigate to notebook URL (will redirect to login if needed)
            driver.get(self.region_config.notebook_url)

            # Wait for user to login and reach kindle reader URL
            start_time = time.time()
            while time.time() - start_time < timeout:
                current_url = driver.current_url

                # Check if we've successfully logged in
                if self.region_config.kindle_reader_url in current_url:
                    # Extract cookies
                    cookies = driver.get_cookies()
                    driver.quit()
                    return {"cookies": cookies}

                time.sleep(1)

            # Timeout reached
            driver.quit()
            raise AuthenticationError("Login timeout - please try again")

        except Exception as e:
            driver.quit()
            raise AuthenticationError(f"Browser error: {e}") from e

    def _save_cookies(self, cookies_data: dict[str, Any]) -> None:
        """
        Save cookies to database.

        Args:
            cookies_data: Dictionary containing cookies
        """
        cookies_json = json.dumps(cookies_data)
        self.db.save_session("cookies", cookies_json)

        # Also save region
        self.db.save_session("region", self.region.value)

    def _load_cookies(self) -> dict[str, Any] | None:
        """
        Load cookies from database.

        Returns:
            Dictionary of cookies, or None if not found
        """
        cookies_json = self.db.get_session("cookies")
        if not cookies_json:
            return None

        try:
            return json.loads(cookies_json)
        except json.JSONDecodeError:
            return None

    def _cookies_to_session(self, cookies_data: dict[str, Any], session: requests.Session) -> None:
        """
        Add cookies to requests.Session.

        Args:
            cookies_data: Dictionary containing cookies
            session: requests.Session to add cookies to
        """
        for cookie in cookies_data.get("cookies", []):
            session.cookies.set(
                name=cookie["name"],
                value=cookie["value"],
                domain=cookie.get("domain", ""),
                path=cookie.get("path", "/"),
            )

"""Configuration management for Kindle Highlights Sync."""

from pathlib import Path

from kindle_sync.models import AmazonRegion, RegionConfig


class Config:
    """Application configuration."""

    # Region configurations
    REGIONS: dict[AmazonRegion, RegionConfig] = {
        AmazonRegion.GLOBAL: RegionConfig(
            name="Global (US)",
            hostname="amazon.com",
            kindle_reader_url="https://read.amazon.com",
            notebook_url="https://read.amazon.com/notebook",
        ),
        AmazonRegion.UK: RegionConfig(
            name="United Kingdom",
            hostname="amazon.co.uk",
            kindle_reader_url="https://read.amazon.co.uk",
            notebook_url="https://read.amazon.co.uk/notebook",
        ),
        AmazonRegion.GERMANY: RegionConfig(
            name="Germany/Swiss/Austria",
            hostname="amazon.de",
            kindle_reader_url="https://lesen.amazon.de",
            notebook_url="https://lesen.amazon.de/notebook",
        ),
        AmazonRegion.JAPAN: RegionConfig(
            name="Japan",
            hostname="amazon.co.jp",
            kindle_reader_url="https://read.amazon.co.jp",
            notebook_url="https://read.amazon.co.jp/notebook",
        ),
        AmazonRegion.INDIA: RegionConfig(
            name="India",
            hostname="amazon.in",
            kindle_reader_url="https://read.amazon.in",
            notebook_url="https://read.amazon.in/notebook",
        ),
        AmazonRegion.SPAIN: RegionConfig(
            name="Spain",
            hostname="amazon.es",
            kindle_reader_url="https://leer.amazon.es",
            notebook_url="https://leer.amazon.es/notebook",
        ),
        AmazonRegion.ITALY: RegionConfig(
            name="Italy",
            hostname="amazon.it",
            kindle_reader_url="https://leggi.amazon.it",
            notebook_url="https://leggi.amazon.it/notebook",
        ),
        AmazonRegion.FRANCE: RegionConfig(
            name="France",
            hostname="amazon.fr",
            kindle_reader_url="https://lire.amazon.fr",
            notebook_url="https://lire.amazon.fr/notebook",
        ),
    }

    # Default settings
    DEFAULT_REGION: AmazonRegion = AmazonRegion.INDIA
    DEFAULT_DB_PATH: str = "~/.kindle-sync/highlights.db"
    DEFAULT_EXPORT_DIR: str = "~/.kindle-sync/exports"
    DEFAULT_TEMPLATE: str = "default"

    # Browser settings
    BROWSER_TIMEOUT: int = 60
    BROWSER_IMPLICIT_WAIT: int = 10
    BROWSER_HEADLESS: bool = False

    # Scraping settings
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 2.0
    RETRY_BACKOFF: int = 2

    # User agent
    USER_AGENT: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    @classmethod
    def get_region_config(cls, region: AmazonRegion) -> RegionConfig:
        """
        Get configuration for a region.

        Args:
            region: Amazon region

        Returns:
            RegionConfig for the specified region
        """
        return cls.REGIONS[region]

    @classmethod
    def expand_path(cls, path: str) -> Path:
        """
        Expand ~ in paths.

        Args:
            path: Path string potentially containing ~

        Returns:
            Expanded Path object
        """
        return Path(path).expanduser()

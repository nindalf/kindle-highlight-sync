"""Service layer for Kindle Highlights Sync.

This package provides a service layer that encapsulates business logic
for authentication, syncing, exporting, and querying books/highlights.

Services are designed to be called from both CLI and web interfaces,
providing a consistent API and behavior across all interfaces.
"""

from kindle_sync.services.auth_service import AuthResult, AuthService
from kindle_sync.services.export_service import ExportResult, ExportService
from kindle_sync.services.sync_service import SyncResult, SyncService

__all__ = [
    "AuthService",
    "AuthResult",
    "SyncService",
    "SyncResult",
    "ExportService",
    "ExportResult",
]

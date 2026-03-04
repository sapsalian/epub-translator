"""Authentication helpers for single-account demo server."""

from nicegui import app, ui

from . import server_config


def check_credentials(username: str, password: str) -> bool:
    """Validate username and password against configured account."""
    return (
        username == server_config.AUTH_USERNAME
        and password == server_config.AUTH_PASSWORD
    )


def is_authenticated() -> bool:
    """Return True if the current user session is authenticated."""
    return app.storage.user.get("authenticated", False)


def login(username: str) -> None:
    """Mark the current user session as authenticated."""
    app.storage.user["authenticated"] = True
    app.storage.user["username"] = username


def logout() -> None:
    """Clear the current user session and redirect to login."""
    app.storage.user.clear()
    ui.navigate.to("/login")


def require_auth() -> bool:
    """Check authentication and redirect to /login if not authenticated.

    Returns True if authenticated, False if redirected.
    """
    if not is_authenticated():
        ui.navigate.to("/login")
        return False
    return True

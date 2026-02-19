"""FastAPI route registration."""

from . import download  # noqa: F401 — registers @app.get("/download/{token}")


def register_routes() -> None:
    """Call to ensure all route modules are imported and registered."""

import argparse

from nicegui import app, ui

from .state import app_state
from .checkpoint_cleaner import cleanup_old_checkpoints
from .views.single import SingleTranslationView


async def on_startup():
    """Initialize app on startup"""
    # Cleanup old checkpoints
    deleted = await cleanup_old_checkpoints(
        app_state.checkpoint_dir,
        app_state.checkpoint_retention_days,
    )
    if deleted > 0:
        print(f"Cleaned up {deleted} old checkpoint(s)")


@ui.page("/")
def main_page():
    """Main application page"""
    ui.page_title("EPUB Translator")

    # Header
    with ui.header().classes("items-center"):
        ui.label("EPUB Translator").classes("text-xl font-bold")

    # Main content
    view = SingleTranslationView()
    view.build()


def run_gui(native: bool = True, port: int = 8080):
    """Run the NiceGUI application"""
    app.on_startup(on_startup)

    if native:
        ui.run(
            native=True,
            window_size=(1000, 800),
            title="EPUB Translator",
            reload=False,
        )
    else:
        ui.run(
            port=port,
            title="EPUB Translator",
            reload=False,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EPUB Translator GUI")
    parser.add_argument(
        "--web", action="store_true", help="Run in web mode instead of native desktop"
    )
    parser.add_argument("--port", type=int, default=8080, help="Port for web mode")
    args = parser.parse_args()

    run_gui(native=not args.web, port=args.port)

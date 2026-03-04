"""pywebview on_download 훅 - 네이티브 저장 다이얼로그."""


def create_download_handler(window):
    """on_download 이벤트 핸들러 팩토리."""

    def on_download(download):
        suggested = getattr(download, "suggested_filename", None) or "translated.epub"

        save_path = window.create_file_dialog(
            dialog_type=window.SAVE_DIALOG,
            save_filename=suggested,
            file_types=("EPUB Files (*.epub)", "All Files (*.*)"),
        )

        if save_path:
            dest = save_path[0] if isinstance(save_path, (list, tuple)) else save_path
            download.set_destination(dest)
        else:
            download.cancel()

    return on_download

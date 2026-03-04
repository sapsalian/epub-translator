"""Login page view."""

from nicegui import ui

from ..auth import check_credentials, login


def build_login_page():
    """Render the login form. Redirects to / on success."""
    with ui.column().classes("absolute-center items-center gap-4 w-full max-w-sm"):
        ui.label("EPUB 번역기").classes("text-3xl font-bold")
        ui.label("계속하려면 로그인하세요").classes("text-gray-500")

        with ui.card().classes("w-full"):
            username_input = ui.input(
                label="아이디",
                placeholder="admin",
            ).classes("w-full")

            password_input = ui.input(
                label="비밀번호",
                password=True,
                password_toggle_button=True,
            ).classes("w-full")

            error_label = ui.label("").classes("text-red-500 text-sm")
            error_label.visible = False

            def attempt_login():
                username = username_input.value.strip()
                password = password_input.value

                if check_credentials(username, password):
                    login(username)
                    ui.navigate.to("/")
                else:
                    error_label.text = "아이디 또는 비밀번호가 올바르지 않습니다."
                    error_label.visible = True
                    password_input.value = ""

            ui.button("로그인", on_click=attempt_login, icon="login").classes(
                "w-full"
            ).props("color=primary size=lg")

            # Allow Enter key on password field
            password_input.on("keydown.enter", attempt_login)
            username_input.on("keydown.enter", lambda: password_input.run_method("focus"))

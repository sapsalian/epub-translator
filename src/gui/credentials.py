"""Secure credential storage using system keyring."""

SERVICE_NAME = "epub-translator"
API_KEY_ACCOUNT = "openai-api-key"


def get_api_key() -> str:
    """Load API key from system keyring."""
    try:
        import keyring

        key = keyring.get_password(SERVICE_NAME, API_KEY_ACCOUNT)
        return key or ""
    except Exception:
        return ""


def save_api_key(api_key: str) -> bool:
    """Save API key to system keyring."""
    try:
        import keyring

        if api_key:
            keyring.set_password(SERVICE_NAME, API_KEY_ACCOUNT, api_key)
        else:
            # Delete if empty
            try:
                keyring.delete_password(SERVICE_NAME, API_KEY_ACCOUNT)
            except keyring.errors.PasswordDeleteError:
                pass
        return True
    except Exception:
        return False

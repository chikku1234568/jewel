"""Who may receive a jewel session.

Google's Testing list does not apply when the only scopes are ``openid email profile``.
The list in ``JEWEL_ALLOWED_EMAILS`` is the lock. Outside ``JEWEL_ENV=local``, an empty
list admits nobody.
"""

from jewel.config import Settings


def email_is_allowed(settings: Settings, email: str) -> bool:
    """True when this verified address may hold a session."""
    allowed = {
        part.strip().casefold() for part in settings.allowed_emails.split(",") if part.strip()
    }
    if not allowed:
        return settings.env == "local"
    return email.strip().casefold() in allowed

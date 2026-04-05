"""
commands/messaging.py — WhatsApp messaging via pywhatkit.
"Send WhatsApp to Mom saying I'll be late"
Requires: pip install pywhatkit
"""
from __future__ import annotations
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Phone book — add your contacts here
_CONTACTS = {
    "mom":    "+91XXXXXXXXXX",
    "dad":    "+91XXXXXXXXXX",
    # Add more: "name": "+countrycode number"
}

def send_whatsapp(contact: str, message: str) -> str:
    try:
        import pywhatkit  # type: ignore
    except ImportError:
        return "WhatsApp requires pywhatkit. Run: pip install pywhatkit"

    phone = _CONTACTS.get(contact.lower().strip())
    if not phone or "XXX" in phone:
        return (f"I don't have a number for '{contact}'. "
                "Add contacts in commands/messaging.py under _CONTACTS.")

    try:
        pywhatkit.sendwhatmsg_instantly(phone, message, wait_time=10, tab_close=True)
        logger.info("WhatsApp sent to %s", contact)
        return f"WhatsApp sent to {contact}: {message[:50]}"
    except Exception as exc:
        return f"WhatsApp error: {exc}"

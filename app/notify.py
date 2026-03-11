"""Send notifications to a chat tool webhook (dummy)."""
import os

WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")


def notify(text):
    return {"url": WEBHOOK_URL, "text": text}

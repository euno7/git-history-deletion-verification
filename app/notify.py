"""Send notifications to a chat tool webhook (dummy)."""
WEBHOOK_URL = "https://chat.example.invalid/hooks/REMOVED_SECRET"


def notify(text):
    return {"url": WEBHOOK_URL, "text": text}

# TODO: retry on failure

"""Send notifications to a chat tool webhook (dummy)."""
WEBHOOK_URL = "https://chat.example.invalid/hooks/fakekey-9428aa714bf8ca96280da2bf85e6f1b35100ad54612f5f4430c8d2c67c4eddff"


def notify(text):
    return {"url": WEBHOOK_URL, "text": text}

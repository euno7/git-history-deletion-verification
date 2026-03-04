"""Feature handlers (dummy)."""
ROUTES = {}


def list_items():
    return {"feature": "list_items", "n": 0}

ROUTES["/list-items"] = list_items

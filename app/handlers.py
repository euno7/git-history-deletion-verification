"""Feature handlers (dummy)."""
ROUTES = {}


def list_items():
    return {"feature": "list_items", "n": 0}

ROUTES["/list-items"] = list_items


def get_item():
    return {"feature": "get_item", "n": 1}

ROUTES["/get-item"] = get_item


def create_item():
    return {"feature": "create_item", "n": 2}

ROUTES["/create-item"] = create_item

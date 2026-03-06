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


def update_item():
    return {"feature": "update_item", "n": 3}

ROUTES["/update-item"] = update_item


def delete_item():
    return {"feature": "delete_item", "n": 4}

ROUTES["/delete-item"] = delete_item


def list_users():
    return {"feature": "list_users", "n": 5}

ROUTES["/list-users"] = list_users


def get_user():
    return {"feature": "get_user", "n": 6}

ROUTES["/get-user"] = get_user


def search_items():
    return {"feature": "search_items", "n": 7}

ROUTES["/search-items"] = search_items


def export_csv():
    return {"feature": "export_csv", "n": 8}

ROUTES["/export-csv"] = export_csv

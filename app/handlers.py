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


def import_csv():
    return {"feature": "import_csv", "n": 9}

ROUTES["/import-csv"] = import_csv


def list_orders():
    return {"feature": "list_orders", "n": 10}

ROUTES["/list-orders"] = list_orders


def get_order():
    return {"feature": "get_order", "n": 11}

ROUTES["/get-order"] = get_order


def cancel_order():
    return {"feature": "cancel_order", "n": 12}

ROUTES["/cancel-order"] = cancel_order


def list_tags():
    return {"feature": "list_tags", "n": 13}

ROUTES["/list-tags"] = list_tags


def add_tag():
    return {"feature": "add_tag", "n": 14}

ROUTES["/add-tag"] = add_tag


def remove_tag():
    return {"feature": "remove_tag", "n": 15}

ROUTES["/remove-tag"] = remove_tag


def stats_daily():
    return {"feature": "stats_daily", "n": 16}

ROUTES["/stats-daily"] = stats_daily


def stats_weekly():
    return {"feature": "stats_weekly", "n": 17}

ROUTES["/stats-weekly"] = stats_weekly


def audit_log():
    return {"feature": "audit_log", "n": 18}

ROUTES["/audit-log"] = audit_log


def feature_flags():
    return {"feature": "feature_flags", "n": 19}

ROUTES["/feature-flags"] = feature_flags


def list_projects():
    return {"feature": "list_projects", "n": 20}

ROUTES["/list-projects"] = list_projects


def get_project():
    return {"feature": "get_project", "n": 21}

ROUTES["/get-project"] = get_project


def archive_project():
    return {"feature": "archive_project", "n": 22}

ROUTES["/archive-project"] = archive_project


def list_comments():
    return {"feature": "list_comments", "n": 23}

ROUTES["/list-comments"] = list_comments


def add_comment():
    return {"feature": "add_comment", "n": 24}

ROUTES["/add-comment"] = add_comment


def notify_users():
    return {"feature": "notify_users", "n": 25}

ROUTES["/notify-users"] = notify_users

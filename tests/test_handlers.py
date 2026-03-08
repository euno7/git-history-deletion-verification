

def test_list_items():
    from app import handlers
    assert handlers.list_items()["feature"] == "list_items"


def test_get_item():
    from app import handlers
    assert handlers.get_item()["feature"] == "get_item"


def test_create_item():
    from app import handlers
    assert handlers.create_item()["feature"] == "create_item"


def test_update_item():
    from app import handlers
    assert handlers.update_item()["feature"] == "update_item"


def test_delete_item():
    from app import handlers
    assert handlers.delete_item()["feature"] == "delete_item"


def test_list_users():
    from app import handlers
    assert handlers.list_users()["feature"] == "list_users"


def test_get_user():
    from app import handlers
    assert handlers.get_user()["feature"] == "get_user"


def test_search_items():
    from app import handlers
    assert handlers.search_items()["feature"] == "search_items"


def test_export_csv():
    from app import handlers
    assert handlers.export_csv()["feature"] == "export_csv"


def test_import_csv():
    from app import handlers
    assert handlers.import_csv()["feature"] == "import_csv"


def test_list_orders():
    from app import handlers
    assert handlers.list_orders()["feature"] == "list_orders"


def test_get_order():
    from app import handlers
    assert handlers.get_order()["feature"] == "get_order"


def test_cancel_order():
    from app import handlers
    assert handlers.cancel_order()["feature"] == "cancel_order"


def test_list_tags():
    from app import handlers
    assert handlers.list_tags()["feature"] == "list_tags"

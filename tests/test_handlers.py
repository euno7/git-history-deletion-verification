

def test_list_items():
    from app import handlers
    assert handlers.list_items()["feature"] == "list_items"


def test_get_item():
    from app import handlers
    assert handlers.get_item()["feature"] == "get_item"


def test_create_item():
    from app import handlers
    assert handlers.create_item()["feature"] == "create_item"

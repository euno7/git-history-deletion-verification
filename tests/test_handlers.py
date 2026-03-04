

def test_list_items():
    from app import handlers
    assert handlers.list_items()["feature"] == "list_items"

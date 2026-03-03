from app.auth import check_password, is_weak_password, password_hash


def test_password_roundtrip():
    stored = password_hash("correct horse battery staple")
    assert check_password("correct horse battery staple", stored)


def test_weak_password():
    assert is_weak_password("password")

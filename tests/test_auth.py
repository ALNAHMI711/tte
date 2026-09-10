from trading.auth import hash_password, needs_rehash, verify_password


def test_password_is_argon2id_and_verifies():
    password = "correct horse battery staple"
    stored = hash_password(password)

    assert stored.startswith("$argon2id$")
    assert stored != password
    assert verify_password(password, stored)
    assert not verify_password("wrong password", stored)


def test_short_password_is_rejected():
    try:
        hash_password("too-short")
    except ValueError:
        pass
    else:
        raise AssertionError("short password must be rejected")


def test_malformed_hash_is_safe():
    assert not verify_password("some password", "not-a-valid-hash")
    assert not needs_rehash("not-a-valid-hash")

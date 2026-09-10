from trading.security_core import StepUpGrant, hash_password, new_session_token, verify_password


def test_password_hash_is_argon2_and_verifies():
    password = "A-secure-test-password-123"
    password_hash = hash_password(password)
    assert password_hash.startswith("$argon2id$")
    assert verify_password(password, password_hash)
    assert not verify_password("wrong-password-123", password_hash)


def test_short_password_rejected():
    try:
        hash_password("too-short")
    except ValueError:
        pass
    else:
        raise AssertionError("short passwords must be rejected")


def test_session_token_is_opaque_and_random():
    first = new_session_token()
    second = new_session_token()
    assert len(first) >= 40
    assert first != second


def test_step_up_grant_is_session_bound_and_expires():
    grant = StepUpGrant("session-a", ttl_seconds=60)
    assert grant.valid_for("session-a", now=grant.expires_at - 1)
    assert not grant.valid_for("session-b", now=grant.expires_at - 1)
    assert not grant.valid_for("session-a", now=grant.expires_at)

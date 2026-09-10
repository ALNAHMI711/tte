from trading.http_security import CookiePolicy, CsrfToken, client_ip_allowed, constant_time_token_match


def test_cookie_policy_is_secure_by_default():
    policy = CookiePolicy()
    assert policy.secure
    assert policy.httponly
    assert policy.samesite == "lax"
    assert policy.path == "/"


def test_csrf_tokens_are_random_and_constant_time_comparable():
    first = CsrfToken.generate()
    second = CsrfToken.generate()
    assert len(first.value) >= 40
    assert first.value != second.value
    assert constant_time_token_match(first.value, first.value)
    assert not constant_time_token_match(first.value, second.value)


def test_client_ip_allowlist_requires_explicit_network():
    assert client_ip_allowed("10.1.2.3", ("10.0.0.0/8",))
    assert not client_ip_allowed("192.168.1.5", ("10.0.0.0/8",))
    assert not client_ip_allowed("not-an-ip", ("10.0.0.0/8",))
    assert not client_ip_allowed("10.1.2.3", ())

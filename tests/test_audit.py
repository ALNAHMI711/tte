from trading.audit import AuditEvent


def test_audit_event_is_utc_and_serializable():
    event = AuditEvent.create(
        "login",
        "user-1",
        "success",
        request_id="req-1",
        details={"ip": "127.0.0.1"},
    )

    data = event.to_dict()
    assert data["action"] == "login"
    assert data["outcome"] == "success"
    assert data["request_id"] == "req-1"
    assert data["details"] == (("ip", "127.0.0.1"),)
    assert data["timestamp"].endswith("+00:00")

from trading.kill_switch import KillSwitch


def test_kill_switch_is_off_by_default():
    switch = KillSwitch()
    assert switch.blocks_new_orders() is False
    assert switch.snapshot().enabled is False


def test_kill_switch_blocks_new_orders_and_preserves_reason():
    switch = KillSwitch()
    state = switch.activate("operator requested stop")
    assert state.enabled is True
    assert state.reason == "operator requested stop"
    assert switch.blocks_new_orders() is True
    assert switch.snapshot() == state


def test_kill_switch_deactivation_restores_order_gate():
    switch = KillSwitch()
    switch.activate("test")
    state = switch.deactivate()
    assert state.enabled is False
    assert state.reason == ""
    assert switch.blocks_new_orders() is False


def test_blank_reason_gets_safe_default():
    switch = KillSwitch()
    state = switch.activate("   ")
    assert state.reason == "manual emergency stop"

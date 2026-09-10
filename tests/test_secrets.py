import pytest

from trading.secrets import (
    EncryptedSecretStore,
    SecretStoreError,
    derive_fernet_key,
    mask_secret,
    secret_fingerprint,
)


def test_secret_is_encrypted_and_round_trips():
    store = EncryptedSecretStore("A" * 40)
    value = "super-secret-binance-key"
    store.put("binance_api_key", value)
    ciphertext = store.ciphertext("binance_api_key")
    assert ciphertext is not None
    assert value.encode() not in ciphertext
    assert store.get("binance_api_key") == value
    assert store.masked("binance_api_key") != value
    assert "secret" not in store.masked("binance_api_key").lower()


def test_wrong_master_key_cannot_decrypt():
    first = EncryptedSecretStore("A" * 40)
    first.put("api_secret", "very-sensitive-value")
    second = EncryptedSecretStore("B" * 40)
    second.load_ciphertext("api_secret", first.ciphertext("api_secret"))
    with pytest.raises(SecretStoreError):
        second.get("api_secret")


def test_configuration_and_input_validation():
    with pytest.raises(SecretStoreError):
        derive_fernet_key("short")
    with pytest.raises(SecretStoreError):
        EncryptedSecretStore("short")
    store = EncryptedSecretStore("C" * 40)
    with pytest.raises(SecretStoreError):
        store.put("", "x")
    with pytest.raises(SecretStoreError):
        store.put("x", "")


def test_masking_and_fingerprint_do_not_expose_secret():
    secret = "abcdefghijklmnopqrstuvwxyz"
    masked = mask_secret(secret)
    fingerprint = secret_fingerprint(secret)
    assert secret not in masked
    assert secret not in fingerprint
    assert len(fingerprint) == 16
    assert secret_fingerprint(secret) == fingerprint
    assert secret_fingerprint("different") != fingerprint

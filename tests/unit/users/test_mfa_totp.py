"""Unit tests for the native TOTP / MFA-crypto utility (addons.users.mfa).

TDD for the Kaupamex base MFA slice (UC-PLT-08 / UC-AUTH-02, T-PLT-33).
Pure RFC 6238 math + Fernet-at-rest with a dedicated MFA_ENCRYPTION_KEY.
No pyotp: native ~implementation.
"""
import base64

import pytest
from django.test import override_settings

from addons.users import mfa


class TestTotpMath:
    def test_rfc6238_sha1_vector(self):
        # RFC 6238 Appendix B, SHA-1, T=59s -> 8-digit TOTP "94287082".
        secret = base64.b32encode(b"12345678901234567890").decode()
        assert mfa.totp_at(secret, timestamp=59, digits=8) == "94287082"

    def test_generate_and_verify_roundtrip(self):
        secret = mfa.generate_totp_secret()
        code = mfa.totp_at(secret, timestamp=1_000_000)
        assert mfa.verify_totp(secret, code, timestamp=1_000_000) is True

    def test_window_accepts_previous_step(self):
        secret = mfa.generate_totp_secret()
        # code generated one 30s step earlier still verifies with window=1
        prev = mfa.totp_at(secret, timestamp=1_000_000 - 30)
        assert mfa.verify_totp(secret, prev, timestamp=1_000_000, window=1) is True

    def test_window_rejects_two_steps_away(self):
        secret = mfa.generate_totp_secret()
        far = mfa.totp_at(secret, timestamp=1_000_000 - 90)
        assert mfa.verify_totp(secret, far, timestamp=1_000_000, window=1) is False

    def test_wrong_code_fails(self):
        secret = mfa.generate_totp_secret()
        assert mfa.verify_totp(secret, "000000", timestamp=1_000_000) is False

    def test_provisioning_uri_shape(self):
        secret = mfa.generate_totp_secret()
        uri = mfa.provisioning_uri(secret, account_name="user@example.com",
                                   issuer="Kaupamex")
        assert uri.startswith("otpauth://totp/")
        assert "secret=" in uri and "issuer=Kaupamex" in uri


class TestMfaCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        blob = mfa.encrypt_secret("JBSWY3DPEHPK3PXP")
        assert blob != "JBSWY3DPEHPK3PXP"  # not plaintext at rest
        assert mfa.decrypt_secret(blob) == "JBSWY3DPEHPK3PXP"

    def test_dedicated_key_not_derived_from_secret_key(self):
        # The MFA key derives from MFA_ENCRYPTION_KEY, not SECRET_KEY:
        # rotating SECRET_KEY must NOT change the MFA fernet key.
        with override_settings(SECRET_KEY="rotated-secret-key-xyz"):
            k_after = mfa._mfa_fernet_key()
        k_before = mfa._mfa_fernet_key()
        assert k_after == k_before

    def test_decrypt_garbage_raises(self):
        with pytest.raises(mfa.MfaCryptoError):
            mfa.decrypt_secret("not-a-valid-fernet-token")


class TestRecoveryCodes:
    def test_generate_recovery_codes_shape(self):
        codes = mfa.generate_recovery_codes(8)
        assert len(codes) == 8
        assert len(set(codes)) == 8  # unique
        for c in codes:
            assert "-" in c and c.replace("-", "").isalnum()

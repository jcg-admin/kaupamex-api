"""Integration tests for the MFADevice model (Kaupamex base MFA, T-PLT-33).

UC-PLT-08 enrolls the factor; UC-AUTH-02 (route 4.6) consumes it at login.
Verifies the secret is encrypted at rest and the enroll/confirm/verify cycle.
"""
import pytest

from apps.users import mfa
from apps.users.models import MFADevice
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


def test_totp_secret_encrypted_at_rest():
    user = UserFactory()
    secret = mfa.generate_totp_secret()
    device = MFADevice(user=user, device_type=MFADevice.TOTP)
    device.set_totp_secret(secret)
    device.save()

    stored = MFADevice.objects.get(pk=device.pk)
    # never stored in clear
    assert stored.data["secret"] != secret
    # round-trips through the dedicated-key Fernet
    assert stored.get_totp_secret() == secret


def test_enroll_confirm_verify_cycle():
    user = UserFactory()
    secret = mfa.generate_totp_secret()
    device = MFADevice.objects.create(
        user=user, device_type=MFADevice.TOTP,
        data={"secret": mfa.encrypt_secret(secret)}, confirmed=False)

    code = mfa.totp_at(secret)
    assert device.verify_totp(code) is True
    device.confirmed = True
    device.save()
    assert device.last_used_at is not None

    assert user.mfa_devices.filter(confirmed=True, device_type=MFADevice.TOTP).exists()


def test_verify_rejects_wrong_code():
    user = UserFactory()
    device = MFADevice.objects.create(
        user=user, device_type=MFADevice.TOTP,
        data={"secret": mfa.encrypt_secret(mfa.generate_totp_secret())})
    assert device.verify_totp("000000") is False


def test_get_secret_without_data_raises():
    user = UserFactory()
    device = MFADevice.objects.create(user=user, device_type=MFADevice.TOTP)
    with pytest.raises(mfa.MfaCryptoError):
        device.get_totp_secret()

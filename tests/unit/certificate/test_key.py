"""Contrato de ``CertificateKey`` — puerto de ``certificate.key`` (Odoo 19c).

Adaptación de Odoo certificate/models/key.py (odoo-tools@622ddc2a, odoo19c:,
LGPL-3). Cubre el cómputo (``_compute_pem_key``), firma/verificación,
descifrado y las tres factories de generación (EC/RSA/Ed25519).
"""
import base64

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from addons.base.models import ResCompany
from addons.certificate.models.key import CertificateKey
from exceptions import UserError

pytestmark = pytest.mark.django_db


def _company(code):
    return ResCompany.objects.create(code=code, name=code)


def _rsa_private_pem(key_size=2048, password=None):
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=key_size)
    encryption = (
        serialization.BestAvailableEncryption(password.encode())
        if password else serialization.NoEncryption()
    )
    return private_key, private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )


class TestGenerateRsaPrivateKey:
    def test_generate_creates_a_row_with_computed_pem_and_public_false(self):
        acme = _company('acme-key-rsa-1')
        key = CertificateKey._generate_rsa_private_key(acme, name='id_rsa')
        assert key.pk is not None
        assert key.public is False
        assert key.loading_error == ''
        assert bytes(key.pem_key).startswith(b'-----BEGIN PRIVATE KEY-----')

    def test_generate_rejects_undersized_key(self):
        acme = _company('acme-key-rsa-2')
        with pytest.raises(UserError):
            CertificateKey._generate_rsa_private_key(acme, key_size=256)

    def test_generate_rejects_unsupported_public_exponent(self):
        acme = _company('acme-key-rsa-3')
        with pytest.raises(UserError):
            CertificateKey._generate_rsa_private_key(acme, public_exponent=17)

    def test_password_is_stored_as_the_original_string_not_bytes(self):
        """Divergencia deliberada vs. la referencia — ver docstring de
        ``_generate_rsa_private_key`` en ``key.py``: la referencia
        re-encodea `password` a bytes y lo persiste tal cual en un campo
        Char; aquí se persiste el string original."""
        acme = _company('acme-key-rsa-4')
        key = CertificateKey._generate_rsa_private_key(
            acme, password='hunter2')
        assert key.password == 'hunter2'
        assert isinstance(key.password, str)


class TestGenerateEcPrivateKey:
    def test_generate_creates_a_row_with_computed_pem(self):
        acme = _company('acme-key-ec-1')
        key = CertificateKey._generate_ec_private_key(acme, name='id_ec')
        assert key.public is False
        assert bytes(key.pem_key).startswith(b'-----BEGIN PRIVATE KEY-----')

    def test_generate_rejects_unsupported_curve(self):
        acme = _company('acme-key-ec-2')
        with pytest.raises(UserError):
            CertificateKey._generate_ec_private_key(acme, curve='SECP384R1')


class TestGenerateEd25519PrivateKey:
    def test_generate_creates_a_row_with_computed_pem(self):
        acme = _company('acme-key-ed-1')
        key = CertificateKey._generate_ed25519_private_key(acme)
        assert key.public is False
        assert bytes(key.pem_key).startswith(b'-----BEGIN PRIVATE KEY-----')


class TestComputePemKey:
    def test_invalid_content_sets_loading_error_and_public_none(self):
        acme = _company('acme-key-bad-1')
        key = CertificateKey(name='bad', company=acme)
        key.content = b'no es una llave'
        key.save()
        assert key.public is None
        assert key.pem_key is None
        assert key.loading_error != ''

    def test_empty_content_resets_computed_fields_without_error(self):
        acme = _company('acme-key-empty-1')
        key = CertificateKey(name='empty', company=acme, content=b'')
        key._compute_pem_key()
        assert key.pem_key is None
        assert key.public is None
        assert key.loading_error == ''

    def test_public_key_content_sets_public_true(self):
        acme = _company('acme-key-pub-1')
        private_key, _pem = _rsa_private_pem()
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        key = CertificateKey(name='pub', company=acme, content=public_pem)
        key.save()
        assert key.public is True
        assert key.loading_error == ''

    def test_password_protected_private_key_loads_with_correct_password(self):
        acme = _company('acme-key-pwd-1')
        _priv, pem = _rsa_private_pem(password='s3cr3t')
        key = CertificateKey(
            name='pwd', company=acme, content=pem, password='s3cr3t')
        key.save()
        assert key.public is False
        assert key.loading_error == ''

    def test_password_protected_private_key_fails_with_wrong_password(self):
        acme = _company('acme-key-pwd-2')
        _priv, pem = _rsa_private_pem(password='s3cr3t')
        key = CertificateKey(
            name='pwd-bad', company=acme, content=pem, password='incorrecta')
        key.save()
        assert key.public is None
        assert key.loading_error != ''


class TestSignAndVerify:
    def test_sign_with_private_key_and_verify_with_matching_public_key(self):
        acme = _company('acme-key-sign-rsa-2')
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        priv_row = CertificateKey.objects.create(
            name='priv', company=acme, content=priv_pem)
        pub_row = CertificateKey.objects.create(
            name='pub', company=acme, content=pub_pem)

        signature = priv_row._sign(b'documento firmado')
        assert pub_row._verify(
            b'documento firmado', base64.decodebytes(signature)) is True
        assert pub_row._verify(
            b'documento alterado', base64.decodebytes(signature)) is False

    def test_sign_raises_user_error_when_key_is_public(self):
        acme = _company('acme-key-sign-pub-1')
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        pub_row = CertificateKey.objects.create(
            name='pub-only', company=acme, content=pub_pem)
        with pytest.raises(UserError):
            pub_row._sign(b'x')

    def test_verify_raises_user_error_when_key_is_private(self):
        acme = _company('acme-key-verify-priv-1')
        priv_row = CertificateKey._generate_rsa_private_key(acme)
        with pytest.raises(UserError):
            priv_row._verify(b'x', b'firma-cualquiera')


class TestDecrypt:
    def test_rsa_decrypt_roundtrip_with_oaep(self):
        acme = _company('acme-key-decrypt-1')
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        priv_row = CertificateKey.objects.create(
            name='priv-decrypt', company=acme, content=priv_pem)

        ciphertext = private_key.public_key().encrypt(
            b'mensaje secreto',
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(), label=None,
            ),
        )
        assert priv_row._decrypt(ciphertext) == 'mensaje secreto'

    def test_decrypt_raises_on_public_key(self):
        acme = _company('acme-key-decrypt-2')
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        pub_row = CertificateKey.objects.create(
            name='pub-decrypt', company=acme, content=pub_pem)
        with pytest.raises(UserError):
            pub_row._decrypt(b'x')


class TestMeta:
    def test_str_returns_name(self):
        acme = _company('acme-key-str-1')
        key = CertificateKey.objects.create(
            name='mi-llave', company=acme,
            content=_rsa_private_pem()[1],
        )
        assert str(key) == 'mi-llave'

    def test_active_defaults_to_true(self):
        acme = _company('acme-key-active-1')
        key = CertificateKey.objects.create(
            name='k', company=acme, content=_rsa_private_pem()[1],
        )
        assert key.active is True

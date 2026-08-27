"""Tests — ``_get_auth_methods``, el catálogo de métodos con que un usuario
confirma su identidad.

Adaptación de ``test_user_auth_methods`` de
``odoo19c: auth_timeout/tests/test_auth_timeout.py:22-47``. Ahí el contrato es
una lista **ordenada**: passkey primero, luego el segundo factor (app o
correo), y la contraseña siempre al final. Ese orden es el que el diálogo de
confirmación usa para decidir qué ofrece primero, así que se afirma sobre la
lista completa, no sobre su pertenencia.

Divergencia de la fuente: allá los cuatro escalones se activan por
``res.config.settings``; aquí cada eslabón vive en su addon
(``authz_totp.totp_enabled``, ``authz_passkey`` con su M2M), así que el caso
los activa por su mecanismo real.

**El caso 5 es el control que exige el sub-patrón D de
``metrica-decide-la-conclusion.md``.** Los cuatro primeros afirman que la
lista *crece* al configurar cada método; un verde ahí no distingue «el método
se detecta» de «la lista siempre trae ese valor». El 5 retira el eslabón y
comprueba que el valor **cae** — sin él, un ``_get_auth_methods`` que
devolviera los cuatro siempre pasaría los cuatro primeros.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.authz_passkey.models.auth_passkey_key import PasskeyKey

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user(
        login='candado-metodos@practicayoruba.mx',
        password='CandadoPass123!',
        name='Candado Metodos',
    )


# === 1. Sin nada configurado: sólo la contraseña ========================

def test_only_password_by_default(user):
    """≙ la primera aserción de la fuente (``:24``)."""
    assert user._get_auth_methods() == ['password']


# === 2. Con TOTP de app: el segundo factor precede a la contraseña ======

def test_totp_precedes_password(user, monkeypatch):
    """≙ ``:34-35`` — el secreto TOTP añade ``'totp'`` **antes** de
    ``'password'``.

    ``_mfa_type`` lee ``totp_enabled``, que es la propiedad que
    ``authz_totp`` cuelga del usuario; el caso la fija en vez de sembrar el
    secreto porque lo que se mide aquí es el orden de la lista, no el alta
    del segundo factor (eso lo cubre ``tests/unit/authz_totp/``).
    """
    monkeypatch.setattr(type(user), 'totp_enabled', property(lambda self: True))
    assert user._get_auth_methods() == ['totp', 'password']


# === 3. Con passkey: WebAuthn encabeza ==================================

def test_passkey_heads_the_list(user):
    """≙ ``:38-46`` — la passkey añade ``'webauthn'`` en primera posición."""
    PasskeyKey.objects.create(
        name='llave-de-prueba',
        credential_identifier='cred-candado',
        public_key='clave-publica-de-prueba',
        user=user,
    )
    assert user._get_auth_methods() == ['webauthn', 'password']


# === 4. Los tres juntos, en el orden de la fuente =======================

def test_all_three_in_order(user, monkeypatch):
    """≙ ``:46`` — ``["webauthn", "totp", "password"]``."""
    monkeypatch.setattr(type(user), 'totp_enabled', property(lambda self: True))
    PasskeyKey.objects.create(
        name='llave-de-prueba',
        credential_identifier='cred-candado-3',
        public_key='clave-publica-de-prueba',
        user=user,
    )
    assert user._get_auth_methods() == ['webauthn', 'totp', 'password']


# === 5. Control: retirar el eslabón hace caer su valor ==================

def test_removing_the_passkey_drops_it_from_the_list(user):
    """El control que discrimina: sin este caso, los cuatro anteriores pasan
    igual con un ``_get_auth_methods`` que devolviera la lista completa
    siempre.

    Se mide con la passkey porque es el único eslabón con fila propia: se
    crea, se afirma presencia, se borra, y se afirma **ausencia** sobre el
    mismo usuario.
    """
    passkey = PasskeyKey.objects.create(
        name='llave-efimera',
        credential_identifier='cred-candado-control',
        public_key='clave-publica-de-prueba',
        user=user,
    )
    assert 'webauthn' in user._get_auth_methods()

    passkey.delete()
    assert user._get_auth_methods() == ['password']

"""Serializers del portal de cuenta — ``/my/*`` de la referencia.

Adaptación fiel de ``odoo19c: addons/portal/controllers/portal.py`` (LGPL-3
declarado en su ``__manifest__.py``, medido). La referencia sirve QWeb; aquí
el mismo contrato se expone como REST para el SPA. Lo que se conserva es la
**semántica**, no el transporte:

- el allowlist de campos editables sale de
  ``portal.models.res_partner.frontend_writable_fields()`` (≙
  ``_get_frontend_writable_fields``) — nunca un campo libre;
- el cambio de contraseña conserva los tres campos ``old``/``new1``/``new2``
  y sus tres errores (vacío · no coinciden · antigua incorrecta) de
  ``_update_password`` (``portal.py:891-913``);
- la baja de cuenta conserva la doble prueba de ``deactivate_account``
  (``portal.py:914-935``): ``validation`` debe igualar el *login*, y además
  la contraseña debe validar.
"""
from rest_framework import serializers

from addons.base.models.res_partner import ResPartner
from addons.portal.models.res_partner import frontend_writable_fields

#: Campos del allowlist de la referencia que existen en nuestro
#: ``res.partner``. La intersección se calcula, no se escribe a mano: el
#: allowlist es la única fuente y así no puede derivar del modelo.
#: ``state_id``/``country_id``/``zipcode`` son la grafía Odoo de campos que
#: aquí se llaman ``state``/``country``/``zip``; el mapa las traduce.
_SOURCE_FIELD_ALIASES = {
    'state_id': 'state',
    'country_id': 'country',
    'zipcode': 'zip',
}

_NOMBRES_DE_MODELO = {f.name for f in ResPartner._meta.get_fields()}

CAMPOS_EDITABLES = sorted(
    {
        _SOURCE_FIELD_ALIASES.get(nombre, nombre)
        for nombre in frontend_writable_fields()
    }
    & _NOMBRES_DE_MODELO
)


class PortalAddressSerializer(serializers.ModelSerializer):
    """Una dirección del usuario — ≙ una fila de ``/my/addresses``."""

    class Meta:
        model = ResPartner
        fields = ['id', 'name', 'type', 'street', 'street2', 'city', 'zip',
                  'state', 'country', 'phone', 'email', 'active']
        read_only_fields = ['id', 'active']


class PortalAccountSerializer(serializers.ModelSerializer):
    """El contacto del usuario — ≙ ``/my/account``.

    Sólo expone y acepta ``CAMPOS_EDITABLES``. Dos campos llevan además una
    guarda que depende del partner concreto (``can_edit_vat`` /
    ``can_edit_country``): vive en la **vista**, no aquí — ver el porqué en
    la nota de ``main.py`` sobre la forma del error.
    """

    class Meta:
        model = ResPartner
        fields = ['id'] + CAMPOS_EDITABLES
        read_only_fields = ['id']



class PasswordChangeSerializer(serializers.Serializer):
    """≙ los tres campos de ``_update_password`` (``portal.py:891-913``).

    Los nombres ``old``/``new1``/``new2`` se conservan verbatim: son el
    contrato de la referencia, y renombrarlos rompería la trazabilidad sin
    ganar nada. Las tres comprobaciones (vacío · no coinciden · antigua
    incorrecta) NO viven aquí: ``_update_password`` las **devuelve** como
    datos, no las lanza — ver ``PortalPasswordView``.
    """

    old = serializers.CharField(write_only=True, allow_blank=True)
    new1 = serializers.CharField(write_only=True, allow_blank=True)
    new2 = serializers.CharField(write_only=True, allow_blank=True)


class DeactivateAccountSerializer(serializers.Serializer):
    """≙ ``deactivate_account(validation, password)`` (``portal.py:914``).

    ``validation`` es el *login* escrito por el usuario: la referencia exige
    que coincida con el suyo **además** de la contraseña. Son dos pruebas
    distintas y las dos se conservan (la primera evita la baja por clic
    accidental; la segunda prueba la identidad).
    """

    validation = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

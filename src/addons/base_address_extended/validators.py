"""Validadores de campos de dirección MX — addons.base_address_extended.

Vivían en ``orders/serializers.py`` porque el primer consumidor fue el
formulario de checkout. No tienen nada que ver con una orden: validan el
**formato de dos campos de dirección/contacto mexicanos**, y ``users`` ya los
importaba desde ahí (``users/serializers.py:23``) — un addon de cuentas
dependiendo del addon de órdenes para validar un teléfono.

E5/R3 del retiro de ``orders`` (:ref:`analisis-retiro-addon-orders-e5`, clase
G5): el módulo se muda a su hogar por dominio.

**Fidelidad a la referencia — declarada, no supuesta.** El destilado de Odoo
(los 11 ``analisis-*odoo*.rst``) da **0 hits** para validación de teléfono, y
ningún addon del puerto la implementaba. Es decir: *la referencia no cubre esto
en el material disponible*, así que la elección de hogar es **nuestra**, no
derivada. Se elige ``base_address_extended`` porque es el addon de campos de
dirección y ambos validadores lo son; el patrón de archivo sigue a
``base_vat/validators.py`` y ``base_bank/validators.py`` (validador-función por
país). Si más adelante se monta la referencia y aparece un hogar distinto para
la validación de teléfono, mover estos dos símbolos es mecánico.

Reglas de formato (sin cambios respecto de ``orders/serializers.py``): el
teléfono es opcional pero, si viene, exactamente 10 dígitos. El C.P. es
requerido y debe tener exactamente 5 dígitos. Sin espacios, guiones ni prefijo
+52.
"""
import re

from rest_framework import serializers

_MX_PHONE_RE = re.compile(r'^\d{10}$')
_MX_ZIP_RE   = re.compile(r'^\d{5}$')


def validate_mx_phone(value):
    if value in (None, ''):
        return value
    if not _MX_PHONE_RE.match(value):
        raise serializers.ValidationError(
            'El teléfono debe tener exactamente 10 dígitos '
            '(sin espacios, guiones ni +52).'
        )
    return value


def validate_mx_zip(value):
    if not _MX_ZIP_RE.match(value or ''):
        raise serializers.ValidationError(
            'El código postal debe tener exactamente 5 dígitos.'
        )
    return value

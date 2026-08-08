"""AppConfig — addons.account_add_gln.

Fiel al addon ``account_add_gln`` de Odoo 19 (``odoo-tools@622ddc2a``,
``odoo19c: addons/account_add_gln/__manifest__.py``): agrega el Global
Location Number (GLN) al partner — usado en direcciones de entrega
(``type='delivery'``) para identificar ubicaciones de stock en las eInvoices
UBL/CII. La referencia lo declara ``auto_install: True`` con
``depends: ['account']``; aquí no hay auto-install (el registro en
``INSTALLED_APPS`` es explícito, ver nota abajo).

Cross-app ``_inherit`` de Odoo sobre ``res.partner`` (que aquí vive en
``base``) → RELATED OneToOne en Django (DEC-SALE-01, mismo criterio que
``base_address_extended``): Django no inyecta columnas cross-app sin migrar
la app dueña de la tabla, así que el GLN vive en ``PartnerGln`` con su propia
tabla — sin tocar ``base`` ni su migración.

**Fuera de este alcance** (el porte se restringió a
``src/addons/account_add_gln/`` — "no tocar ningún otro addon"): registrar
``addons.account_add_gln`` en ``INSTALLED_APPS``
(``config/settings/base.py``, después de ``addons.account`` — mismo orden que
la referencia declara con ``depends: ['account']``). Sin ese registro Django
no descubre esta app ni corre su migración inicial.
"""
from django.apps import AppConfig


class AccountAddGlnConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account_add_gln'
    label = 'account_add_gln'
    verbose_name = 'Contabilidad — Global Location Number del partner'

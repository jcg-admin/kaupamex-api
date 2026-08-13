"""AppConfig — ``addons.account_update_tax_tags``.

Fiel al addon ``account_update_tax_tags`` de Odoo 19 (``odoo-tools@622ddc2a``,
``odoo19c: addons/account_update_tax_tags/__manifest__.py``): recomputa las
casillas fiscales de asientos ya contabilizados tras un cambio de
configuración de impuestos. La referencia declara ``depends: ['account']``;
aquí no hay auto-install (registro explícito en ``INSTALLED_APPS``, ver la
nota de alcance abajo).

Sin ``ready()`` — a diferencia de ``account_debit_note``/``account_fleet``
================================================================================

Este addon no cuelga comportamiento sobre un modelo ajeno que ya exista
(no hay ningún ``_inherit`` de método): los tres modelos de ``models/`` son
datos NUEVOS con FK hacia ``account`` (mismo patrón ``DEC-SALE-01`` que
``account_debit_note.AccountMoveDebitNote``), y Django los descubre por
convención de ``models/`` sin necesitar ``importlib`` en ``ready()``. El
wizard (``TransientModel``, ``abstract = True``) tampoco necesita registro:
es una clase Python que otro código importa directamente, no un modelo
Django concreto.

**Fuera de este alcance** (el porte se restringió a
``src/addons/account_update_tax_tags/`` — "no tocar ningún otro addon"):
registrar ``addons.account_update_tax_tags`` en ``INSTALLED_APPS``
(``config/settings/base.py``, después de ``addons.account``). Sin ese
registro Django no descubre esta app ni corre su migración inicial. Mismo
límite ya declarado por ``account_debit_note/apps.py``.
"""
from django.apps import AppConfig


class AccountUpdateTaxTagsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account_update_tax_tags'
    label = 'account_update_tax_tags'
    verbose_name = 'Contabilidad — Actualizar casillas fiscales'

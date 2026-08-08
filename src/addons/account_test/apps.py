"""AppConfig — ``addons.account_test``.

Fiel al addon ``account_test`` de Odoo 19 (``odoo-tools@622ddc2a``,
``odoo19c: addons/account_test/__manifest__.py``): pruebas manuales de
consistencia contable ejecutadas bajo demanda. La referencia declara
``depends: ['account']``; aquí no hay auto-install (registro explícito en
``INSTALLED_APPS``, ver la nota de alcance abajo).

Sin ``_inherit`` sobre modelos ajenos
========================================

A diferencia de ``account_debit_note``/``account_qr_code_sepa``/``l10n_mx``,
``account_test`` **no** cuelga comportamiento de ``account.AccountMove`` ni de
ningún otro modelo compartido — su único modelo (``AccountingAssertTest``) es
propio, y ``reconciled_inv()``/los datos semilla sólo **leen** (consultas
ORM/SQL), nunca escriben en la clase de otro addon. Por eso este ``AppConfig``
no necesita ``ready()``: no hay nada que colgar vía ``chain_method``/
``setattr`` — Django descubre el modelo por convención (``models/``).

Fuera de este alcance
========================

El porte se restringió a ``src/addons/account_test/`` ("no tocar ningún otro
addon"), así que quedan **pendientes de wiring** (mismo criterio que
``account_debit_note``/``account_qr_code_sepa``):

- registrar ``addons.account_test`` en ``INSTALLED_APPS``
  (``config/settings/base.py``);
- incluir ``addons.account_test.controllers.urls`` en ``config/urls.py``
  (bajo, p. ej., ``api/v2/admin/finance/``).

Sin esos dos registros Django no descubre esta app ni corre su migración
inicial, y el endpoint no es alcanzable — el modelo/controlador/seed sí
existen y son autocontenidos.
"""
from django.apps import AppConfig


class AccountTestConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account_test'
    label = 'account_test'
    verbose_name = 'Contabilidad — Pruebas de consistencia'

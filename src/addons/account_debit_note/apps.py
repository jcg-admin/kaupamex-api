"""AppConfig — ``addons.account_debit_note``.

Fiel al addon ``account_debit_note`` de Odoo 19 (``odoo-tools@622ddc2a``,
``odoo19c: addons/account_debit_note/__manifest__.py``): agrega la nota de
débito — el opuesto de una nota de crédito, con el vínculo a la factura
original. La referencia declara ``depends: ['account']``; aquí no hay
auto-install (registro explícito en ``INSTALLED_APPS``, ver la nota de
alcance abajo).

Cross-app ``_inherit`` sobre ``account.move``/``account.journal`` (que aquí
viven en ``account``, NO en este addon) → dos mecanismos distintos, según si
lo que se cuelga es DATO o COMPORTAMIENTO ya existente (DEC-SALE-01 cubre
sólo el primero):

- **Dato nuevo** (``debit_sequence`` de ``account.journal``; el vínculo
  ``debit_origin_id``/``debit_note_ids`` de ``account.move``) → modelo
  RELATED con OneToOne/FK, mismo criterio que ``account_add_gln.PartnerGln``.
  Se declara normal, en ``models/__init__.py`` — no necesita ``ready()``.
- **Comportamiento que YA existe y hay que extender** (``get_starting_
  sequence``/``get_last_sequence_domain`` de ``AccountMove``, definidos en
  ``account/models/account_move.py``) → el patrón ``setattr(Modelo, nombre,
  funcion)`` que este árbol ya usa (``account/models/res_company.py``,
  ``l10n_mx``, ``account_qr_code_sepa``) sirve para AÑADIR un método que no
  existe (``if not hasattr(...)``); aquí el método SÍ existe y hay que
  encadenarlo, no reemplazarlo — ver el docstring de
  ``models/account_move_sequence.py`` para el mecanismo exacto y por qué va
  en un archivo aparte, importado sólo desde ``ready()``.

**Fuera de este alcance** (el porte se restringió a
``src/addons/account_debit_note/`` — "no tocar ningún otro addon"): registrar
``addons.account_debit_note`` en ``INSTALLED_APPS``
(``config/settings/base.py``, después de ``addons.account``). Sin ese
registro Django no descubre esta app ni corre su migración inicial.
"""
import importlib

from django.apps import AppConfig


class AccountDebitNoteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account_debit_note'
    label = 'account_debit_note'
    verbose_name = 'Contabilidad — Notas de débito'

    def ready(self):
        """Cuelga los dos ganchos de numeración sobre ``AccountMove``.

        ``importlib.import_module`` y no un ``import`` al top porque en
        tiempo de import de este módulo el registro de apps aún no está
        poblado (``AppRegistryNotReady``) — excepción #4 de
        ``no-lazy-imports``: una llamada de función, no un statement
        ``import``. Mismo patrón que ``AccountConfig.ready()`` /
        ``L10nMxConfig.ready()``.
        """
        importlib.import_module(
            'addons.account_debit_note.models.account_move_sequence'
        ).apply_account_debit_note_extensions()

r"""``account.edi.format`` — el registro de formatos EDI (Odoo
``account_edi``).

Adaptación de ``addons/account_edi/models/account_edi_format.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:``,
LGPL-3, 128 líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

Modelo base, pensado para ser extendido por ``l10n_*_edi``
================================================================

La referencia lo describe en el docstring de sus métodos: cada formato
concreto (PEPPOL, factura-e, CFDI, …) es una fila creada por un addon
``l10n_*_edi`` que **sobreescribe** los métodos de esta clase base. Ningún
``l10n_*_edi`` está portado en este árbol (medido: ``grep -rl
"account.edi.format" addons/*/models/*.py`` sólo devuelve este addon), así
que hoy la tabla existe pero permanece vacía en producción — igual que en la
referencia antes de instalar un formato de país concreto.

Once símbolos (2 campos + 9 métodos) — 10 portados, 1 bloqueado
====================================================================

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Símbolo
     - Estado
     - Nota
   * - ``name`` / ``code`` (campos)
     - portados
     - ``_unique_code`` → ``Meta.constraints``
       (``atributos-de-clase-de-modelo.md``)
   * - ``create`` (override)
     - portado
     - recalcula los diarios al crear formatos y activa el cron si un formato
       necesita web-service
   * - ``_register_hook``
     - **bloqueado**
     - hook de ciclo de vida de instalación de módulo Odoo; sin equivalente
       (Django no tiene un paso post-migrate por app con esta semántica)
   * - ``_get_move_applicability``
     - portado
     - terminal — devuelve ``None``; lo sobreescribe el ``l10n_*_edi`` concreto
   * - ``_needs_web_services``
     - portado
     - terminal — ``False``
   * - ``_is_compatible_with_journal``
     - portado
     - terminal — ``journal.type == 'sale'``
   * - ``_is_enabled_by_default_on_journal``
     - portado
     - terminal — ``True``
   * - ``_check_move_configuration``
     - portado
     - terminal — ``[]``
   * - ``_prepare_invoice_report``
     - portado
     - terminal — no-op
   * - ``_format_error_message``
     - portado
     - HTML de lista de errores; ``html_escape`` → ``django.utils.html.escape``

``create`` — recalcula los diarios
==================================

≙ ``create``
(``odoo19c: addons/account_edi/models/account_edi_format.py:24-44``): tras
crear formatos, recalcula ``edi_format_ids`` de todos los diarios para que
el formato nuevo aparezca donde corresponda (paso (a) de la fuente). La versión
anterior lo declaraba bloqueado por un import circular entre este módulo y
``account_journal.py``; la fuente no importa la clase, la pide al entorno
(``self.env['account.journal']``), y aquí igual.

El paso (b), activar el cron ``account_edi.ir_cron_edi_network`` si un
formato necesita web-service (``:40-42``), escribe sobre el cron que siembra
la migración ``0007_seed_cron_edi_network``. La rama ``self.pool.loaded`` /
``_delay_compute_edi_format_ids`` es la carga diferida del registro de la
fuente; aquí el registro de Django está completo antes del primer ``create``.
"""
import api
import fields
import models
from django.utils.html import escape as html_escape


class AccountEdiFormat(models.BaseModel):
    """``account.edi.format`` — un formato de facturación electrónica.

    Fila vacía de comportamiento hasta que un ``l10n_*_edi`` concreto
    sobreescriba sus cinco métodos "TO OVERRIDE" (ver el docstring del
    módulo). La relación con los diarios la declara el diario
    (``edi_format_ids``, ``account_journal.py`` de este addon), como en la
    fuente: el formato no lleva inverso.
    """

    _name = 'account.edi.format'
    _description = 'EDI format'

    name = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Nombre visible del formato (Odoo name).',
    )
    code = fields.Char(
        max_length=64,
        help_text='Código técnico único del formato (Odoo code, requerido).',
    )

    class Meta:
        db_table = 'account_edi_format'
        verbose_name = 'Formato EDI'
        verbose_name_plural = 'Formatos EDI'
        constraints = [
            # ≙ ``_unique_code`` (``odoo19c: account_edi_format.py:14-17``).
            models.UniqueConstraint(
                fields=['code'], name='uniq_edi_format_code'),
        ]

    def __str__(self) -> str:
        return self.name or self.code

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create``, paso (a): recalcula los diarios.

        ``odoo19c: addons/account_edi/models/account_edi_format.py:24-44``
        """
        edi_formats = super().create(vals_list)
        if not edi_formats:
            return edi_formats
        journals = edi_formats.env['account.journal'].search([])
        journals._compute_edi_format_ids()
        # Paso (b) (``odoo19c: addons/account_edi/models/
        # account_edi_format.py:40-42``): activar el cron.
        if any(edi_format._needs_web_services()
               for edi_format in edi_formats):
            # ``ir.cron`` es un modelo de Django: la asignación de la fuente
            # es aquí un ``write``.
            edi_formats.env.ref('account_edi.ir_cron_edi_network').write(
                {'active': True})
        return edi_formats

    ####################################################
    # Export method to override based on EDI Format
    ####################################################

    def _get_move_applicability(self, move):
        """≙ ``_get_move_applicability`` (``odoo19c: :57-67``, terminal —
        sobreescribir). Devuelve ``None``: sin formato concreto instalado,
        nada es aplicable a ningún asiento."""
        return None

    def _needs_web_services(self):
        """≙ ``_needs_web_services`` (``odoo19c: :69-74``, terminal)."""
        return False

    def _is_compatible_with_journal(self, journal):
        """≙ ``_is_compatible_with_journal`` (``odoo19c: :76-84``, terminal —
        sobreescribir). Compatible con diarios de venta por defecto."""
        return journal.type == 'sale'

    def _is_enabled_by_default_on_journal(self, journal):
        """≙ ``_is_enabled_by_default_on_journal`` (``odoo19c: :86-92``,
        terminal — sobreescribir)."""
        return True

    def _check_move_configuration(self, move):
        """≙ ``_check_move_configuration`` (``odoo19c: :94-100``, terminal —
        sobreescribir). Sin errores por defecto."""
        return []

    ####################################################
    # Import methods to override based on EDI Format
    ####################################################

    def _prepare_invoice_report(self, pdf_writer, edi_document):
        """≙ ``_prepare_invoice_report`` (``odoo19c: :103-109``, terminal —
        sobreescribir). No-op: el formato base no embebe nada en el PDF."""
        return None

    ####################################################
    # Other helpers
    ####################################################

    @classmethod
    def _format_error_message(cls, error_title, errors):
        """≙ ``_format_error_message`` (``odoo19c: :113-115``).

        ``html_escape`` de la referencia (``odoo.tools``) → ``django.utils.
        html.escape`` — mismo contrato: escapa entidades HTML.
        """
        bullet_list_msg = ''.join(
            f'<li>{html_escape(msg)}</li>' for msg in errors)
        return f'{error_title}<ul>{bullet_list_msg}</ul>'


def apply_account_edi_extensions():
    """No aplica — ``AccountEdiFormat`` es un modelo NUEVO (``_name``, no
    ``_inherit``), no cuelga sobre otro addon. Se define por uniformidad con
    el resto de ``_EXTENSIONS`` de ``AccountEdiConfig.ready()`` (mismo
    criterio que ``account/models/account_document_import_mixin.py``)."""
    return None

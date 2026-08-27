r"""``account.edi.format`` — el registro de formatos EDI (Odoo ``account_edi``).

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
     - ``_unique_code`` → ``Meta.constraints`` (``atributos-de-clase-de-modelo.md``)
   * - ``create`` (override)
     - **divergencia de mecanismo**
     - disponible como llamada explícita, no side-effect de ``save()`` (ver
       abajo)
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

``create`` — bloqueado como efecto automático; disponible como llamada explícita
====================================================================================

La referencia, al crear un formato, (a) recalcula ``edi_format_ids`` de todos
los diarios existentes para que el nuevo formato aparezca donde corresponda, y
(b) activa el cron ``account_edi.ir_cron_edi_network`` si algún formato creado
necesita web-service.

Ninguna de las dos se cuelga de ``save()`` aquí — **divergencia de mecanismo
declarada, no omisión**: ``account_journal.py`` (extensión de
``account.journal`` en este mismo addon) necesita importar
``AccountEdiFormat`` para computar ``edi_format_ids``/``compatible_edi_ids``;
si este archivo importara ``AccountJournal`` de vuelta al tope, sería un
import circular real entre dos módulos del mismo addon. La recomputación
(a) sigue disponible, pero como llamada **explícita** —
``account_journal.compute_edi_format_ids(journal)``, exportada desde
``account_journal.py``— que se invoca donde haga falta, en vez de un
side-effect automático de ``create``. (b) queda bloqueado por completo: el
cron no existe — sembrarlo exige una migración de datos (``sembrar_cron``,
patrón de ``mail/migrations/0004_seed_cron_email_queue.py``) y este agente NO
crea migraciones (``makemigrations`` es del orquestador).

La rama ``self.pool.loaded`` / ``self.pool._delay_compute_edi_format_ids`` de
la referencia es maquinaria de carga de registro de Odoo (``Registry.loaded``,
poblado a mitad de arranque) — Django no tiene ese concepto (las apps ya están
100% registradas cuando el primer ``ready()`` corre); se omite sin sustituto.
"""
import fields
import models
from django.utils.html import escape as html_escape


class AccountEdiFormat(models.Model):
    """``account.edi.format`` — un formato de facturación electrónica.

    Fila vacía de comportamiento hasta que un ``l10n_*_edi`` concreto
    sobreescriba sus cinco métodos "TO OVERRIDE" (ver el docstring del
    módulo). ``journals`` es el M2M inverso de ``account.journal.
    edi_format_ids`` (``odoo19c: account_edi/models/account_journal.py:12``,
    ``compute='_compute_edi_format_ids', store=True``) — se declara **aquí**,
    no en ``account/models/account_journal.py`` (fuera del write-set de este
    agente): ``related_name`` en el lado ``Many2many`` crea el accesor
    inverso sin tocar el archivo ajeno, mismo idioma que
    ``account/models/account_journal_group.py::excluded_journals``.
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
    #: ≙ ``account.journal.edi_format_ids`` (M2M inverso) — ver el docstring
    #: de la clase para por qué vive aquí y no en ``account_journal.py``.
    journals = fields.Many2many(
        'account.AccountJournal', blank=True,
        related_name='edi_format_ids',
        help_text='Diarios donde este formato está activo (Odoo journal_id, '
                  'lado inverso de journal.edi_format_ids).',
    )

    class Meta:
        db_table = 'account_edi_format'
        verbose_name = 'Formato EDI'
        verbose_name_plural = 'Formatos EDI'
        constraints = [
            # ≙ ``_unique_code`` (``odoo19c: account_edi_format.py:14-17``).
            models.UniqueConstraint(fields=['code'], name='uniq_edi_format_code'),
        ]

    def __str__(self) -> str:
        return self.name or self.code

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
        bullet_list_msg = ''.join(f'<li>{html_escape(msg)}</li>' for msg in errors)
        return f'{error_title}<ul>{bullet_list_msg}</ul>'


def apply_account_edi_extensions():
    """No aplica — ``AccountEdiFormat`` es un modelo NUEVO (``_name``, no
    ``_inherit``), no cuelga sobre otro addon. Se define por uniformidad con
    el resto de ``_EXTENSIONS`` de ``AccountEdiConfig.ready()`` (mismo
    criterio que ``account/models/account_document_import_mixin.py``)."""
    return None

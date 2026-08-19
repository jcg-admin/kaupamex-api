"""``account.move.send.batch.wizard`` — envío de facturas en lote.

Adaptación de Odoo ``addons/account/wizard/account_move_send_batch_wizard.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla — mismo patrón que
``AccountDebitNoteWizard``.

Bloqueado por ``account.move.send`` (en porte paralelo)
========================================================

La referencia declara ``_inherit = ['account.move.send']`` — el mixin de
envío que otro agente está portando EN PARALELO en
``models/account_move_send.py`` (por directiva del orquestador este archivo
NO lo lee ni lo importa). El atributo ``_inherit`` se declara verbatim; el
wiring de la herencia (componer este wizard sobre el mixin) es del
orquestador al consolidar. Los métodos que delegan en el mixin se definen
con la llamada verbatim (``cls._get_alerts(...)`` etc.): compilan hoy, y
resuelven en cuanto el mixin quede compuesto — hasta entonces fallan en voz
alta (``AttributeError``), no en silencio.

Ocho símbolos de la referencia (3 campos + 5 defs) — el desglose
=================================================================

===============================  ==========================================
Símbolo de la referencia          Qué pasa aquí
===============================  ==========================================
``move_ids`` (campo)              PORTADO — parámetro ``moves``
``summary_data`` (compute)        PORTADO — retorno de
                                   ``_compute_summary_data`` (delegación al
                                   mixin, bloqueada — arriba)
``alerts`` (compute)              PORTADO — ídem ``_compute_alerts``
``default_get``                   PORTADO
``_compute_summary_data``         PORTADO (parcial declarado — el catálogo
                                   de métodos de envío sale del selection
                                   de ``res.partner.invoice_sending_method``
                                   en la referencia; ese campo no está
                                   portado, así que las etiquetas las
                                   provee ``_get_all_extra_edis`` /
                                   ``_get_default_sending_methods`` del
                                   mixin en paralelo)
``_compute_alerts``               PORTADO (delegación, bloqueada — arriba)
``_check_move_ids_constraints``   PORTADO (delegación, bloqueada — arriba)
``action_send_and_print``         PORTADO (parcial declarado, ver su
                                   docstring)
===============================  ==========================================
"""
from collections import Counter

from addons.account.models.account_move import AccountMove
from exceptions import UserError
from orm.models_transient import TransientModel
from tools.translate import _


class AccountMoveSendBatchWizard(TransientModel):
    """Wizard that handles the sending of multiple invoices.

    (Docstring verbatim de la referencia.) ≙ ``account.move.send.batch.wizard``.
    """

    _name = 'account.move.send.batch.wizard'
    _inherit = ['account.move.send']
    _description = "Account Move Send Batch Wizard"

    class Meta:
        abstract = True
        managed = False

    # -------------------------------------------------------------------------
    # DEFAULTS
    # -------------------------------------------------------------------------

    @classmethod
    def default_get(cls, move_ids):
        """≙ ``default_get`` — los asientos activos son el lote a enviar."""
        return list(AccountMove.objects.filter(pk__in=list(move_ids)))

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------

    @classmethod
    def _compute_summary_data(cls, moves):
        """≙ ``_compute_summary_data`` — cuántos asientos van por cada método
        de envío / EDI extra. Delegación al mixin en porte paralelo (ver el
        docstring del módulo)."""
        extra_edis = cls._get_all_extra_edis()
        edi_counter = Counter()
        sending_method_counter = Counter()
        for move in moves:
            edi_counter += Counter(cls._get_default_extra_edis(move))
            sending_settings = cls._get_default_sending_settings(move)
            sending_method_counter += Counter([
                sending_method
                for sending_method in cls._get_default_sending_methods(move)
                if cls._is_applicable_to_move(sending_method, move,
                                              **sending_settings)
            ])

        summary_data = {}
        for edi, edi_count in edi_counter.items():
            summary_data[edi] = {
                'count': edi_count,
                'label': _('by %s') % extra_edis[edi]['label'],
            }
        for sending_method, count in sending_method_counter.items():
            summary_data[sending_method] = {
                'count': count,
                'label': sending_method if sending_method != 'manual'
                         else _('Manually'),
            }
        return summary_data

    @classmethod
    def _compute_alerts(cls, moves):
        """≙ ``_compute_alerts`` — delegación al mixin en porte paralelo."""
        moves_data = {move: cls._get_default_sending_settings(move)
                      for move in moves}
        return cls._get_alerts(moves, moves_data)

    # -------------------------------------------------------------------------
    # CONSTRAINS
    # -------------------------------------------------------------------------

    @classmethod
    def _check_move_ids_constraints(cls, moves):
        """≙ ``_check_move_ids_constraints`` — delegación al mixin en porte
        paralelo."""
        return cls._check_move_constraints(moves)

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------

    @classmethod
    def action_send_and_print(cls, moves, force_synchronous=False,
                               allow_fallback_pdf=False):
        """ Launch asynchronously the generation and sending of invoices.

        (Docstring verbatim de la referencia.) Parcial declarado:

        - La generación misma delega en
          ``_generate_and_send_invoices`` del mixin en porte paralelo.
        - La rama asíncrona de la referencia arma el envío sobre el cron
          ``account.ir_cron_account_move_send`` + ``move.sending_data`` —
          el cron por xmlid y ese campo Json no están portados; aquí TODO
          envío es síncrono (``force_synchronous`` se acepta por paridad de
          firma). El ``RedirectWarning`` a la config del cron y el
          ``display_notification`` son navegación del cliente Odoo (misma
          exclusión que ``AccountDebitNoteWizard``).
        """
        alerts = cls._compute_alerts(moves)
        if alerts:
            cls._raise_danger_alerts(alerts)
        if not force_synchronous:
            raise UserError(_(
                'El envío en lote asíncrono (cron '
                'account.ir_cron_account_move_send) no está portado — '
                'usa force_synchronous=True.'))
        return cls._generate_and_send_invoices(
            moves, allow_fallback_pdf=allow_fallback_pdf)

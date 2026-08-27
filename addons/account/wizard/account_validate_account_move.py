"""``validate.account.move`` — el asistente "Publicar asientos" en lote.

Adaptación de Odoo ``addons/account/wizard/account_validate_account_move.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla — mismo patrón que
``AccountDebitNoteWizard``: el estado del wizard (qué asientos, qué flags)
lo pasa el llamador como argumentos.

Diecisiete símbolos de la referencia (10 campos + 7 defs) — el desglose
========================================================================

===================================  ======================================
Símbolo de la referencia              Qué pasa aquí
===================================  ======================================
``move_ids`` (campo)                  PORTADO — parámetro ``moves``
``force_post`` (campo)                PORTADO — parámetro ``force_post``
``force_hash`` (campo)                PORTADO — parámetro ``force_hash``
``ignore_abnormal_date`` (campo)      NO — checkbox del diálogo; su consumo
                                       (``validate_move``) está bloqueado
                                       (ver abajo).
``ignore_abnormal_amount`` (campo)    NO — ídem.
``display_force_post`` (compute)      PORTADO — ``_compute_display_force_post``
``display_force_hash`` (compute)      NO — lee
                                       ``move.restrict_mode_hash_table``
                                       (candado de hash del diario), campo
                                       no portado. Bloqueado por el
                                       mecanismo de hash inalterable.
``is_entries`` (compute)              PORTADO — ``_compute_is_entries``
``abnormal_date_partner_ids``         NO — lee ``move.abnormal_date_warning``
(compute)                              (heurística de fechas atípicas por
                                       partner, ``odoo19c: account_move.py``),
                                       no portada. Bloqueado por esa
                                       heurística.
``abnormal_amount_partner_ids``       NO — ídem con
(compute)                              ``abnormal_amount_warning``.
``_compute_display_force_post``       PORTADO
``_compute_display_force_hash``       NO — ver ``display_force_hash``.
``_compute_is_entries``               PORTADO
``_compute_abnormal_date_partner_ids``   NO — ver arriba.
``_compute_abnormal_amount_partner_ids`` NO — ver arriba.
``default_get``                       PORTADO — ``default_get`` (la parte
                                       con lógica real: la selección de
                                       borradores y sus dos ``UserError``;
                                       la lectura de ``active_model`` /
                                       ``active_ids`` es mecánica del
                                       cliente web de Odoo — el llamador
                                       pasa ``moves`` o ``journal``).
``validate_move``                     PORTADO (parcial declarado, ver su
                                       docstring)
===================================  ======================================

Divergencias declaradas en ``validate_move``
=============================================

- ``self.move_ids.auto_post = 'no'`` (rama ``force_post``): ``auto_post``
  no está en el puerto de ``account.move`` (la publicación diferida a
  fecha futura vive en ``ir.cron`` de la referencia, mecanismo no portado).
  La semántica efectiva se conserva: aquí TODO post es inmediato, así que
  ``force_post`` sólo levanta el guard de fechas futuras.
- ``moves_to_post._post(not self.force_post)``: el puerto expone ``post()``
  sin el parámetro ``soft`` — la publicación suave (diferir los futuros)
  depende de ``auto_post`` (arriba). Sin ``force_post``, un asiento con
  fecha futura levanta ``UserError`` en vez de diferirse: falla en voz
  alta, no difiere en silencio.
- ``moves_to_post._show_autopost_bills_wizard()``: método de
  ``account.move`` no portado (su wizard sí — ver
  ``account_autopost_bills_wizard.py``, bloqueado por
  ``res_partner.autopost_bills``). El retorno de acciones de ventana
  (``ir.actions.act_window_close``) es navegación del cliente Odoo, fuera
  de alcance — misma exclusión que ``AccountDebitNoteWizard``.
"""
from django.utils import timezone

from addons.account.models.account_move import AccountMove
from exceptions import UserError
from orm.models_transient import TransientModel
from tools.translate import _


class ValidateAccountMove(TransientModel):
    """≙ ``validate.account.move`` — publica en lote los borradores
    seleccionados (o todos los de un diario)."""

    _name = 'validate.account.move'
    _description = "Validate Account Move"

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def default_get(cls, moves=None, journal=None):
        """La selección de borradores — ≙ el cuerpo real de ``default_get``.

        La referencia decide por ``active_model`` (asientos seleccionados o
        el diario entero); aquí el llamador pasa ``moves`` **o** ``journal``.
        Conserva sus dos ``UserError`` y el filtro ``filtered('line_ids')``
        (un borrador sin apuntes no se publica).
        """
        if moves is not None:
            queryset = AccountMove.objects.filter(
                pk__in=[m.pk for m in moves], state='draft')
        elif journal is not None:
            queryset = AccountMove.objects.filter(
                journal=journal, state='draft')
        else:
            raise UserError(_("Missing 'active_model' in context."))

        selected = [move for move in queryset if move.line_ids.exists()]
        if not selected:
            raise UserError(_(
                'There are no journal items in the draft state to post.'))
        return selected

    @classmethod
    def _compute_display_force_post(cls, moves):
        """¿Hay asientos con fecha futura? — ≙ ``_compute_display_force_post``.

        La referencia mira ``m.date or m.invoice_date or today``;
        ``invoice_date`` no está portado en ``account.move``, así que el
        fallback intermedio se omite (divergencia declarada — un asiento sin
        ``date`` cae directo a ``today``, mismo desenlace).
        """
        today = timezone.now().date()
        return [move for move in moves if (move.date or today) > today]

    @classmethod
    def _compute_is_entries(cls, moves):
        """¿Alguno es asiento manual? — ≙ ``_compute_is_entries``."""
        return any(move.move_type == 'entry' for move in moves)

    @classmethod
    def validate_move(cls, moves, force_post=False, force_hash=False):
        """Publica los asientos — ≙ ``validate_move`` (parcial declarado,
        ver el docstring del módulo).

        ``force_hash`` se acepta por paridad de firma; sin el mecanismo de
        hash inalterable no hay asientos que excluir, así que el filtro
        ``filtered(lambda m: not m.restrict_mode_hash_table)`` es la
        identidad (divergencia declarada).
        """
        if not force_post:
            future_moves = cls._compute_display_force_post(moves)
            if future_moves:
                raise UserError(_(
                    'Hay asientos con fecha futura. Usa "Forzar" para '
                    'publicarlos ahora (la publicación diferida auto_post '
                    'no está portada).'))
        posted = []
        for move in moves:
            move.post()
            posted.append(move)
        return posted

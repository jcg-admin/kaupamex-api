"""``account.secure.entries.wizard`` — asegurar (hashear) asientos hasta una fecha.

Adaptación de Odoo ``addons/account/wizard/account_secure_entries_wizard.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla — mismo patrón que
``AccountDebitNoteWizard``.

Bloqueado por el mecanismo de hash inalterable (la mayor parte del archivo)
============================================================================

Este wizard es la puerta de entrada al **hash encadenado** de asientos:
``account.move.inalterable_hash``, ``_hash_moves``, ``_get_chain_info`` y
``restrict_mode_hash_table`` (``odoo19c: account_move.py`` /
``account_journal.py``). Ninguna de esas piezas está en el puerto (medido:
``grep -rn "inalterable_hash\\|_hash_moves\\|_get_chain_info"
addons/account/models/`` → 0 hits). No es una divergencia de mecanismo: es
la pieza central ausente, y este archivo no la reconstruye — el hash
encadenado es un subsistema propio (campo + cadena por diario/prefijo +
verificación), no un helper de wizard.

Diecinueve símbolos de la referencia (9 campos + 10 defs) — el desglose
========================================================================

=========================================  ================================
Símbolo de la referencia                    Qué pasa aquí
=========================================  ================================
``company_id`` (campo)                      PORTADO — parámetro ``company``
``country_code`` (related)                  NO — visibilidad por país del
                                             formulario, sin lector.
``hash_date`` (campo)                       PORTADO — parámetro/compute
``chains_to_hash_with_gaps`` (compute)      NO — ``_get_chain_info``
``max_hash_date`` (compute)                 NO — ``_get_chains_to_hash``
``unreconciled_bank_statement_line_ids``    NO — ``_get_chain_info`` +
(compute)                                    ``is_reconciled`` de la línea
                                             de extracto.
``not_hashable_unlocked_move_ids``          NO — ``inalterable_hash``.
``move_to_hash_ids`` (compute)              NO — ``_get_chain_info``.
``warnings`` (compute)                      NO — compone los cinco avisos
                                             sobre los computes bloqueados
                                             de arriba.
``_compute_hash_date``                      PORTADO
``_compute_max_hash_date``                  NO — bloqueado (arriba).
``_get_chains_to_hash``                     NO — bloqueado (arriba).
``_compute_data``                           NO — bloqueado (arriba).
``_compute_warnings``                       NO — bloqueado (arriba).
``_get_unhashed_moves_in_hashed_period_domain``  PORTADO (parcial
                                             declarado, ver su docstring)
``_get_draft_moves_in_hashed_period_domain``     PORTADO
``action_show_moves``                       NO — devuelve un
                                             ``ir.actions.act_window``
                                             (navegación del cliente Odoo,
                                             misma exclusión que
                                             ``AccountDebitNoteWizard``).
``action_show_draft_moves_in_hashed_period``     NO — ídem.
``action_secure_entries``                   PORTADO (guard + delegación;
                                             la delegación misma falla en
                                             voz alta mientras
                                             ``_hash_moves`` no exista)
=========================================  ================================

Sucesor: el subsistema de hash inalterable entero (campo + cadena +
verificación) es alcance de una iniciativa propia — al aterrizar, los NO de
esta tabla se convierten en portes directos sin cambiar la firma de nada de
lo ya escrito aquí.
"""
from django.utils import timezone

from addons.account.models.account_move import AccountMove
from exceptions import UserError
from orm.models_transient import TransientModel
from tools.translate import _


class AccountSecureEntriesWizard(TransientModel):
    """
    This wizard is used to secure journal entries (with a hash)

    (Docstring verbatim de la referencia.) ≙ ``account.secure.entries.wizard``.
    """

    _name = 'account.secure.entries.wizard'
    _description = 'Secure Journal Entries'

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def _compute_hash_date(cls, hash_date=None, max_hash_date=None):
        """≙ ``_compute_hash_date`` — el default de la fecha: la máxima ya
        asegurada, o hoy. ``max_hash_date`` lo pasa el llamador porque su
        compute está bloqueado (ver el docstring del módulo)."""
        if hash_date:
            return hash_date
        return max_hash_date or timezone.now().date()

    @classmethod
    def _get_unhashed_moves_in_hashed_period_domain(cls, company, hash_date,
                                                     extra_filters=None):
        """
        Return the domain to find all moves before `self.hash_date` that have not been hashed yet.
        We ignore whether hashing is activated for the journal or not.
        :return a search domain

        (Docstring verbatim de la referencia.) Aquí devuelve un queryset de
        ``AccountMove`` en vez de un domain — parcial declarado: el filtro
        ``('inalterable_hash', '=', False)`` está bloqueado por el campo
        (ver el docstring del módulo), así que el conjunto devuelto es un
        **superconjunto** del de la referencia (todos los asientos del
        periodo, no sólo los sin hash). El ``child_of`` de empresa se toma
        como igualdad — el árbol de empresas hijas se filtra donde el
        llamador lo necesite.
        """
        if not (company and hash_date):
            return AccountMove.objects.none()
        queryset = AccountMove.objects.filter(
            date__lte=hash_date, company=company)
        if extra_filters:
            queryset = queryset.filter(**extra_filters)
        return queryset

    @classmethod
    def _get_draft_moves_in_hashed_period_domain(cls, company, hash_date):
        """≙ ``_get_draft_moves_in_hashed_period_domain`` — los borradores
        del periodo a asegurar."""
        return cls._get_unhashed_moves_in_hashed_period_domain(
            company, hash_date, {'state': 'draft'})

    @classmethod
    def action_secure_entries(cls, company, hash_date, moves_to_hash=None):
        """≙ ``action_secure_entries`` — el guard de fecha se porta; la
        delegación final (``moves._hash_moves(force_hash=True,
        raise_if_gap=False)``) está bloqueada por el mecanismo de hash
        (ver el docstring del módulo) y falla en voz alta."""
        if not hash_date:
            raise UserError(_(
                'Set a date. The moves will be secured up to including '
                'this date.'))
        if not moves_to_hash:
            return None
        raise UserError(_(
            'El hash inalterable de asientos no está portado todavía '
            '(account.move._hash_moves) — ver el docstring de este wizard.'))

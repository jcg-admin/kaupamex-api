"""``account.debit.note`` — el asistente "Crear nota de débito".

Adaptación de ``odoo19c: addons/account_debit_note/wizard/
account_debit_note.py`` (``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``,
LGPL-3 — atribución y aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla
==========================================================

La referencia es ``models.TransientModel``: "formulario, no tabla" — mismo
criterio ya fijado por ``base_setup.ResConfigSettings`` (ver su docstring) y
``base.BaseEnableProfilingWizard``, del que este archivo copia el patrón
exacto: ``class Meta: abstract = True; managed = False`` + classmethods. El
estado del wizard (qué movimientos, qué fecha, qué razón) no vive en una
fila — lo pasa el llamador como parámetros, igual que
``BaseEnableProfilingWizard.submit(duration)`` recibe su único dato por
parámetro en vez de leerlo de una instancia guardada.

Trece símbolos de la referencia — ocho se portan, cinco no (medido)
========================================================================

===========================  ==========================================
Símbolo de la referencia      Qué pasa aquí
===========================  ==========================================
``move_ids`` (campo)          PORTADO — parámetro ``moves``
``date`` (campo)              PORTADO — parámetro ``date``
``reason`` (campo)            PORTADO — parámetro ``reason``
``journal_id`` (campo)        PORTADO — parámetro ``journal``
``copy_lines`` (campo)        PORTADO — parámetro ``copy_lines``
``default_get``               PORTADO — ``validate_moves()``
``_prepare_default_values``   PORTADO — ``prepare_default_values()``
``create_debit``              PORTADO — ``create_debit()``
``move_type`` (campo compute) NO — sólo alimenta ``journal_type`` y la
                               visibilidad de ``copy_lines`` en el
                               formulario; sin lector de negocio.
``journal_type`` (compute)    NO — sólo filtra el dominio del widget
                               ``journal_id`` en el formulario.
``country_code`` (related)    NO — sólo lectura de UI
                               (``move_ids.company_id.country_id.code``),
                               sin consumidor en la lógica del wizard.
``_compute_from_moves``       NO — alimenta a ``move_type`` (arriba).
``_compute_journal_type``     NO — alimenta a ``journal_type`` (arriba).
===========================  ==========================================

Los tres campos NO portados son soporte de widgets del formulario Odoo
(dominio del ``Many2one``, visibilidad condicional) — no hay formulario
DRF en este pase (ver ``__init__.py`` del addon). Mismo criterio que la
exclusión de navegación en ``models/account_move.py``.

``default_get`` → ``validate_moves(moves)``: la referencia lee
``self.env.context['active_ids']`` (los movimientos que el usuario
seleccionó en la lista antes de abrir el wizard) — mecánica del cliente web
de Odoo sin equivalente aquí. Se porta la parte con lógica real: las tres
validaciones (``UserError`` si algún movimiento no está publicado, si ya es
él mismo una nota de débito, o si su tipo no es facturable/reembolsable),
recibiendo ``moves`` como argumento en vez de leerlo del contexto.

Divergencia declarada — ``move.copy(default=...)`` no existe aquí
=======================================================================

``create_debit`` de la referencia hace ``move.copy(default=default_values)``:
copia TODOS los campos del movimiento original y sobreescribe sólo los de
``default_values``. Medido: ningún modelo de este árbol declara un
``copy()`` genérico (``grep -n "def copy" account/models/account_move.py
base/models/*.py`` → 0 hits salvo ``ResConfigSettings.copy``, de otro
dominio). El stack no trae el mecanismo → se construye: ``prepare_default_
values()`` copia explícitamente los tres campos que la referencia heredaría
gratis (``partner``, ``currency``, ``company``) además de los que sí
sobreescribe.

Divergencia declarada — la condición muerta de ``copy_lines`` en refunds
==============================================================================

La referencia escribe::

    if not self.copy_lines or move.move_type in [('in_refund', 'out_refund')]:
        default_values['line_ids'] = [(5, 0, 0)]

``move.move_type in [('in_refund', 'out_refund')]`` compara un ``str``
contra una lista que contiene una única ``tuple`` — nunca es verdadero para
ningún ``move_type`` real. La rama se reduce, en la práctica, a
``if not self.copy_lines: clear()`` — el formulario oculta el checkbox para
refunds (``invisible="move_type in ['in_refund', 'out_refund']"``), pero
eso es UI, no la condición de negocio. Se porta el comportamiento
**efectivamente ejecutado** (``if copy_lines: copiar líneas``), no la
condición muerta — replicarla tal cual habría sido reproducir un bug de la
referencia sin ningún lector que lo note.
"""
from addons.account_debit_note.models.account_move import AccountMoveDebitNote
from exceptions import UserError
from orm.models_transient import TransientModel
from tools.translate import _


class AccountDebitNoteWizard(TransientModel):
    """Asistente "Crear nota de débito" — ≙ ``account.debit.note``.

    Sin tabla (``TransientModel``, ``managed = False``): el estado del
    wizard lo pasa el llamador como argumentos de los classmethods.
    """

    class Meta:
        abstract = True
        managed = False

    #: ≙ el ``UserError`` de ``default_get`` (``odoo19c: account_debit_note/
    #: wizard/account_debit_note.py:38``): sólo estos cuatro tipos son
    #: debitables.
    ALLOWED_MOVE_TYPES = ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')
    #: Tipos "nota de crédito" — cambian de tipo al debitarse (in_refund →
    #: in_invoice, out_refund → out_invoice) y nunca copian líneas.
    REFUND_MOVE_TYPES = ('in_refund', 'out_refund')
    #: Campos de ``account.move.line`` que se copian cuando ``copy_lines``
    #: es ``True`` — el subconjunto de columnas propias de la línea (sin
    #: ``move``, que apunta al nuevo movimiento).
    LINE_COPY_FIELDS = (
        'account', 'name', 'debit', 'credit', 'display_type',
        'quantity', 'price_unit', 'currency',
    )

    @classmethod
    def validate_moves(cls, moves):
        """Las tres validaciones de ``default_get`` — ≙ el cuerpo real
        (sin la lectura de ``active_ids``, ver el docstring del módulo)."""
        moves = list(moves)
        if any(move.state != 'posted' for move in moves):
            raise UserError(_('Sólo se pueden debitar asientos publicados.'))
        if any(AccountMoveDebitNote.origin_for(move) is not None
               for move in moves):
            raise UserError(_(
                "No se puede crear una nota de débito de una factura que "
                "ya está vinculada a otra nota de débito."))
        if any(move.move_type not in cls.ALLOWED_MOVE_TYPES for move in moves):
            raise UserError(_(
                "Sólo se puede crear una nota de débito de una factura de "
                "cliente, una nota de crédito de cliente, una factura de "
                "proveedor o una nota de crédito de proveedor."))
        return moves

    @classmethod
    def prepare_default_values(cls, move, date=None, reason=None, journal=None):
        """Los valores del nuevo movimiento — ≙ ``_prepare_default_values``.

        Incluye ``partner``/``currency``/``company``, que la referencia
        hereda gratis de ``move.copy()`` (ver la divergencia declarada del
        módulo: aquí no existe ``copy()`` genérico).
        """
        if move.move_type in cls.REFUND_MOVE_TYPES:
            move_type = 'in_invoice' if move.move_type == 'in_refund' else 'out_invoice'
        else:
            move_type = move.move_type
        ref = f'{move.name}, {reason}' if reason else move.name
        return {
            'ref': ref,
            'date': date or move.date,
            'journal': journal or move.journal,
            'partner': move.partner,
            'currency': move.currency,
            'company': move.company,
            'move_type': move_type,
        }

    @classmethod
    def _copy_lines(cls, source_move, target_move):
        """Copia las líneas de ``source_move`` a ``target_move``.

        ≙ la parte "no limpiar ``line_ids``" del ``copy()`` de la
        referencia. ``source_move.line_ids.model`` evita importar
        ``AccountMoveLine`` a nivel de módulo (este archivo se importa
        normal desde ``__init__.py`` — ver el docstring de
        ``models/account_move_sequence.py`` para la razón de este criterio).
        """
        line_model = source_move.line_ids.model
        for line in source_move.line_ids.all():
            values = {field: getattr(line, field) for field in cls.LINE_COPY_FIELDS}
            line_model.objects.create(move=target_move, **values)

    @classmethod
    def create_debit(cls, moves, date=None, reason=None, journal=None,
                      copy_lines=False):
        """Crea una nota de débito por cada movimiento — ≙ ``create_debit``.

        Devuelve la lista de movimientos creados (aquí no hay
        ``ir.actions.act_window`` que devolver — ver el docstring del
        módulo: la navegación queda fuera de alcance).
        """
        moves = cls.validate_moves(moves)
        new_moves = []
        for move in moves:
            values = cls.prepare_default_values(
                move, date=date, reason=reason, journal=journal)
            new_move = type(move).objects.create(**values)
            AccountMoveDebitNote.objects.create(move=new_move, origin=move)
            if copy_lines:
                cls._copy_lines(move, new_move)
            new_moves.append(new_move)
        return new_moves

"""``account.move`` — el vínculo con la factura debitada (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/account_debit_note/models/account_move.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 — atribución
y aviso de licencia preservados, DEC-KX-03).

Nueve símbolos — seis se portan, tres no (medido, no supuesto)
==================================================================

===========================  ==========================================
Símbolo de la referencia      Qué pasa aquí
===========================  ==========================================
``debit_origin_id`` (campo)   PORTADO — ``AccountMoveDebitNote.origin``
``debit_note_ids`` (campo)    PORTADO — ``debit_notes_for()``
``debit_note_count`` (campo)  PORTADO — ``count_for()``
``_compute_debit_count``      PORTADO — cuerpo de ``count_for()``
``_get_last_sequence_domain`` PORTADO — en ``account_move_sequence.py``
``_get_starting_sequence``    PORTADO — en ``account_move_sequence.py``
``action_view_debit_notes``   NO — navegación pura, ver abajo
``action_debit_note``         NO — navegación pura, ver abajo
``_get_copy_message_content`` NO — no hay mecanismo de chatter, ver abajo
===========================  ==========================================

**Por qué NO se portan las dos acciones de navegación.** Ambas devuelven un
diccionario ``ir.actions.act_window`` (``action_view_debit_notes`` abre la
lista filtrada por ``debit_origin_id``; ``action_debit_note`` abre el
formulario del wizard) — sin lógica de negocio propia, sólo construyen la
navegación del cliente web de Odoo. Mismo criterio que
``fleet.FleetVehicle`` fija para su punto 7 ("NO se portan los helpers de
navegación de vista... sin equivalente DRF"). La CAPACIDAD que exponían
—contar/listar las notas de un origen— sí se porta: es ``count_for()`` y
``debit_notes_for()`` de abajo.

**Por qué NO se porta ``_get_copy_message_content``.** Es un hook de
``mail.thread`` (chatter): compone el mensaje "Esta nota de débito se creó
desde: %s" que se postea al copiar. Medido: ``account.AccountMove`` de este
árbol NO hereda ningún ``MailThread`` (``grep -n "MailThread" account/
models/account_move.py`` → 0 hits) y no existe ``_get_html_link`` en ningún
addon portado (``grep -rn "_get_html_link" src/addons`` → 0 hits). No hay
mecanismo base que extender — construirlo sería levantar el sistema de
chatter completo, fuera de alcance de este addon. **DESCONOCIDO declarado**:
se decide cuando ``mail.thread`` se porte sobre ``account.move``.

Cross-app ``_inherit`` sobre un modelo ajeno → RELATED (DEC-SALE-01, mismo
criterio que ``sale_crm.SaleOrderOpportunity`` para ``sale.order``↔
``crm.lead``): ``AccountMoveDebitNote`` cuelga de ``account.AccountMove`` con
su propia tabla — sin tocar ``account`` ni su migración.

``debit_origin_id`` es ``Many2one`` (readonly, copy=False, ``index=
'btree_not_null'``): cada nota de débito apunta a **un** origen, pero un
mismo origen puede tener varias notas de débito. Por eso ``move`` es
``OneToOneField`` (la nota de débito misma — una fila de vínculo por nota) y
``origin`` es ``ForeignKey`` (el origen — varias notas pueden compartirlo).
"""
from addons.base.models import TimeStampedModel
import fields
import models


class AccountMoveDebitNote(TimeStampedModel):
    """Vincula una nota de débito (``account.move``) a la factura que debita.

    ≙ ``account.move.debit_origin_id`` (columna que vive en este registro,
    del lado de la nota de débito) + su reverso ``debit_note_ids``/
    ``debit_note_count`` (del lado del origen, ver los classmethods).
    """

    move = models.OneToOneField(
        'account.AccountMove', on_delete=models.CASCADE,
        related_name='debit_note_link',
        help_text='La nota de débito misma (Odoo debit_origin_id vive en '
                  'este registro — el Many2one de la referencia, leído '
                  'desde el lado de la nota).',
    )
    origin = fields.Many2one(
        'account.AccountMove', on_delete=models.PROTECT,
        related_name='debit_notes', db_index=True,
        help_text='Factura original debitada (Odoo debit_origin_id).',
    )

    class Meta:
        db_table = 'account_debit_note_link'
        verbose_name = 'Nota de débito'
        verbose_name_plural = 'Notas de débito'

    def __str__(self) -> str:
        return f'{self.move} ← {self.origin}'

    @classmethod
    def origin_for(cls, move):
        """La factura que ``move`` debita, o ``None`` — ≙ ``debit_origin_id``."""
        if move is None or move.pk is None:
            return None
        link = cls.objects.filter(move_id=move.pk).select_related('origin').first()
        return link.origin if link else None

    @classmethod
    def debit_notes_for(cls, move):
        """Las notas de débito creadas desde ``move`` — ≙ ``debit_note_ids``.

        ``move is None`` no tiene modelo del que derivar un queryset vacío
        (``type(None).objects`` no existe) — devuelve ``[]`` en ese caso,
        distinto de ``move`` sin guardar (``move.pk is None``), donde SÍ hay
        clase concreta de la que pedir ``.objects.none()``.
        """
        if move is None:
            return []
        if move.pk is None:
            return type(move).objects.none()
        return type(move).objects.filter(debit_note_link__origin_id=move.pk)

    @classmethod
    def count_for(cls, move) -> int:
        """Cuántas notas de débito tiene ``move`` — ≙ ``debit_note_count``
        (cuerpo de ``_compute_debit_count``: ``_read_group`` por
        ``debit_origin_id`` — aquí, un ``count()`` filtrado por ``origin``)."""
        if move is None or move.pk is None:
            return 0
        return cls.objects.filter(origin_id=move.pk).count()

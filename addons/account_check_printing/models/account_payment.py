"""``account.payment`` — lo que ``account_check_printing`` le cuelga.

Adaptación de ``odoo19c: addons/account_check_printing/models/
account_payment.py`` (``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso
de licencia preservados, DEC-KX-03).

Símbolos de la referencia — qué pasa aquí (medido, no supuesto)
=====================================================================

======================================  =========================================
Símbolo de la referencia                  Qué pasa aquí
======================================  =========================================
``check_amount_in_words``                PORTADO — ``amount_in_words()``
``check_manual_sequencing`` (related)    PORTADO — ``CheckPrintingJournalSettings.manual_sequencing``
``check_number``                         PORTADO — ``CheckPrintingPaymentInfo.check_number``
``payment_method_line_id`` (index=True)  NO — Divergencia 1
``show_check_number``                    PORTADO — ``show_check_number()``
``check_layout_available``               PORTADO — ``CheckPrintingCompanySettings.check_layout_available()``
``_compute_show_check_number``           PORTADO — cuerpo de ``show_check_number()``
``_constrains_check_number``             PORTADO — ``clean()`` de ``CheckPrintingPaymentInfo`` (llamado en ``save()``)
``_auto_init``                           NO NECESARIO — Django migra la columna (ver Divergencia 2)
``_constrains_check_number_unique``      PORTADO — ``validate_check_number_uniqueness()``
``_compute_check_amount_in_words``       PORTADO — cuerpo de ``amount_in_words()``
``_compute_check_number``                PORTADO — cuerpo de ``compute_check_number()``
``_inverse_check_number``                PORTADO — ``set_check_number()``
``fields_get`` (readonly pretend)        NO — Divergencia 3
``_get_trigger_fields_to_synchronize``   NO — Divergencia 4
``_get_aml_default_display_name_list``   NO — Divergencia 5 (depende de ``move_id``)
``action_post`` (asignar número)         PORTADO — ``assign_check_number_on_post()``
``print_checks``                         PORTADO — ``prepare_print_checks()``
``action_void_check``                    PORTADO — ``void_check()``, Divergencia 6
``do_print_checks``                      PARCIAL — ``mark_as_sent()`` portado; el render, Divergencia 7
``_check_fill_line``                     NO — Divergencia 8 (sirve sólo al stub, ver abajo)
``_check_build_page_info``               NO — Divergencia 8
``_check_get_pages``                     NO — Divergencia 8
``_check_make_stub_pages``                NO — Divergencia 8
======================================  =========================================

Divergencia 1 — sin ``payment_method_line_id``: la presencia de la fila ES
el marcador
================================================================================

``AccountPayment`` de este árbol no modela métodos de pago en absoluto
(``grep -n "payment_method" account/models/account_payment.py`` → **0
hits** [PROVEN]) — es infraestructura de ``account`` (fuera de alcance: "no
tocar ningún otro addon"; ``AccountPaymentMethodLine`` existe, pero nada en
``AccountPayment`` apunta a ella). Sin ese campo, "este pago usa Cheques" no
se puede leer de un código — se representa con la EXISTENCIA de la fila
``CheckPrintingPaymentInfo`` (mismo patrón que
``account_debit_note.AccountMoveDebitNote``: el vínculo ES el marcador,
igual que ``debit_origin_id is not None`` ↔ "es nota de débito"). Se crea
explícitamente cuando el llamador elige Cheques (``for_payment(payment,
create=True)``), no de forma implícita.

Divergencia 2 — sin ``_auto_init`` a mano
===============================================

La referencia comenta la columna a mano (``create_column``) "para evitar
``MemoryError`` en bases grandes" — un problema del ALTER TABLE en vivo de
Odoo. Aquí ``check_number`` vive en la tabla PROPIA de
``CheckPrintingPaymentInfo`` (Divergencia 1: RELATED, no columna en
``account_payment``), así que la migración normal de Django la crea sin ese
riesgo — no hay ALTER TABLE sobre una tabla ajena que evitar.

Divergencia 3 — sin ``fields_get``
========================================

``fields_get`` finge que ``check_number`` es de sólo lectura en el
metadato del formulario Odoo — es infraestructura del cliente web
(introspección de campos), sin análogo en un serializer DRF que este addon
no declara en este pase (mismo criterio que ``account_debit_note`` para sus
tres campos de soporte de widget). **DESCONOCIDO declarado**: el día que
exista un serializer DRF de ``account.payment``, marcar ``check_number``
como ``read_only=True`` ahí es el lugar correcto.

Divergencia 4 — sin ``_get_trigger_fields_to_synchronize``
================================================================

Ese hook alimenta la sincronización pago↔línea de asiento contable
(``account.payment`` ↔ ``account.move.line``) cuando ``check_number``
cambia — depende de la conciliación con ``move_id`` (Divergencia 5).
**DESCONOCIDO declarado**, misma condición de cierre que la Divergencia 5.

Divergencia 5 — sin ``move_id``: el nombre en el asiento no se puede
recomponer
=================================================================================

``_get_aml_default_display_name_list`` compone el nombre ``"Checks - NNNN:
memo"`` de la línea de asiento generada al postear. ``AccountPayment`` de
este árbol no tiene ``move_id`` (``grep -n "move_id\\|move\\b"
account/models/account_payment.py`` → **0 hits** [PROVEN]) — no hay asiento
contable generado por un pago en este núcleo, así que no hay línea cuyo
nombre componer. **DESCONOCIDO declarado**: depende de que ``account``
porte la generación de asiento de ``account.payment`` (fuera de este addon).

Divergencia 6 — ``action_void_check`` sin ``action_draft``/``action_cancel``
================================================================================

La referencia encadena ``self.action_draft(); self.action_cancel()`` — dos
métodos de workflow que ``AccountPayment`` de este árbol tampoco tiene
(``grep -n "def action_draft\\|def action_cancel"
account/models/account_payment.py`` → **0 hits** [PROVEN]: no hay motor de
estados sobre el pago, sólo el campo ``state``). ``void_check()`` escribe
``state = 'canceled'`` directamente — mismo efecto final que la cadena de
dos acciones ausentes, sin inventar el motor de estados completo (eso es
trabajo de ``account``).

Divergencia 7 — ``do_print_checks`` sin declaración de reporte propia
========================================================================

Corregido 2026-08-12 (H-API-407): este comentario decía *"no hay ningún
motor de reportes/PDF en todo el árbol"* y citaba como prueba
``grep -rln "report_action\\|ir.actions.report" src/`` → **0 hits**,
marcado ``[PROVEN]``. Ese grep, corrido sobre el mismo commit que escribió
la afirmación (``5630af7``, 2026-08-08) y excluyendo este propio archivo,
devuelve **11 archivos** — entre ellos ``base/models/ir_actions_report.py``,
que existe desde ``bacee17`` (2026-08-01), una semana antes.

No fue una métrica ciega ni una afirmación que envejeció: el motor usa
exactamente los símbolos que el grep buscaba. La cifra citada nunca fue el
resultado de ese comando. Se registra como tal en H-API-407 —
``react-verification-gate``, no ``metrica-decide-la-conclusion``.

El motor **sí existe**: ``base/models/ir_actions_report.py``
(declaración de ``ir.actions.report``), ``base/report_catalog.py``
(patrón de catálogo por familia) y los helpers ``libharu`` de
``tools/pdf/`` (ADR-017) — ya consumidos por ``sale/report/
report_catalog.py`` y por el recibo de UC-PAY-10, en producción.

La parte QUE SÍ se porta: ``mark_as_sent()`` (≙ ``self.write({'is_sent':
'True'})``) y la validación de diseño (≙ el ``RedirectWarning`` si no hay
``check_layout``). La parte que NO: ``report_action.report_action(self)`` —
no porque falte el motor, sino porque ``account_check_printing`` **no
declara su ``ReportSpec``** en un ``report_catalog.py`` propio, como sí lo
hace ``sale``. Es un eslabón de wiring pendiente, no infraestructura
ausente. ``render_checks()`` documenta el bloqueo con ``NotImplementedError``
explícito — condición de cierre: declarar el ``ReportSpec`` del cheque en
``account_check_printing/report_catalog.py`` y llamar al motor existente
(mismo patrón que ``sale``).

Divergencia 8 — el stub de facturas pagadas depende de ``move_id`` (igual
que la Divergencia 5)
=================================================================================

``_check_get_pages``/``_check_make_stub_pages``/``_check_build_page_info``/
``_check_fill_line`` construyen el detalle de facturas conciliadas
(``move_id.line_ids`` filtradas por cuenta por cobrar/pagar, y sus
``account.partial.reconcile``). Sin ``move_id`` en ``AccountPayment``
(Divergencia 5), no hay de dónde leer qué facturas paga este pago.
**DESCONOCIDO declarado**, misma condición de cierre que la Divergencia 5:
depende de que ``account`` porte la generación de asiento + conciliación de
``account.payment`` — trabajo de ese addon, no de éste.
"""
from django.db.models import IntegerField
from django.db.models.functions import Cast

import fields
import models
from addons.account.models import AccountPayment
from addons.account_check_printing.models.account_journal import (
    CheckPrintingJournalSettings,
)
from addons.account_check_printing.models.res_company import (
    CheckPrintingCompanySettings,
)
from addons.base.models import TimeStampedModel
from exceptions import UserError, ValidationError
from tools.translate import _

#: ≙ ``self.env.ref('account_check_printing.account_payment_method_check')``
#: — el ``code`` con el que la migración de datos siembra el catálogo (ver
#: ``migrations/0002_seed_check_payment_method.py``).
CHECK_PRINTING_METHOD_CODE = 'check_printing'


class CheckPrintingPaymentInfo(TimeStampedModel):
    """Datos de impresión de cheque de un pago — ≙ los campos ``check_*``
    de ``account.payment``.

    La EXISTENCIA de la fila es el marcador "este pago usa Cheques" — ver
    la Divergencia 1 del docstring del módulo.
    """

    payment = models.OneToOneField(
        AccountPayment, on_delete=models.CASCADE,
        related_name='check_printing_info',
        help_text='Pago (Odoo _inherit account.payment).',
    )
    check_number = fields.Char(
        max_length=32, blank=True, default='', db_index=True,
        help_text='Número de cheque impreso o asignado a este pago (Odoo '
                  'check_number).',
    )
    is_sent = fields.Boolean(
        default=False, verbose_name='Cheque impreso',
        help_text='Marca que el cheque ya se imprimió — evita reimprimirlo '
                  '(Odoo is_sent, campo genérico de account.payment que '
                  'este núcleo tampoco declara; se porta aquí porque sólo '
                  'esta funcionalidad lo necesita).',
    )

    class Meta:
        db_table = 'account_check_printing_payment_info'
        verbose_name = 'Datos de impresión de cheque'
        verbose_name_plural = 'Datos de impresión de cheques'
        # ≙ _constrains_check_number_unique — unicidad por (diario, número)
        # se aplica en validate_check_number_uniqueness(), no como
        # UniqueConstraint de tabla: un pago cancelado libera su número
        # (ver esa función), lo que un UNIQUE de columna no puede expresar.

    def __str__(self) -> str:
        return f'Cheque {self.check_number or "(sin número)"} — {self.payment}'

    def clean(self):
        """≙ ``_constrains_check_number`` (``odoo19c: account_payment.py:47-51``):
        el número de cheque sólo contiene dígitos."""
        super().clean()
        if self.check_number and not self.check_number.isdecimal():
            raise ValidationError(_('Check numbers can only consist of digits'))

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    # -- fábrica: la existencia de la fila es el marcador -------------------

    @classmethod
    def for_payment(cls, payment, create=False):
        """La fila de ``payment``, o ``None`` si no eligió Cheques — ≙
        "``payment_method_line_id.code == 'check_printing'``" de la
        referencia, leído por existencia (Divergencia 1).

        ``create=True`` es el punto donde el llamador ELIGE Cheques para
        este pago — equivalente a asignar
        ``payment_method_line_id = <línea de Cheques>`` en la referencia.
        """
        row = cls.objects.filter(payment=payment).first()
        if row is not None or not create:
            return row
        return cls.objects.create(payment=payment)

    @classmethod
    def is_check_payment(cls, payment):
        return cls.objects.filter(payment=payment).exists()

    # -- campos computados ---------------------------------------------------

    def amount_in_words(self):
        """≙ ``_compute_check_amount_in_words``
        (``odoo19c: account_payment.py:98-104``). Usa el conversor colgado
        de ``base.ResCurrency`` (``models/res_currency.py``, este mismo
        addon) — divergencia de forma declarada ahí (español, "PESOS")."""
        currency = self.payment.currency
        if not currency:
            return ''
        return currency.amount_to_text(self.payment.amount)

    def compute_check_number(self):
        """≙ ``_compute_check_number`` (``odoo19c: account_payment.py:106-113``):
        con numeración manual del diario, el próximo número SIN
        consumirlo (peek); si no, vacío."""
        journal_settings = CheckPrintingJournalSettings.ensure_for(self.payment.journal)
        if journal_settings.manual_sequencing:
            return journal_settings.next_check_number()
        return ''

    def set_check_number(self, value):
        """≙ ``_inverse_check_number`` (``odoo19c: account_payment.py:115-119``):
        fija el número Y ajusta el ``padding`` de la secuencia del diario
        al ancho del número escrito a mano.

        ≙ ``@api.constrains('check_number', 'journal_id')`` de la
        referencia se dispara sola en cada escritura; aquí se invoca
        explícitamente tras escribir — ver ``validate_check_number_uniqueness``.
        """
        self.check_number = value
        self.save(update_fields=['check_number', 'updated_at'])
        type(self).validate_check_number_uniqueness(self.payment)
        if value:
            journal_settings = CheckPrintingJournalSettings.ensure_check_sequence(
                self.payment.journal)
            journal_settings.sequence.padding = len(value)
            journal_settings.sequence.save(update_fields=['padding'])

    def show_check_number(self):
        """≙ ``_compute_show_check_number``
        (``odoo19c: account_payment.py:39-45``): sólo si el pago usa
        Cheques Y ya tiene número asignado."""
        return bool(self.check_number)

    @staticmethod
    def check_layout_available():
        """≙ ``check_layout_available`` (``odoo19c: account_payment.py:33-37``):
        ¿hay más de un diseño de cheque entre los que elegir? Delega en
        ``CheckPrintingCompanySettings`` — mismo criterio de la referencia
        (lee el selection de la empresa, no algo propio del pago)."""
        return CheckPrintingCompanySettings.check_layout_available()

    # -- unicidad (≙ _constrains_check_number_unique) ------------------------

    @classmethod
    def validate_check_number_uniqueness(cls, payment):
        """≙ ``_constrains_check_number_unique``
        (``odoo19c: account_payment.py:63-96``). En la referencia el
        conflicto exige ambos asientos ``posted`` — este núcleo no tiene
        ``move_id`` (Divergencia 5), así que el estado comparable es el del
        propio ``account.payment``: un pago ``canceled``/``draft`` no
        compite por el número (libera la serie), sólo ``in_process``/
        ``paid`` cuentan como "ya comprometido".
        """
        row = cls.for_payment(payment)
        if row is None or not row.check_number:
            return
        conflicto = cls.objects.filter(
            check_number=row.check_number,
            payment__journal=payment.journal,
            payment__state__in=('in_process', 'paid'),
        ).exclude(pk=row.pk).first()
        if conflicto is not None:
            raise ValidationError(_(
                'The following numbers are already used:\n%(number)s in '
                'journal %(journal)s') % {
                    'number': row.check_number, 'journal': str(payment.journal)})

    # -- ciclo de vida (≙ action_post / print_checks / do_print_checks) -----

    @classmethod
    def assign_check_number_on_post(cls, payment):
        """≙ el filtro de ``action_post`` (``odoo19c: account_payment.py:155-160``):
        asigna el siguiente número SÓLO si el diario tiene numeración
        manual y el pago usa Cheques. Consume la secuencia (a diferencia de
        ``compute_check_number``, que sólo mira)."""
        row = cls.for_payment(payment)
        if row is None:
            return None
        journal_settings = CheckPrintingJournalSettings.ensure_for(payment.journal)
        if not journal_settings.manual_sequencing:
            return row
        journal_settings = CheckPrintingJournalSettings.ensure_check_sequence(payment.journal)
        row.check_number = journal_settings.sequence.next_by_id()
        row.save(update_fields=['check_number', 'updated_at'])
        cls.validate_check_number_uniqueness(payment)
        return row

    @classmethod
    def prepare_print_checks(cls, payments):
        """≙ ``print_checks`` (``odoo19c: account_payment.py:162-203``).

        Valida el lote y decide entre dos caminos, igual que la referencia:

        - diario con numeración manual → asigna número a cada pago y
          devuelve la lista lista para imprimir (equivalente a
          ``valid_payments.do_print_checks()``).
        - diario SIN numeración manual → devuelve el ``next_check_number``
          sugerido para el wizard ``PrintPrenumberedChecksWizard`` (el
          llamador decide el ``target``/``view_mode`` — eso es capa cliente
          Odoo, fuera de este backend).
        """
        rows_by_payment = {p.pk: cls.for_payment(p) for p in payments}
        valid_payments = [
            p for p in payments
            if rows_by_payment[p.pk] is not None and not rows_by_payment[p.pk].is_sent
        ]
        if not valid_payments:
            raise UserError(_(
                "Payments to print as a checks must have 'Check' selected "
                "as payment method and not have already been reconciled"))
        journal = valid_payments[0].journal
        if any(p.journal_id != journal.pk for p in valid_payments):
            raise UserError(_(
                'In order to print multiple checks at once, they must '
                'belong to the same bank journal.'))

        journal_settings = CheckPrintingJournalSettings.ensure_for(journal)
        if journal_settings.manual_sequencing:
            for payment in valid_payments:
                if payment.state == 'draft':
                    payment.state = 'in_process'
                    payment.save(update_fields=['state'])
            return {'mode': 'print', 'payments': cls.mark_as_sent(valid_payments)}

        # ≙ ``ORDER BY payment.check_number::BIGINT DESC LIMIT 1``
        # (``odoo19c: account_payment.py:176-185``). ``Cast`` a entero para
        # ordenar — nunca orden de cadena: '9' > '10' lexicográficamente
        # propondría un número ya usado (mismo defecto que H-API-339 fija
        # para sequence_mixin).
        last = cls.objects.filter(
            payment__journal=journal, check_number__gt='',
        ).annotate(
            check_number_int=Cast('check_number', output_field=IntegerField()),
        ).order_by('-check_number_int').values_list('check_number', flat=True).first()
        number_len = len(last or '')
        next_check_number = f'{int(last or 0) + 1:0{number_len}}' if last else '1'
        return {'mode': 'wizard', 'payments': valid_payments,
                'next_check_number': next_check_number}

    @classmethod
    def mark_as_sent(cls, payments):
        """≙ la parte portable de ``do_print_checks``
        (``odoo19c: account_payment.py:209-220``): valida el diseño de
        cheque y marca los pagos como enviados. El render en sí es
        Divergencia 7 — ver ``render_checks``.
        """
        for payment in payments:
            journal_settings = CheckPrintingJournalSettings.ensure_for(payment.journal)
            layout = journal_settings.effective_layout()
            if not layout or layout == 'disabled':
                raise UserError(_(
                    "You have to choose a check layout. For this, go in "
                    "Invoicing/Accounting Settings, search for 'Checks "
                    "layout' and set one."))
            row = cls.for_payment(payment, create=True)
            row.is_sent = True
            row.save(update_fields=['is_sent', 'updated_at'])
        return payments

    @classmethod
    def render_checks(cls, payments):
        """≙ el paso final de ``do_print_checks``
        (``report_action.report_action(self)``) — Divergencia 7: el motor
        de reportes existe (``base/models/ir_actions_report.py`` +
        ``report_catalog.py``, ADR-017), pero este addon no declara su
        ``ReportSpec`` todavía. Llamar primero a ``mark_as_sent(payments)``
        (side effect portado); esto es sólo el terminal bloqueado.
        """
        raise NotImplementedError(
            'render_checks: motor de reportes/PDF disponible '
            '(base.report_catalog + tools/pdf, ADR-017; ya consumido por '
            'sale y por el recibo de UC-PAY-10), pero account_check_printing '
            'aún no declara su ReportSpec — condición de cierre: crear '
            'account_check_printing/report_catalog.py con la definición del '
            'cheque, mismo patrón que sale/report/report_catalog.py.')

    @classmethod
    def void_check(cls, payment):
        """≙ ``action_void_check`` (``odoo19c: account_payment.py:205-207``).

        Divergencia 6: sin ``action_draft``/``action_cancel`` que encadenar
        — se escribe el estado terminal directamente."""
        payment.state = 'canceled'
        payment.save(update_fields=['state'])
        return payment

    # -- "Checks to Print" ---------------------------------------------------

    @classmethod
    def checks_to_print_queryset(cls, journal):
        """Pagos de ``journal`` elegibles para "Checks to Print" — ≙ la
        capacidad detrás de ``action_checks_to_print``/
        ``_get_journal_dashboard_data_batched``
        (``odoo19c: account_journal.py:96-120``), cuya navegación/tablero
        NO se portan (ver ``models/account_journal.py``, Divergencia 3).
        Vive aquí y no en ``account_journal.py`` para no crear un ciclo de
        imports entre los dos archivos (filtra por ``payment__journal`` sin
        necesitar importar ``AccountJournal``).
        """
        return cls.objects.filter(
            payment__journal=journal, payment__state='in_process', is_sent=False,
        )

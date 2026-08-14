"""``account.payment.register`` — asistente de registro de pago (Odoo ``account``).

Adaptación de Odoo ``addons/account/wizard/account_payment_register.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3) —
atribución y aviso de licencia preservados (DEC-KX-03). ``TransientModel``
sin tabla en la referencia — igual que ``AccountDebitNoteWizard``, el
estado del wizard lo pasa el llamador como argumentos.

Cierra dos de los tres huecos de :ref:`h-api-408` que corresponden a este
archivo (el tercero, ``payment_state``, vive en ``account_move.py``):
el álgebra de conciliación (``AccountPartialReconcile``/
``AccountFullReconcile``) ya estaba portada; lo que faltaba era la ACCIÓN
que la dispara — UC-PAY-14 (``uc-pay-14-pago-parcial-abono``, tarea #55).

Alcance — ver PARTE 1.3 / PARTE 8.1 del UC
==========================================

- Consume ``AccountPartialReconcile.create_partial`` y
  ``AccountFullReconcile.create_from_partials`` — **no reimplementa** el
  emparejamiento debe/haber ni el algoritmo de ``matching_number``.
- **Una sola línea receivable/payable por factura.** Divergencia declarada:
  la referencia soporta múltiples ``account.move.line`` conciliables por
  factura; aquí se toma la primera encontrada, consistente con el resto del
  puerto de facturación simple (``_posted_move`` en los tests de
  ``account_debit_note`` crea exactamente una línea por cobrar). Sucesor si
  aparece un caso multi-línea real.
- Sin base imponible en efectivo (cash basis) ni multi-moneda de la
  conciliación — mismas divergencias ya declaradas en
  ``account_partial_reconcile.py``; no se duplican aquí.
- El apunte del pago (y el de la diferencia, si aplica) se registran en
  **un solo asiento** (``move_type='entry'``), no dos — la referencia
  también compone el pago y el write-off en el mismo movimiento cuando
  ``payment_difference_handling == 'reconcile'``
  (``odoo19c: account_payment_register.py:1010-1046``).
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from addons.account.models.account_full_reconcile import AccountFullReconcile
from addons.account.models.account_move import AccountMove
from addons.account.models.account_move_line import AccountMoveLine
from addons.account.models.account_partial_reconcile import AccountPartialReconcile
from exceptions import UserError
from tools.translate import _


class AccountPaymentRegisterWizard:
    """≙ ``account.payment.register`` — sin tabla propia, mismo patrón que
    ``AccountDebitNoteWizard``: un ``classmethod`` que recibe los argumentos
    del wizard (ya validados por la capa DRF) y devuelve el resultado."""

    @classmethod
    @transaction.atomic
    def register_payment(cls, move, *, amount, journal, difference_handling='open',
                          difference_account=None, difference_label='Write-Off',
                          date=None):
        """Registra un abono (o pago completo) sobre ``move`` — ≙ el botón
        "Registrar Pago" del wizard (PARTE 3 del UC, pasos 5-7).

        Levanta ``UserError`` en las tres condiciones de PARTE 5 (EX-01/02/03)
        más las dos precondiciones operativas (PRE-01/03) — la vista mapea
        cada mensaje a su ``codigo_error`` HTTP.

        Mecánica (≙ PARTE 8.5, envío de mensajes):

        1. Crea el apunte del pago: un asiento nuevo con la línea de banco/
           efectivo (debe, cuenta por defecto del diario) y la línea de
           receivable/payable (haber), ambas por ``amount``.
        2. Empareja la línea receivable de la factura con la línea de haber
           del pago vía ``AccountPartialReconcile.create_partial`` — POST-01.
        3. Si ``difference_handling == 'reconcile'`` y queda diferencia,
           agrega al MISMO asiento un apunte adicional (debe en
           ``difference_account``, haber en receivable) por el resto, y un
           segundo partial que lo empareja — POST-04 / Alternativa A.
        4. Publica el asiento del pago (``AccountMove.post()`` — valida
           balance, asigna secuencia).
        5. Si el saldo pendiente de la factura llega a 0, agrupa **todos**
           los partials abiertos de su línea receivable (los de esta
           llamada y los de abonos previos — Alternativa B) en un
           ``AccountFullReconcile`` — POST-03.
        6. Recalcula ``payment_state`` de la factura
           (``AccountMove.compute_payment_state``).
        """
        if move.state != 'posted':
            raise UserError(_('El movimiento no está publicado.'))

        receivable_line = move.line_ids.filter(
            account__account_type__in=AccountMove._RESIDUAL_ACCOUNT_TYPES,
        ).first()
        if receivable_line is None:
            raise UserError(_(
                'El movimiento no tiene línea por cobrar/pagar (PRE-01).'))

        if journal.default_account_id is None:
            raise UserError(_(
                'El diario no tiene cuenta por defecto configurada (PRE-03).'))

        residual = move.get_amount_residual()
        if amount <= Decimal('0.00'):
            raise UserError(_('El monto debe ser mayor a cero (EX-02).'))
        if amount > residual:
            raise UserError(_(
                'El monto excede el saldo pendiente de la factura (EX-01).'))
        if difference_handling == 'reconcile' and difference_account is None:
            raise UserError(_(
                'Se requiere una cuenta de diferencia para conciliar el '
                'resto como Write-Off (EX-03).'))

        payment_date = date or timezone.now().date()
        difference = (residual - amount) if difference_handling == 'reconcile' \
            else Decimal('0.00')

        payment_move = AccountMove.objects.create(
            move_type='entry', date=payment_date, journal=journal,
            company=move.company, partner=move.partner, state='draft',
        )
        AccountMoveLine.objects.create(
            move=payment_move, account=journal.default_account,
            name=_('Abono %s') % move.name, debit=amount,
        )
        receivable_credit_line = AccountMoveLine.objects.create(
            move=payment_move, account=receivable_line.account,
            name=_('Abono %s') % move.name, credit=amount,
        )
        partials = [AccountPartialReconcile.create_partial(
            debit_move=receivable_line, credit_move=receivable_credit_line,
            amount=amount,
        )]

        if difference > Decimal('0.00'):
            AccountMoveLine.objects.create(
                move=payment_move, account=difference_account,
                name=difference_label, debit=difference,
            )
            writeoff_credit_line = AccountMoveLine.objects.create(
                move=payment_move, account=receivable_line.account,
                name=difference_label, credit=difference,
            )
            partials.append(AccountPartialReconcile.create_partial(
                debit_move=receivable_line, credit_move=writeoff_credit_line,
                amount=difference,
            ))

        payment_move.post()

        if move.get_amount_residual() <= Decimal('0.00'):
            # Agrupa TODOS los partials abiertos de esta línea, no sólo los
            # de esta llamada — un segundo abono (Alternativa B, PARTE 4.2)
            # debe agrupar también el partial del primero, que ya existía.
            open_partials = AccountPartialReconcile.objects.filter(
                debit_move=receivable_line, full_reconcile__isnull=True)
            AccountFullReconcile.create_from_partials(open_partials)

        move.compute_payment_state()
        return payment_move, partials

"""Los 4 modelos RELATED que sostienen todo el porte — DEC-SALE-01.

Django no permite inyectar una columna en el modelo de OTRO addon sin
migrar la app dueña de la tabla (mismo problema que ``account_add_gln.
PartnerGln`` y ``account_debit_note.AccountMoveDebitNote``/
``JournalDebitSequence`` ya resolvieron). La referencia declara estos campos
como columnas directas vía ``_inherit``; aquí cada uno se modela como fila
de una tabla propia de ``account_payment``, enlazada por OneToOne o FK — sin
tocar ``account/migrations/`` ni ``payment/migrations/`` (fuera del alcance
de este agente).

Los 6 archivos ``models/*.py`` que espejan la referencia (``account_payment.
py``, ``account_move.py``, ``account_payment_method_line.py``,
``payment_provider.py``) cuelgan **propiedades no-almacenadas** sobre las
clases ajenas (``AccountPayment``, ``AccountMove``, ``AccountPaymentMethod
Line``, ``PaymentGateway``) que navegan estas 4 tablas — ``setattr(cls,
nombre, property(...))`` después de la definición de la clase no pasa por
``Model.add_to_class``/``contribute_to_class``, así que no genera columna ni
migración: es Python puro, igual que un ``property`` colgado desde otro
módulo.

Los 4 modelos, con su correspondencia en la referencia
==========================================================

======================================  ================================================  ==================================================
Modelo aquí                              ≙ campo(s) de la referencia                       Anfitrión ↔ enlazado
======================================  ================================================  ==================================================
``AccountPaymentTransaction``            ``account.payment.payment_transaction_id`` +      OneToOne ``account.AccountPayment`` ↔ FK
                                          ``payment_token_id`` + ``source_payment_id``      ``payment.Payment`` / ``payment.SavedCard`` /
                                                                                             ``account.AccountPayment`` (self)
``AccountMoveTransactionLink``           ``account.move.transaction_ids`` (M2M)            FK×2: ``account.AccountMove`` — ``payment.Payment``
``AccountPaymentMethodLineProvider``     ``account.payment.method.line.payment_provider_id`` OneToOne ``account.AccountPaymentMethodLine`` ↔ FK
                                                                                             ``payment.PaymentGateway``
``PaymentGatewayJournal``                ``payment.provider.journal_id``                    OneToOne ``payment.PaymentGateway`` ↔ FK
                                                                                             ``account.AccountJournal``
======================================  ================================================  ==================================================

Ninguno de los 4 trae ``TimeStampedModel`` (a diferencia de
``AccountMoveDebitNote``) — mismo criterio minimalista que
``PartnerGln``: son filas de enlace, no entidades de negocio con
auditoría propia.
"""
import models


class AccountPaymentTransaction(models.Model):
    """Enlace 1-a-1 de un ``account.AccountPayment`` con su transacción de
    pago, su token guardado y —si él mismo es un reembolso— el pago origen.

    ≙ ``odoo19c: account_payment/models/account_payment.py:11-44`` (los tres
    campos ``payment_transaction_id``/``payment_token_id``/
    ``source_payment_id``). Ver ``models/account_payment.py`` para las
    propiedades que navegan esta tabla.
    """

    payment          = models.OneToOneField(
        'account.AccountPayment', on_delete=models.CASCADE,
        related_name='payment_transaction_link',
        help_text='El account.payment dueño de este enlace.',
    )
    transaction      = models.ForeignKey(
        'payment.Payment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='account_payment_links',
        help_text='Transacción de pago (Odoo payment_transaction_id).',
    )
    token            = models.ForeignKey(
        'payment.SavedCard', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='account_payment_links',
        help_text='Tarjeta guardada usada (Odoo payment_token_id).',
    )
    source_payment   = models.ForeignKey(
        'account.AccountPayment', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='refund_links',
        help_text='Pago original del que ESTE pago es reembolso (Odoo '
                  'source_payment_id — related a través de la transacción '
                  'en la referencia; aquí, FK directa por simplicidad).',
    )

    class Meta:
        db_table = 'account_payment_transaction_link'
        verbose_name = 'Enlace pago↔transacción'
        verbose_name_plural = 'Enlaces pago↔transacción'

    def __str__(self) -> str:
        return f'AccountPayment#{self.payment_id} ↔ Payment#{self.transaction_id}'


class AccountMoveTransactionLink(models.Model):
    """Fila del M2M ``account.move.transaction_ids`` — ≙ ``odoo19c:
    account_payment/models/account_move.py:16-19``.

    Una factura puede tener varios intentos de pago (reintentos); una
    transacción puede cubrir varias facturas agrupadas (pago de vencidas) —
    de ahí M2M y no FK simple, igual que la referencia.
    """

    move        = models.ForeignKey(
        'account.AccountMove', on_delete=models.CASCADE,
        related_name='transaction_links',
        help_text='Factura/asiento (Odoo invoice_ids, lado inverso).',
    )
    transaction = models.ForeignKey(
        'payment.Payment', on_delete=models.CASCADE,
        related_name='invoice_links',
        help_text='Transacción de pago (Odoo transaction_ids).',
    )

    class Meta:
        db_table = 'account_move_transaction_link'
        constraints = [
            models.UniqueConstraint(
                fields=['move', 'transaction'],
                name='unique_move_transaction_link',
            ),
        ]
        verbose_name = 'Enlace factura↔transacción'
        verbose_name_plural = 'Enlaces factura↔transacción'

    def __str__(self) -> str:
        return f'AccountMove#{self.move_id} ↔ Payment#{self.transaction_id}'


class AccountPaymentMethodLineProvider(models.Model):
    """Enlace 1-a-1 de una línea de método de pago con la pasarela que la
    respalda — ≙ ``odoo19c: account_payment/models/
    account_payment_method_line.py:10-16`` (``payment_provider_id``).
    """

    method_line = models.OneToOneField(
        'account.AccountPaymentMethodLine', on_delete=models.CASCADE,
        related_name='provider_link',
        help_text='Línea de método de pago del diario.',
    )
    provider    = models.ForeignKey(
        'payment.PaymentGateway', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='method_lines',
        help_text='Pasarela que procesa esta línea (Odoo payment_provider_id).',
    )

    class Meta:
        db_table = 'account_payment_method_line_provider'
        verbose_name = 'Enlace línea de método↔pasarela'
        verbose_name_plural = 'Enlaces línea de método↔pasarela'

    def __str__(self) -> str:
        return f'AccountPaymentMethodLine#{self.method_line_id} ↔ PaymentGateway#{self.provider_id}'


class PaymentGatewayJournal(models.Model):
    """Enlace 1-a-1 de una pasarela con el diario donde postea sus pagos
    exitosos — ≙ ``odoo19c: account_payment/models/payment_provider.py:
    10-19`` (``journal_id``).

    Divergencia declarada: la referencia computa este campo
    (``_compute_journal_id``) buscando/creando una línea de método de pago
    elegible y cae a un diario tipo ``bank`` de la compañía si el proveedor
    está ``enabled``/``test``. Ese cómputo depende de ``_ensure_payment_
    method_line``, que no se porta (ver ``models/payment_provider.py``,
    sección "No portado") — aquí el campo es de asignación **directa**, sin
    cómputo automático ni el ``_inverse_journal_id`` que sincroniza la línea
    de método. Condición de cierre: cuando ``_ensure_payment_method_line``
    se porte, este campo puede volver a ser derivado.
    """

    gateway = models.OneToOneField(
        'payment.PaymentGateway', on_delete=models.CASCADE,
        related_name='journal_link',
        help_text='La pasarela dueña de este enlace.',
    )
    journal = models.ForeignKey(
        'account.AccountJournal', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='payment_gateways',
        help_text='Diario donde se postean los pagos exitosos de la pasarela.',
    )

    class Meta:
        db_table = 'payment_gateway_journal_link'
        verbose_name = 'Enlace pasarela↔diario'
        verbose_name_plural = 'Enlaces pasarela↔diario'

    def __str__(self) -> str:
        return f'PaymentGateway#{self.gateway_id} ↔ AccountJournal#{self.journal_id}'

"""
Models — apps.finance (MOD-028, capa-3 en arquitectura-tecnica/modulos/finance).

Primer slice del modulo financiero: ``CashConcept`` (UC-FIN-06), el catalogo
maestro de conceptos de caja que clasifica todo ingreso/egreso. Jerarquico
(``parent``), con cuenta contable (``account``), ``kind`` income/expense y flags
``editable``/``leaf``. Enums/choices en INGLES (canon-idioma).

Entidades restantes del modelo de dominio (GatewaySettlement, CashMovement,
CashClose, CarrierInvoice, CashFlowProjection, PeriodClose) llegan en slices
posteriores del loop.
"""
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class CashConceptKind(models.TextChoices):
    """Clase del concepto de caja (UC-FIN-06)."""
    INCOME = 'income', 'Ingreso'
    EXPENSE = 'expense', 'Egreso'


class CashConcept(TimeStampedModel):
    """Concepto de caja del catalogo (UC-FIN-06).

    ``code`` y ``kind`` son inmutables una vez creado el concepto (para no
    reinterpretar la clasificacion historica). El catalogo es jerarquico:
    un concepto ``leaf`` cuelga de una categoria via ``parent``.
    """
    code = models.CharField(
        max_length=64, unique=True,
        verbose_name='Codigo',
        help_text='Codigo unico e inmutable del concepto (p. ej. FREIGHT_OUT).',
    )
    name = models.CharField(max_length=160, verbose_name='Nombre')
    kind = models.CharField(
        max_length=8, choices=CashConceptKind.choices,
        verbose_name='Clase',
        help_text='income (ingreso) o expense (egreso); inmutable tras crear.',
    )
    parent = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='children', verbose_name='Concepto padre',
    )
    account = models.CharField(
        max_length=32, blank=True, default='',
        verbose_name='Cuenta contable',
        help_text='Cuenta contable asociada (opcional).',
    )
    editable = models.BooleanField(
        default=True, verbose_name='Editable',
        help_text='Un concepto de sistema (False) no admite cambios.',
    )
    leaf = models.BooleanField(
        default=True, verbose_name='Hoja',
        help_text='True si es el ultimo nivel (clasifica movimientos).',
    )
    active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        db_table = 'finance_cash_concept'
        ordering = ['kind', 'code']
        verbose_name = 'Concepto de caja'
        verbose_name_plural = 'Conceptos de caja'

    def __str__(self):
        return f'{self.code} ({self.kind})'

    def is_used(self):
        """¿El concepto esta referenciado por algun movimiento de caja?

        Habilita el gate ``CONCEPT_IN_USE`` del borrado fisico (UC-FIN-06 EX-03):
        un concepto con al menos un ``CashMovement`` no se puede borrar, solo
        desactivar. (Cierra H-API-FIN-01.)
        """
        return self.movements.exists()


class SettlementStatus(models.TextChoices):
    """Estado de una liquidacion del gateway (UC-FIN-01)."""
    IMPORTED = 'imported', 'Importada'
    VALIDATED = 'validated', 'Validada'
    RECONCILED = 'reconciled', 'Conciliada'


class SettlementLineFlag(models.TextChoices):
    """Marca por linea de la liquidacion (UC-FIN-01)."""
    MATCHED = 'matched', 'Cuadrada'
    DISCREPANT = 'discrepant', 'Discrepante'
    DUPLICATE = 'duplicate', 'Duplicada'


class GatewaySettlement(TimeStampedModel):
    """Liquidacion del gateway de pago (UC-FIN-01).

    Fuente del **percibido** (base ``settled_at``): ``gross`` bruto, ``fee``
    comision del gateway, ``net`` neto liberado. Gateway-agnostico via
    ``adapter`` (MercadoPago hoy es un adaptador).
    """
    adapter = models.CharField(max_length=32, verbose_name='Adaptador')
    gateway_ref = models.CharField(
        max_length=128, unique=True, verbose_name='Referencia del gateway',
    )
    gross = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Bruto')
    fee = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Comision')
    net = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Neto')
    settled_at = models.DateTimeField(verbose_name='Fecha de liberacion')
    status = models.CharField(
        max_length=12, choices=SettlementStatus.choices,
        default=SettlementStatus.IMPORTED, verbose_name='Estado',
    )
    payment = models.ForeignKey(
        'payments.Payment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='settlements', verbose_name='Pago',
    )

    class Meta:
        db_table = 'finance_gateway_settlement'
        ordering = ['-settled_at']
        verbose_name = 'Liquidacion del gateway'
        verbose_name_plural = 'Liquidaciones del gateway'

    def __str__(self):
        return f'{self.gateway_ref} ({self.status})'

    def reconcile(self):
        """Marca la liquidacion como conciliada (UC-FIN-01 POST)."""
        self.status = SettlementStatus.RECONCILED
        self.save(update_fields=['status', 'updated_at'])


class GatewaySettlementLine(TimeStampedModel):
    """Linea de una liquidacion con su marca de cuadre (UC-FIN-01)."""
    settlement = models.ForeignKey(
        GatewaySettlement, on_delete=models.CASCADE, related_name='lines',
        verbose_name='Liquidacion',
    )
    flag = models.CharField(
        max_length=12, choices=SettlementLineFlag.choices,
        default=SettlementLineFlag.MATCHED, verbose_name='Marca',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Importe')

    class Meta:
        db_table = 'finance_gateway_settlement_line'
        verbose_name = 'Linea de liquidacion'
        verbose_name_plural = 'Lineas de liquidacion'


class CarrierInvoiceStatus(models.TextChoices):
    """Estado del flete por pagar al transportista (UC-FIN-03)."""
    PAYABLE = 'payable', 'Por pagar'
    PAID = 'paid', 'Pagado'
    DISPUTED = 'disputed', 'En disputa'


class CarrierInvoice(TimeStampedModel):
    """Flete por pagar al transportista (UC-FIN-03).

    ``free_shipping_subsidy`` = parte del flete que el negocio subsidia por la
    politica de envio gratis. ``payable`` -> ``paid`` (o ``disputed``).
    """
    carrier = models.CharField(max_length=64, verbose_name='Transportista')
    gross = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Importe')
    free_shipping_subsidy = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Subsidio envio gratis',
    )
    status = models.CharField(
        max_length=8, choices=CarrierInvoiceStatus.choices,
        default=CarrierInvoiceStatus.PAYABLE, verbose_name='Estado',
    )
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de pago')

    class Meta:
        db_table = 'finance_carrier_invoice'
        ordering = ['-created_at']
        verbose_name = 'Flete por pagar'
        verbose_name_plural = 'Fletes por pagar'

    def __str__(self):
        return f'{self.carrier} {self.gross} ({self.status})'

    def pay(self):
        """Marca el flete como pagado (UC-FIN-03, ``finance.disburse``)."""
        self.status = CarrierInvoiceStatus.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=['status', 'paid_at', 'updated_at'])


class CashMovement(TimeStampedModel):
    """Movimiento de caja individual (ingreso/egreso), clasificado por concepto.

    Ligado a su origen: una liquidacion del gateway (``settlement``) hoy;
    ``carrier_invoice`` / ``cash_close`` cuando esos modelos aterricen.
    """
    concept = models.ForeignKey(
        CashConcept, on_delete=models.PROTECT, related_name='movements',
        verbose_name='Concepto',
    )
    kind = models.CharField(
        max_length=8, choices=CashConceptKind.choices, verbose_name='Clase',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Importe')
    occurred_at = models.DateTimeField(verbose_name='Fecha del movimiento')
    settlement = models.ForeignKey(
        GatewaySettlement, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='movements', verbose_name='Liquidacion origen',
    )

    class Meta:
        db_table = 'finance_cash_movement'
        ordering = ['-occurred_at']
        verbose_name = 'Movimiento de caja'
        verbose_name_plural = 'Movimientos de caja'

    def __str__(self):
        return f'{self.concept.code} {self.kind} {self.amount}'

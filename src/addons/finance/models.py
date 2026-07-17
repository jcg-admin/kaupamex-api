"""
Models — addons.finance (MOD-028, capa-3 en arquitectura-tecnica/modulos/finance).

Primer slice del modulo financiero: ``CashConcept`` (UC-FIN-06), el catalogo
maestro de conceptos de caja que clasifica todo ingreso/egreso. Jerarquico
(``parent``), con cuenta contable (``account``), ``kind`` income/expense y flags
``editable``/``leaf``. Enums/choices en INGLES (canon-idioma).

Entidades restantes del modelo de dominio (GatewaySettlement, CashMovement,
CashClose, CarrierInvoice, CashFlowProjection, PeriodClose) llegan en slices
posteriores del loop.
"""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from core.models import TimeStampedModel


def _day_bounds(business_date):
    """Rango [inicio, fin) del dia en la tz activa, robusto sin tz-tables MySQL.

    Evita el lookup ``__date`` (que exige las tablas de zona horaria de MySQL
    cuando ``USE_TZ`` esta activo): filtra por rango de ``DateTimeField``.
    """
    start = timezone.make_aware(datetime.combine(business_date, time.min))
    return start, start + timedelta(days=1)


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


class CashCloseStatus(models.TextChoices):
    """Estado del corte de caja diario (UC-FIN-02).

    ``open`` -> ``balanced`` (arqueo cuadrado) -> ``sealed`` (aprobado y sellado,
    inmutable) -> ``reopened`` (reapertura autorizada, vuelve a ``balanced``).
    """
    OPEN = 'open', 'Abierto'
    BALANCED = 'balanced', 'Cuadrado'
    SEALED = 'sealed', 'Sellado'
    REOPENED = 'reopened', 'Reabierto'


class CashClose(TimeStampedModel):
    """Corte de caja diario (UC-FIN-02, MOD-028).

    Encadena ``opening_balance`` (saldo del corte sellado anterior) ->
    ``closing_balance``. La **segregacion de funciones** exige
    ``prepared_by`` != ``approved_by``: quien prepara el arqueo no puede
    aprobar/sellar su propio corte. Un ``sealed`` es inmutable; solo
    ``finance.close`` puede reabrirlo (``reopened``) dejando rastro.
    """
    business_date = models.DateField(verbose_name='Fecha de negocio')
    status = models.CharField(
        max_length=10, choices=CashCloseStatus.choices,
        default=CashCloseStatus.OPEN, verbose_name='Estado',
    )
    opening_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Saldo inicial',
    )
    counted_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Saldo contado (arqueo)',
    )
    closing_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Saldo final',
    )
    discrepancy = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Diferencia',
        help_text='contado - esperado; distinto de 0 = corte con diferencia (Alt A).',
    )
    note = models.TextField(
        blank=True, default='', verbose_name='Nota del aprobador',
        help_text='Justificacion de la diferencia al aprobar (Alt A).',
    )
    reopen_reason = models.TextField(
        blank=True, default='', verbose_name='Motivo de reapertura',
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cash_closes_prepared', verbose_name='Preparado por',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cash_closes_approved', verbose_name='Aprobado por',
    )
    sealed_at = models.DateTimeField(null=True, blank=True, verbose_name='Sellado en')

    class Meta:
        db_table = 'finance_cash_close'
        ordering = ['-business_date']
        verbose_name = 'Corte de caja'
        verbose_name_plural = 'Cortes de caja'

    def __str__(self):
        return f'CashClose {self.business_date} ({self.status})'

    def expected_balance(self):
        """Saldo esperado del cierre (UC-FIN-02 paso 3, base percibido).

        ``opening_balance`` + neto de las liquidaciones **conciliadas** del dia
        - egresos (``CashMovement`` de tipo ``expense``) del dia. La comparacion
        contra el contado produce la ``discrepancy``.
        """
        start, end = _day_bounds(self.business_date)
        net_income = GatewaySettlement.objects.filter(
            settled_at__gte=start, settled_at__lt=end,
            status=SettlementStatus.RECONCILED,
        ).aggregate(total=Sum('net'))['total'] or Decimal('0.00')
        expenses = CashMovement.objects.filter(
            occurred_at__gte=start, occurred_at__lt=end,
            kind=CashConceptKind.EXPENSE,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        return self.opening_balance + net_income - expenses

    def has_unreconciled_settlements(self):
        """¿Quedan liquidaciones del dia sin conciliar? (UC-FIN-02 EX-03).

        Gate previo al sello: no se sella un corte con liquidaciones del periodo
        que no esten ``reconciled``.
        """
        start, end = _day_bounds(self.business_date)
        return GatewaySettlement.objects.filter(
            settled_at__gte=start, settled_at__lt=end,
        ).exclude(status=SettlementStatus.RECONCILED).exists()

    def arqueo(self, counted_balance):
        """Arma el arqueo y cuadra el corte (UC-FIN-02 pasos 2-3).

        Fija ``counted_balance`` = ``closing_balance``, calcula la
        ``discrepancy`` contra el esperado y pasa a ``balanced``.
        """
        expected = self.expected_balance()
        self.counted_balance = counted_balance
        self.closing_balance = counted_balance
        self.discrepancy = counted_balance - expected
        self.status = CashCloseStatus.BALANCED
        self.save(update_fields=[
            'counted_balance', 'closing_balance', 'discrepancy', 'status',
            'updated_at',
        ])

    def approve(self, approver, note=''):
        """Registra la aprobacion por un segundo usuario (UC-FIN-02 paso 5).

        La validacion SoD (``approver`` != ``prepared_by``) la hace la vista
        antes de llamar aqui. El corte queda ``balanced`` con ``approved_by``.
        """
        self.approved_by = approver
        if note:
            self.note = note
        self.save(update_fields=['approved_by', 'note', 'updated_at'])

    def seal(self):
        """Sella el corte (UC-FIN-02 paso 6): ``balanced`` -> ``sealed``.

        El sello es inmutable; ``sealed_at`` marca el momento.
        """
        self.status = CashCloseStatus.SEALED
        self.sealed_at = timezone.now()
        self.save(update_fields=['status', 'sealed_at', 'updated_at'])

    def reopen(self, reason):
        """Reapertura autorizada (UC-FIN-02 Alt B): ``sealed`` -> ``reopened``.

        Exige ``finance.close`` y motivo; el corte vuelve a ``balanced`` para
        correccion. Aqui deja el estado ``reopened`` con el ``reason``; el
        re-cuadre posterior lo devuelve a ``balanced`` via ``arqueo``.
        """
        self.status = CashCloseStatus.REOPENED
        self.reopen_reason = reason
        self.save(update_fields=['status', 'reopen_reason', 'updated_at'])


class ProjectionScenario(models.TextChoices):
    """Escenario del presupuesto de caja proyectado (UC-FIN-05)."""
    BASE = 'base', 'Base'
    OPTIMISTIC = 'optimistic', 'Optimista'
    PESSIMISTIC = 'pessimistic', 'Pesimista'


class ProjectionGranularity(models.TextChoices):
    """Granularidad del sub-periodo de proyeccion (UC-FIN-05)."""
    WEEK = 'week', 'Semana'
    MONTH = 'month', 'Mes'


#: Multiplicador de ingresos por escenario (UC-FIN-05 Alt B). ``base`` = 1;
#: optimista/pesimista mueven el run-rate de ingresos +/- 15%.
_SCENARIO_INCOME_MULT = {
    ProjectionScenario.BASE: Decimal('1.00'),
    ProjectionScenario.OPTIMISTIC: Decimal('1.15'),
    ProjectionScenario.PESSIMISTIC: Decimal('0.85'),
}


class CashFlowProjection(TimeStampedModel):
    """Presupuesto de caja proyectado por metodo directo (UC-FIN-05).

    Base **percibido** (cash-basis): parte de la ``opening_balance`` (caja
    inicial), suma ingresos y resta egresos por sub-periodo, y **encadena** la
    ``closing_balance`` de un sub-periodo como ``opening_balance`` del siguiente
    (rolling). Los supuestos (``income_per_period`` / ``expense_per_period`` /
    ``min_balance``) viven en ``assumptions``; el ``scenario`` aplica un
    multiplicador al run-rate de ingresos.

    Adaptacion nativa (DEC-KX-03; H-API-FIN-03). El analogo real en Odoo19
    enterprise es ``account_budget`` (OEEL-1): ``budget.analytic`` (nombre +
    rango de fechas + ``state`` + ``budget_type`` + responsable ``user_id``) y
    ``budget.line`` (``budget_amount`` planeado vs ``achieved_amount`` real vs
    ``theoritical_amount`` pro-rata). De ahi se **reimplementa nativo** (no se
    copia OEEL-1): ``name`` + ``created_by`` (= responsable) + ``assumptions``
    (monto planeado por sub-periodo = ``budget_amount``). Pero ``account_budget``
    es **variance hacia atras** (planeado vs logrado sobre un periodo fijo); UC-
    FIN-05 agrega lo que Odoo **no** trae: el **encadenamiento rolling de caja**
    (``opening -> closing`` por sub-periodo) y el **marcador de deficit**. El
    encadenamiento sigue el patron de ``pos.session`` (LGPL-3;
    ``cash_register_balance_start = last.balance_end_real``), que tambien
    sustenta ``CashClose`` (UC-FIN-02). ``project_forecast`` es planeacion de
    recursos HR y ``account_reports`` Cash Flow es un reporte hacia atras —
    ninguno es una proyeccion de liquidez.
    """
    name = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Nombre del escenario',
    )
    scenario = models.CharField(
        max_length=12, choices=ProjectionScenario.choices,
        default=ProjectionScenario.BASE, verbose_name='Escenario',
    )
    horizon = models.PositiveIntegerField(
        verbose_name='Horizonte (nº de sub-periodos)',
    )
    granularity = models.CharField(
        max_length=8, choices=ProjectionGranularity.choices,
        default=ProjectionGranularity.WEEK, verbose_name='Granularidad',
    )
    opening_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Caja inicial',
    )
    assumptions = models.JSONField(
        default=dict, blank=True, verbose_name='Supuestos',
        help_text='income_per_period / expense_per_period / min_balance.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cash_flow_projections', verbose_name='Creado por',
    )

    class Meta:
        db_table = 'finance_cash_flow_projection'
        ordering = ['-created_at']
        verbose_name = 'Proyeccion de flujo de caja'
        verbose_name_plural = 'Proyecciones de flujo de caja'

    def __str__(self):
        return f'{self.name or "proyeccion"} ({self.scenario}, {self.horizon}{self.granularity[0]})'

    def build(self):
        """Construye la proyeccion rolling por sub-periodo (UC-FIN-05 paso 4-5).

        Devuelve un dict con la lista de ``periods`` (cada uno con
        ``opening_balance`` / ``income`` / ``expense`` / ``closing_balance``) y
        el ``deficit_index`` = primer sub-periodo cuya ``closing_balance`` cruza
        por debajo del ``min_balance`` (``None`` si nunca ocurre).
        """
        a = self.assumptions or {}
        income = Decimal(str(a.get('income_per_period', '0')))
        expense = Decimal(str(a.get('expense_per_period', '0')))
        min_balance = Decimal(str(a.get('min_balance', '0')))
        mult = _SCENARIO_INCOME_MULT.get(self.scenario, Decimal('1.00'))
        cent = Decimal('0.01')

        periods = []
        deficit_index = None
        balance = self.opening_balance
        for i in range(self.horizon):
            opening = balance
            period_income = (income * mult).quantize(cent)
            closing = (opening + period_income - expense).quantize(cent)
            if deficit_index is None and closing < min_balance:
                deficit_index = i
            periods.append({
                'index': i,
                'opening_balance': str(opening.quantize(cent)),
                'income': str(period_income),
                'expense': str(expense.quantize(cent)),
                'closing_balance': str(closing),
            })
            balance = closing
        return {
            'scenario': self.scenario,
            'granularity': self.granularity,
            'horizon': self.horizon,
            'periods': periods,
            'deficit_index': deficit_index,
        }

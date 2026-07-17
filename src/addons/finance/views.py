"""
Views — addons.finance (UC-FIN-06 CashConcept CRUD).

Gateado por el recurso graduado ``finance`` (DEC-11): listar/ver = ``finance.view``,
crear/editar/desactivar = ``finance.edit``, borrar = ``finance.full``. Usa la
azucar de authz (``HasCapability`` + ``permission_map``).
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet, ViewSet
from django.utils import timezone

from addons.authz.permissions import HasCapability
from addons.finance.availability import AvailabilityQuery
from addons.finance.exceptions import (
    BackupRequired, CashCloseAlreadyOpen, CashCloseSealed, ConceptInUse,
    OutOfOrderClose, PeriodInvalidState, PeriodOpenMovements,
    SettlementsNotReconciled, SodViolation,
)
from addons.finance.models import (
    CarrierInvoice, CashClose, CashCloseStatus, CashConcept, CashFlowProjection,
    GatewaySettlement, PeriodClose, PeriodCloseStatus,
)
from addons.finance.serializers import (
    CarrierInvoiceSerializer, CashCloseApproveSerializer, CashCloseArqueoSerializer,
    CashCloseReopenSerializer, CashCloseSerializer, CashConceptSerializer,
    CashFlowProjectionSerializer, GatewaySettlementSerializer,
    PeriodCloseCloseSerializer, PeriodCloseReopenSerializer, PeriodCloseSerializer,
)


class CashConceptViewSet(ModelViewSet):
    """CRUD del catalogo de conceptos de caja (UC-FIN-06).

    Filtros de query: ``kind`` (income/expense) y ``active`` (true/false).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    permission_map = {
        'list': 'finance.view',
        'retrieve': 'finance.view',
        'create': 'finance.edit',
        'update': 'finance.edit',
        'partial_update': 'finance.edit',
        'destroy': 'finance.full',
    }
    serializer_class = CashConceptSerializer
    queryset = CashConcept.objects.all()
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        kind = self.request.query_params.get('kind')
        if kind:
            qs = qs.filter(kind=kind)
        active = self.request.query_params.get('active')
        if active is not None:
            qs = qs.filter(active=(active.lower() == 'true'))
        return qs

    def perform_destroy(self, instance):
        # Borrado fisico solo si el concepto nunca se uso (UC-FIN-06 EX-03).
        # is_used() consulta CashMovement (H-API-FIN-01 cerrado).
        if instance.is_used():
            raise ConceptInUse()
        instance.delete()


class GatewaySettlementViewSet(ReadOnlyModelViewSet):
    """Conciliacion de liquidaciones del gateway (UC-FIN-01).

    Listar/ver = ``finance.view``; la accion ``reconcile`` exige la accion SoD
    ``finance.reconcile`` (segregacion de funciones, DEC-11).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    permission_map = {
        'list': 'finance.view',
        'retrieve': 'finance.view',
        'reconcile': 'finance.reconcile',
    }
    serializer_class = GatewaySettlementSerializer
    queryset = GatewaySettlement.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        status_q = self.request.query_params.get('status')
        if status_q:
            qs = qs.filter(status=status_q)
        return qs

    @action(detail=True, methods=['post'])
    def reconcile(self, request, pk=None):
        """Marca la liquidacion como ``reconciled`` (UC-FIN-01)."""
        settlement = self.get_object()
        settlement.reconcile()
        return Response(self.get_serializer(settlement).data)


class CarrierInvoiceViewSet(ModelViewSet):
    """Flete por pagar al transportista (UC-FIN-03).

    Listar/ver = ``finance.view``; registrar (``create``) y pagar (``pay``)
    exigen la accion SoD ``finance.disburse`` (salida de dinero).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    permission_map = {
        'list': 'finance.view',
        'retrieve': 'finance.view',
        'create': 'finance.disburse',
        'pay': 'finance.disburse',
    }
    serializer_class = CarrierInvoiceSerializer
    queryset = CarrierInvoice.objects.all()
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        status_q = self.request.query_params.get('status')
        if status_q:
            qs = qs.filter(status=status_q)
        return qs

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """Marca el flete como ``paid`` (UC-FIN-03, ``finance.disburse``)."""
        invoice = self.get_object()
        invoice.pay()
        return Response(self.get_serializer(invoice).data)


class CashCloseViewSet(ModelViewSet):
    """Corte de caja diario (UC-FIN-02).

    Segregacion de funciones (SoD): preparar/arquear = ``finance.record``;
    aprobar/sellar/reabrir = ``finance.close``. Quien prepara **no** puede
    aprobar/sellar su propio corte (``prepared_by`` != ``approved_by``).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    permission_map = {
        'list': 'finance.view',
        'retrieve': 'finance.view',
        'create': 'finance.record',
        'arqueo': 'finance.record',
        'approve': 'finance.close',
        'seal': 'finance.close',
        'reopen': 'finance.close',
    }
    serializer_class = CashCloseSerializer
    queryset = CashClose.objects.all()
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        status_q = self.request.query_params.get('status')
        if status_q:
            qs = qs.filter(status=status_q)
        business_date = self.request.query_params.get('business_date')
        if business_date:
            qs = qs.filter(business_date=business_date)
        return qs

    def perform_create(self, serializer):
        # EX-06: no se abre un segundo corte sin sellar para la misma fecha.
        business_date = serializer.validated_data['business_date']
        if CashClose.objects.filter(business_date=business_date).exclude(
            status=CashCloseStatus.SEALED,
        ).exists():
            raise CashCloseAlreadyOpen()
        serializer.save(prepared_by=self.request.user)

    @action(detail=True, methods=['post'])
    def arqueo(self, request, pk=None):
        """Arma el arqueo y cuadra el corte (UC-FIN-02 pasos 2-3)."""
        close = self.get_object()
        if close.status == CashCloseStatus.SEALED:
            raise CashCloseSealed()
        body = CashCloseArqueoSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        close.arqueo(body.validated_data['counted_balance'])
        return Response(self.get_serializer(close).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Registra la aprobacion por un segundo usuario (UC-FIN-02 paso 5).

        EX-01: ``approved_by`` != ``prepared_by`` (SoD) o ``SOD_VIOLATION``.
        """
        close = self.get_object()
        if close.status == CashCloseStatus.SEALED:
            raise CashCloseSealed()
        if close.prepared_by_id == request.user.id:
            raise SodViolation()
        body = CashCloseApproveSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        close.approve(request.user, note=body.validated_data.get('note', ''))
        return Response(self.get_serializer(close).data)

    @action(detail=True, methods=['post'])
    def seal(self, request, pk=None):
        """Sella el corte (UC-FIN-02 paso 6): ``balanced`` -> ``sealed``.

        EX-02: un ``sealed`` es inmutable (``CASH_CLOSE_SEALED``). El sello exige
        un aprobador distinto en registro (SoD); sin ``approved_by`` -> EX-01
        ``SOD_VIOLATION``. EX-03: liquidaciones del dia sin conciliar ->
        ``SETTLEMENTS_NOT_RECONCILED``.
        """
        close = self.get_object()
        if close.status == CashCloseStatus.SEALED:
            raise CashCloseSealed()
        if close.approved_by_id is None:
            raise SodViolation('El corte debe ser aprobado por un segundo usuario antes de sellar.')
        if close.has_unreconciled_settlements():
            raise SettlementsNotReconciled()
        close.seal()
        return Response(self.get_serializer(close).data)

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        """Reapertura autorizada (UC-FIN-02 Alt B): ``sealed`` -> ``reopened``."""
        close = self.get_object()
        body = CashCloseReopenSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        close.reopen(body.validated_data['reason'])
        return Response(self.get_serializer(close).data)


class CashFlowProjectionViewSet(ModelViewSet):
    """Proyeccion de flujo de caja (UC-FIN-05).

    Proyectar/consultar = ``finance.view``; **guardar** un escenario =
    ``finance.edit`` (DEC-11). ``compute`` calcula una proyeccion transitoria
    (sin persistir); ``create`` guarda el escenario.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    permission_map = {
        'list': 'finance.view',
        'retrieve': 'finance.view',
        'compute': 'finance.view',
        'create': 'finance.edit',
    }
    serializer_class = CashFlowProjectionSerializer
    queryset = CashFlowProjection.objects.all()
    http_method_names = ['get', 'post', 'head', 'options']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'])
    def compute(self, request):
        """Proyecta sin persistir (UC-FIN-05, ``finance.view``).

        Valida el input con el mismo serializer (choices de ``scenario`` /
        ``granularity``) y devuelve ``build()`` de una instancia transitoria.
        """
        body = self.get_serializer(data=request.data)
        body.is_valid(raise_exception=True)
        proj = CashFlowProjection(**body.validated_data)
        return Response(proj.build())


class PeriodCloseViewSet(ReadOnlyModelViewSet):
    """Cierre de ejercicio anual (UC-FIN-08).

    ``ver`` = ``finance.view`` (piso); ``close``/``reopen`` = accion SoD
    ``finance.close`` (FULL). La **reautenticacion** (DEC-12) sobre esas dos
    acciones la aplica la capa authz (``HasCapability`` -> ``assert_session_fresh``)
    cuando ``finance.close`` esta sembrada ``is_sensitive`` — no se cablea aqui.

    El lookup es por ``fiscal_year`` (``/period-closes/{year}/close``). El cierre
    es sellante y transaccional: ``close`` verifica precondiciones y delega en
    ``PeriodClose.seal`` (que congela el saldo y abre el siguiente en una
    transaccion).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    permission_map = {
        'list': 'finance.view',
        'retrieve': 'finance.view',
        'close': 'finance.close',
        'reopen': 'finance.close',
    }
    serializer_class = PeriodCloseSerializer
    queryset = PeriodClose.objects.all()
    lookup_field = 'fiscal_year'

    @action(detail=True, methods=['post'])
    def close(self, request, fiscal_year=None):
        """Cierra el ejercicio y abre el siguiente (UC-FIN-08 PARTE 3).

        Orden de verificacion: idempotencia/estado (EX-05) -> backup (EX-07) ->
        orden cronologico (EX-04) -> pendientes (EX-03) -> sello transaccional.
        """
        period = self.get_object()
        body = PeriodCloseCloseSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        key = body.validated_data['idempotency_key']

        if period.status == PeriodCloseStatus.SEALED:
            # Alt C / AC-04: mismo key -> idempotente (devuelve el primer cierre);
            # otro key sobre un sellado -> INVALID_STATE (EX-05).
            if period.idempotency_key and period.idempotency_key == key:
                nxt = PeriodClose.objects.filter(fiscal_year=period.fiscal_year + 1).first()
                return Response(self._close_payload(period, nxt))
            raise PeriodInvalidState('El ejercicio ya esta cerrado.')

        if not body.validated_data['backup_confirmed']:
            raise BackupRequired()
        if period.has_earlier_open_period():
            raise OutOfOrderClose()
        if period.has_open_movements():
            raise PeriodOpenMovements()

        nxt = period.seal(sealed_by=request.user, idempotency_key=key)
        return Response(self._close_payload(period, nxt))

    @action(detail=True, methods=['post'])
    def reopen(self, request, fiscal_year=None):
        """Reabre un ejercicio cerrado (UC-FIN-08 Alt B, alto control).

        Solo un ejercicio ``sealed`` se reabre; reabrir uno ``open`` ->
        INVALID_STATE (EX-05).
        """
        period = self.get_object()
        if period.status != PeriodCloseStatus.SEALED:
            raise PeriodInvalidState('El ejercicio no esta cerrado.')
        body = PeriodCloseReopenSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        period.reopen(reopened_by=request.user, reason=body.validated_data['reason'])
        return Response(self.get_serializer(period).data)

    def _close_payload(self, sealed, nxt):
        """Respuesta del cierre: ejercicio sellado + ejercicio siguiente abierto."""
        return {
            'sealed': self.get_serializer(sealed).data,
            'next': self.get_serializer(nxt).data if nxt else None,
        }


class AvailabilityViewSet(ViewSet):
    """Disponibilidad caja vs banco (UC-FIN-04), consulta de solo lectura.

    Todos los endpoints exigen ``finance.view`` (DEC-11) y son ``GET``: KPIs
    (``list``), serie diaria (``series``) y pivote (``pivot``). No es un modelo:
    la disponibilidad es un **valor derivado** que ``AvailabilityQuery`` agrega
    del percibido conciliado − egresos + saldo previo. ``period`` = ``YYYY-MM``
    (por defecto el mes en curso); mal formado → ``INVALID_PERIOD`` (400).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    permission_map = {
        'list': 'finance.view',
        'series': 'finance.view',
        'pivot': 'finance.view',
    }

    def _query(self, request):
        period = request.query_params.get('period') or timezone.localtime().strftime('%Y-%m')
        return AvailabilityQuery(period)

    def list(self, request):
        """KPIs del periodo (percibido, egresos, saldo actual, mínimo, estado)."""
        return Response(self._query(request).kpis())

    @action(detail=False, methods=['get'])
    def series(self, request):
        """Serie diaria de recaudación caja vs banco (UC-FIN-04 paso 4)."""
        return Response(self._query(request).series())

    @action(detail=False, methods=['get'])
    def pivot(self, request):
        """Pivote concepto x periodo (UC-FIN-04 paso 5)."""
        return Response(self._query(request).pivot())

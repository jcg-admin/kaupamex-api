"""
Views — apps.addons.finance (UC-FIN-06 CashConcept CRUD).

Gateado por el recurso graduado ``finance`` (DEC-11): listar/ver = ``finance.view``,
crear/editar/desactivar = ``finance.edit``, borrar = ``finance.full``. Usa la
azucar de authz (``HasCapability`` + ``permission_map``).
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.platform.authz.permissions import HasCapability
from apps.addons.finance.exceptions import (
    CashCloseAlreadyOpen, CashCloseSealed, ConceptInUse, SettlementsNotReconciled,
    SodViolation,
)
from apps.addons.finance.models import (
    CarrierInvoice, CashClose, CashCloseStatus, CashConcept, GatewaySettlement,
)
from apps.addons.finance.serializers import (
    CarrierInvoiceSerializer, CashCloseApproveSerializer, CashCloseArqueoSerializer,
    CashCloseReopenSerializer, CashCloseSerializer, CashConceptSerializer,
    GatewaySettlementSerializer,
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

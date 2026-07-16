"""
Views — apps.finance (UC-FIN-06 CashConcept CRUD).

Gateado por el recurso graduado ``finance`` (DEC-11): listar/ver = ``finance.view``,
crear/editar/desactivar = ``finance.edit``, borrar = ``finance.full``. Usa la
azucar de authz (``HasCapability`` + ``permission_map``).
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.authz.permissions import HasCapability
from apps.finance.exceptions import ConceptInUse
from apps.finance.models import CarrierInvoice, CashConcept, GatewaySettlement
from apps.finance.serializers import (
    CarrierInvoiceSerializer, CashConceptSerializer, GatewaySettlementSerializer,
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

"""
Views — apps.finance (UC-FIN-06 CashConcept CRUD).

Gateado por el recurso graduado ``finance`` (DEC-11): listar/ver = ``finance.view``,
crear/editar/desactivar = ``finance.edit``, borrar = ``finance.full``. Usa la
azucar de authz (``HasCapability`` + ``permission_map``).
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from apps.authz.permissions import HasCapability
from apps.finance.exceptions import ConceptInUse
from apps.finance.models import CashConcept
from apps.finance.serializers import CashConceptSerializer


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
        # Mientras no exista CashMovement, is_used() es False (ver modelo).
        if instance.is_used():
            raise ConceptInUse()
        instance.delete()

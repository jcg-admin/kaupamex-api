"""Views — apps.platform.company (consola L0 del operador Kaupamex).

Directorio de companies L1 de solo lectura bajo ``/api/v2/platform/companies/``
(UC-PLT-12). El operador L0 (Kaupamex) es **cross-company** por definición:
NO se filtra el queryset por company — el operador ve todas las companies de la
plataforma.

**Scope por acción (least-privilege).** La lectura del directorio se gobierna
con ``platform.view``; la escritura (crear/suspender/reactivar) se reserva a
``platform.provision`` (regla de negocio del mockup: "solo platform.provision
crea/suspende"). Gatear un endpoint mutante con una sola capacidad "de
operador" abriría una ventana de seguridad (una capacidad de lectura
concediendo escritura); por eso read/write son capacidades distintas
—``HasCapability`` ya soporta el mapeo por acción vía ``permission_map``. La
elevación temporal auditada (sudo/StaffSession, DEC-12) es una capa adicional,
no sustituye a la capacidad.

Identificadores + claves JSON en inglés (DEC-DOC-005).
"""
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.platform.authz.permissions import CapabilityRequiredMixin
from apps.platform.company.models import Company, CompanyModuleSubscription
from apps.platform.company.serializers import (
    CompanyModuleSubscriptionSerializer,
    CompanySerializer,
)


class CompanyViewSet(CapabilityRequiredMixin, ReadOnlyModelViewSet):
    """Directorio de companies para el operador L0 (``list`` + ``retrieve``).

    Fail-closed vía la azúcar ``CapabilityRequiredMixin`` (declara
    ``[IsAuthenticated, HasCapability]``): sin ``platform.view`` → 403. No
    expone escritura en esta rebanada (provisión/suspensión llegan en la
    rebanada de operaciones L0).
    """

    required_capability = 'platform.view'
    serializer_class = CompanySerializer
    queryset = Company.objects.all().order_by('code')
    http_method_names = ['get', 'head', 'options']


class CompanyModuleSubscriptionViewSet(CapabilityRequiredMixin, ModelViewSet):
    """CRUD de suscripciones módulo↔company para el operador L0 (SOL-085 S4).

    Least-privilege por acción (azúcar ``CapabilityRequiredMixin`` +
    ``permission_map``): lectura ``platform.view``; escritura (contratar/
    actualizar/dar de baja) ``platform.provision``. El guard de dependencias
    S3 se valida en el serializer → 400.
    """

    permission_map = {
        'list': 'platform.view',
        'retrieve': 'platform.view',
        'create': 'platform.provision',
        'update': 'platform.provision',
        'partial_update': 'platform.provision',
        'destroy': 'platform.provision',
    }
    serializer_class = CompanyModuleSubscriptionSerializer
    queryset = (
        CompanyModuleSubscription.objects
        .select_related('company', 'module')
        .order_by('company__code', 'module__code')
    )

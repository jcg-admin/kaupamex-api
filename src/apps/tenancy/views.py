"""Views — apps.tenancy (consola L0 del operador Kaupamex).

Directorio de tenants de solo lectura bajo ``/api/v2/platform/tenants/``
(UC-PLT-12). El operador L0 (Kaupamex) es **cross-tenant** por definición:
NO se filtra el queryset por tenant — el operador ve todos los tenants de la
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
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.authz.permissions import HasCapability
from apps.tenancy.models import Tenant
from apps.tenancy.serializers import TenantSerializer


class TenantViewSet(ReadOnlyModelViewSet):
    """Directorio de tenants para el operador L0 (``list`` + ``retrieve``).

    Fail-closed vía ``HasCapability``: sin ``platform.provision`` → 403. No
    expone escritura en esta rebanada (provisión/suspensión llegan en la
    rebanada de operaciones L0).
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'platform.view'
    serializer_class = TenantSerializer
    queryset = Tenant.objects.all().order_by('code')
    http_method_names = ['get', 'head', 'options']

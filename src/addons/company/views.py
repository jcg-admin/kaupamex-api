"""Views — addons.company (consola L0 del operador Kaupamex).

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
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from addons.authz.models import Module
from addons.authz.permissions import CapabilityRequiredMixin
from addons.company.models import (
    Company,
    CompanyModuleSubscription,
    ModulePrice,
)
from addons.company.serializers import (
    CompanyCreateSerializer,
    CompanyModuleSubscriptionSerializer,
    CompanySerializer,
    ModuleCatalogSerializer,
    ModulePriceSerializer,
)


class ModuleCatalogViewSet(CapabilityRequiredMixin, ReadOnlyModelViewSet):
    """Catálogo L0 de módulos (read-only, #179) bajo ``/api/v2/platform/modules/``.

    Lo consume la consola del operador (mockup ``asignar-modulos-kaupamex``)
    para pintar los módulos contratables con su metadata (``is_application``/
    ``tier``/``category``/``depends``). Gateado con ``platform.view`` (la
    escritura del catálogo es del operador Kaupamex, fuera de esta rebanada).
    """

    required_capability = 'platform.view'
    serializer_class = ModuleCatalogSerializer
    queryset = Module.objects.all().prefetch_related('depends').order_by('category', 'code')
    http_method_names = ['get', 'head', 'options']


class ModulePriceViewSet(CapabilityRequiredMixin, ModelViewSet):
    """CRUD de tarifas L0 (``ModulePrice``) para el operador Kaupamex (S4).

    Least-privilege por acción: lectura ``platform.view``; escritura (sembrar/
    versionar tarifas) ``platform.provision``. Es la contraparte del price-copy:
    lo que el operador siembra aquí es lo que una suscripción congela al
    contratar (``CompanyModuleSubscription.apply_current_price``).
    """

    permission_map = {
        'list': 'platform.view',
        'retrieve': 'platform.view',
        'create': 'platform.provision',
        'update': 'platform.provision',
        'partial_update': 'platform.provision',
        'destroy': 'platform.provision',
    }
    serializer_class = ModulePriceSerializer
    queryset = ModulePrice.objects.select_related('module').all()


class CompanyViewSet(CapabilityRequiredMixin, ModelViewSet):
    """Directorio + ciclo de vida de companies para el operador L0 (UC-PLT-12).

    Least-privilege por acción (``permission_map``): lectura ``platform.view``;
    escritura (alta + suspender/reactivar) ``platform.provision``. No hay
    ``update``/``destroy``: el tenant no se edita ni se borra físicamente por
    esta consola (``PROTECT`` en las FKs hijas; el "cancelado" es un delete
    lógico vía ``status``). Alta con estado forzado ``trial``.
    """

    permission_map = {
        'list': 'platform.view',
        'retrieve': 'platform.view',
        'create': 'platform.provision',
        'suspend': 'platform.provision',
        'reactivate': 'platform.provision',
    }
    queryset = Company.objects.all().order_by('code')
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyCreateSerializer
        return CompanySerializer

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        company = self.get_object()
        if company.is_system:
            raise ValidationError({
                'detail': 'No se puede suspender la company de sistema.',
                'codigo_error': 'SYSTEM_COMPANY_PROTECTED',
            })
        if company.status not in (Company.Status.ACTIVE, Company.Status.TRIAL):
            raise ValidationError({
                'detail': 'Solo un tenant activo o en prueba puede suspenderse.',
                'codigo_error': 'INVALID_STATUS_TRANSITION',
            })
        company.status = Company.Status.SUSPENDED
        company.save(update_fields=['status', 'updated_at'])
        return Response(CompanySerializer(company).data)

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        company = self.get_object()
        if company.status != Company.Status.SUSPENDED:
            raise ValidationError({
                'detail': 'Solo un tenant suspendido puede reactivarse.',
                'codigo_error': 'INVALID_STATUS_TRANSITION',
            })
        company.status = Company.Status.ACTIVE
        company.save(update_fields=['status', 'updated_at'])
        return Response(CompanySerializer(company).data)


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

    def get_queryset(self):
        # La consola provisiona un tenant a la vez: ``?company=<id>`` acota el
        # listado a esa company. Sin el filtro se devuelven todas (el operador
        # L0 es cross-company). ``company`` inválido/ausente → sin filtrar.
        qs = super().get_queryset()
        company_id = self.request.query_params.get('company')
        if company_id:
            qs = qs.filter(company_id=company_id)
        return qs

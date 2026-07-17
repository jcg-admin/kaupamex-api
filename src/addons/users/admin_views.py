"""
admin_views.py — addons.users
Sprint 4 — UC-AUTH-12/13/14/15: gestión de usuarios por el administrador.
"""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from addons.authz.models import Role, RoleAssignment
from addons.authz.permissions import HasCapability
from addons.authz.services import (
    SUPERADMIN_ROLE_CODE, has_capability, invalidate_capabilities, is_superadmin,
)
from addons.orders.models import Order, OrderValue
from .audit import audit_log_business
from .models import AuthEvent, BusinessEvent, UserDeactivationEvent
from .serializers import AddressSerializer, AdminUserListSerializer
from .tokens_email import invalidate_all_sessions

import rest_framework.pagination



User = get_user_model()


class AdminUserPagination(rest_framework.pagination.PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminUserDetailSerializer(AdminUserListSerializer):
    """UC-AUTH-12: perfil completo de usuario para el administrador."""
    profile_completeness = drf_serializers.SerializerMethodField()
    address_count        = drf_serializers.SerializerMethodField()
    # H-CICLO40-04: AdminUserDetailPage.jsx lee addresses (list), recent_orders,
    # lifetime_value. Se añaden estos campos para que el detalle de usuario
    # no muestre siempre "Sin direcciones / Sin pedidos / $0".
    addresses            = drf_serializers.SerializerMethodField()
    recent_orders        = drf_serializers.SerializerMethodField()
    lifetime_value       = drf_serializers.SerializerMethodField()
    # H-UI-02 / T-201 (party+authz): UC-ADM-02 — el formulario de permisos
    # pre-carga los roles authz vigentes del usuario. Party/authz (DEC-01=B):
    # los ``Group`` nativos ya no existen; el acceso admin se otorga con
    # ``RoleAssignment`` (indirect entitlement). Se expone como lista de ids
    # (lo que /permissions/ espera) más código/nombre para mostrar en el UI.
    roles                = drf_serializers.SerializerMethodField()

    class Meta(AdminUserListSerializer.Meta):
        # first_name, last_name ya vienen del base AdminUserListSerializer
        fields = AdminUserListSerializer.Meta.fields + [
            'phone',
            'profile_completeness', 'address_count',
            'addresses', 'recent_orders', 'lifetime_value',
            'roles',
        ]

    def get_roles(self, obj) -> list:
        return [
            {'id': ra.role_id, 'code': ra.role.code, 'name': ra.role.name}
            for ra in obj.role_assignments.select_related('role').order_by('role__code')
        ]

    def get_profile_completeness(self, obj) -> int:
        return obj.profile_completeness()

    def get_address_count(self, obj) -> int:
        return obj.addresses.count()

    def get_addresses(self, obj) -> list:
        qs = obj.addresses.order_by('-is_default', 'alias')
        return AddressSerializer(qs, many=True).data

    def get_recent_orders(self, obj) -> list:
        STATUS_LABEL = {
            'PENDING': 'Pendiente',
            'PROCESSING': 'En proceso',
            'SHIPPED': 'Enviado',
            'DELIVERED': 'Entregado',
            'CANCELLED': 'Cancelado',
            'CANCELLED_TIMEOUT': 'Cancelado (timeout)',
            'REFUNDED': 'Reembolsado',
        }
        STATUS_TONE = {
            'DELIVERED': 'lime',
            'CANCELLED': 'vino',
            'CANCELLED_TIMEOUT': 'vino',
            'REFUNDED': 'vino',
            'SHIPPED': 'bronze',
            'PROCESSING': 'bronze',
            'PENDING': 'muted',
        }
        qs = (
            Order.objects.filter(user=obj)
            .prefetch_related('items')
            .order_by('-created_at')[:5]
        )
        result = []
        for order in qs:
            v = getattr(order, 'value', None)
            total = str(v.total) if v else '0.00'
            result.append({
                'order_number': order.order_number,
                'created_at': order.created_at.isoformat(),
                'item_count': order.items.count(),
                'total': total,
                'status': order.status,
                'status_label': STATUS_LABEL.get(order.status, order.status),
                'tone': STATUS_TONE.get(order.status, 'muted'),
            })
        return result

    def get_lifetime_value(self, obj) -> str:
        agg = OrderValue.objects.filter(
            order__user=obj,
        ).exclude(
            order__status__in=['CANCELLED', 'CANCELLED_TIMEOUT'],
        ).aggregate(total=Sum('total'))
        return str(agg['total'] or Decimal('0.00'))


class AdminCreateUserSerializer(drf_serializers.Serializer):
    """UC-AUTH-15: crear usuario administrador.

    Party/authz (T-201, DEC-01=B): la identidad es sólo ``email`` + password
    (sin ``username``/``is_staff`` nativos). El acceso admin se otorga
    asignando el rol ``superadmin`` de addons.authz."""
    email    = drf_serializers.EmailField()
    password = drf_serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise drf_serializers.ValidationError('El email ya está registrado.')
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise drf_serializers.ValidationError(list(e.messages))
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
        )
        role, _ = Role.objects.get_or_create(
            code=SUPERADMIN_ROLE_CODE, defaults={'name': 'Superadministrador'},
        )
        RoleAssignment.objects.get_or_create(user=user, role=role)
        return user


def _require_admin(user):
    # Party/authz (DEC-01=B): ``is_staff`` ya no existe. La barrera admin
    # mínima del módulo de usuarios es la capacidad ``users.view`` (el
    # superadmin la satisface por bypass). Defensa en profundidad sobre el
    # ``HasCapability`` a nivel de clase.
    if not has_capability(user, 'users.view'):
        raise PermissionDenied('Solo administradores pueden acceder.')


class AdminPermissionsSerializer(drf_serializers.Serializer):
    """UC-ADM-02: asignación de roles authz de un usuario por el administrador.

    Party/authz (T-201, DEC-01=B): los ``Group``/``is_staff``/``is_superuser``
    nativos ya no existen. El permiso admin es un ``RoleAssignment`` (indirect
    entitlement). ``roles`` es la lista de ids de Role a asignar (reemplaza el
    set actual). Campo opcional (edición parcial). Las claves de error usan
    ``codigo_error`` (canon, DEC-DOC-005)."""
    roles = drf_serializers.ListField(
        child=drf_serializers.IntegerField(), required=False,
    )

    def validate_roles(self, value):
        existing = set(
            Role.objects.filter(pk__in=value).values_list('pk', flat=True)
        )
        missing = [r for r in value if r not in existing]
        if missing:
            raise drf_serializers.ValidationError(
                f'Roles inexistentes: {missing}.'
            )
        return value


class AdminUserViewSet(ModelViewSet):
    """
    /api/v1/admin/users/ — UC-AUTH-11/12/13/14/15.

    GET    /users/            — listar (UC-AUTH-11)
    GET    /users/{pk}/       — ver perfil (UC-AUTH-12)
    POST   /users/            — crear admin (UC-AUTH-15)
    POST   /users/{pk}/suspend/    — suspender (UC-AUTH-13)
    POST   /users/{pk}/reactivate/ — reactivar (UC-AUTH-14)
    """
    # H-CICLO79-02 / T-201: barrera authz a nivel de clase. ``HasCapability``
    # rechaza requests sin la capacidad requerida antes de llegar a los
    # handlers (incl. OPTIONS/HEAD). ``permission_map`` resuelve por acción;
    # ``required_capability`` es el fallback (incl. @actions sin entrada en el
    # mapa) — cierra el trap H-API-AUTHZ-04.
    permission_classes = [IsAuthenticated, HasCapability]
    permission_map     = {
        'list':       'users.view',
        'retrieve':   'users.view',
        'create':     'users.create',
        'suspend':    'users.edit',
        'reactivate': 'users.edit',
        'permissions': 'permissions.full',
    }
    required_capability = 'users.edit'
    queryset           = User.objects.all().order_by('-date_joined')
    http_method_names  = ['get', 'post', 'head', 'options']
    pagination_class   = AdminUserPagination

    def get_serializer_class(self):
        if self.action == 'create':
            return AdminCreateUserSerializer
        if self.action == 'retrieve':
            return AdminUserDetailSerializer
        return AdminUserListSerializer

    def get_queryset(self):
        _require_admin(self.request.user)
        # H-CICLO88-01: annotate order count to avoid N+1 in list view.
        # AdminUserListSerializer.get_order_count previously called
        # obj.orders.count() per row — one COUNT query per user.
        # Using annotate(order_count_db=Count('orders')) reduces this to
        # a single query with a GROUP BY.
        qs = User.objects.annotate(
            order_count_db=Count('orders'),
        ).order_by('-date_joined')
        search   = self.request.query_params.get('search')
        is_active = self.request.query_params.get('is_active')
        is_admin  = self.request.query_params.get('is_admin')
        if search:
            # Party (T-201): ``username`` ya no existe; nombre vive en Person.
            qs = qs.filter(
                Q(email__icontains=search) |
                Q(person__first_name__icontains=search) |
                Q(person__last_name__icontains=search)
            )
        # UC-AUTH-11 + GAP-3: el admin filtra por motivo concreto de
        # inactividad para decidir el camino correcto (suspended
        # requiere UC-AUTH-14; unverified/self_deleted esperan
        # UC-AUTH-01 Alt-A.2).
        deactivated_reason = self.request.query_params.get('deactivated_reason')
        if is_active is not None:
            qs = qs.filter(is_active=(is_active.lower() == 'true'))
        if is_admin is not None:
            # Party/authz: "admin" = titular del rol superadmin (no is_staff).
            has_superadmin = Q(role_assignments__role__code=SUPERADMIN_ROLE_CODE)
            if is_admin.lower() == 'true':
                qs = qs.filter(has_superadmin).distinct()
            else:
                qs = qs.exclude(has_superadmin)
        if deactivated_reason:
            qs = qs.filter(deactivated_reason=deactivated_reason)
        return qs

    @extend_schema(summary='Listar usuarios', tags=['admin'],
                   responses={200: AdminUserListSerializer(many=True)})
    def list(self, request, *args, **kwargs):
        _require_admin(request.user)
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Ver perfil de usuario', tags=['admin'],
                   responses={200: AdminUserDetailSerializer, 404: None})
    def retrieve(self, request, *args, **kwargs):
        _require_admin(request.user)
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary='Crear usuario administrador (UC-AUTH-15)',
        request=AdminCreateUserSerializer,
        responses={201: AdminUserDetailSerializer},
        tags=['admin'],
    )
    def create(self, request, *args, **kwargs):
        _require_admin(request.user)
        serializer = AdminCreateUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        user = serializer.save()
        return Response(
            AdminUserDetailSerializer(user).data,
            status=201,
        )

    @extend_schema(
        summary='Suspender cuenta de usuario (UC-AUTH-13)',
        responses={200: None, 400: None, 403: None},
        tags=['admin'],
    )
    @action(detail=True, methods=['post'], url_path='suspend')
    def suspend(self, request, pk=None):
        _require_admin(request.user)
        # H-CICLO104-01: adquirir lock sobre el User dentro del atomic para
        # serializar solicitudes concurrentes de suspension. Sin
        # select_for_update() dos admins podrian pasar simultaneamente el
        # chequeo self-suspend y escribir estado inconsistente.
        with transaction.atomic():
            try:
                target = User.objects.select_for_update().get(pk=pk)
            except User.DoesNotExist:
                return Response({'detail': 'No encontrado.'}, status=404)
            if target.pk == request.user.pk:
                return Response(
                    {'detail': 'Un administrador no puede suspenderse a sí mismo.'},
                    status=400,
                )
            # UC-AUTH-13 PRE-04 / EX-03 (Protección de superusuario): las
            # cuentas superadmin no pueden suspenderse desde el backoffice —
            # solo se gestionan desde la consola del servidor. Party/authz
            # (DEC-01=B): "superusuario" = titular del rol superadmin.
            # PARTE 7.3 → 403 / codigo_error = ACCOUNT_PROTECTED.
            if is_superadmin(target):
                return Response(
                    {'detail': 'No se puede suspender una cuenta de '
                               'superusuario desde el backoffice.',
                     'codigo_error': 'ACCOUNT_PROTECTED'},
                    status=403,
                )
            target.is_active = False
            # GAP-3 cierre: registrar la causa explicita para que
            # ResendVerificationView no reactive por email (UC-AUTH-01
            # Alt-A.3). Solo UC-AUTH-14 restaura cuentas suspendidas.
            target.deactivated_reason = User.DEACTIVATION_SUSPENDED
            target.deactivated_at = timezone.now()
            target.save(update_fields=[
                'is_active', 'deactivated_reason', 'deactivated_at',
            ])
            invalidate_all_sessions(target)
            # GAP 10: audit log del evento (append-only).
            UserDeactivationEvent.objects.create(
                user=target,
                reason=User.DEACTIVATION_SUSPENDED,
                source=UserDeactivationEvent.SOURCE_ADMIN,
                actor=request.user,
                note=request.data.get('note', '')[:255],
            )
        return Response({'message': f'Cuenta de {target.email} suspendida.'})

    @extend_schema(
        summary='Reactivar cuenta de usuario (UC-AUTH-14)',
        responses={200: None, 403: None},
        tags=['admin'],
    )
    @action(detail=True, methods=['post'], url_path='reactivate')
    def reactivate(self, request, pk=None):
        _require_admin(request.user)
        # H-CICLO111-01: adquirir lock sobre el User DENTRO del atomic para
        # serializar solicitudes concurrentes de reactivacion. El patron es
        # identico a suspend() (H-CICLO104-01). self.get_object() fuera de
        # atomic() no aplica select_for_update, por lo que dos admins podian
        # pasar el check y escribir estados inconsistentes concurrentemente.
        with transaction.atomic():
            try:
                target = User.objects.select_for_update().get(pk=pk)
            except User.DoesNotExist:
                return Response({'detail': 'No encontrado.'}, status=404)
            target.is_active = True
            # Limpiar la causa para que el estado quede consistente.
            target.deactivated_reason = None
            target.deactivated_at = None
            target.save(update_fields=[
                'is_active', 'deactivated_reason', 'deactivated_at',
            ])
            # H-CICLO103-01: audit log de reactivacion (append-only, simetrico
            # con suspend). Sin este registro, el audit log mostraba
            # suspensiones pero nunca las reactivaciones correspondientes,
            # dejando el historial de la cuenta incompleto para compliance.
            # BusinessEvent.action no tiene una constante ADMIN_REACTIVATE:
            # se escribe directamente el string (max_length=20, sin constraint
            # DB — solo choices=). El atomic() envuelve el save + on_commit.
            audit_log_business(
                request.user,
                'ADMIN_REACTIVATE',
                request,
                target_type='user',
                target_id=target.pk,
                extra={
                    'target_username': target.email,
                    'note': request.data.get('note', '')[:255],
                },
            )
        return Response({'message': f'Cuenta de {target.email} reactivada.'})

    @extend_schema(
        summary='Editar permisos de usuario (UC-ADM-02)',
        request=AdminPermissionsSerializer,
        responses={200: AdminUserDetailSerializer, 400: None, 403: None, 404: None},
        tags=['admin'],
    )
    @action(detail=True, methods=['post'], url_path='permissions')
    def permissions(self, request, pk=None):
        """UC-ADM-02: asignar los roles authz de un usuario.

        Party/authz (T-201, DEC-01=B): los ``is_staff``/``is_superuser``/
        ``groups`` nativos ya no existen. El acceso admin es un
        ``RoleAssignment`` (indirect entitlement); ``roles`` reemplaza el set
        actual. POST (no PATCH) para ser consistente con suspend/reactivate.
        Guard espejo del self-suspend: un admin no puede quitarse a sí mismo el
        rol ``superadmin`` (evita auto-lockout del panel). El cambio se audita
        (BusinessEvent) y purga la cache de capacidades del usuario afectado.
        """
        _require_admin(request.user)

        ser = AdminPermissionsSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {'detail': 'Payload inválido.',
                 'codigo_error': 'INVALID_PAYLOAD',
                 'errors': ser.errors},
                status=400,
            )
        vdata = ser.validated_data

        with transaction.atomic():
            try:
                target = User.objects.select_for_update().get(pk=pk)
            except User.DoesNotExist:
                return Response({'detail': 'No encontrado.',
                                 'codigo_error': 'USER_NOT_FOUND'}, status=404)

            is_self = target.pk == request.user.pk
            role_ids = vdata.get('roles')

            # Guard espejo del self-suspend: un admin no puede degradarse a sí
            # mismo (quitarse el rol superadmin), lo que lo dejaría sin acceso
            # al panel admin.
            if is_self and role_ids is not None and is_superadmin(target):
                superadmin_id = (
                    Role.objects.filter(code=SUPERADMIN_ROLE_CODE)
                    .values_list('pk', flat=True).first()
                )
                if superadmin_id is not None and superadmin_id not in role_ids:
                    return Response(
                        {'detail': 'Un administrador no puede quitarse a sí '
                                   'mismo el rol de superusuario.',
                         'codigo_error': 'CANNOT_DEMOTE_SELF'},
                        status=400,
                    )

            # Contención de escalada de privilegios (G-PERM-01 / H-API-AUTHZ):
            # un admin que NO es superadmin no puede CAMBIAR la membresía del
            # rol superadmin de ningún usuario (ni concederla —auto-promoción—
            # ni revocarla —neutralizar al superadmin—), aunque tenga
            # ``permissions.manage`` y adivine el id del rol. El superadmin sí
            # puede (test_admin_puede_promover_a_superadmin). Simétrico con el
            # filtro del catálogo en AdminRoleListView.
            if role_ids is not None and not is_superadmin(request.user):
                superadmin_id = (
                    Role.objects.filter(code=SUPERADMIN_ROLE_CODE)
                    .values_list('pk', flat=True).first()
                )
                if superadmin_id is not None:
                    would_have = superadmin_id in set(role_ids)
                    if would_have != is_superadmin(target):
                        return Response(
                            {'detail': 'Solo un superadministrador puede '
                                       'conceder o revocar el rol de '
                                       'superusuario.',
                             'codigo_error': 'CANNOT_GRANT_SUPERADMIN'},
                            status=403,
                        )

            changed = {}
            if role_ids is not None:
                # Reconciliar el set de RoleAssignment: agregar los que faltan,
                # borrar los sobrantes (equivalente a ``groups.set()``).
                desired = set(role_ids)
                current = set(
                    RoleAssignment.objects
                    .filter(user=target).values_list('role_id', flat=True)
                )
                for rid in desired - current:
                    RoleAssignment.objects.get_or_create(
                        user=target, role_id=rid,
                        defaults={'assigned_by': request.user},
                    )
                RoleAssignment.objects.filter(
                    user=target, role_id__in=(current - desired),
                ).delete()
                changed['roles'] = sorted(desired)

            if changed:
                # Purgar la cache de capacidades del afectado (roles mutados).
                invalidate_capabilities(target.pk)
                # Auditoría con la infra existente. BusinessEvent.action no
                # tiene constante ADMIN_PERMISSIONS_CHANGED: string directo,
                # mismo patrón que ADMIN_REACTIVATE en reactivate().
                audit_log_business(
                    request.user,
                    'ADMIN_PERMISSIONS_CHANGED',
                    request,
                    target_type='user',
                    target_id=target.pk,
                    extra={
                        'target_username': target.email,
                        'changes': changed,
                    },
                )

        return Response(AdminUserDetailSerializer(target).data)


class AuditLogView(APIView):
    """
    UC-ADM-03: Feed paginado del audit log admin (read-only).
    Combina AuthEvent + BusinessEvent + UserDeactivationEvent.
    GET /api/v1/admin/audit-log/
    Filtros: ?event_type=auth|business|deactivation  ?user_id=<pk>
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'audit.view'
    _PAGE_SIZE = 25
    # H-CICLO79-01: cap por tabla para evitar carga ilimitada en memoria.
    # Sin este limite, tres tablas de eventos sin LIMIT iteran sobre TODOS
    # los registros historicos antes de la paginacion Python, lo que puede
    # causar OOM con millones de filas. El cap es conservador (10 000
    # por tipo = max 30 000 filas) y cubre el 99.9% de los casos de uso
    # de auditoría (busqueda reciente + user_id filter).
    _PER_TYPE_LIMIT = 10_000

    @extend_schema(
        summary='Listar audit log de eventos (UC-ADM-03)',
        parameters=[
            OpenApiParameter('event_type', str, description='auth | business | deactivation'),
            OpenApiParameter('user_id',    int, description='Filtrar por usuario'),
            OpenApiParameter('page',       int, description='Número de página'),
        ],
        tags=['admin'],
        responses={200: inline_serializer('AuditLogPage', {
            'count':   drf_serializers.IntegerField(),
            'page':    drf_serializers.IntegerField(),
            'pages':   drf_serializers.IntegerField(),
            'results': inline_serializer('AuditLogEntry', {
                'id':         drf_serializers.IntegerField(),
                'event_type': drf_serializers.CharField(),
                'user_id':    drf_serializers.IntegerField(allow_null=True),
                'username':   drf_serializers.CharField(),
                'action':     drf_serializers.CharField(),
                'created_at': drf_serializers.CharField(),
                'extra':      drf_serializers.DictField(),
            }, many=True),
        })},
    )
    def get(self, request):
        event_type = request.query_params.get('event_type')
        raw_user_id = request.query_params.get('user_id')
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (ValueError, TypeError):
            raise DRFValidationError({'page': 'Debe ser un entero valido.'})
        # H-CICLO125-01: validate user_id as integer before passing to ORM.
        # filter(user_id="abc") on an integer FK raises unhandled ValueError
        # (500). Convert here with the same try/except pattern used for page.
        user_id = None
        if raw_user_id:
            try:
                user_id = int(raw_user_id)
            except (ValueError, TypeError):
                raise DRFValidationError({'user_id': 'Debe ser un entero valido.'})
        page_size  = self._PAGE_SIZE

        rows = []

        if not event_type or event_type == 'auth':
            qs = AuthEvent.objects.select_related('user').order_by('-created_at')
            if user_id:
                qs = qs.filter(user_id=user_id)
            # H-CICLO79-01: aplicar LIMIT en BD antes de iterar en Python.
            for ev in qs[:self._PER_TYPE_LIMIT]:
                rows.append({
                    'id':         ev.pk,
                    'event_type': 'auth',
                    'user_id':    ev.user_id,
                    'username':   ev.user.email if ev.user_id else None,
                    'action':     ev.action,
                    'created_at': ev.created_at.isoformat(),
                    'extra':      {
                        'ip_addr': str(ev.ip_addr) if ev.ip_addr else None,
                        'reason':  ev.reason or None,
                    },
                })

        if not event_type or event_type == 'business':
            qs = BusinessEvent.objects.select_related('actor').order_by('-created_at')
            if user_id:
                qs = qs.filter(actor_id=user_id)
            # H-CICLO79-01: aplicar LIMIT en BD antes de iterar en Python.
            for ev in qs[:self._PER_TYPE_LIMIT]:
                rows.append({
                    'id':         ev.pk,
                    'event_type': 'business',
                    'user_id':    ev.actor_id,
                    'username':   ev.actor.email if ev.actor_id else None,
                    'action':     ev.action,
                    'created_at': ev.created_at.isoformat(),
                    'extra':      {
                        'target_type': ev.target_type,
                        'target_id':   ev.target_id,
                    },
                })

        if not event_type or event_type == 'deactivation':
            qs = UserDeactivationEvent.objects.select_related('user', 'actor').order_by('-created_at')
            if user_id:
                qs = qs.filter(user_id=user_id)
            # H-CICLO79-01: aplicar LIMIT en BD antes de iterar en Python.
            for ev in qs[:self._PER_TYPE_LIMIT]:
                rows.append({
                    'id':         ev.pk,
                    'event_type': 'deactivation',
                    'user_id':    ev.user_id,
                    'username':   ev.user.email,
                    'action':     ev.reason,
                    'created_at': ev.created_at.isoformat(),
                    'extra':      {
                        'source': ev.source,
                        'actor':  ev.actor.email if ev.actor_id else None,
                    },
                })

        if not event_type:
            rows.sort(key=lambda r: r['created_at'], reverse=True)

        total = len(rows)
        pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        return Response({
            'count':   total,
            'page':    page,
            'pages':   pages,
            'results': rows[start: start + page_size],
        })

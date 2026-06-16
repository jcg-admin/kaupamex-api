"""
admin_views.py — apps.users
Sprint 4 — UC-AUTH-12/13/14/15: gestión de usuarios por el administrador.
"""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from apps.orders.models import Order, OrderValue
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
    # H-UI-02: UC-ADM-02 — el formulario de permisos necesita pre-cargar los
    # grupos actuales del usuario. Sin esto, el POST a /permissions/ con
    # ``groups`` hace ``.set()`` (reemplaza todo) a ciegas, con riesgo de
    # borrar grupos que el admin no quiso tocar. Se expone como lista de ids
    # (lo que /permissions/ espera) más sus nombres para mostrar en el UI.
    groups               = drf_serializers.SerializerMethodField()

    class Meta(AdminUserListSerializer.Meta):
        # first_name, last_name ya vienen del base AdminUserListSerializer
        fields = AdminUserListSerializer.Meta.fields + [
            'phone',
            'profile_completeness', 'address_count',
            'addresses', 'recent_orders', 'lifetime_value',
            'groups',
        ]

    def get_groups(self, obj) -> list:
        return [
            {'id': g.pk, 'name': g.name}
            for g in obj.groups.all().order_by('name')
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
    """UC-AUTH-15: crear usuario administrador."""
    username = drf_serializers.CharField(min_length=3, max_length=150)
    email    = drf_serializers.EmailField()
    password = drf_serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise drf_serializers.ValidationError('El nombre de usuario ya existe.')
        return value

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
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            is_staff=True,
            is_active=True,
        )


def _require_admin(user):
    if not user.is_staff:
        raise PermissionDenied('Solo administradores pueden acceder.')


class AdminPermissionsSerializer(drf_serializers.Serializer):
    """UC-ADM-02: edición de permisos de un usuario por el administrador.

    Todos los campos son opcionales; solo se aplican los presentes en el
    payload (edición parcial). ``groups`` es la lista de ids de Group a
    asignar (reemplaza el set actual). Las claves de error usan ``codigo_error``
    (canon, DEC-DOC-005)."""
    is_staff     = drf_serializers.BooleanField(required=False)
    is_superuser = drf_serializers.BooleanField(required=False)
    groups       = drf_serializers.ListField(
        child=drf_serializers.IntegerField(), required=False,
    )

    def validate_groups(self, value):
        existing = set(
            Group.objects.filter(pk__in=value).values_list('pk', flat=True)
        )
        missing = [g for g in value if g not in existing]
        if missing:
            raise drf_serializers.ValidationError(
                f'Grupos inexistentes: {missing}.'
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
    # H-CICLO79-02: agregar IsAdminUser al nivel de clase para que el
    # framework DRF rechace requests de usuarios no-staff antes de llegar
    # a los action handlers. El guard _require_admin() en cada accion
    # protege correctamente en runtime, pero la ausencia de IsAdminUser
    # aqui dejaba OPTIONS/HEAD accesibles a cualquier usuario autenticado
    # y eliminaba la barrera de DRF para acciones futuras sin guard manual.
    permission_classes = [IsAuthenticated, IsAdminUser]
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
        is_staff  = self.request.query_params.get('is_staff')
        if search:
            qs = qs.filter(
                Q(username__icontains=search) | Q(email__icontains=search) |
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
            )
        # UC-AUTH-11 + GAP-3: el admin filtra por motivo concreto de
        # inactividad para decidir el camino correcto (suspended
        # requiere UC-AUTH-14; unverified/self_deleted esperan
        # UC-AUTH-01 Alt-A.2).
        deactivated_reason = self.request.query_params.get('deactivated_reason')
        if is_active is not None:
            qs = qs.filter(is_active=(is_active.lower() == 'true'))
        if is_staff is not None:
            qs = qs.filter(is_staff=(is_staff.lower() == 'true'))
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
            # cuentas is_superuser=True no pueden suspenderse desde el
            # backoffice — solo se gestionan desde la consola del servidor.
            # PARTE 7.3 → 403 / codigo_error = ACCOUNT_PROTECTED.
            if target.is_superuser:
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
        return Response({'message': f'Cuenta de {target.username} suspendida.'})

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
                    'target_username': target.username,
                    'note': request.data.get('note', '')[:255],
                },
            )
        return Response({'message': f'Cuenta de {target.username} reactivada.'})

    @extend_schema(
        summary='Editar permisos de usuario (UC-ADM-02)',
        request=AdminPermissionsSerializer,
        responses={200: AdminUserDetailSerializer, 400: None, 403: None, 404: None},
        tags=['admin'],
    )
    @action(detail=True, methods=['post'], url_path='permissions')
    def permissions(self, request, pk=None):
        """UC-ADM-02: editar is_staff / is_superuser / groups de un usuario.

        POST (no PATCH) para ser consistente con suspend/reactivate — el
        viewset no expone PATCH (http_method_names sin patch). Guard espejo
        del self-suspend: un admin no puede quitarse a sí mismo is_superuser
        ni is_staff (evita auto-lockout del panel admin). El cambio se audita
        vía la infra de eventos existente (BusinessEvent / audit_log_business).
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
            # Guard espejo del self-suspend: un admin no puede degradarse a sí
            # mismo (quitarse is_superuser o is_staff), lo que lo dejaría sin
            # acceso al panel admin.
            if is_self and vdata.get('is_superuser') is False:
                return Response(
                    {'detail': 'Un administrador no puede quitarse a sí mismo '
                               'el rol de superusuario.',
                     'codigo_error': 'CANNOT_DEMOTE_SELF'},
                    status=400,
                )
            if is_self and vdata.get('is_staff') is False:
                return Response(
                    {'detail': 'Un administrador no puede quitarse a sí mismo '
                               'el acceso de staff.',
                     'codigo_error': 'CANNOT_DEMOTE_SELF'},
                    status=400,
                )

            changed = {}
            if 'is_staff' in vdata:
                target.is_staff = vdata['is_staff']
                changed['is_staff'] = vdata['is_staff']
            if 'is_superuser' in vdata:
                target.is_superuser = vdata['is_superuser']
                changed['is_superuser'] = vdata['is_superuser']
            if changed:
                target.save(update_fields=list(changed.keys()))
            if 'groups' in vdata:
                target.groups.set(vdata['groups'])
                changed['groups'] = vdata['groups']

            # Auditoría del cambio con la infra existente. BusinessEvent.action
            # no tiene constante ADMIN_PERMISSIONS_CHANGED: se escribe el string
            # directo (max_length=30, choices sin constraint DB), mismo patrón
            # que ADMIN_REACTIVATE en reactivate().
            audit_log_business(
                request.user,
                'ADMIN_PERMISSIONS_CHANGED',
                request,
                target_type='user',
                target_id=target.pk,
                extra={
                    'target_username': target.username,
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
    permission_classes = [IsAuthenticated, IsAdminUser]
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
                    'username':   ev.user.username if ev.user_id else None,
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
                    'username':   ev.actor.username if ev.actor_id else None,
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
                    'username':   ev.user.username,
                    'action':     ev.reason,
                    'created_at': ev.created_at.isoformat(),
                    'extra':      {
                        'source': ev.source,
                        'actor':  ev.actor.username if ev.actor_id else None,
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

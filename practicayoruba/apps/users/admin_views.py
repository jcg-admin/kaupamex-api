"""
admin_views.py — apps.users
Sprint 4 — UC-AUTH-12/13/14/15: gestión de usuarios por el administrador.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

import rest_framework.pagination
from .serializers import AdminUserListSerializer


class AdminUserPagination(rest_framework.pagination.PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
from .tokens_email import invalidate_all_sessions

User = get_user_model()


class AdminUserDetailSerializer(AdminUserListSerializer):
    """UC-AUTH-12: perfil completo de usuario para el administrador."""
    profile_completeness = drf_serializers.SerializerMethodField()
    address_count        = drf_serializers.SerializerMethodField()

    class Meta(AdminUserListSerializer.Meta):
        fields = AdminUserListSerializer.Meta.fields + [
            'first_name', 'last_name', 'phone',
            'profile_completeness', 'address_count',
        ]

    def get_profile_completeness(self, obj) -> int:
        return obj.profile_completeness()

    def get_address_count(self, obj) -> int:
        return obj.addresses.count()


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


class AdminUserViewSet(ModelViewSet):
    """
    /api/v1/admin/users/ — UC-AUTH-11/12/13/14/15.

    GET    /users/            — listar (UC-AUTH-11)
    GET    /users/{pk}/       — ver perfil (UC-AUTH-12)
    POST   /users/            — crear admin (UC-AUTH-15)
    POST   /users/{pk}/suspend/    — suspender (UC-AUTH-13)
    POST   /users/{pk}/reactivate/ — reactivar (UC-AUTH-14)
    """
    permission_classes = [IsAuthenticated]
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
        qs = User.objects.all().order_by('-date_joined')
        search   = self.request.query_params.get('search')
        is_active = self.request.query_params.get('is_active')
        is_staff  = self.request.query_params.get('is_staff')
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(username__icontains=search) | Q(email__icontains=search) |
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
            )
        if is_active is not None:
            qs = qs.filter(is_active=(is_active.lower() == 'true'))
        if is_staff is not None:
            qs = qs.filter(is_staff=(is_staff.lower() == 'true'))
        return qs

    @extend_schema(summary='Listar usuarios', tags=['admin'])
    def list(self, request, *args, **kwargs):
        _require_admin(request.user)
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Ver perfil de usuario', tags=['admin'])
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
        target = self.get_object()
        if target.pk == request.user.pk:
            return Response(
                {'detail': 'Un administrador no puede suspenderse a sí mismo.'},
                status=400,
            )
        with transaction.atomic():
            target.is_active = False
            target.save(update_fields=['is_active'])
            invalidate_all_sessions(target)
        return Response({'message': f'Cuenta de {target.username} suspendida.'})

    @extend_schema(
        summary='Reactivar cuenta de usuario (UC-AUTH-14)',
        responses={200: None, 403: None},
        tags=['admin'],
    )
    @action(detail=True, methods=['post'], url_path='reactivate')
    def reactivate(self, request, pk=None):
        _require_admin(request.user)
        target = self.get_object()
        target.is_active = True
        target.save(update_fields=['is_active'])
        return Response({'message': f'Cuenta de {target.username} reactivada.'})

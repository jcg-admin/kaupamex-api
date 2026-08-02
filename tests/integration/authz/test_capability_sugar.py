"""Azúcar declarativa sobre ``HasCapability`` (mapeo pretix ↔ catálogo DB).

Cubre las ergonomías recomendadas en
:ref:`analisis-mapeo-registro-permisos-pretix-vs-catalogo-db`:

- **#2 ``CapabilityRequiredMixin``** — la vista sólo declara
  ``required_capability`` y hereda ``permission_classes``.
- **#3 ``@require_capability``** — decorador para vistas función ``@api_view``.
- **#5 ``unknown_capability_codes``** — check anti-typo (adopta
  ``assert_valid_permission`` de pretix en data-driven), incluyendo un barrido
  **de todo el URLconf**: cada capacidad declarada mapea a un ``Capability``
  sembrado.

Se usa el sustantivo NO sensible ``catalogue`` para aislar la azúcar del gate
de re-auth (DEC-12), que sólo dispara en sustantivos sensibles.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import get_resolver
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from addons.authz.models import (
    AccessLevel, Capability, Module, Role, RoleAssignment, RoleCapability,
)
from addons.authz.permissions import CapabilityRequiredMixin, require_capability
from addons.authz.services import unknown_capability_codes

User = get_user_model()


@pytest.fixture
def seeded(db):
    call_command('seed_authz')


def _user_with_noun(noun, level=AccessLevel.VIEW):
    u = User.objects.create_user(login=f'cap-{noun}-{level}@t.mx', password='x')
    module, _ = Module.objects.get_or_create(code=noun, defaults={'name': noun})
    cap, _ = Capability.objects.get_or_create(
        code=noun, defaults={'module': module, 'name': noun})
    role = Role.objects.create(code=f'r-{noun}-{level}', name='r')
    RoleCapability.objects.create(role=role, capability=cap, level=level)
    RoleAssignment.objects.create(user=u, role=role)
    return u


# ─── #2 CapabilityRequiredMixin ──────────────────────────────────────────────

class _MixinView(CapabilityRequiredMixin, APIView):
    required_capability = 'catalogue.view'

    def get(self, request):
        return Response({'ok': True})


@pytest.mark.django_db
def test_mixin_denies_without_capability(seeded):
    u = User.objects.create_user(login='nocap@t.mx', password='x')
    req = APIRequestFactory().get('/x')
    force_authenticate(req, user=u)
    assert _MixinView.as_view()(req).status_code == 403


@pytest.mark.django_db
def test_mixin_allows_with_capability(seeded):
    u = _user_with_noun('catalogue', AccessLevel.VIEW)
    req = APIRequestFactory().get('/x')
    force_authenticate(req, user=u)
    assert _MixinView.as_view()(req).status_code == 200


# ─── #3 @require_capability (function-based @api_view) ───────────────────────

@api_view(['GET'])
@require_capability('catalogue.view')
def _decorated_view(request):
    return Response({'ok': True})


@pytest.mark.django_db
def test_decorator_denies_without_capability(seeded):
    u = User.objects.create_user(login='deco@t.mx', password='x')
    req = APIRequestFactory().get('/x')
    force_authenticate(req, user=u)
    assert _decorated_view(req).status_code == 403


@pytest.mark.django_db
def test_decorator_allows_with_capability(seeded):
    u = _user_with_noun('catalogue', AccessLevel.VIEW)
    req = APIRequestFactory().get('/x')
    force_authenticate(req, user=u)
    assert _decorated_view(req).status_code == 200


# ─── #5 unknown_capability_codes (anti-typo) ────────────────────────────────

@pytest.mark.django_db
def test_unknown_capability_codes_matrix(seeded):
    # Todos válidos (graded noun, named action, self-account) → vacío.
    assert unknown_capability_codes([
        'catalogue.view', 'payments.edit', 'platform.provision', 'account.profile',
    ]) == set()
    # Typos de varios tipos → todos detectados.
    bad = unknown_capability_codes([
        'catalogue.viewx',   # verbo no-CRUD → named exacto inexistente
        'bogus.view',        # noun inexistente
        'notacap',           # sin punto, code inexistente
        'platform.provisionx',
    ])
    assert bad == {'catalogue.viewx', 'bogus.view', 'notacap', 'platform.provisionx'}


def _collect_declared_capability_codes():
    """Recorre TODO el URLconf y junta los códigos declarados en las vistas
    (``required_capability`` + ``permission_map`` + ``admin_capability``)."""
    codes = set()

    def walk(resolver):
        for pat in resolver.url_patterns:
            if hasattr(pat, 'url_patterns'):
                walk(pat)
                continue
            cb = getattr(pat, 'callback', None)
            cls = getattr(cb, 'cls', None) or getattr(cb, 'view_class', None)
            if cls is None:
                continue
            rc = getattr(cls, 'required_capability', None)
            if rc:
                codes.add(rc)
            ac = getattr(cls, 'admin_capability', None)
            if ac:
                codes.add(ac)
            pmap = getattr(cls, 'permission_map', None)
            if isinstance(pmap, dict):
                codes.update(v for v in pmap.values() if v)

    walk(get_resolver())
    return codes


@pytest.mark.django_db
def test_all_declared_capabilities_are_seeded(seeded):
    """CI anti-typo: ninguna capacidad declarada en una vista queda sin sembrar
    (un typo produciría un fail-closed silencioso perpetuo, 403)."""
    declared = _collect_declared_capability_codes()
    assert declared, 'el barrido del URLconf no encontró capacidades declaradas'
    unknown = unknown_capability_codes(declared)
    assert unknown == set(), (
        f'Capacidades declaradas sin Capability sembrado (typos): {sorted(unknown)}'
    )

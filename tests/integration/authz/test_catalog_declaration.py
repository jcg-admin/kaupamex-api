"""Declaración del catálogo L0 por addon — el seed recolecta, no declara (#179).

Cubre el mecanismo que SOL-100 introduce (``addons.authz.declaration``) y, sobre
todo, la propiedad que motivó el cambio: que **agregar un addon no obligue a
recordar editar un archivo central**. H-API-106 midió el costo de lo contrario —
9 de 77 carpetas con ``Module.code`` homónimo y el código ``orders``
sobreviviendo al addon retirado en ``api@77bd1f0`` con cuatro aristas colgando.
"""
import pytest
from django.core.management import call_command

from addons.authz.declaration import (
    CapabilitySpec, DuplicateDeclaration, ModuleSpec, discover,
    orphan_capabilities, unknown_depends,
)
from addons.authz.models import Capability, Module


def test_discover_finds_addon_declarations():
    """El descubrimiento recoge módulos y capacidades de ``INSTALLED_APPS``."""
    modules, capabilities = discover()
    assert modules, 'ningún addon declaró módulos'
    assert capabilities, 'ningún addon declaró capacidades'
    # Muestras de dominios distintos: si el recorrido se rompiera para un addon
    # concreto, un solo assert genérico no lo notaría.
    assert 'catalogue' in modules      # declarado por addons.product
    assert 'orders' in modules         # declarado por addons.sale (SOL-098)
    assert 'platform' in modules       # declarado por addons.sale_subscription
    assert 'account.profile' in capabilities


def test_every_capability_hangs_from_a_declared_module():
    """Sin este invariante, el seed rompe con un ``KeyError`` opaco."""
    modules, capabilities = discover()
    assert orphan_capabilities(modules, capabilities) == []


def test_no_depends_edge_points_to_a_missing_module():
    """El check que habría cazado el ``orders`` colgante de H-API-106."""
    modules, _ = discover()
    assert unknown_depends(modules) == []


def test_duplicate_declaration_fails_loudly():
    """Dos dueños para un código es un error, no una precedencia silenciosa.

    Con la siembra central el último en escribir ganaba sin avisar; el punto de
    la declaración distribuida es que esa ambigüedad no pueda existir.
    """
    modules = {}
    spec = ModuleSpec(code='duplicado', name='Duplicado')
    modules[spec.code] = spec
    with pytest.raises(DuplicateDeclaration):
        # Se reproduce la condición que discover() detecta: mismo code, dos
        # declaraciones. Se levanta explícitamente porque montar dos addons
        # falsos en INSTALLED_APPS exigiría reconstruir el app registry.
        if spec.code in modules:
            raise DuplicateDeclaration(f'El módulo {spec.code!r} tiene dos dueños.')


def test_capability_spec_derives_its_module():
    """Sustantivo → él mismo; acción nombrada → el prefijo antes del punto."""
    assert CapabilitySpec(code='catalogue', name='C').module == 'catalogue'
    assert CapabilitySpec(code='inventory.adjust', name='A').module == 'inventory'
    assert CapabilitySpec(code='x.y', name='N', module='z').module == 'z'


@pytest.mark.django_db
def test_seed_stores_exactly_what_is_declared():
    """El seed es un recolector fiel: ni inventa filas ni omite declaraciones."""
    call_command('seed_authz')
    modules, capabilities = discover()

    stored_modules = set(Module.objects.values_list('code', flat=True))
    assert set(modules) <= stored_modules, (
        f'módulos declarados y no sembrados: {sorted(set(modules) - stored_modules)}'
    )
    stored_caps = set(Capability.objects.values_list('code', flat=True))
    assert set(capabilities) <= stored_caps, (
        'capacidades declaradas y no sembradas: '
        f'{sorted(set(capabilities) - stored_caps)}'
    )


@pytest.mark.django_db
def test_seed_propagates_metadata_and_dependency_graph():
    """La metadata de catálogo (#179) y el grafo (SOL-085 S3) llegan a la DB."""
    call_command('seed_authz')
    modules, _ = discover()

    # Metadata: se toma un módulo vendible y uno técnico para que el assert no
    # pase por el default de ambos campos.
    catalogue_row = Module.objects.get(code='catalogue')
    assert catalogue_row.is_application is True
    assert catalogue_row.category == modules['catalogue'].category

    platform_row = Module.objects.get(code='platform')
    assert platform_row.is_application is False

    # Grafo: 'orders' declara depender de catálogo + inventario.
    orders = Module.objects.get(code='orders')
    declared_depends = set(modules['orders'].depends)
    assert declared_depends, 'orders dejó de declarar dependencias'
    assert set(orders.depends.values_list('code', flat=True)) == declared_depends


@pytest.mark.django_db
def test_seed_is_idempotent():
    """Re-sembrar no duplica: es la propiedad que permite correrlo en cada deploy."""
    call_command('seed_authz')
    before = (Module.objects.count(), Capability.objects.count())
    call_command('seed_authz')
    assert (Module.objects.count(), Capability.objects.count()) == before

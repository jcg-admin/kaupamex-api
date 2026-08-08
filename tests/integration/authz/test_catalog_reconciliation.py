"""Reconciliación catálogo ↔ árbol (SOL-100 punto 2).

Dos niveles, dos herramientas:

- ``scripts/check_catalog_declaration.py`` — estático, sin DB: las
  declaraciones son coherentes entre sí y con ``INSTALLED_APPS``.
- ``manage.py reconcile_catalog`` — runtime: la DB coincide con la declaración.

El caso que motiva ambos es H-API-106: el addon ``orders`` se retiró
(``api@77bd1f0``) y su fila sobrevivió en toda base ya sembrada, porque la
siembra sólo añade — ``get_or_create`` nunca retira lo que dejó de declararse.
"""
import io
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from addons.authz.declaration import discover
from addons.authz.models import Capability, Module
from addons.sale_subscription.models import (
    CompanyModuleSubscription,
)
from addons.base.models import ResCompany

BASE = Path(__file__).resolve().parents[3]


def test_static_gate_passes_on_the_current_tree():
    """El árbol tal como está declarado pasa los cinco checks."""
    proc = subprocess.run(
        [sys.executable, str(BASE / 'scripts' / 'check_catalog_declaration.py')],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert 'Coherencia: OK' in proc.stdout


@pytest.mark.django_db
def test_reconciles_clean_right_after_seeding():
    """Sembrar y reconciliar de inmediato no debe reportar nada."""
    call_command('seed_authz')
    out = io.StringIO()
    call_command('reconcile_catalog', '--strict', stdout=out)
    assert 'Catálogo reconciliado' in out.getvalue()


@pytest.mark.django_db
def test_detects_stored_module_nobody_declares():
    """El caso ``orders`` de H-API-106, reproducido."""
    call_command('seed_authz')
    Module.objects.create(code='addon_retirado', name='Addon retirado')

    out = io.StringIO()
    with pytest.raises(CommandError):
        call_command('reconcile_catalog', '--strict', stdout=out)
    assert 'addon_retirado' in out.getvalue()


@pytest.mark.django_db
def test_detects_stored_capability_nobody_declares():
    call_command('seed_authz')
    module = Module.objects.get(code='catalogue')
    Capability.objects.create(
        code='catalogue.inventada', module=module, name='Inventada',
    )

    out = io.StringIO()
    with pytest.raises(CommandError):
        call_command('reconcile_catalog', '--strict', stdout=out)
    assert 'catalogue.inventada' in out.getvalue()


@pytest.mark.django_db
def test_detects_diverging_metadata():
    """Editar la fila en la consola L0 sin tocar la declaración es divergencia."""
    call_command('seed_authz')
    module = Module.objects.get(code='catalogue')
    module.category = 'Categoría inventada'
    module.save(update_fields=['category', 'updated_at'])

    out = io.StringIO()
    with pytest.raises(CommandError):
        call_command('reconcile_catalog', '--strict', stdout=out)
    assert 'Categoría inventada' in out.getvalue()


@pytest.mark.django_db
def test_prune_removes_the_undeclared():
    call_command('seed_authz')
    Module.objects.create(code='addon_retirado', name='Addon retirado')

    call_command('reconcile_catalog', '--prune', stdout=io.StringIO())
    assert not Module.objects.filter(code='addon_retirado').exists()

    # Y tras podar, la reconciliación queda limpia.
    out = io.StringIO()
    call_command('reconcile_catalog', '--strict', stdout=out)
    assert 'Catálogo reconciliado' in out.getvalue()


@pytest.mark.django_db
def test_prune_spares_a_subscribed_module():
    """Una company puede estar pagando por un módulo cuya declaración se borró.

    Retirar la fila destruiría ese registro comercial. El freno es la razón por
    la que ``--prune`` es opt-in y no parte del seed.
    """
    call_command('seed_authz')
    module = Module.objects.create(code='addon_retirado', name='Addon retirado')
    company = ResCompany.objects.create(code='acme', name='ACME')
    CompanyModuleSubscription.objects.create(company=company, module=module)

    out = io.StringIO()
    call_command('reconcile_catalog', '--prune', stdout=out)

    assert Module.objects.filter(code='addon_retirado').exists()
    assert 'NO se retira' in out.getvalue()


@pytest.mark.django_db
def test_detects_declared_but_not_stored():
    """Sin correr el seed, todo lo declarado aparece como faltante."""
    modules, _ = discover()
    out = io.StringIO()
    with pytest.raises(CommandError):
        call_command('reconcile_catalog', '--strict', stdout=out)
    text = out.getvalue()
    assert 'sin sembrar' in text
    # Una muestra concreta, no sólo el encabezado.
    assert 'catalogue' in text and 'catalogue' in modules

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
from addons.company.models import Company, CompanyModuleSubscription

BASE = Path(__file__).resolve().parents[3]


def test_gate_estatico_pasa_sobre_el_arbol_actual():
    """El árbol tal como está declarado pasa los cinco checks."""
    proc = subprocess.run(
        [sys.executable, str(BASE / 'scripts' / 'check_catalog_declaration.py')],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert 'Coherencia: OK' in proc.stdout


@pytest.mark.django_db
def test_reconcilia_limpio_tras_sembrar():
    """Sembrar y reconciliar de inmediato no debe reportar nada."""
    call_command('seed_authz')
    salida = io.StringIO()
    call_command('reconcile_catalog', '--strict', stdout=salida)
    assert 'Catálogo reconciliado' in salida.getvalue()


@pytest.mark.django_db
def test_detecta_modulo_sembrado_que_nadie_declara():
    """El caso ``orders`` de H-API-106, reproducido."""
    call_command('seed_authz')
    Module.objects.create(code='addon_retirado', name='Addon retirado')

    salida = io.StringIO()
    with pytest.raises(CommandError):
        call_command('reconcile_catalog', '--strict', stdout=salida)
    assert 'addon_retirado' in salida.getvalue()


@pytest.mark.django_db
def test_detecta_capacidad_sembrada_que_nadie_declara():
    call_command('seed_authz')
    modulo = Module.objects.get(code='catalogue')
    Capability.objects.create(
        code='catalogue.inventada', module=modulo, name='Inventada',
    )

    salida = io.StringIO()
    with pytest.raises(CommandError):
        call_command('reconcile_catalog', '--strict', stdout=salida)
    assert 'catalogue.inventada' in salida.getvalue()


@pytest.mark.django_db
def test_detecta_metadata_divergente():
    """Editar la fila en la consola L0 sin tocar la declaración es divergencia."""
    call_command('seed_authz')
    modulo = Module.objects.get(code='catalogue')
    modulo.category = 'Categoría inventada'
    modulo.save(update_fields=['category', 'updated_at'])

    salida = io.StringIO()
    with pytest.raises(CommandError):
        call_command('reconcile_catalog', '--strict', stdout=salida)
    assert 'Categoría inventada' in salida.getvalue()


@pytest.mark.django_db
def test_prune_retira_lo_no_declarado():
    call_command('seed_authz')
    Module.objects.create(code='addon_retirado', name='Addon retirado')

    call_command('reconcile_catalog', '--prune', stdout=io.StringIO())
    assert not Module.objects.filter(code='addon_retirado').exists()

    # Y tras podar, la reconciliación queda limpia.
    salida = io.StringIO()
    call_command('reconcile_catalog', '--strict', stdout=salida)
    assert 'Catálogo reconciliado' in salida.getvalue()


@pytest.mark.django_db
def test_prune_no_toca_un_modulo_contratado():
    """Una company puede estar pagando por un módulo cuya declaración se borró.

    Retirar la fila destruiría ese registro comercial. El freno es la razón por
    la que ``--prune`` es opt-in y no parte del seed.
    """
    call_command('seed_authz')
    modulo = Module.objects.create(code='addon_retirado', name='Addon retirado')
    company = Company.objects.create(code='acme', name='ACME')
    CompanyModuleSubscription.objects.create(company=company, module=modulo)

    salida = io.StringIO()
    call_command('reconcile_catalog', '--prune', stdout=salida)

    assert Module.objects.filter(code='addon_retirado').exists()
    assert 'NO se retira' in salida.getvalue()


@pytest.mark.django_db
def test_detecta_declarado_sin_sembrar():
    """Sin correr el seed, todo lo declarado aparece como faltante."""
    modules, _ = discover()
    salida = io.StringIO()
    with pytest.raises(CommandError):
        call_command('reconcile_catalog', '--strict', stdout=salida)
    texto = salida.getvalue()
    assert 'sin sembrar' in texto
    # Una muestra concreta, no sólo el encabezado.
    assert 'catalogue' in texto and 'catalogue' in modules

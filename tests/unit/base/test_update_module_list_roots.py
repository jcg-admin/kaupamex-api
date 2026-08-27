"""``update_module_list`` recorre TODAS las raíces de addons, no sólo una.

Regresión de :ref:`h-api-649`. La tarea #317 movió 90 addons de ``src/addons``
a ``<repo>/addons`` y dejó únicamente ``base`` en la primera. El comando
conservó una constante propia —``ADDONS_ROOT = BASE_DIR / 'addons'``— que
resuelve a ``src/addons``, así que registraba **1** módulo de 94 y lo
reportaba como éxito.

El mecanismo correcto ya existía: ``modules.module.ADDONS_PATHS`` declara las
dos raíces y ``get_modules()`` las recorre. El defecto no era falta de
mecanismo, sino una **segunda fuente de verdad** sobre dónde viven los addons.
"""

import os

import pytest
from django.core.management import call_command

from addons.base.models.ir_module import IrModule
from modules.module import ADDONS_PATHS, get_modules


def addons_on_disk():
    """Los addons con manifest, medidos sobre las raíces canónicas."""
    return {
        entry
        for root in ADDONS_PATHS
        if root.is_dir()
        for entry in os.listdir(root)
        if (root / entry / '__manifest__.py').is_file()
    }


def test_addons_live_in_more_than_one_root():
    """Control positivo: si el árbol vuelve a una sola raíz, el test sobra."""
    populated = [root for root in ADDONS_PATHS if root.is_dir() and any(
        (root / entry / '__manifest__.py').is_file() for entry in os.listdir(root)
    )]
    assert len(populated) > 1, (
        'el árbol declara %d raíz(ces) poblada(s); esta regresión sólo tiene '
        'sentido con más de una' % len(populated)
    )


@pytest.mark.django_db
def test_registers_every_addon_with_a_manifest():
    """El registro cubre el disco entero, no el subconjunto de una raíz."""
    call_command('update_module_list', verbosity=0)

    on_disk = addons_on_disk()
    registered = set(IrModule.objects.values_list('name', flat=True))

    missing = on_disk - registered
    assert not missing, (
        '%d addon(s) con manifest sin registrar (de %d en disco): %s'
        % (len(missing), len(on_disk), sorted(missing)[:10])
    )


@pytest.mark.django_db
def test_the_reported_count_matches_what_landed():
    """La cifra del reporte describe lo registrado, no otro universo.

    El defecto de :ref:`h-api-649` no fue sólo registrar de menos: fue
    **publicar 94** en la misma salida, desde un instrumento distinto
    (``get_modules()``) del que hacía el recorrido. Dos denominadores en un
    reporte es el sub-patrón A de ``metrica-decide-la-conclusion.md``.
    """
    call_command('update_module_list', verbosity=0)

    assert IrModule.objects.count() == len(get_modules())

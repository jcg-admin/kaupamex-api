"""La lista negra de menús como punto de enganche (tarea #78).

Porta ``_load_menus_blacklist`` (``odoo19c: odoo/addons/base/models/
ir_ui_menu.py:209-211``, LGPL-3), que la fuente declara devolviendo ``[]`` y
consume antes de filtrar por visibilidad (``:237-241``).

Por qué se declara sin consumidor todavía
------------------------------------------

Enterprise 19 lo extiende **7 veces**, más que ningún otro símbolo de
``ir.ui.menu`` (:ref:`h-api-819`), y cada addon **suma** sus ids a los del
``super()``. Sin base que extender, dos addons que lo declararan se pisarían —
el mismo defecto que ``SELF_READABLE_FIELDS`` tenía y que #66 cerró.

El control que puede fallar
---------------------------

Devolviendo la lista de ítems **sin** el ``exclude`` —el estado anterior— cae
``test_a_blacklisted_menu_is_not_visible`` y sobreviven los otros dos, que
miden la forma del punto y no su efecto.

*Métrica:* ids devueltos por ``visible_menu_ids`` con y sin veto.
*Ciega a:* la caché — la clave se compone de la generación y las capacidades,
no de la lista negra, así que un veto calculado por usuario no se propagaría.
Está declarado en el docstring del método; hoy la lista es estática.
"""
import pytest
from django.core.cache import cache

from addons.base.models.ir_ui_menu import (CapabilityPrunedMenuManager,
                                            IrUiMenu)

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def test_the_hook_exists_and_is_empty_by_default(db):
    """≙ ``return []`` de la fuente: el punto existe y no veta nada."""
    assert IrUiMenu.objects._load_menus_blacklist() == []


def test_a_blacklisted_menu_is_not_visible(db, monkeypatch):
    """El veto gana a la capacidad, como en la fuente (``:237-241``)."""
    vetado = IrUiMenu.objects.create(
        name='Vetado', route='/vetado', sequence=1, key='test.vetado')
    otro = IrUiMenu.objects.create(
        name='Otro', route='/otro', sequence=2, key='test.otro')

    visibles = IrUiMenu.objects.visible_menu_ids(None, frozenset(), superadmin=True)
    assert {vetado.pk, otro.pk} <= set(visibles)

    monkeypatch.setattr(CapabilityPrunedMenuManager, '_load_menus_blacklist',
                        lambda self: [vetado.pk])
    cache.clear()
    visibles = IrUiMenu.objects.visible_menu_ids(None, frozenset(), superadmin=True)
    assert vetado.pk not in visibles
    assert otro.pk in visibles


def test_the_cache_does_not_see_the_blacklist(db, monkeypatch):
    """La ceguera declarada, medida en vez de supuesta.

    La clave de :meth:`visible_menu_ids` se compone de la generación y del
    conjunto de capacidades; la lista negra **no** entra en ella. Con la lista
    estática por instalación eso es correcto —un addon la fija al cargarse— y
    dejaría de serlo el día que alguien la calcule por usuario o por empresa.

    Este caso no arregla nada: prueba que el hueco existe, para que ese día no
    haya que redescubrirlo. Es el mismo instrumento que :ref:`h-api-816` usó
    con el invalidador de grupos.
    """
    menu = IrUiMenu.objects.create(
        name='Tarde', route='/tarde', sequence=1, key='test.tarde')

    visibles = IrUiMenu.objects.visible_menu_ids(None, frozenset(), superadmin=True)
    assert menu.pk in visibles                      # entra al caché

    monkeypatch.setattr(CapabilityPrunedMenuManager, '_load_menus_blacklist',
                        lambda self: [menu.pk])
    # Sin tocar la generación, el veto no llega: el caché responde lo viejo.
    assert menu.pk in IrUiMenu.objects.visible_menu_ids(
        None, frozenset(), superadmin=True)

    cache.clear()
    assert menu.pk not in IrUiMenu.objects.visible_menu_ids(
        None, frozenset(), superadmin=True)

"""Contrato de ``StockLocation.warehouse`` frente a la creación tardía del
almacén — regresión de :ref:`h-api-667` (tarea **#503**).

La referencia declara ``warehouse_id`` **almacenado**
(``odoo19c: stock_location.py:85`` — ``compute='_compute_warehouse_id',
store=True``), con ``@api.depends('warehouse_view_ids', 'location_id')``. Este
ORM no tiene el motor de dependencias que dispararía el recálculo del lado
``stock.warehouse`` de esa relación (tarea **#191**; ``src/orm/decorators.py``
deja ``@api.depends`` como anotación no-op), así que ``StockWarehouse.save()``
lo dispara a mano (D-4 del docstring de ``stock_warehouse.py``).

Los tres casos cubren, en este orden:

1. **El defecto que el hallazgo midió** — crear la ubicación antes que su
   almacén dejaba ``warehouse`` en ``None`` sin que nada lo tocara de nuevo.
   Es exactamente el patrón que ``tests/integration/stock/
   test_stock_orderpoint.py::warehouse`` usa como fixture — ``view``/``stock``
   se crean primero, el almacén después.
2. **La propia ``view_location`` SÍ se resuelve a su almacén** — el
   ``[:-1]`` de ``odoo19c: stock_location.py:171`` recorta el elemento vacío
   que deja la barra final de ``parent_path``, no el ``id`` de la ubicación.
   El primer pase de la tarea #503 leyó ese recorte al revés y escribió tres
   docstrings y esta aserción afirmando una exclusión inexistente; se
   corrigieron midiendo la fuente (:ref:`h-api-676`).
3. **El alcance del backfill — todo el subárbol, no sólo los hijos
   directos.** El backfill manual retirado sólo tocaba
   ``view_location`` y sus hijos directos (``Q(location__in=raiz)``); una
   ubicación más profunda (nieta de ``view_location``) quedaba fuera.
"""
import pytest

from addons.base.models import ResCompany
from addons.stock.models import StockLocation, StockWarehouse

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='test_h667', name='Test H-667')


def test_warehouse_created_after_its_locations_backfills_direct_child(company):
    """Caso 1 — reproduce la Premisa verificada de :ref:`h-api-667`.

    ``view`` y ``shelf`` (hija directa) se crean ANTES que el almacén, sin
    ``save()`` explícito posterior. El almacén se crea con
    ``StockWarehouse.objects.create(...)`` — el camino real de los siete
    llamadores del árbol (``res_company.py`` y las fixtures de test); ninguno
    invoca el ``classmethod create()``.
    """
    view = StockLocation.objects.create(
        name='WH-667', usage=StockLocation.USAGE_VIEW, company=company,
        barcode='H667-VIEW')
    shelf = StockLocation.objects.create(
        name='WH-667/Stock', usage=StockLocation.USAGE_INTERNAL,
        location=view, company=company, barcode='H667-STOCK')
    assert shelf.warehouse_id is None

    warehouse = StockWarehouse.objects.create(
        name='WH 667', code='W667', company=company,
        view_location=view, lot_stock=shelf)

    shelf.refresh_from_db()
    assert shelf.warehouse_id == warehouse.pk


def test_view_location_resolves_to_its_own_warehouse(company):
    """Caso 2 — ``view_location.warehouse`` es su propio almacén, como la fuente.

    ``odoo19c: stock_location.py:171`` construye el conjunto de candidatos con
    ``loc.parent_path.split('/')[:-1]``. La ruta materializada **termina en
    ``/``** —allá por ``_parent_store``, aquí por ``compute_parent_path()``
    (``f'{raiz}{self.pk}/'``)— así que ``split('/')`` deja un elemento vacío al
    final y ``[:-1]`` recorta **ese vacío**, no el ``id`` de la propia
    ubicación. Una ``view_location`` SÍ se encuentra a sí misma.

    Esta aserción se escribió invertida en el primer pase de la tarea #503, y
    con ella tres docstrings que declaraban una «exclusión» inexistente. Se
    corrigieron midiendo la fuente en vez de razonar sobre el nombre del
    recorte; ver :ref:`h-api-676`.
    """
    view = StockLocation.objects.create(
        name='WH-667b', usage=StockLocation.USAGE_VIEW, company=company,
        barcode='H667B-VIEW')
    shelf = StockLocation.objects.create(
        name='WH-667b/Stock', usage=StockLocation.USAGE_INTERNAL,
        location=view, company=company, barcode='H667B-STOCK')

    warehouse = StockWarehouse.objects.create(
        name='WH 667b', code='W667B', company=company,
        view_location=view, lot_stock=shelf)

    view.refresh_from_db()
    assert view.warehouse_id == warehouse.pk


def test_backfill_reaches_grandchildren_not_just_direct_children(company):
    """Caso 3 — una ubicación más profunda que un hijo directo también se cierra.

    El backfill manual retirado sólo alcanzaba ``view_location`` y sus hijos
    directos (``Q(location__in=raiz)``); una ubicación anidada un nivel más
    —``bin``, hija de ``shelf``, nieta de ``view``— quedaba fuera. El
    ``save()`` nuevo recorre ``parent_path__startswith=vista.parent_path``,
    que sí la alcanza.
    """
    view = StockLocation.objects.create(
        name='WH-667c', usage=StockLocation.USAGE_VIEW, company=company,
        barcode='H667C-VIEW')
    shelf = StockLocation.objects.create(
        name='WH-667c/Stock', usage=StockLocation.USAGE_INTERNAL,
        location=view, company=company, barcode='H667C-STOCK')
    bin_ = StockLocation.objects.create(
        name='WH-667c/Stock/Bin-01', usage=StockLocation.USAGE_INTERNAL,
        location=shelf, company=company, barcode='H667C-BIN')
    assert bin_.warehouse_id is None

    warehouse = StockWarehouse.objects.create(
        name='WH 667c', code='W667C', company=company,
        view_location=view, lot_stock=shelf)

    bin_.refresh_from_db()
    assert bin_.warehouse_id == warehouse.pk

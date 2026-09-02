"""Cierre de la divergencia D-5 de ``stock_rule.py`` — tarea **#271**.

``_orderpoint_model()`` avisaba en el log citando la tarea #330 como si
``stock.warehouse.orderpoint`` no estuviera portado. Medido antes de este
archivo (``addons/stock/models/stock_rule.py``, ``_orderpoint_model``):

.. code-block:: text

    grep -n "_orderpoint_model\\|#330\\|orderpoint" addons/stock/models/stock_rule.py

La clase existe desde ``addons/stock/models/stock_orderpoint.py:230``
(``class StockWarehouseOrderpoint``), registrada en
``addons/stock/models/__init__.py`` y consumida además por
``stock_move.py:1401`` y ``purchase_stock``. La referencia
(``odoo19c: addons/stock/models/stock_rule.py:437,:697``) accede al modelo
directamente —``self.env['stock.warehouse.orderpoint']``— sin ningún camino
alterno para el caso en que falte: no hay rama muerta que portar.

Estos casos discriminan la corrección de dos formas:

1. ``_orderpoint_model()`` devuelve la clase real, sin pasar por ningún
   ``try``/``except`` que la esconda tras un ``warning``.
2. ``StockRule._run_scheduler_tasks`` ya NO omite la primera de sus tres
   tareas — el recálculo de puntos de pedido se ejecuta sobre una regla real
   y dos de sus campos calculados y ``store``\\ ados cambian, prueba de que el
   bloque corrió y no se saltó silenciosamente.
"""
import pytest
from django.apps import apps
from django.utils import timezone

from addons.base.models import ResCompany
from addons.product.models import ProductProduct
from addons.stock.models import (
    StockLocation,
    StockRule,
    StockWarehouse,
    StockWarehouseOrderpoint,
)
from addons.stock.models.stock_rule import _orderpoint_model
from orm.environments import set_current_company
from tests.factories.product_factory import make_product

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company(db):
    company_record = ResCompany.objects.create(
        code='test_rule_op_271', name='Kaupamex D-5')
    set_current_company(company_record.pk)
    yield company_record
    set_current_company(None)


@pytest.fixture
def warehouse(company):
    view = StockLocation.objects.create(
        name='WH', usage=StockLocation.USAGE_VIEW, company=company,
        barcode='RULE-OP-VIEW')
    stock = StockLocation.objects.create(
        name='WH/Stock', usage=StockLocation.USAGE_INTERNAL,
        location=view, company=company, barcode='RULE-OP-STOCK')
    return StockWarehouse.objects.create(
        name='Main D-5', code='D5', company=company,
        view_location=view, lot_stock=stock)


def test_orderpoint_model_returns_the_class_directly():
    """``_orderpoint_model()`` == ``apps.get_model(...)``, sin ``None`` posible.

    Antes el ``try``/``except LookupError`` sólo podía devolver ``None`` con
    un ``warning`` citando la tarea #330. Hoy el modelo existe: no hay
    excepción que atrapar, así que la función se limita a resolverlo por
    nombre — igual que ``stock_move.py:1401``.

    ``_orderpoint_model`` es una función de módulo, no un método de
    ``StockRule`` — igual que sus llamadores en el propio archivo
    (``_get_lead_days``, ``_run_scheduler_tasks``), que la invocan sin
    prefijo de clase.
    """
    resuelto = _orderpoint_model()
    assert resuelto is apps.get_model('stock', 'StockWarehouseOrderpoint')
    assert resuelto is StockWarehouseOrderpoint


def test_orderpoint_model_never_logs_the_stale_d5_warning(caplog):
    """El ``warning`` «no está portado (divergencia D-5, tarea #330)»
    ya no puede emitirse — la rama que lo producía se retiró porque el
    modelo que citaba está en el árbol."""
    with caplog.at_level('WARNING', logger='addons.stock.models.stock_rule'):
        _orderpoint_model()
    mensajes = [r.message for r in caplog.records]
    assert not any('no está portado' in m for m in mensajes)
    assert not any('#330' in m for m in mensajes)


def test_run_scheduler_tasks_no_longer_skips_the_first_task(
        company, warehouse, monkeypatch):
    """``_run_scheduler_tasks`` recalcula el punto de pedido — no lo omite.

    Con ``product_min_qty`` por encima del pronóstico (sin quants, el
    pronóstico es 0), la primera tarea del planificador tiene que:

    - fijar ``deadline_date`` a hoy (``qty_on_hand < product_min_qty``,
      ``odoo19c: :691-724`` vía ``_compute_deadline_date``);
    - recalcular ``qty_to_order_computed`` a un valor no nulo
      (``_compute_qty_to_order_computed``).

    Si la primera tarea se omitiera —el defecto que esta corrección cierra—
    los dos campos se quedarían en su valor por defecto (``None`` y ``0.0``).

    **Fuera de alcance, encontrado al escribir este caso:**
    ``stock_orderpoint.py`` (``_qty_pair``, ``_get_qty_to_order``…) llama
    ``self.product._quantity_for(...)`` como si fuera un método ligado, pero
    ``addons/stock/models/product.py`` nunca lo cuelga de ``ProductProduct``
    con ``setattr`` — sólo cuelga ``qty_available``/``virtual_available``/etc.
    (medido: ``grep -rn "'_quantity_for'" addons/ src/`` → 0 hits). Es un bug
    preexistente, ajeno a la tarea #271 y a un archivo fuera del alcance
    asignado a este pase (ni ``stock_rule.py`` ni ``report_catalog.py``), así
    que no se corrige aquí. Se parchea sólo para este test, para poder
    ejercitar ``_run_scheduler_tasks`` de verdad.
    """
    monkeypatch.setattr(
        ProductProduct, '_quantity_for',
        lambda self, key, **kwargs: 0.0, raising=False)

    product = make_product(name='Reabastecido D-5')
    orderpoint = StockWarehouseOrderpoint.objects.create(
        product=product, company=company, warehouse=warehouse,
        location=warehouse.lot_stock,
        product_min_qty=10.0, product_max_qty=20.0,
    )

    # Precondición: el estado por defecto, antes de correr el planificador.
    assert orderpoint.deadline_date is None
    assert orderpoint.qty_to_order_computed == 0.0
    assert orderpoint.trigger == 'auto'

    StockRule._run_scheduler_tasks(company_id=company.pk)

    orderpoint.refresh_from_db()
    # ``_today()`` (stock_orderpoint.py:229) usa ``timezone.now().date()``,
    # que resuelve en ``TIME_ZONE`` (``America/Mexico_City``, base.py:342) —
    # no la fecha local ingenua del contenedor. Se compara con la misma
    # función para no fallar por el desfase horario cerca de medianoche.
    assert orderpoint.deadline_date == timezone.now().date(), (
        'la primera tarea (recalcular puntos de pedido) no corrió — '
        'stock.warehouse.orderpoint se sigue tratando como no portado')
    assert orderpoint.qty_to_order_computed == pytest.approx(20.0), (
        'qty_to_order_computed se quedó en su default: '
        '_compute_qty_to_order_computed no se ejecutó')

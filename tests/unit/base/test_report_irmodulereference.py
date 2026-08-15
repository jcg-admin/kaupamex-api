"""``report.base.report_irmodulereference`` — referencia técnica de un módulo.

Ejercita el porte de
``odoo19c: odoo/addons/base/report/report_base_report_irmodulereference.py``
(``odoo-tools@622ddc2a``), incluido el símbolo que **no** se portó: que su
bloqueo sea ruidoso es parte del contrato, no un detalle.
"""
import pytest

from addons.base.models.ir_model import IrModel, IrModelData
from addons.base.models.ir_module import IrModule
from addons.base.report.report_base_report_irmodulereference import (
    ReportBaseReportIrmodulereference,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def module():
    return IrModule.objects.create(name='sale', shortdesc='Ventas')


@pytest.fixture
def other_module():
    return IrModule.objects.create(name='stock', shortdesc='Inventario')


def _declare(model_name, module_name):
    """Declara un ``ir.model`` como perteneciente a un módulo.

    Es el rodeo de la fuente: la pertenencia vive en ``ir.model.data``, no en
    un campo del propio ``ir.model``.
    """
    modelo = IrModel.objects.create(name=model_name, model=model_name)
    IrModelData.objects.create(
        name=f'model_{model_name.replace(".", "_")}',
        model='ir.model', module=module_name, res_id=modelo.pk)
    return modelo


def test_object_find_returns_the_models_the_module_declares(module):
    """``:11-16``: los ``ir.model`` cuyo ``ir.model.data`` cita al módulo."""
    pedido = _declare('sale.order', 'sale')
    encontrados = ReportBaseReportIrmodulereference._object_find(module)
    assert list(encontrados) == [pedido]


def test_object_find_ignores_models_of_another_module(module, other_module):
    """La pertenencia es por módulo — no devuelve lo que declaró otro."""
    _declare('sale.order', 'sale')
    _declare('stock.picking', 'stock')
    encontrados = ReportBaseReportIrmodulereference._object_find(module)
    assert [m.model for m in encontrados] == ['sale.order']


def test_object_find_ignores_rows_that_point_elsewhere(module):
    """``('model', '=', 'ir.model')``: una fila de otro modelo no cuenta."""
    IrModelData.objects.create(
        name='view_order_form', model='ir.ui.view', module='sale', res_id=1)
    assert not ReportBaseReportIrmodulereference._object_find(module).exists()


def test_object_find_is_empty_for_a_module_that_declares_nothing(module):
    assert list(ReportBaseReportIrmodulereference._object_find(module)) == []


def test_report_values_carry_the_selected_modules(module, other_module):
    """``:33-35``: ``docs`` son los módulos que el llamador pidió."""
    valores = ReportBaseReportIrmodulereference._get_report_values(
        [module.pk])
    assert list(valores['docs']) == [module]


def test_report_values_echo_the_ids_they_received(module):
    valores = ReportBaseReportIrmodulereference._get_report_values(
        [module.pk])
    assert valores['doc_ids'] == [module.pk]


def test_report_values_expose_both_finders_as_callables(module):
    """``:36-37``: la plantilla los invoca por nombre, así que viajan."""
    valores = ReportBaseReportIrmodulereference._get_report_values(
        [module.pk])
    assert callable(valores['findobj'])
    assert callable(valores['findfields'])


def test_the_exposed_finder_is_the_working_one(module):
    """``findobj`` no es un envoltorio: es el método que ya se ejercitó."""
    pedido = _declare('sale.order', 'sale')
    valores = ReportBaseReportIrmodulereference._get_report_values(
        [module.pk])
    assert list(valores['findobj'](module)) == [pedido]


def test_doc_model_is_none_while_the_report_spec_is_not_declared(module):
    """El ``ReportSpec`` de este reporte aún no existe — ver el docstring.

    La fuente asume que el registro existe porque su XML lo siembra; aquí el
    valor sale ``None`` en vez de reventar, y el docstring dice por qué.
    """
    valores = ReportBaseReportIrmodulereference._get_report_values(
        [module.pk])
    assert valores['doc_model'] is None


def test_fields_find_fails_loudly_instead_of_returning_empty():
    """El símbolo bloqueado grita su motivo.

    Devolver ``[]`` dejaría la sección de campos en blanco sin nada que lo
    delate — el OK silencioso que ``check_silent_oks`` prohíbe.
    """
    with pytest.raises(NotImplementedError) as exc:
        ReportBaseReportIrmodulereference._fields_find('sale.order', None)
    assert 'fields_get' in str(exc.value)


def test_the_block_names_its_successor():
    """Un bloqueo sin sucesor es deuda anónima (``hallazgo-abierto``)."""
    with pytest.raises(NotImplementedError) as exc:
        ReportBaseReportIrmodulereference._fields_find('sale.order', None)
    assert '#399' in str(exc.value)

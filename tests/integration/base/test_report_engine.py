"""Tests — motor de reportes (``ir.actions.report`` → helper libharu).

Cubre la cadena completa que ``report_catalog.py`` describe: declaración por
addon dueño (paso 1) → constructor de descriptor (paso 3) → despacho por
``report_type`` (paso 4) → conversión por el helper en C (paso 5).

El motor era el hueco que ADR-017 dejó abierto: los helpers compilaban y
producían PDF, pero **ningún Python los invocaba** (H-API-287, "los llamadores
siguen huérfanos"). Estos casos son el primer consumidor real.

Requieren los binarios construidos (``make pdf``). Cuando no están, el motor
levanta ``HelperNotBuilt`` — un error de despliegue, distinto de un fallo de
datos — y los casos que ejercen el helper se saltan en vez de fallar en rojo
por una causa que no es del código bajo prueba.
"""
import json
import subprocess

import pytest

from addons.base import report_catalog
from addons.base.report_catalog import ReportSpec, UnknownHelper
from addons.base.models.ir_actions_report import (
    HELPER_DIR,
    HelperFailed,
    HelperNotBuilt,
    IrActionsReport,
    UnknownReport,
    run_helper,
)
from addons.sale.models.sale_order_line import SaleOrderLine
from tests.factories.order_factory import make_order
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db

#: Se saltan los casos que ejercen el binario si no está construido.
helpers_built = pytest.mark.skipif(
    not (HELPER_DIR / 'pdf_receipt').exists(),
    reason='helpers PDF sin construir; correr `make pdf` (ADR-017)',
)


@pytest.fixture
def orden_con_lineas():
    """Una orden con dos líneas — el sujeto de ``sale.report_saleorder``."""
    producto = make_product(name='Ofrenda de Osun', price='150.00')
    orden = make_order(product=producto, quantity=2, unit_price='150.00')
    SaleOrderLine.objects.create(
        order=orden, product=producto, name='Vela de siete días',
        price_unit='45.50', product_uom_qty=3,
    )
    return orden


@pytest.fixture
def reporte_orden():
    """El registro ``ir.actions.report`` de la orden de venta.

    Se crea en el test y no se siembra: la siembra es de la migración de datos
    del addon dueño, y lo que estos casos prueban es el **motor**, no el
    sembrador. Que el registro exista en producción es otra prueba.
    """
    return IrActionsReport.objects.create(
        name='Orden de venta',
        report_name='sale.report_saleorder',
        model='sale.SaleOrder',
        report_type='pdf',
    )


class TestCatalogo:
    """Paso 1 — la declaración por addon dueño."""

    def test_sale_declara_su_reporte(self):
        declarados = report_catalog.discover()
        assert 'sale.report_saleorder' in declarados

    def test_la_declaracion_apunta_a_su_modelo_y_helper(self):
        spec = report_catalog.get('sale.report_saleorder')
        assert spec.model == 'sale.SaleOrder'
        assert spec.report_type == 'pdf'
        assert spec.helper == 'pdf_receipt'

    def test_report_name_no_declarado_no_se_inventa(self):
        assert report_catalog.get('sale.report_que_no_existe') is None

    def test_helper_desconocido_se_rechaza_al_declarar(self):
        with pytest.raises(UnknownHelper):
            ReportSpec(report_name='x.y', model='sale.SaleOrder', name='X',
                       builder=lambda records, **ctx: {}, helper='pdf_inexistente')


class TestDescriptor:
    """Paso 3 — el constructor produce lo que el helper sabe leer."""

    def test_lleva_las_lineas_de_la_orden(self, orden_con_lineas):
        spec = report_catalog.get('sale.report_saleorder')
        descriptor = spec.builder(orden_con_lineas)
        assert len(descriptor['items']) == orden_con_lineas.order_line.count()

    def test_los_importes_viajan_preformateados(self, orden_con_lineas):
        """El contrato del helper lo exige: strings, no Decimal ni float.

        *"All numeric fields are passed as already-formatted strings from
        Django to avoid float/Decimal drift"* (``pdf_receipt.c:25-26``).
        """
        spec = report_catalog.get('sale.report_saleorder')
        descriptor = spec.builder(orden_con_lineas)
        for item in descriptor['items']:
            assert isinstance(item['unit_price'], str)
            assert item['unit_price'].count('.') == 1
        for valor in descriptor['totals'].values():
            assert isinstance(valor, str)

    def test_es_json_serializable(self, orden_con_lineas):
        """Si no lo es, el fallo aparecería recién dentro del subprocess."""
        spec = report_catalog.get('sale.report_saleorder')
        json.dumps(spec.builder(orden_con_lineas), ensure_ascii=False)

    def test_una_orden_de_venta_no_lleva_seccion_de_pago(self, orden_con_lineas):
        """No es un comprobante de pago; el helper omite la sección si falta."""
        spec = report_catalog.get('sale.report_saleorder')
        assert 'payment' not in spec.builder(orden_con_lineas)


class TestDespacho:
    """Paso 4 — ``report_type`` elige el renderizador."""

    def test_report_name_sin_declarante_levanta(self, reporte_orden):
        reporte_orden.report_name = 'sale.report_fantasma'
        with pytest.raises(UnknownReport):
            reporte_orden.render(None)

    def test_tipo_sin_renderizador_devuelve_none(self, reporte_orden,
                                                 orden_con_lineas):
        """Contrato de ausencia de la referencia (``:1150``): ``None``, no error.

        Un tipo fuera de ``RENDERER_BY_TYPE`` — una fila escrita por una
        migración vieja, o por un addon que declare un formato que este árbol
        aún no emite — no revienta el motor: devuelve ``None``.
        """
        reporte_orden.report_type = 'formato-que-no-emitimos'
        assert reporte_orden.render(orden_con_lineas) is None


@helpers_built
class TestConversion:
    """Paso 5 — el helper en C convierte y devuelve PDF."""

    def test_la_cadena_completa_produce_un_pdf(self, reporte_orden,
                                               orden_con_lineas):
        contenido, extension = reporte_orden.render(orden_con_lineas)
        assert extension == 'pdf'
        assert contenido.startswith(b'%PDF')
        # Un PDF de una página con dos líneas no baja de 1 KB; por debajo de
        # eso el helper habría emitido un documento vacío con exit 0.
        assert len(contenido) > 1024

    def test_descriptor_invalido_sale_con_el_codigo_de_su_contrato(self):
        """Exit 1 = JSON no parseable (cabecera de ``pdf_receipt.c``)."""
        completed = subprocess.run(
            [str(HELPER_DIR / 'pdf_receipt')], input=b'no soy json',
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
            check=False,
        )
        assert completed.returncode == 1

    def test_el_motor_traduce_el_fallo_del_helper(self):
        with pytest.raises(HelperFailed):
            run_helper('pdf_receipt', 'no soy un objeto')


class TestDespliegue:
    """El binario ausente es un fallo de despliegue, no de datos."""

    def test_helper_inexistente_levanta_su_propio_error(self):
        with pytest.raises(HelperNotBuilt):
            run_helper('pdf_que_nadie_construyo', {})

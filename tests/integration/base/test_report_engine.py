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
import re
import subprocess
import zlib

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

#: Un byte >127 dentro de una cadena literal de PDF va escapado en octal.
_OCTAL = re.compile(rb'\\([0-7]{3})')


def texto_impreso(pdf: bytes) -> str:
    """Los textos que el PDF realmente dibuja, decodificados a str.

    Es la única lectura que ve lo que sale en el papel. Un test que sólo
    comprueba el prefijo ``%PDF`` y el tamaño da verde con el documento
    corrompido — que es exactamente cómo H-API-290 sobrevivió al primer
    test de esta suite.
    """
    salida = []
    for bloque in re.finditer(rb'stream\r?\n(.*?)endstream', pdf, re.S):
        crudo = bloque.group(1)
        try:
            crudo = zlib.decompress(crudo)
        except zlib.error:
            # silent OK because libharu no comprime siempre: un stream corto
            # va en claro y `crudo` ya sirve tal cual. Distinguir "no estaba
            # comprimido" de "venía roto" exigiría leer /Filter del objeto,
            # y un stream ilegible se delata igual — el texto no aparece.
            pass
        for literal in re.findall(rb'\((.*?)\)\s*Tj', crudo):
            byteado = _OCTAL.sub(
                lambda m: bytes([int(m.group(1), 8)]), literal)
            salida.append(byteado.decode('cp1252', errors='replace'))
    return '\n'.join(salida)


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

    def test_los_acentos_llegan_intactos_al_papel(self, reporte_orden,
                                                  orden_con_lineas):
        """H-API-290 — el español del producto no puede salir corrompido.

        El descriptor viaja con ``\\uXXXX`` (``ensure_ascii=True``) porque es
        la única rama del lector del helper que produce un byte WinAnsi; con
        UTF-8 crudo, ``días`` llegaba como los dos bytes ``C3 AD`` y la página
        decía ``dÃ­as``. Se afirma sobre el texto dibujado, no sobre el
        descriptor: el descriptor ya era correcto cuando el papel no lo era.

        El nombre se mantiene bajo 36 **bytes**: el helper corta ahí para que
        entre en la columna (``pdf_receipt.c:446``). Con la codificación ya
        corregida cada acento ocupa uno, así que el corte no parte un carácter
        por la mitad — con UTF-8 crudo sí podía.
        """
        acentuado = 'Vela 7 días · ñ ó ú ¿va?'
        linea = orden_con_lineas.order_line.first()
        linea.name = acentuado
        linea.save(update_fields=['name'])

        contenido, _ = reporte_orden.render(orden_con_lineas)
        assert acentuado in texto_impreso(contenido)

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

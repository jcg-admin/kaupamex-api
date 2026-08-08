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
import base64
import json
import re
import struct
import subprocess
import zlib
from datetime import datetime

import pytest

from addons.base import report_catalog
from addons.base.models.ir_ui_view import IrUiView
from addons.base.report_template import InvalidReportTemplate
from addons.base.report_catalog import ReportSpec, UnknownHelper
from addons.base.models.ir_actions_report import (
    HELPER_DIR,
    RENDERER_BY_TYPE,
    REPORT_TYPE_CHOICES,
    HelperFailed,
    HelperNotBuilt,
    IrActionsReport,
    UnknownReport,
    run_helper,
)
from addons.sale.models.sale_order_line import SaleOrderLine
from addons.sale_stock.models.sale_order import SaleOrderDelivery
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
        # Fuente TrueType embebida (T-002): el texto va como ``<hex>``, no
        # como literal. Se decodifica UTF-16BE porque libharu escribe el code
        # point y no un índice de glifo del subconjunto — medido: ``αβγ`` sale
        # como ``03B1 03B2 03B3``, que sólo cuadra si son code points.
        #
        # Dos operadores de dibujo: ``Tj`` (draw_text) y ``'`` — el
        # salto-de-línea-y-muestra que ``HPDF_Page_TextRect`` emite por cada
        # línea envuelta (T-004, medido en el stream).
        for hexado in re.findall(rb"<([0-9A-Fa-f]+)>\s*(?:Tj|')", crudo):
            salida.append(
                bytes.fromhex(hexado.decode()).decode('utf-16-be', 'replace'))
        # Rama de la base-14 (WinAnsi), viva mientras algún texto no pase por
        # la fuente embebida. Si deja de haber literales, esto queda inerte —
        # no se borra hasta comprobar que ningún helper los emite.
        for literal in re.findall(rb"\((.*?)\)\s*(?:Tj|')", crudo):
            byteado = _OCTAL.sub(
                lambda m: bytes([int(m.group(1), 8)]), literal)
            salida.append(byteado.decode('cp1252', errors='replace'))
    return '\n'.join(salida)


def operadores(pdf: bytes) -> bytes:
    """Los content streams inflados, para afirmar sobre operadores de dibujo.

    ``texto_impreso`` sólo ve texto; los operadores de trazo (``re``, ``f``,
    ``rg``) requieren el stream crudo. Misma tolerancia a streams sin
    comprimir que arriba.
    """
    ops = b''
    for bloque in re.finditer(rb'stream\r?\n(.*?)endstream', pdf, re.S):
        crudo = bloque.group(1)
        try:
            crudo = zlib.decompress(crudo)
        except zlib.error:
            # silent OK because libharu no comprime siempre (ver texto_impreso)
            pass
        ops += crudo
    return ops


def _png_1x1_b64() -> str:
    """Un PNG 1×1 válido construido a mano, como base64 (T-006).

    Sin Pillow ni fixture en disco: el contrato bajo prueba es que el logo
    viaja por el descriptor y el helper no toca el filesystem — un fixture
    en disco desmentiría el punto. Chunks con su CRC real, que es lo que la
    validación estructural del helper exige.
    """
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b'\x00\xff\x00\x00')   # filtro None + pixel RGB
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
           + chunk(b'IDAT', idat) + chunk(b'IEND', b''))
    return base64.b64encode(png).decode('ascii')


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

        Se usa ``text`` a propósito, y no un string inventado: es el caso
        **real** desde H-API-291 — el valor salió del enum por no tener quien
        lo declarara, y una fila vieja podría traerlo. Así el test mide el
        escenario que puede ocurrir, no uno imaginado.
        """
        reporte_orden.report_type = 'text'
        assert reporte_orden.render(orden_con_lineas) is None

    def test_el_enum_solo_declara_lo_que_hay_como_renderizador(self):
        """Ningún formato ofrecido sin quien lo rinda — la invariante de H-API-291.

        El defecto que cierra no es que ``text``/``html`` fueran erróneos: es
        que se ofrecían como opción por venir del catálogo de la referencia,
        sin nada aquí que los emitiera. Este caso lo vuelve mecánico.
        """
        ofrecidos = {valor for valor, _label in REPORT_TYPE_CHOICES}
        assert ofrecidos == set(RENDERER_BY_TYPE)


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

        Se afirma sobre el texto **dibujado**, no sobre el descriptor: el
        descriptor ya era correcto cuando el papel no lo era, y por eso un
        test que sólo mirara el JSON habría dado verde con el bug vivo.

        Cubre además lo que WinAnsi no podía expresar (``€``, ``—``, ``αβγ``):
        desde T-002 la fuente es LiberationSans embebida y el documento habla
        UTF-8, así que el juego de caracteres dejó de estar limitado a
        Latin-1. Antes ``€`` y ``—`` llegaban al papel como ``?``.

        El nombre se mantiene corto: el helper recorta la columna por ancho
        (T-003) — un nombre largo se cortaría por razones de espacio y
        enmascararía lo que este caso mide, que es la codificación.
        """
        acentuado = 'Vela ñ ó ú € — αβγ'
        linea = orden_con_lineas.order_line.first()
        linea.name = acentuado
        linea.save(update_fields=['name'])

        contenido, _ = reporte_orden.render(orden_con_lineas)
        assert acentuado in texto_impreso(contenido)

    def test_la_columna_recorta_por_ancho_no_por_bytes(self, reporte_orden,
                                                       orden_con_lineas):
        """T-003 — el presupuesto de columna es geométrico, no de bytes.

        El corte anterior era ``name[36] = '\\0'``: 36 **bytes**, que con la
        fuente UTF-8 de T-002 eran 36 letras latinas pero sólo 18 acentuadas —
        el ancho dibujado dependía del idioma del dato. Ahora el helper mide
        con ``HPDF_Page_TextWidth`` y corta donde termina la columna.

        Se afirma la propiedad, no una cifra: con el mismo nombre en versión
        estrecha (``i``) y ancha (``W``), caben **más** estrechas que anchas —
        exactamente lo que un corte por bytes no puede producir (daría el
        mismo conteo para ambas). Medido en el pase: 90 ``i`` vs 22 ``W``.
        """
        linea = orden_con_lineas.order_line.first()
        dibujadas = {}
        for letra in ('i', 'W'):
            linea.name = letra * 90
            linea.save(update_fields=['name'])
            contenido, _ = reporte_orden.render(orden_con_lineas)
            fila = next(t for t in texto_impreso(contenido).splitlines()
                        if t.startswith(letra * 3))
            dibujadas[letra] = len(fila)

        assert dibujadas['i'] > dibujadas['W'], (
            'con corte por bytes ambas darían igual; por ancho caben más '
            f'estrechas que anchas — medido {dibujadas}'
        )
        # Ninguna fila desborda el buffer de 90: el recorte actuó o cupo todo.
        assert dibujadas['W'] < 90

    def test_la_direccion_larga_se_envuelve_no_se_corta(self):
        """T-004 — un campo largo se reparte en líneas, sin perder texto.

        Antes las direcciones se dibujaban en UNA llamada sin envoltura: lo
        que no cabía se salía de la caja. Con ``TextRect`` el texto se
        envuelve por palabras y — clave — ante caja insuficiente la libharu
        vendorizada devuelve ``HPDF_PAGE_INSUFFICIENT_SPACE`` SIN pasar por
        el manejador de errores (``hpdf_page_operator.c:2631``), así que no
        tumba el helper.
        """
        direccion = ('Avenida de los Insurgentes Sur número 3500, interior '
                     '12-B, colonia Peña Pobre, alcaldía Tlalpan, Ciudad de '
                     'México, C.P. 14060, México')
        contenido = run_helper('pdf_receipt', {
            'issuer': {'name': 'Kaupamex'},
            'order_number': 'A-1', 'date': '2026-08-05',
            'buyer': {'name': 'José Ñuñez', 'address': direccion},
            'items': [], 'totals': {'total': '0.00'},
        })
        impreso = texto_impreso(contenido)
        lineas = impreso.splitlines()
        # Nada se perdió: el final de la dirección llegó al papel...
        assert '14060' in impreso
        # ...y ninguna línea la contiene entera — se envolvió de verdad.
        assert not any(direccion in linea for linea in lineas)
        assert sum('Insurgentes' in l or '14060' in l for l in lineas) >= 2

    def test_el_encabezado_lleva_banda_sombreada_sin_mover_el_texto(self):
        """T-005 — ``Rectangle`` + ``Fill`` sombrean el encabezado de tabla.

        Los operadores estaban compilados en la libharu vendorizada y nunca
        se llamaban. La banda se pinta ANTES del texto (los glifos usan el
        fill color, así que el helper restaura ``0 0 0 rg`` antes de
        escribir) y la no-regresión es que el contenido no se desplaza: los
        rótulos y datos siguen llegando al papel.
        """
        contenido = run_helper('pdf_receipt', {
            'issuer': {'name': 'Kaupamex'},
            'order_number': 'A-2', 'date': '2026-08-05',
            'buyer': {'name': 'Ana', 'address': 'Calle 1'},
            'items': [{'name': 'Ofrenda', 'sku': 'S1', 'quantity': '1',
                       'unit_price': '10.00', 'amount': '10.00'}],
            'totals': {'subtotal': '10.00', 'total': '10.00'},
        })
        ops = operadores(contenido)
        # La banda: gris de relleno → rectángulo → fill → negro restaurado.
        assert re.search(rb'0\.9\d* 0\.9\d* 0\.9\d* rg', ops)
        assert re.search(rb'[\d.]+ [\d.]+ [\d.]+ [\d.]+ re\s+f\s', ops)
        assert b'0 0 0 rg' in ops
        # No-regresión: el dibujo no desplazó el contenido.
        impreso = texto_impreso(contenido)
        for esperado in ('Producto', 'SKU', 'Ofrenda', '10.00', 'TOTAL'):
            assert esperado in impreso

    def test_el_logo_viaja_en_el_descriptor_y_se_incrusta(self):
        """T-006 — el PNG va en base64 dentro del descriptor, no en disco.

        Antes el helper leía ``logo_path`` con ``LoadPngImageFromFile``;
        ahora decodifica ``issuer.logo`` y usa ``LoadPngImageFromMem`` —
        cero filesystem. El PNG del caso se construye a mano (firma + IHDR
        + IDAT + IEND con sus CRC) para no depender de fixtures en disco:
        el punto del contrato es justamente que no hay archivos.
        """
        contenido = run_helper('pdf_receipt', {
            'issuer': {'name': 'Kaupamex', 'logo': _png_1x1_b64()},
            'order_number': 'A-3', 'date': '2026-08-05',
            'buyer': {'name': 'Ana', 'address': 'Calle 1'},
            'items': [], 'totals': {'total': '0.00'},
        })
        # El XObject de imagen sale como diccionario en claro en el PDF.
        assert b'/Subtype /Image' in contenido
        assert 'Kaupamex' in texto_impreso(contenido)

    def test_el_logo_corrupto_degrada_a_sin_logo(self):
        """H-API-294 — un PNG roto NO cuelga ni tumba el recibo.

        El ``PngErrorFunc`` del libharu vendorizado retorna, y libpng exige
        que su callback de error no retorne: con firma válida y cuerpo
        corrupto el proceso quedaba COLGADO (medido con ``timeout``). El
        helper valida ahora la estructura de chunks + CRC antes de llamar a
        libpng; lo que no pasa degrada a "sin logo" y el documento sale.
        """
        roto = base64.b64encode(
            b'\x89PNG\r\n\x1a\n' + b'basura' * 10).decode()
        contenido = run_helper('pdf_receipt', {
            'issuer': {'name': 'Kaupamex', 'logo': roto},
            'order_number': 'A-4', 'date': '2026-08-05',
            'buyer': {'name': 'Ana', 'address': 'Calle 1'},
            'items': [], 'totals': {'total': '0.00'},
        })
        assert b'/Subtype /Image' not in contenido
        assert 'Kaupamex' in texto_impreso(contenido)

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


@helpers_built
class TestPlantillaEnBD:
    """La plantilla del documento vive en ``ir.ui.view`` — interpretada.

    Directiva del ejecutor 2026-08-05: el reporte usa también
    ``self.env['ir.ui.view']``. La vista se resuelve por ``key`` =
    ``report_name`` (el camino de la referencia, ``:769-781``), su arch
    combinado se interpreta hacia el descriptor JSON, y las extensiones
    XPath de otros addons entran solas por ``get_combined_arch``.
    """

    ARCH = (
        '<descriptor>'
        '<section name="issuer">'
        '<field name="name">Plantilla Kaupamex ñ</field>'
        '</section>'
        '<field name="order_number">{{ docs.pk }}</field>'
        '<list name="items" in="docs.order_line.all">'
        '<field name="name">{{ item.name }}</field>'
        '<field name="quantity">{{ item.quantity }}</field>'
        '</list>'
        '</descriptor>'
    )

    def make_template_view(self, arch=None, **kwargs):
        # ``priority=1`` gana sobre la fila SEMBRADA por sale.0002 (default
        # 16): el orden de resolución es priority,id y estos casos prueban
        # el mecanismo con SU plantilla, no con la del addon.
        return IrUiView.objects.create(
            name='reporte de prueba', type='qweb',
            key='sale.report_saleorder', arch_db=arch or self.ARCH,
            mode='primary', priority=1, **kwargs,
        )

    def test_la_vista_redefine_el_documento(self, reporte_orden,
                                            orden_con_lineas):
        self.make_template_view()
        contenido, _ext = reporte_orden.render(orden_con_lineas)
        impreso = texto_impreso(contenido)
        # El emisor sale de la plantilla en BD, no del builder — y con acento,
        # porque el camino UTF-8 de T-002 también cubre esta vía.
        assert 'Plantilla Kaupamex ñ' in impreso
        # La lista se iteró contra el recordset real.
        linea = orden_con_lineas.order_line.first()
        assert linea.name in impreso

    def test_sin_vista_el_builder_sigue_siendo_el_documento(
            self, reporte_orden, orden_con_lineas):
        # Open/Closed: la vista es extensión, no reemplazo del mecanismo. La
        # fila sembrada por sale.0002 se retira (extensiones primero, por el
        # inherit_id) para probar el respaldo; el rollback por test la
        # restaura.
        IrUiView.objects.filter(inherit_id__isnull=False).delete()
        IrUiView.objects.filter(key='sale.report_saleorder').delete()
        contenido, _ext = reporte_orden.render(orden_con_lineas)
        assert contenido.startswith(b'%PDF')

    def test_una_extension_xpath_agrega_su_campo(self, reporte_orden,
                                                 orden_con_lineas):
        # El análogo del bloque incoterm que sale_stock añade al reporte de
        # sale en la referencia (sale_order_report_templates.xml): otra vista
        # parcha el documento SIN tocar la plantilla base.
        base = self.make_template_view()
        IrUiView.objects.create(
            name='extension incoterm', type='qweb',
            key='sale.report_saleorder_inherit_prueba',
            inherit_id=base, mode='extension',
            arch_db=('<xpath expr="//section[@name=\'issuer\']" '
                     'position="inside">'
                     '<field name="phone">Incoterm EXW</field>'
                     '</xpath>'),
        )
        contenido, _ext = reporte_orden.render(orden_con_lineas)
        assert 'Incoterm EXW' in texto_impreso(contenido)

    def test_arch_fuera_de_vocabulario_levanta(self, reporte_orden,
                                               orden_con_lineas):
        self.make_template_view(arch='<html><body/></html>')
        with pytest.raises(InvalidReportTemplate):
            reporte_orden.render(orden_con_lineas)


@helpers_built
class TestPlantillaSembrada:
    """La plantilla real de ``sale`` vive sembrada en BD (#63).

    ``sale.0002`` siembra la vista primaria (el aterrizaje nativo del
    ``data/*.xml`` de la referencia) y ``sale_stock.0003`` cuelga su
    extensión Incoterm — el análogo del ``<xpath position="after">`` de
    ``sale_order_report_templates.xml``, anclado en la sección ``notes``
    que el helper dibuja línea a línea.
    """

    def test_la_siembra_existe_y_es_la_forma_de_la_referencia(self):
        primaria = IrUiView.objects.get(
            key='sale.report_saleorder', mode='primary')
        extension = IrUiView.objects.get(
            key='sale_stock.report_saleorder_incoterm')
        assert extension.inherit_id_id == primaria.pk
        assert extension.mode == 'extension'

    def test_la_vista_sembrada_espeja_al_builder(self, reporte_orden,
                                                 orden_con_lineas):
        """La siembra releva al builder SIN cambiar el documento.

        Igualdad campo a campo entre las dos vías; la fecha se compara
        parseada (el filtro ``date:'c'`` y ``isoformat`` difieren en la
        zona con que escriben el mismo instante). El descriptor de la vista
        puede traer claves EXTRA (``notes`` de las extensiones): el helper
        ignora lo que no dibuja, así que el subconjunto del builder es el
        contrato.
        """
        del_builder = report_catalog.get(
            'sale.report_saleorder').builder(orden_con_lineas)
        de_la_vista = reporte_orden._descriptor_from_view(
            orden_con_lineas, {})
        assert de_la_vista is not None
        for clave, valor in del_builder.items():
            if clave == 'date':
                # Mismo instante con distinto traje: el filtro ``date:'c'``
                # escribe en zona local y con microsegundos; ``isoformat``
                # del builder trunca a segundos en UTC. Se comparan
                # parseados y sin microsegundos.
                assert (datetime.fromisoformat(
                            de_la_vista[clave]).replace(microsecond=0)
                        == datetime.fromisoformat(valor))
            else:
                assert de_la_vista[clave] == valor, clave

    def test_incoterm_de_sale_stock_llega_al_papel(self, reporte_orden,
                                                   orden_con_lineas):
        SaleOrderDelivery.objects.create(
            order=orden_con_lineas, incoterm_location='FOB Veracruz')
        contenido, _ext = reporte_orden.render(orden_con_lineas)
        assert 'Incoterm: FOB Veracruz' in texto_impreso(contenido)

    def test_sin_incoterm_la_nota_no_se_dibuja(self, reporte_orden,
                                               orden_con_lineas):
        contenido, _ext = reporte_orden.render(orden_con_lineas)
        assert 'Incoterm' not in texto_impreso(contenido)

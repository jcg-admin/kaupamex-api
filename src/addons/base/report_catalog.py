"""Declaración de reportes por addon dueño — el catálogo de ``ir.actions.report``.

Espejo de cómo la referencia declara sus reportes, adaptado al sustrato de este
árbol.

Qué hace la referencia
======================

En ``odoo19c:`` un reporte es un **registro de datos**, no código: cada addon
declara los suyos en ``<addon>/report/*.xml`` con ``model="ir.actions.report"``.
Medido (``odoo-tools@622ddc2a``, ``odoo19c:``): **8 addons** que también
existen aquí declaran reportes — ``stock`` 21, ``product`` 7, ``account`` 6,
``mrp`` 6, ``sale`` 2, ``purchase`` 2, ``loyalty`` 2, ``hr`` 1.

El campo que enlaza el registro con lo que se dibuja es ``report_name``
(``sale.report_saleorder``, ``stock.report_deliveryslip``…): apunta a una
**plantilla QWeb** que el motor genérico renderiza. Un motor, N documentos —
la razón por la que la referencia tiene ~900 líneas de motor y 92 registros,
no 92 motores.

La lógica abstracta, medida — seis pasos, no "una librería"
===========================================================

Lo que gobierna no es ``wkhtmltopdf``; es la **cadena** que la referencia
monta, y en la que ``wkhtmltopdf`` ocupa **un solo paso**, intercambiable por
construcción. Medido en ``odoo19c: odoo/addons/base/models/ir_actions_report.py``:

.. code-block:: text

   1 DECLARACIÓN   ir.actions.report — registro: modelo, report_name, tipo, papel
                   ↓ report_name (puntero indirecto)
   2 CONTEXTO      _get_rendering_context(report, docids, data)   :1123
                   ↓ recordset → datos
   3 COMPOSICIÓN   _render_template(report_name, data)            :769
                   ↓ datos → INTERMEDIO
   4 DESPACHO      _render → _render_<report_type>                :1145-1151
                   ↓ el mismo intermedio sale como html / text / pdf
   5 CONVERSIÓN    _run_wkhtmltopdf(intermedio)                   :879-891
                   ↓ sólo para el tipo pdf
   6 POST-PROCESO  _merge_pdfs :795 · add_banner (tools/pdf) · retrieve_attachment
                   ↓ opera sobre el PDF ya hecho

La prueba de que 3 y 5 son pasos distintos: ``_render_qweb_pdf`` **llama a**
``_render_qweb_html`` (``:879``) y luego convierte. Los tres ``report_type``
comparten la misma plantilla y el mismo contexto — cambia sólo qué se hace con
el intermedio.

**Fuera de la cadena:** ``barcode()`` (``:688``) se sirve por HTTP
(``/report/barcode/<tipo>/<valor>``) y la composición lo referencia como
``<img>``. No es un paso del pipeline: es un **recurso externo direccionable**.
Por eso el motor nunca dibuja un símbolo.

Qué ocupa cada paso aquí
========================

Los pasos **1, 2, 4 y 6** y el recurso externo son idénticos: no dependen del
sustrato. Cambian dos:

- **Paso 3 (intermedio):** donde la referencia compone HTML con QWeb, aquí se
  compone un **descriptor JSON**. ``report_name`` sigue siendo el puntero
  indirecto, pero apunta a un **constructor de descriptor** en vez de a una
  plantilla.
- **Paso 5 (conversión):** libharu en vez de ``wkhtmltopdf`` (ADR-017).

Deuda declarada — nuestros helpers colapsan 3 y 5
=================================================

En la referencia el intermedio existe **fuera** del conversor, y por eso un
mismo ``report_name`` sale en tres formatos sin tocar la plantilla. Nuestros
helpers en C reciben el descriptor y devuelven PDF en un solo proceso: componen
**y** convierten.

Consecuencia concreta: aquí ``report_type`` **no puede variar
independientemente** del helper. Un reporte declarado ``pdf`` no se puede
servir como ``html`` reutilizando su constructor, porque no hay intermedio
neutral que un segundo conversor pueda leer.

Se acepta el colapso —construir un intermedio neutral propio es trabajo mayor y
hoy prematuro— pero se declara, y por eso ``ReportSpec`` nombra su ``helper``:
no es que la declaración deba conocer el sustrato, es que en este árbol **no
hay separación que ocultar**. El día que exista, ``helper`` sale del spec.

Layout — ``<addon>/report/report_catalog.py``
=============================================

Se calca el layout de la referencia, que agrupa los reportes bajo ``report/``
en 7 de los 8 addons medidos (la excepción es ``account``, que los mete en
``views/``). El descubrimiento acepta las dos rutas por el mismo criterio
retrocompatible que ``authz/declaration.py``:

1. ``<app>.report.report_catalog`` — layout fiel a la referencia.
2. ``<app>.report_catalog`` — layout plano, para addons aún sin ``report/``.

Se usa ``importlib.import_module`` —una **llamada**, no un statement
``import``— porque el descubrimiento es dinámico
(``.claude/rules/no-lazy-imports.md`` excepción #4; pasa el gate AST).
"""
import importlib
import logging

from django.apps import apps

#: Nombre del módulo que cada addon puede definir para declarar sus reportes.
DECLARATION_MODULE = 'report_catalog'

#: Helpers disponibles, con la forma de descriptor que cada uno consume.
#: Medido sobre ``src/tools/pdf/*.c`` (claves que parsea cada binario):
#:
#: - ``pdf_report``  — genérico tabular: ``title``/``subtitle``/
#:   ``generated_at``/``columns``/``rows``.
#: - ``pdf_receipt`` — documento fiscal: ``issuer``/``buyer``/``payment``/
#:   ``items``/``totals``.
#:
#: La frontera entre los dos es la respuesta medida a "hasta dónde llega un
#: solo binario": ``pdf_report`` cubre **todo lo tabular** (listados, precios,
#: inventario); ``pdf_receipt`` cubre la forma emisor+receptor+líneas+totales.
#: Un tercer helper sólo se justifica ante una forma que ninguno de los dos
#: exprese — no ante un documento nuevo de una forma ya cubierta.
HELPERS = ('pdf_report', 'pdf_receipt')

_logger = logging.getLogger(__name__)


class DuplicateReport(Exception):
    """Dos addons declaran el mismo ``report_name``.

    Ruidoso a propósito, mismo criterio que ``DuplicateDeclaration`` del
    catálogo authz: un ``report_name`` tiene exactamente un dueño. Si dos
    addons lo reclaman, el registro sembrado dependería del orden de
    ``INSTALLED_APPS`` — un ganador silencioso.
    """


class UnknownHelper(Exception):
    """Un ``ReportSpec`` declara un helper que no está en ``HELPERS``."""


class ReportSpec:
    """Declaración de un ``ir.actions.report`` por parte de su addon dueño.

    Los cinco primeros campos calcan el registro de la referencia; ``helper`` y
    ``builder`` son el sustrato propio (ver el docstring del módulo).

    :param report_name: identificador estable, ``<addon>.<slug>``. Es la clave
        del registro y lo que el modelo guarda — mismo rol que en la
        referencia.
    :param model: modelo destino, en el formato de este árbol
        (``'sale.SaleOrder'``, label Django) y no en el de Odoo
        (``'sale.order'``). Mismo criterio ya fijado por
        ``ir_rule.model_name``.
    :param name: etiqueta legible; la que ve quien imprime.
    :param report_type: formato de salida. Hoy **sólo** ``pdf`` — el enum
        lista lo que este árbol sabe emitir, no el catálogo de la referencia
        (H-API-291). **Sin** el prefijo ``qweb-``: aquí no hay QWeb, así que
        el prefijo afirmaría un sustrato inexistente. Ver
        ``REPORT_TYPE_CHOICES`` en ``ir_actions_report.py`` para la tabla de
        correspondencia con la referencia.
    :param helper: binario de ``tools/pdf/`` que dibuja. Sólo para ``pdf``.
    :param builder: callable ``(records, **ctx) -> dict``. Recibe el recordset
        y devuelve el descriptor JSON del helper. Es el análogo de la
        plantilla QWeb.
    """

    __slots__ = ('report_name', 'model', 'name', 'report_type', 'helper',
                 'builder')

    def __init__(self, report_name, model, name, builder,
                 report_type='pdf', helper='pdf_report'):
        if report_type == 'pdf' and helper not in HELPERS:
            raise UnknownHelper(
                f'{report_name}: helper {helper!r} no está en {HELPERS}')
        self.report_name = report_name
        self.model = model
        self.name = name
        self.builder = builder
        self.report_type = report_type
        self.helper = helper

    def __repr__(self):
        return f'ReportSpec({self.report_name!r})'


def _import_declaration(app_config):
    """Importa el módulo de declaración de un addon, o ``None`` si no tiene.

    Dos rutas aceptadas, en orden (ver el docstring del módulo). Sólo se traga
    la ausencia del propio archivo (o de su paquete ``report``): un
    ``ModuleNotFoundError`` lanzado **desde dentro** del catálogo se propaga,
    porque tragarlo haría desaparecer los reportes del addon en silencio.
    """
    for dotted_path in (
        f'{app_config.name}.report.{DECLARATION_MODULE}',
        f'{app_config.name}.{DECLARATION_MODULE}',
    ):
        try:
            return importlib.import_module(dotted_path)
        except ModuleNotFoundError as exc:
            if exc.name in (dotted_path, f'{app_config.name}.report'):
                continue
            raise
    return None


def discover():
    """Recorre ``INSTALLED_APPS`` y devuelve ``{report_name: ReportSpec}``.

    El orden de inserción es el de ``INSTALLED_APPS``, estable entre corridas.
    Levanta ``DuplicateReport`` si dos addons declaran el mismo
    ``report_name``.
    """
    found = {}
    owners = {}
    for app_config in apps.get_app_configs():
        declared = _import_declaration(app_config)
        if declared is None:
            continue
        for spec in getattr(declared, 'REPORTS', ()):
            previous = owners.get(spec.report_name)
            if previous is not None:
                raise DuplicateReport(
                    f'{spec.report_name!r} declarado por {previous!r} y '
                    f'{app_config.label!r}')
            owners[spec.report_name] = app_config.label
            found[spec.report_name] = spec
    return found


def get(report_name):
    """Devuelve el ``ReportSpec`` de ``report_name``, o ``None``.

    Sin caché deliberadamente: ``discover()`` sólo recorre ``INSTALLED_APPS``
    y lee módulos ya importados por Python, y una caché a nivel de módulo
    sobreviviría entre tests con distinto ``INSTALLED_APPS``. Si el perfil lo
    justifica, la caché va con invalidación explícita, no implícita.
    """
    return discover().get(report_name)

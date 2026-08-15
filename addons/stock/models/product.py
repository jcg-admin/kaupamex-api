"""``product.template`` / ``product.product`` — la superficie que ``stock`` cuelga.

Adaptación de Odoo ``stock/models/product.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Porte PARCIAL declarado — 1 de 141 símbolos
=============================================

Medido sobre ``odoo19c: addons/stock/models/product.py`` (1393 líneas):
4 clases (``ProductProduct``, ``ProductTemplate``, ``ProductCategory``,
``UomUom``), **58 campos y 83 métodos**. Este archivo porta **uno**:
``tracking``.

No es un porte a medias en silencio —lo que ``porte-completo-no-parcial.md``
prohíbe— sino la **dependencia mínima nombrada** que ``product_expiry``
necesita para portar su ``write`` sin racionalizarlo. El resto del archivo es
alcance de la tarea **#274** (``stock``: 17 archivos ausentes, 564 métodos y
272 campos medidos), donde este módulo se completa por bloques.

Por qué ``tracking`` vive aquí y no en ``product_expiry``
----------------------------------------------------------

Porque es donde la referencia lo declara: ``odoo19c: stock/models/product.py:842``.
``product_expiry`` lo **lee** (``if tracking == 'none': use_expiration_date =
False``) pero no lo declara — colgarlo desde el satélite pondría el símbolo en
el addon equivocado, que es la clase de defecto que :ref:`h-api-350` registra
(el porte que entrega todos los símbolos con la forma y el sitio cambiados).

Divergencia declarada — los dos ``compute`` se invocan a mano
--------------------------------------------------------------

La referencia declara ``is_storable`` y ``tracking`` como campos
**almacenados con compute** (``compute='compute_is_storable'`` y
``compute='_compute_tracking'``, ambos ``store=True, readonly=False,
precompute=True``): su ORM los recalcula cuando cambia la dependencia y el
valor queda editable. Aquí son campos almacenados con default y sus dos
computes se portan como métodos que el consumidor invoca — el motor de
``@api.depends`` no existe todavía (tarea **#191**).

El texto anterior de esta sección decía que ``_compute_tracking`` estaba
bloqueado porque dependía de ``is_storable``/``type``, «dos campos de este
mismo archivo que aún no están portados». Ya lo están —``is_storable`` en este
pase, ``type`` desde ``product.template``— así que el compute entró con ellos,
que es la condición que ese texto fijaba.
"""
import fields

from tools.mail import html2plaintext, is_html_empty

from addons.product.models import ProductProduct, ProductTemplate
from addons.product.models.product_template import TYPE_CONSU

#: ≙ ``tracking`` (``odoo19c: stock/models/product.py:842-848``). El
#: vocabulario es el de la referencia, verbatim y en el mismo orden.
TRACKING_CHOICES = [
    ('serial', 'Por número de serie único'),
    ('lot', 'Por lotes'),
    ('none', 'Por cantidad'),
]


def _add_if_absent(model, name, field):
    """Añade el campo sólo si el modelo no lo tiene ya — ver ``account_fleet``."""
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def tracking(self):
    """≙ ``product.product.tracking`` — delegado al template.

    Mismo idioma que ``categ``/``uom``/``type`` en
    ``api: addons/product/models/product_product.py``: la variante expone por
    property lo que el template declara como columna.
    """
    return self.product_tmpl.tracking


def is_storable(self):
    """≙ ``product.product.is_storable`` — delegado al template.

    Mismo idioma que ``tracking``: la variante expone por property lo que el
    template declara como columna.
    """
    return self.product_tmpl.is_storable


def compute_is_storable(self):
    """≙ ``compute_is_storable`` (``odoo19c: stock/models/product.py:898-899``).

    «``self.filtered(lambda t: t.type != 'consu' and t.is_storable).is_storable
    = False``» — sólo un **bien** (``consu``) puede llevar existencias; un
    servicio o un combo no, y si alguien lo marcó se desmarca.

    El nombre va **sin** guion bajo porque la referencia lo declara así
    (``compute='compute_is_storable'``, ``:826``): es de los pocos ``compute``
    que expone en público, y el porte conserva su visibilidad
    (``porte-completo-no-parcial.md``, H-API-581).
    """
    if self.type != TYPE_CONSU and self.is_storable:
        self.is_storable = False


def _compute_tracking(self):
    """≙ ``_compute_tracking`` (``odoo19c: stock/models/product.py:1080-1082``).

    «``self.filtered(lambda t: not t.is_storable and t.tracking != 'none')
    .tracking = 'none'``» — sin existencias que rastrear no hay trazabilidad
    que declarar.

    Estaba **bloqueado** hasta este pase: el docstring de arriba decía que
    depende de ``is_storable``/``type``, «dos campos de este mismo archivo que
    aún no están portados». Ya lo están, así que el compute entra con ellos —
    que es exactamente lo que ese texto anticipaba.
    """
    if not self.is_storable and self.tracking != 'none':
        self.tracking = 'none'


def _get_description(self, picking_type):
    """≙ ``_get_description`` (``odoo19c: stock/models/product.py:319-329``).

    Descripción del producto según el tipo de operación: en una **salida**
    siempre manda el nombre; en el resto se intenta la descripción larga y,
    si está vacía, se cae al nombre.

    El guion bajo se conserva porque la fuente lo declara así
    (``porte-completo-no-parcial.md``, H-API-581).
    """
    if getattr(picking_type, 'code', None) == 'outgoing':
        return self.display_name
    descripcion = getattr(self.product_tmpl, 'description', None)
    return html2plaintext(descripcion) if not is_html_empty(descripcion) \
        else self.display_name


def _get_picking_description(self, picking_type):
    """≙ ``_get_picking_description`` (``odoo19c: stock/models/product.py:331-339``).

    La descripción **específica de la operación**: recepción, entrega o
    interna. Sin tipo de operación no hay descripción que elegir.
    """
    tmpl = self.product_tmpl
    return {
        'incoming': tmpl.description_pickingin,
        'outgoing': tmpl.description_pickingout,
        'internal': tmpl.description_picking,
    }.get(getattr(picking_type, 'code', None), '')


def apply_stock_product_extensions():
    """Cuelga ``is_storable`` y ``tracking`` sobre ``product.template``.

    La llama ``StockConfig.ready()``; los tests la invocan explícitamente
    (mismo criterio que ``account_fleet``).
    """
    _add_if_absent(ProductTemplate, 'is_storable', fields.Boolean(
        default=False,
        help_text='Lleva existencias en almacén (Odoo is_storable, '
                  '«Track Inventory»).',
    ))
    _add_if_absent(ProductTemplate, 'tracking', fields.Selection(
        choices=TRACKING_CHOICES, max_length=16, default='none',
        help_text='Trazabilidad del producto almacenable (Odoo tracking).',
    ))
    if not hasattr(ProductTemplate, 'compute_is_storable'):
        ProductTemplate.compute_is_storable = compute_is_storable
    if not hasattr(ProductTemplate, '_compute_tracking'):
        ProductTemplate._compute_tracking = _compute_tracking
    if not hasattr(ProductProduct, 'tracking'):
        ProductProduct.tracking = property(tracking)
    if not hasattr(ProductProduct, 'is_storable'):
        ProductProduct.is_storable = property(is_storable)

    # ≙ ``description_picking`` / ``description_pickingout`` /
    # ``description_pickingin`` (``odoo19c: stock/models/product.py:856-858``).
    # Los declara ``product.template``; los consume ``_get_picking_description``.
    for nombre, etiqueta in (
        ('description_picking', 'Descripción en el albarán'),
        ('description_pickingout', 'Descripción en órdenes de entrega'),
        ('description_pickingin', 'Descripción en recepciones'),
    ):
        _add_if_absent(ProductTemplate, nombre, fields.Text(
            null=True, blank=True, verbose_name=etiqueta,
            help_text=f'Odoo {nombre}. La referencia lo declara traducible; '
                      'el almacenamiento jsonb de translate=True es la tarea #333.',
        ))
    if not hasattr(ProductProduct, '_get_description'):
        ProductProduct._get_description = _get_description
    if not hasattr(ProductProduct, '_get_picking_description'):
        ProductProduct._get_picking_description = _get_picking_description

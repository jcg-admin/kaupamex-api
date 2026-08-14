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

Divergencia declarada — el ``compute`` de ``tracking``
--------------------------------------------------------

La referencia declara ``compute='_compute_tracking', store=True,
readonly=False, precompute=True``: el valor se recalcula cuando cambia el tipo
de producto y queda editable. Aquí se porta como campo **almacenado con
default**, sin el compute: ``_compute_tracking`` depende de
``is_storable``/``type``, dos campos de este mismo archivo que aún no están
portados. El compute entra con ellos, en el mismo bloque de #274 — no antes,
porque un compute sobre campos ausentes no se puede escribir sin inventar sus
dependencias.
"""
import fields

from addons.product.models import ProductProduct, ProductTemplate

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


def apply_stock_product_extensions():
    """Cuelga ``tracking`` sobre ``product.template`` y su delegación.

    La llama ``StockConfig.ready()``; los tests la invocan explícitamente
    (mismo criterio que ``account_fleet``).
    """
    _add_if_absent(ProductTemplate, 'tracking', fields.Selection(
        choices=TRACKING_CHOICES, max_length=16, default='none',
        help_text='Trazabilidad del producto almacenable (Odoo tracking).',
    ))
    if not hasattr(ProductProduct, 'tracking'):
        ProductProduct.tracking = property(tracking)

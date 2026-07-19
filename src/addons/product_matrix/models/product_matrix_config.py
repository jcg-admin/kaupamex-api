"""Modelo ``ProductMatrixConfig`` — addon ``product_matrix``.

Adaptación de Odoo ``product_matrix``, que **extiende** ``product.template``
con ``product_add_mode`` (``configurator`` | ``matrix``) y el método
``_get_template_matrix`` que arma la grilla de combinaciones de atributos. Como
módulo-extensión (DEC-SALE-01), en Django es una app propia con **modelo
relacionado** (OneToOne a ``catalogue.Product``) para el ``add_mode``, más el
constructor de la grilla.

El sistema de variantes de este stack es ``chartsize`` (``VariantType`` =
línea de atributo, ``VariantOption`` = valor, ``ProductVariant`` = variante
concreta). La grilla se construye sobre él: cada ``VariantType`` es una fila y
sus ``VariantOption`` activos son las celdas (la variante, su SKU, precio y
stock). No se fabrica el motor de combinaciones cartesianas ni el widget JS de
Odoo (Clausula 5): aquí cada ``ProductVariant`` ya es una celda concreta.
"""
import fields
import models

from core.models import TimeStampedModel


class ProductMatrixConfig(TimeStampedModel):
    """Configura el modo de alta por matriz de un ``catalogue.Product``."""

    MODE_CONFIGURATOR = 'configurator'
    MODE_MATRIX       = 'matrix'
    MODE_CHOICES = [
        (MODE_CONFIGURATOR, 'Configurador'),
        (MODE_MATRIX, 'Matriz'),
    ]

    product  = models.OneToOneField(
        'catalogue.Product', on_delete=models.CASCADE, related_name='matrix_config',
        help_text='Producto (Odoo product.template).',
    )
    # Odoo product.template.product_add_mode.
    add_mode = fields.Selection(
        max_length=16, choices=MODE_CHOICES, default=MODE_CONFIGURATOR,
        help_text='Modo de alta (Odoo product_add_mode).',
    )

    class Meta:
        db_table = 'product_matrix_config'
        verbose_name = 'Config de matriz de producto'
        verbose_name_plural = 'Configs de matriz de producto'

    def __str__(self) -> str:
        return f'{self.product} [{self.add_mode}]'

    @staticmethod
    def build(product) -> dict:
        """Arma la grilla de variantes de ``product`` (Odoo _get_template_matrix).

        Devuelve ``{'header': str, 'rows': [...]}`` donde cada fila corresponde a
        un ``VariantType`` activo y cada celda a un ``VariantOption`` activo con
        su variante concreta (id/sku/precio/stock). Sólo variantes no borradas y
        activas entran en la grilla.
        """
        rows = []
        variant_types = product.variant_types.filter(
            is_active=True, is_deleted=False,
        ).order_by('order', 'name')
        for vtype in variant_types:
            cells = []
            options = vtype.options.filter(
                is_active=True, is_deleted=False,
            ).order_by('order', 'label')
            for option in options:
                variant = getattr(option, 'variant', None)
                if variant is None or variant.is_deleted or not variant.is_active:
                    continue
                cells.append({
                    'variant_id': variant.id,
                    'label': option.label,
                    'sku': variant.sku,
                    'price': variant.effective_price(),
                    'stock': variant.stock,
                })
            rows.append({'type': vtype.name, 'cells': cells})
        return {'header': product.name, 'rows': rows}

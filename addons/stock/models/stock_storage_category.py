"""``stock.storage.category`` y su capacidad — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_storage_category.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Qué es: la **categoría de almacenamiento** limita qué y cuánto cabe en una
ubicación. Una estantería de categoría *"refrigerado, sólo un producto"*
rechaza mezclar; una de *"tarima"* admite hasta N paquetes de un tipo. Es la
pieza que ``stock.location`` consulta antes de aceptar un producto, y la que
``stock.package.type`` usa para declarar cuántos paquetes suyos entran.

Porte símbolo por símbolo — 20 de 20
======================================

Medido sobre ``odoo19c: addons/stock/models/stock_storage_category.py``
(75 líneas): 2 clases, 13 campos y 7 métodos/restricciones.

``StockStorageCategory`` — 3 atributos de clase + 8 campos + 4 métodos
-----------------------------------------------------------------------

=============================================  =========================================
Símbolo de la referencia (línea)               Aquí
=============================================  =========================================
``_name`` (8)                                  ``_name`` verbatim
``_description`` (9)                           ``_description`` verbatim
``_order`` (10)                                ``_order`` verbatim + ``Meta.ordering``
``name`` (12)                                  ``name``
``max_weight`` (13)                            ``max_weight``
``capacity_ids`` (14)                          reverso ``capacity_ids`` de la capacidad
``product_capacity_ids`` (15)                  property ``product_capacity_ids``
``package_capacity_ids`` (16)                  property ``package_capacity_ids``
``allow_new_product`` (17-20)                  ``allow_new_product``
``location_ids`` (21)                          reverso ``location_ids`` de la ubicación
``company_id`` (22)                            ``company``
``weight_uom_name`` (23)                       property ``weight_uom_name``
``_positive_max_weight`` (25-28)               ``CheckConstraint`` homónimo
``_compute_storage_capacity_ids`` (30-34)      las dos properties de arriba
``_compute_weight_uom_name`` (36-37)           property ``weight_uom_name``
``_set_storage_capacity_ids`` (39-41)          ``_set_storage_capacity_ids``
``copy_data`` (43-45)                          ``copy_data``
=============================================  =========================================

``StockStorageCategoryCapacity`` — 4 atributos de clase + 6 campos + 3 restricciones
--------------------------------------------------------------------------------------

=============================================  =========================================
Símbolo de la referencia (línea)               Aquí
=============================================  =========================================
``_name`` (49)                                 ``_name`` verbatim
``_description`` (50)                          ``_description`` verbatim
``_check_company_auto`` (51)                   ``_check_company_auto`` verbatim
``_order`` (52)                                ``_order`` verbatim + ``Meta.ordering``
``storage_category_id`` (54)                   ``storage_category``
``product_id`` (55-59)                         ``product``
``package_type_id`` (60)                       ``package_type``
``quantity`` (61)                              ``quantity``
``product_uom_id`` (62)                        property ``product_uom``
``company_id`` (63)                            property ``company``
``_positive_quantity`` (65-68)                 ``CheckConstraint`` homónimo
``_unique_product`` (69-72)                    ``UniqueConstraint`` homónimo
``_unique_package_type`` (73-76)               ``UniqueConstraint`` homónimo
=============================================  =========================================

Divergencias declaradas
=========================

1. **Los ``compute`` sin ``store`` son ``property``.** ``product_capacity_ids``,
   ``package_capacity_ids``, ``weight_uom_name``, ``product_uom_id`` y
   ``company_id`` (de la capacidad) son ``related``/``compute`` no almacenados
   en la referencia: no tienen columna allá y no la tienen aquí. Su
   ``inverse`` (``_set_storage_capacity_ids``) se porta como método explícito
   **con su guion bajo intacto** — este ORM no cablea el par compute/inverse
   sobre un descriptor, y construirlo es la tarea **#191**.
2. **``max_weight`` es ``Monetary``, no ``Float``.** El árbol usa
   ``DecimalField`` para toda magnitud con redondeo declarado; la referencia
   pide lo mismo con ``digits='Stock Weight'``.

Deuda saldada al tocar el archivo (2026-08-15)
================================================

Dos formas que ``porte-completo-no-parcial.md`` y
``atributos-de-clase-de-modelo.md`` nombran, y que este archivo tenía:

1. **Los atributos de clase no estaban declarados.** La referencia declara 3 en
   ``StockStorageCategory`` y 4 en la capacidad; aquí había **0**. Se portan los
   siete verbatim. La regla es condicional —si la fuente declara, se portan
   todos— y la fuente declara.
2. **``_set_storage_capacity_ids`` estaba despromovido** a
   ``set_storage_capacity_ids``. Quitar el guion bajo no renombra: publica como
   API un ayudante que la fuente reservó (H-API-581). Restaurado; medido antes
   del cambio, **0 consumidores** fuera de este archivo, así que el renombre no
   rompe a nadie.
"""
from decimal import Decimal

import fields
import models

from addons.base.models import TimeStampedModel
from addons.product.models.product_template import ProductTemplate

ALLOW_EMPTY = 'empty'
ALLOW_SAME = 'same'
ALLOW_MIXED = 'mixed'

ALLOW_NEW_PRODUCT_CHOICES = [
    (ALLOW_EMPTY, 'Si la ubicación está vacía'),
    (ALLOW_SAME, 'Si todos los productos son el mismo'),
    (ALLOW_MIXED, 'Permitir productos mezclados'),
]


class StockStorageCategory(TimeStampedModel):
    """``stock.storage.category`` — qué y cuánto admite una ubicación."""

    # Atributos de clase de modelo — los tres que la referencia declara
    # (``odoo19c: :8-10``), verbatim.
    _name = 'stock.storage.category'
    _description = "Storage Category"
    _order = "name"

    name              = fields.Char(
        max_length=120,
        help_text='Nombre de la categoría de almacenamiento (Odoo name).',
    )
    max_weight        = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Peso máximo admitido (Odoo max_weight, digits Stock Weight).',
    )
    allow_new_product = fields.Selection(
        max_length=8, choices=ALLOW_NEW_PRODUCT_CHOICES, default=ALLOW_MIXED,
        help_text='Criterio de mezcla al ingresar un producto nuevo '
                  '(Odoo allow_new_product).',
    )
    company           = fields.Many2one(
        'base.ResCompany', null=True, blank=True, on_delete=models.CASCADE,
        related_name='storage_categories',
        help_text='Empresa (Odoo company_id).',
    )

    class Meta:
        db_table = 'stock_storage_category'
        ordering = ['name']            # ≙ ``_order = "name"``
        verbose_name = 'Categoría de almacenamiento'
        verbose_name_plural = 'Categorías de almacenamiento'
        constraints = [
            # ≙ ``_positive_max_weight`` (``odoo19c: :25-28``).
            models.CheckConstraint(
                condition=models.Q(max_weight__gte=0),
                name='stock_storage_category_positive_max_weight',
                violation_error_message='El peso máximo debe ser positivo.',
            ),
        ]

    def __str__(self) -> str:
        return self.name

    # -- los tres compute de la referencia --

    @property
    def product_capacity_ids(self):
        """≙ ``product_capacity_ids`` (``odoo19c: :15``, compute ``:30-34``).

        Las capacidades de esta categoría que acotan un **producto**.
        """
        return self.capacity_ids.filter(product__isnull=False)

    @property
    def package_capacity_ids(self):
        """≙ ``package_capacity_ids`` (``odoo19c: :16``, compute ``:30-34``).

        Las capacidades que acotan un **tipo de paquete**.
        """
        return self.capacity_ids.filter(package_type__isnull=False)

    @property
    def weight_uom_name(self):
        """≙ ``weight_uom_name`` / ``_compute_weight_uom_name`` (``odoo19c: :23``, ``:36-37``).

        Etiqueta de la unidad de peso, leída del parámetro de sistema — igual
        que la referencia, que delega en
        ``product.template._get_weight_uom_name_from_ir_config_parameter``.
        """
        return ProductTemplate.get_weight_uom_name_from_ir_config_parameter()

    def _set_storage_capacity_ids(self, product_capacities=(), package_capacities=()):
        """≙ ``_set_storage_capacity_ids`` (``odoo19c: :39-41``).

        El ``inverse`` de las dos properties: reescribe ``capacity_ids`` con la
        unión de ambas listas. Se porta como método explícito porque este ORM
        no cablea compute/inverse sobre un descriptor (tarea **#191**).
        """
        self.capacity_ids.set(list(product_capacities) + list(package_capacities))

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``odoo19c: :43-45``) — el duplicado lleva «(copia)»."""
        valores = dict(default or {})
        valores.setdefault('name', f'{self.name} (copia)')
        valores.setdefault('max_weight', self.max_weight)
        valores.setdefault('allow_new_product', self.allow_new_product)
        valores.setdefault('company', self.company)
        return valores


class StockStorageCategoryCapacity(TimeStampedModel):
    """``stock.storage.category.capacity`` — cuánto de X cabe en la categoría."""

    # Atributos de clase de modelo — los cuatro que la referencia declara
    # (``odoo19c: :49-52``), verbatim.
    _name = 'stock.storage.category.capacity'
    _description = "Storage Category Capacity"
    _check_company_auto = True
    _order = "storage_category_id"

    storage_category = fields.Many2one(
        'stock.StockStorageCategory', on_delete=models.CASCADE,
        related_name='capacity_ids', db_index=True,
        help_text='Categoría a la que pertenece la regla '
                  '(Odoo storage_category_id, requerido).',
    )
    product          = fields.Many2one(
        'product.ProductProduct', null=True, blank=True, on_delete=models.CASCADE,
        related_name='storage_category_capacity_ids', db_index=True,
        help_text='Producto acotado (Odoo product_id).',
    )
    package_type     = fields.Many2one(
        'stock.StockPackageType', null=True, blank=True, on_delete=models.CASCADE,
        related_name='storage_category_capacity_ids', db_index=True,
        help_text='Tipo de paquete acotado (Odoo package_type_id).',
    )
    quantity         = fields.Monetary(
        max_digits=12, decimal_places=2,
        help_text='Cantidad admitida (Odoo quantity, requerido).',
    )

    class Meta:
        db_table = 'stock_storage_category_capacity'
        ordering = ['storage_category_id']   # ≙ ``_order = "storage_category_id"``
        verbose_name = 'Capacidad de categoría de almacenamiento'
        verbose_name_plural = 'Capacidades de categoría de almacenamiento'
        constraints = [
            # ≙ ``_positive_quantity`` (``odoo19c: :65-68``).
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name='stock_storage_capacity_positive_quantity',
                violation_error_message='La cantidad debe ser un número positivo.',
            ),
            # ≙ ``_unique_product`` (``odoo19c: :69-72``).
            models.UniqueConstraint(
                fields=['product', 'storage_category'],
                name='stock_storage_capacity_unique_product',
                violation_error_message='Varias reglas de capacidad para un producto.',
            ),
            # ≙ ``_unique_package_type`` (``odoo19c: :73-76``).
            models.UniqueConstraint(
                fields=['package_type', 'storage_category'],
                name='stock_storage_capacity_unique_package_type',
                violation_error_message='Varias reglas de capacidad para un tipo de paquete.',
            ),
        ]

    def __str__(self) -> str:
        objetivo = self.product or self.package_type
        return f'{self.storage_category}: {objetivo} × {self.quantity}'

    @property
    def product_uom(self):
        """≙ ``product_uom_id`` (``related='product_id.uom_id'``, ``:62``)."""
        return self.product.uom if self.product is not None else None

    @property
    def company(self):
        """≙ ``company_id`` (``related='storage_category_id.company_id'``, ``:63``)."""
        return self.storage_category.company if self.storage_category is not None else None

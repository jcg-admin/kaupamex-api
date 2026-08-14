"""Modelo ``StockLot`` — addon ``stock``.

Adaptación fiel de Odoo ``stock.lot`` (``stock/models/stock_lot.py``, núcleo
idéntico en 18 y 19): un lote / número de serie de un producto. Verificado en
ambas versiones — ``name`` (Lot/Serial Number, requerido, o18:57-59 ≡ o19),
``ref`` (referencia interna, o18:60), ``product_id`` (o18:61-65),
``quant_ids`` (One2many inverso, o18:69) y ``product_qty`` (a la mano,
compute sobre los quants del lote, o18:70).

Es la **base** que ``product_expiry`` extiende con fechas de caducidad y la
estrategia de remoción FEFO (DEC-SALE-01: la extensión ``_inherit`` de Odoo se
adapta como modelo RELATED en el addon satélite).
"""
from decimal import Decimal

import fields
import models

from addons.base.models import TimeStampedModel


class StockLot(TimeStampedModel):
    """``stock.lot`` — lote / número de serie de un producto.

    .. warning:: Porte parcial declarado — **2 de 24 métodos**.

       Medido contra ``odoo19c: addons/stock/models/stock_lot.py`` (AST, ambos
       lados). Ausentes los 22: ``_check_create``, ``_check_unique_lot``,
       ``_compute_company_id``, ``_compute_delivery_ids``,
       ``_compute_display_complete``, ``_compute_name``,
       ``_compute_partner_ids``, ``_compute_single_location``,
       ``_find_delivery_ids_by_lot``, ``_find_delivery_ids_by_lot_iterative``,
       ``_get_next_serial``, ``_get_outgoing_domain``, ``_product_qty``,
       ``_read_group_location_id``, ``_search_partner_ids``,
       ``_search_product_qty``, ``_set_single_location``,
       ``action_lot_open_quants``, ``action_lot_open_transfers``,
       ``copy_data``, ``create``, ``default_get``, ``generate_lot_names``,
       ``write``.

       El docstring de módulo decía *"adaptación fiel"* y esa palabra no se
       sostiene con 2 de 24: lo que hay es el núcleo (``name``/``ref``/
       ``product``/la cantidad a la mano). El porte completo es parte de la
       tarea **#330**; hasta entonces la cobertura queda declarada aquí y no se
       presenta como terminada (``porte-completo-no-parcial.md``).

       Tampoco están los **cinco** atributos de clase que la fuente declara —
       ``_name`` (``odoo19c: :25``), ``_inherit`` (``:26``), ``_description``
       (``:27``), ``_check_company_auto`` (``:28``) y ``_order`` (``:29``).
       ``atributos-de-clase-de-modelo.md`` los exige enteros o ninguno, y
       entran con el porte completo.
    """

    name       = fields.Char(
        max_length=120,
        help_text='Número de lote / serie (Odoo stock.lot.name, requerido).',
    )
    ref        = fields.Char(
        max_length=120, blank=True, default='',
        help_text='Referencia interna (Odoo stock.lot.ref).',
    )
    product    = fields.Many2one(
        'product.ProductProduct', on_delete=models.CASCADE, related_name='lots',
        help_text='Producto (Odoo product_id).',
    )

    class Meta:
        db_table = 'stock_lot'
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'name'], name='unique_lot_product_name',
            ),
        ]
        ordering = ['name', 'id']
        verbose_name = 'Lote / número de serie'
        verbose_name_plural = 'Lotes / números de serie'

    def __str__(self) -> str:
        return f'{self.name} ({self.product})'

    @property
    def product_qty(self) -> Decimal:
        """Porta el **campo** ``product_qty`` (``odoo19c: stock_lot.py:53``).

        El nombre es público porque en la referencia lo es: ``product_qty =
        fields.Float('On Hand Quantity', compute='_product_qty',
        search='_search_product_qty')``. Lo privado es su *compute*
        (``_product_qty``, ``:212``) y su *search* (``_search_product_qty``,
        ``:237``); aquí una ``property`` es la forma del campo calculado no
        almacenado, así que el símbolo que este método encarna es el campo.

        Es el caso (b) que ``porte-completo-no-parcial.md`` excluye del defecto
        de despromoción: *"el símbolo es un campo, no un método"*. El docstring
        anterior decía *"réplica de ``_product_qty``"* y con eso se leía como una
        despromoción — que es exactamente lo que el ejecutor señaló. Ver
        :ref:`h-api-596`.

        **El gate de la tarea #338 lo marca como falso positivo** y no es un
        defecto del código sino del instrumento: compara métodos contra métodos
        y es ciego a los campos de la referencia, así que no puede ver que el
        nombre público ya estaba tomado por uno.

        ``_search_product_qty`` **no está portado** — es uno de los 22 símbolos
        que el aviso de la clase enumera.
        """
        total = self.quants.aggregate(s=models.Sum('quantity'))['s']
        return total if total is not None else Decimal('0.00')

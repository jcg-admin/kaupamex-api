"""``res.partner`` — el proveedor: puntualidad de entrega y agrupación de RFQ
(Odoo ``purchase_stock``).

Adaptación de Odoo ``purchase_stock/models/res_partner.py``
(``odoo19c: addons/purchase_stock/models/res_partner.py``, 71 líneas, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

Qué añade: dos ejes independientes sobre el proveedor.

1. **Su puntualidad** — qué porcentaje de lo que se le pidió llegó en la fecha
   comprometida, sobre una ventana de días configurable.
2. **Cómo se le agrupan las solicitudes de cotización** — si cada necesidad de
   reabastecimiento genera su propia RFQ o si varias se juntan por día, por
   semana o siempre; más los tres parámetros de la sugerencia de compra.

Porte símbolo por símbolo — 5 de 8
====================================

*Métrica:* entradas del cuerpo de ``class ResPartner`` contadas por AST sobre
la fuente. Son **9** con ``_inherit``; **8** sin él: 7 campos y 1 método.
*Ciega a:* lo que otros addons cuelgan sobre ``res.partner`` — ``stock`` ya le
cuelga lo suyo en ``addons/stock/models/res_partner.py`` y este conteo mira un
solo archivo de la fuente.

.. list-table::
   :header-rows: 1
   :widths: 34 16 50

   * - Símbolo (línea)
     - Estado
     - Forma aquí
   * - ``suggest_based_on`` (``:18``)
     - portado
     - ``Char`` con ``default='30_days'``
   * - ``suggest_days`` (``:19``)
     - portado
     - ``Integer`` con ``default=7``
   * - ``suggest_percent`` (``:20``)
     - portado
     - ``Integer`` con ``default=100``
   * - ``group_rfq`` (``:21-28``)
     - portado
     - ``Selection`` de 4, ``default='default'``, ``help`` verbatim
   * - ``group_on`` (``:29-38``)
     - portado
     - ``Selection`` de 8 (día de la semana), ``default='default'``
   * - ``purchase_line_ids`` (``:13``)
     - **bloqueado**
     - ``purchase.order.line`` no tiene ``partner_id`` aquí — ver abajo
   * - ``on_time_rate`` (``:14-17``)
     - **bloqueado**
     - depende del anterior y de 4 campos más
   * - ``_compute_on_time_rate`` (``:40-71``)
     - **bloqueado**
     - es el cómputo del campo anterior

Los dos bloqueos, con su medición
===================================

``purchase_line_ids`` es ``One2many('purchase.order.line', 'partner_id')``: el
reverso de un campo que **no existe en este árbol**. Medido:

.. code-block:: text

    grep -rn "partner" addons/purchase/models/purchase_order_line.py  → 0

Y el eslabón de arriba tampoco sirve de puente: ``PurchaseOrder.partner``
(``addons/purchase/models/purchase_order.py:44-47``) apunta a
``settings.AUTH_USER_MODEL`` —**un usuario**, no un ``res.partner``—, así que
``PurchaseOrderLine.objects.filter(order__partner=self)`` con ``self`` siendo un
``ResPartner`` no compila ni conceptual ni técnicamente. Es una divergencia del
addon ``purchase`` de este árbol, no de este puerto, y no se corrige desde aquí:
``purchase`` está fuera del write-set de este pase.

``_compute_on_time_rate`` necesita, además de lo anterior, cinco campos que la
línea de compra tampoco tiene: ``qty_received``, ``date_planned``,
``date_order``, ``product_uom_qty`` y ``order_id.state == 'purchase'``. Los tres
primeros los porta ``purchase_stock`` en la referencia
(``purchase_order_line.py``), pero sobre un modelo que ya trae los otros dos.
El bloqueo por tanto es de **cuatro** piezas, no de una.

Lo que SÍ está disponible y se deja anotado
---------------------------------------------

El parámetro de sistema que la fuente lee
(``purchase_stock.on_time_delivery_days``, ``odoo19c: :42``) **sí tiene motor
aquí**: ``base.SystemParameter.get_param`` (``src/addons/base/models/
ir_config_parameter.py:133``, ``_name = 'ir.config_parameter'``). No es lo que
bloquea el método — se anota para que quien lo retome no vuelva a medirlo.

Nota sobre ``group_rfq`` / ``group_on`` — ``required=True`` de la fuente
=========================================================================

Los dos son ``required=True, default='default'`` allá. Aquí se traducen a
``null=False, blank=False`` con el mismo ``default``: una columna ``NOT NULL``
con valor por defecto es exactamente lo que ``required`` + ``default`` produce
en la fuente, y evita el ``blank=True`` que dejaría pasar la cadena vacía.

El ``help`` de ``group_rfq`` se conserva **traducido pero completo** — sus
cuatro reglas (On Order / Daily / Weekly / Always) son la semántica del campo,
no adorno: quien lea el valor ``'week'`` sin ellas no sabe qué agrupa.
"""
from orm.model_classes import extend_model

import fields

#: ≙ la cabecera que la fuente declara en su clase (la extensión aquí no es clase).
_inherit = 'res.partner'

#: ≙ ``group_rfq`` (``odoo19c: :21-28``) — cuándo se juntan varias necesidades
#: de reabastecimiento en una sola solicitud de cotización.
GROUP_RFQ_CHOICES = [
    ('default', 'Por pedido'),
    ('day', 'Diaria'),
    ('week', 'Semanal'),
    ('all', 'Siempre'),
]

#: ≙ ``group_on`` (``odoo19c: :29-38``) — el día de la semana con el que se
#: alinea la agrupación semanal. ``'default'`` = la fecha prevista de llegada.
GROUP_ON_CHOICES = [
    ('default', 'Fecha prevista'),
    ('1', 'Lunes'),
    ('2', 'Martes'),
    ('3', 'Miércoles'),
    ('4', 'Jueves'),
    ('5', 'Viernes'),
    ('6', 'Sábado'),
    ('7', 'Domingo'),
]


def apply_purchase_stock_res_partner_extensions():
    """Cuelga sobre ``res.partner`` los 5 campos portables — ≙ ``_inherit``."""
    extend_model(
        _inherit,
        campos={
            'suggest_based_on': fields.Char(
                max_length=32, default='30_days', blank=True,
                help_text='Base sobre la que se calcula la cantidad sugerida '
                          'de compra (Odoo suggest_based_on).',
            ),
            'suggest_days': fields.Integer(
                default=7,
                help_text='Días de horizonte de la sugerencia de compra '
                          '(Odoo suggest_days).',
            ),
            'suggest_percent': fields.Integer(
                default=100,
                help_text='Porcentaje que se aplica a la cantidad sugerida '
                          '(Odoo suggest_percent).',
            ),
            'group_rfq': fields.Selection(
                max_length=8, choices=GROUP_RFQ_CHOICES, default='default',
                help_text='Define si las solicitudes de cotización se agrupan '
                          'según la llegada prevista, salvo en dropship '
                          '(Odoo group_rfq). Por pedido: las necesidades de '
                          'reabastecimiento se agrupan salvo las MTO. '
                          'Diaria: se agrupan si la llegada prevista es el '
                          'mismo día. Semanal: se agrupan si la llegada '
                          'prevista cae en la misma semana o el mismo día de '
                          'la semana. Siempre: se agrupan sin condición.',
            ),
            'group_on': fields.Selection(
                max_length=8, choices=GROUP_ON_CHOICES, default='default',
                help_text='Día de la semana con el que se alinea la '
                          'agrupación semanal de RFQ (Odoo group_on).',
            ),
        },
    )

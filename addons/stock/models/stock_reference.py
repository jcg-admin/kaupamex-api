"""``stock.reference`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_reference.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Qué es: el hilo que une varios documentos de inventario que nacieron del mismo
origen. Un pedido de venta que se sirve en tres entregas parciales produce tres
albaranes distintos; la referencia es lo que permite decir «estos tres son el
mismo encargo» sin que ninguno de ellos conozca a los otros.

En 19 sustituye al antiguo ``procurement.group``: el agrupador dejó de ser un
modelo con reglas y quedó reducido a un **nombre compartido**, y la relación
con los movimientos pasó de Many2one a **Many2many** — un movimiento puede
pertenecer a más de un encargo.

Porte símbolo por símbolo — 4 de 4
===================================

Medido sobre ``odoo19c: addons/stock/models/stock_reference.py`` (15 líneas):
1 campo escalar, 2 relacionales y 1 método.

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``name`` (8)                                     ``name``
``move_ids`` (9-10)                              ``move_ids`` (M2M, tabla conservada)
``picking_ids`` (11)                             property ``picking_ids``
``_compute_picking_ids`` (13-15)                 lo consume la property
===============================================  ======================================

Por qué el M2M se declara AQUÍ y no en ``StockMove``
======================================================

La referencia declara el mismo M2M dos veces —``stock.reference.move_ids`` y
``stock.move.reference_ids``, ambos sobre la tabla ``stock_reference_move_rel``—
porque su ORM admite las dos mitades. Django declara la relación **una vez** y
genera el accesor inverso; declararla en los dos lados produce dos tablas.

Se declara en este modelo, no en ``StockMove``, y el motivo es de orden: un
``ManyToManyField`` a ``'stock.StockMove'`` resuelve porque ese modelo ya
existe, mientras que lo contrario exigiría que ``stock.reference`` existiera
antes de que ``stock_move.py`` se pudiera declarar. El ``related_name`` conserva
el nombre de la otra mitad, así que ``move.reference_ids`` se lee igual que en
la fuente.

Divergencia declarada
=======================

**``_compute_picking_ids`` es una property, no un campo calculado.** La
referencia lo declara ``compute=`` sin ``store=``, así que su ORM lo recalcula
en cada lectura y nunca lo persiste — que es exactamente lo que una property de
Python hace, sin motor de dependencias de por medio. El nombre del método se
conserva en el docstring de la property por trazabilidad.
"""
from django.apps import apps

import fields
import models

from addons.base.models import TimeStampedModel


class StockReference(TimeStampedModel):
    """``stock.reference`` — el nombre que comparten los documentos de un encargo."""

    # Atributos de clase de modelo — los dos que la referencia declara
    # (``odoo19c: addons/stock/models/stock_reference.py:5-6``), verbatim.
    _name = 'stock.reference'
    _description = 'Reference between stock documents'

    name      = fields.Char(
        max_length=255,
        help_text='Referencia compartida (Odoo name, requerido y readonly).',
    )
    move_ids  = fields.Many2many(
        'stock.StockMove', blank=True, related_name='reference_ids',
        db_table='stock_reference_move_rel',
        help_text='Movimientos que comparten esta referencia (Odoo move_ids). '
                  'El inverso es ``move.reference_ids``, el nombre que la '
                  'referencia le da a la otra mitad del M2M.',
    )

    class Meta:
        db_table = 'stock_reference'
        ordering = ['id']
        verbose_name = 'Referencia de inventario'
        verbose_name_plural = 'Referencias de inventario'

    def __str__(self) -> str:
        return self.name

    @property
    def picking_ids(self):
        """Albaranes de los movimientos de esta referencia (≙ ``_compute_picking_ids``).

        La fuente lo declara ``compute='_compute_picking_ids'`` sin almacenar,
        y su cuerpo es ``reference.move_ids.picking_id`` — la proyección del
        albarán sobre los movimientos, deduplicada por el ORM. Aquí el
        ``distinct()`` hace esa deduplicación explícita.
        """
        StockPicking = apps.get_model('stock', 'StockPicking')
        return StockPicking.objects.filter(move_ids__in=self.move_ids.all()).distinct()

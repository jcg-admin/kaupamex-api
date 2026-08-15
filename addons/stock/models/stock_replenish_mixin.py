r"""``stock.replenish.mixin`` — la ruta preferida al reabastecer, addon ``stock``.

Adaptación de Odoo ``stock/models/stock_replenish_mixin.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 40 líneas) — atribución y aviso
de licencia preservados (DEC-KX-03).

Qué es: el contrato que comparte **todo formulario que reabastece un producto**
— el asistente de reabastecimiento, la orden de dropship, la de
subcontratación. Aporta dos cosas: el campo donde se elige una ruta concreta en
vez de dejar que el producto decida, y **la lista de rutas que tiene sentido
ofrecer** para ese producto y ese almacén.

Por qué la lista no es «todas las rutas»
==========================================

``_get_allowed_route_domain`` (``odoo19c: :26-40``) filtra por cuatro
condiciones, y las cuatro son necesarias:

1. ``product_selectable`` — la ruta se puede elegir desde el producto. Sin
   esto aparecerían las rutas internas del almacén, que nadie elige a mano.
2. **más** las rutas de reabastecimiento del propio almacén que sean válidas
   para este producto (``|``, no ``&``): son elegibles aunque no estén
   marcadas ``product_selectable``, porque el almacén las declara suyas.
3. y 4. **ninguna de sus reglas toca la ubicación de tránsito entre empresas**
   — ésas son el mecanismo de la transferencia inter-compañía, no una opción de
   reabastecimiento.
5. y su destino tiene almacén: una regla que apunta a una ubicación suelta no
   reabastece nada.

El comentario de la fuente sobre estos dos métodos es la parte que no hay que
perder: *"INHERITS in 'Drop Shipping', 'Dropship and Subcontracting
Management'"* y *"OVERWRITE in … to hide it"*. Es decir, el mixin **existe para
ser extendido**: el dominio de aquí es el caso base y cada addon de envío lo
acota o lo oculta.

Divergencias declaradas
========================

**D-1 — clase Python, no modelo abstracto de Django.** La referencia lo declara
``models.AbstractModel`` con dos campos, pero **ninguno de los dos es una
columna**: ``route_id`` lo redeclara cada consumidor concreto y
``allowed_route_ids`` es ``compute=`` sin ``store``. Es el mismo criterio ya
fijado por ``product.catalog.mixin``
(``addons/product/models/product_catalog_mixin.py:99``) y por
``BusListenerMixin``: **mixin con columnas → abstracto de Django; mixin de
comportamiento → clase Python**.

**D-2 — ``allowed_route_ids`` es una ``property``, no un campo calculado.** La
fuente lo declara ``compute='_compute_allowed_route_ids'`` sin ``store=True``,
así que no tiene columna allá tampoco; el motor de ``@api.depends`` que lo
invalidaría no está construido aquí (tarea **#191**). El método de cálculo se
porta con su nombre verbatim y la ``property`` lo invoca, que es la forma que
``H-API-611`` fija para este caso.

**D-3 — el dominio se arma con la primitiva ``Domain`` portada, no con ``Q``.**
``src/orm/domains.py`` es la adaptación de ``odoo/orm/domains.py`` (tarea #356),
así que las cuatro condiciones se escriben **con la misma forma que la fuente**
—incluido ``Domain.AND``, el método de clase que ella usa— y se compilan a ``Q``
con ``to_q`` al construir el queryset. Usar ``Q`` directo aquí sería el defecto
que ``H-API-582`` registra: rodear el espejo de la primitiva teniéndolo
construido.

Cuidado con el homónimo: ``orm.domains`` exporta **dos** ``AND``. El de módulo
(``domains.py:871``) es el espejo de ``expression.AND`` y combina objetos ``Q``;
el de la fuente de este archivo es ``Domain.AND`` (``:303``), que combina
dominios. Pasarle dominios al primero levanta ``TypeError`` — medido al escribir
este archivo. Ver la tarea **#380**, que unifica ese hogar.

Porte símbolo por símbolo — 4 de 4
====================================

.. list-table::
   :header-rows: 1
   :widths: 38 12 50

   * - Símbolo (línea)
     - Estado
     - Forma aquí
   * - ``route_id`` (``:11-14``)
     - portado
     - ``ROUTE_FIELD``, la fábrica que cada consumidor concreto declara
   * - ``allowed_route_ids`` (``:15``)
     - portado
     - ``property`` sobre ``_compute_allowed_route_ids`` (D-2)
   * - ``_compute_allowed_route_ids`` (``:18-22``)
     - portado
     - devuelve el queryset en vez de escribir el campo (D-2)
   * - ``_get_allowed_route_domain`` (``:26-40``)
     - portado
     - ``Domain`` verbatim, incluida la rama ``|`` del almacén (D-3)

*Métrica:* entradas del cuerpo de ``class StockReplenishMixin``, por AST — 2
asignaciones (``_name``/``_description`` se cuentan aparte) y 2 métodos.
*Ciega a:* lo que los addons de dropship extienden sobre este mixin; ninguno de
ellos está portado.

Lo que este archivo NO cierra
===============================

- **El XML ID ``stock.stock_location_inter_company``** no está sembrado
  (``INTER_COMPANY_XMLID`` en ``stock_location.py:175`` lo nombra, y
  ``res_company.py:429`` lo busca). Sin él, las dos condiciones que excluyen el
  tránsito **no filtran nada** — el dominio es más permisivo que el de la
  fuente. Se resuelve solo cuando la siembra exista; sucesor: tarea **#330**.
- **Ningún consumidor concreto lo hereda todavía.** El asistente
  ``product.replenish`` de la referencia no está portado. El mixin queda
  disponible y sin llamador, que es exactamente lo que ``H-API-410`` enseña a
  declarar en vez de callar. Sucesor: tarea **#330**.
"""
import fields
import models
from django.apps import apps

from addons.base.models import IrModelData
from orm.domains import Domain, to_q

#: ≙ ``route_id`` (``odoo19c: :11-14``) — «Apply specific route for the
#: replenishment instead of product's default routes».
#:
#: Es una **fábrica**, no un campo colgado: el mixin no tiene tabla, así que
#: cada consumidor concreto declara ``route = ROUTE_FIELD()`` en su propia
#: clase. ``check_company=True`` de la fuente se expresa con
#: ``_check_company_auto`` en el modelo que lo declara.
def ROUTE_FIELD(**kwargs):
    kwargs.setdefault('null', True)
    kwargs.setdefault('blank', True)
    kwargs.setdefault('on_delete', models.SET_NULL)
    kwargs.setdefault('verbose_name', 'Ruta preferida')
    kwargs.setdefault(
        'help_text',
        'Ruta específica para el reabastecimiento, en vez de las rutas por '
        'defecto del producto (Odoo route_id).')
    return fields.Many2one('stock.StockRoute', **kwargs)


class StockReplenishMixin:
    """``stock.replenish.mixin`` — «Product Replenish Mixin»."""

    # Atributos de clase de modelo — los dos que la referencia declara
    # (``odoo19c: :8-9``), verbatim. No lleva más: no es un modelo con tabla.
    _name = 'stock.replenish.mixin'
    _description = 'Product Replenish Mixin'

    @property
    def allowed_route_ids(self):
        """≙ ``allowed_route_ids`` (``odoo19c: :15``) — D-2 del docstring.

        Origen: campo ``compute='_compute_allowed_route_ids'`` **sin**
        ``store``. Aquí es ``property`` porque tampoco tiene columna allá y el
        motor de ``@api.depends`` no está construido (tarea #191).
        """
        return self._compute_allowed_route_ids()

    def _compute_allowed_route_ids(self):
        """≙ ``_compute_allowed_route_ids`` (``odoo19c: :18-22``).

        La fuente escribe el campo; aquí devuelve el queryset y la ``property``
        lo expone — misma consulta, un paso menos.
        """
        route_model = apps.get_model('stock', 'StockRoute')
        return route_model.objects.filter(
            to_q(self._get_allowed_route_domain(), route_model))

    def _get_allowed_route_domain(self):
        """≙ ``_get_allowed_route_domain`` (``odoo19c: :26-40``).

        Las cuatro condiciones de la fuente, con su misma forma y su mismo
        orden. La rama del almacén entra con ``|`` (no ``&``): una ruta de
        reabastecimiento del almacén es elegible aunque no esté marcada
        ``product_selectable``.
        """
        inter_company = IrModelData.objects.filter(
            module='stock', name='stock_location_inter_company').first()
        inter_company_id = inter_company.res_id if inter_company is not None else None

        base_domain = Domain('product_selectable', '=', True)
        warehouse = getattr(self, 'warehouse', None)
        if warehouse is not None:
            product = getattr(self, 'product', None)
            wh_route_ids = [
                route.pk for route in warehouse.route_ids.all()
                if route._is_valid_resupply_route_for_product(product)
            ]
            if wh_route_ids:
                base_domain |= Domain('id', 'in', wh_route_ids)

        return Domain.AND([
            base_domain,
            Domain('rule_ids.location_src_id', '!=', inter_company_id),
            Domain('rule_ids.location_dest_id', '!=', inter_company_id),
            Domain('rule_ids.location_dest_id.warehouse_id', '!=', False),
        ])

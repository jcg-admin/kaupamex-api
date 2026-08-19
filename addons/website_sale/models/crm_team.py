"""``crm.team`` — el contador de carritos abandonados del equipo de venta.

Adaptación de ``odoo19c: addons/website_sale/models/crm_team.py``
(``odoo-tools@622ddc2a``, LGPL-3) — atribución y aviso de licencia preservados
(DEC-KX-03). El archivo de la referencia tiene **54 líneas** y declara una sola
clase, ``CrmTeam(_inherit='crm.team')``, con **5 símbolos**: tres campos y dos
métodos.

Universo medido — 5 símbolos
=============================

.. list-table::
   :header-rows: 1
   :widths: 38 12 50

   * - Símbolo de la referencia (línea)
     - Estado
     - Forma aquí
   * - ``website_ids`` (``:9-11``)
     - portado
     - el ``related_name`` de ``WebsiteSaleSettings.salesteam`` — ver D-1
   * - ``abandoned_carts_amount`` (``:12-14``)
     - portado
     - ``fields.NonStored`` — es ``compute`` sin ``store`` en la fuente
   * - ``abandoned_carts_count`` (``:15-17``)
     - portado
     - ``fields.NonStored`` — ídem
   * - ``_compute_abandoned_carts`` (``:19-33``)
     - portado
     - función de módulo instalada como método; D-2, D-3, D-4
   * - ``get_abandoned_carts`` (``:35-54``)
     - **no portado**
     - arista abajo

*Métrica:* entradas del cuerpo de ``class CrmTeam`` en el archivo de la
referencia, contadas por AST — 3 ``Assign`` de campo y 2 ``FunctionDef``.
*Ciega a:* lo que **otros** addons cuelgan de ``crm.team`` (``crm`` y ``sale``
añaden ahí ``use_leads``, ``invoiced``, el tablero). Este conteo sólo ve el
archivo de ``website_sale``, que es el universo de esta tarea.

Atributos de clase — 1, y lo expresa el ``extend_model``
---------------------------------------------------------

Medido con el comando de ``atributos-de-clase-de-modelo.md``, la clase de la
referencia declara **uno**: ``_inherit = 'crm.team'`` (``odoo19c: :7``). No hay
``_name``, ``_description`` ni ``_order`` — es una **extensión**, que es lo que
el 65 % de las clases de la referencia son.

Ese único atributo se porta como la **llamada** ``extend_model('sales_team',
'CrmTeam', …)`` del final de este archivo: ahí está nombrado el modelo que se
reabre, que es exactamente lo que ``_inherit`` declara. No se escribe además
como atributo porque este archivo no declara clase alguna — colgar un
``_inherit`` suelto sobre un módulo no lo leería nadie. Es la misma forma que
``models/sale_order.py`` y ``models/product_template.py`` ya usan en este
addon.

La pieza que faltaba, y de dónde salió
=======================================

Este archivo estuvo **bloqueado entero** hasta este pase, y no por las piezas
que la tarea nombraba —``sales_team.CrmTeam`` y ``sale.SaleOrder.team`` ya
existían las dos— sino por una tercera que no nombraba: el inverso
``salesteam_id``, que la referencia declara en
``odoo19c: website_sale/models/website.py:63-69``. Medido antes de portarlo:
``grep -rn "salesteam\|salesperson" addons/ src/ --include=*.py`` → **0 hits**.

Cuatro de los cinco símbolos colgaban de él, porque ``_compute_abandoned_carts``
**abre** con el guard (``odoo19c: :23``)::

    website_teams = self.filtered(lambda team: team.website_ids)

Ese guard no es decoración: decide la población. Con ``for team in self`` al
final (``:31-33``), un equipo que **no** sea salesteam de ningún sitio recibe
``0`` en los dos campos. Sin el inverso quedaban dos salidas, las dos peores
que esperar: portar sin el guard —un equipo con carritos abandonados que no
fuera salesteam de ningún sitio reportaría ``> 0`` donde la referencia da
``0``, cambio de conducta invisible— o portarlo devolviendo siempre ``0``, que
es código muerto que aparenta estar vivo.

La FK se portó en ``models/website.py`` de este addon con sus cinco atributos
(ver allí la fila ``salesteam_id`` de su tabla y su D-7), y con ella los cuatro
símbolos entran enteros. El par de tests
``tests/unit/website_sale/test_crm_team_abandoned_carts.py`` existe para
justamente esto: comprueba que el guard **sigue vivo**, con un equipo que es
salesteam de un sitio y cuenta, y otro con carritos que no lo es y da ``0``.

Divergencias declaradas
========================

**D-1 — ``website_ids`` no se declara: es el ``related_name``.** Un
``One2many`` de la referencia no tiene columna — es el espejo del ``Many2one``
del otro lado, igual que un ``related_name`` de Django. Declararlo aquí como
campo propio sería inventar un segundo mecanismo para lo que la FK ya provee.

El nombre pierde el sufijo ``_ids`` como en todo el árbol
(``website_ids`` → ``websites``), y **alcanza la fila de política, no el
sitio**: la FK sale de ``WebsiteSaleSettings``, así que el sitio está un salto
más allá (``settings.website``). La cardinalidad es idéntica porque esa
relación es 1-1, y eso es lo único que el guard pregunta. Ver D-7 de
``models/website.py``.

**D-2 — el cómputo opera sobre un registro, no sobre un recordset.** La fuente
recorre ``self`` (varios equipos), agrupa con ``_read_group`` por ``team_id`` y
reparte el resultado con ``counts.get(team.id, 0)``. Este ORM no tiene
recordset: ``self`` es **un** equipo, así que la agrupación se colapsa en una
agregación de una fila. El ``.get(..., 0)`` de la fuente —su forma de decir
"cero si no apareció"— se conserva como el ``or 0`` de la agregación vacía.

**D-3 — un cómputo, dos campos, una consulta.** La fuente declara los dos
campos con el **mismo** ``compute='_compute_abandoned_carts'`` y los asigna
juntos (``:32-33``). Aquí cada ``NonStored`` tiene su propio ``default``, así
que el cómputo escribe **los dos** en la instancia y el segundo campo leído ya
lo encuentra puesto (``NonStored.__get__`` mira ``instance.__dict__`` antes de
resolver su default). Es la misma consulta única de la fuente, no dos.

**D-4 — el importe conserva su precisión monetaria; la fuente lo trunca.**
``abandoned_carts_amount`` es ``fields.Integer`` en la referencia (``:12``)
alimentado por ``amount_total:sum`` — un total de dinero metido en un entero.
Aquí ``sale.SaleOrder.amount_total`` es ``Monetary``
(``addons/sale/models/sale_order.py:233``) y la suma se devuelve tal cual:
truncar un total a entero reportaría una cifra falsa, y copiarlo sería copiar
un defecto, no portar una conducta. Divergencia declarada, no descuido.

**D-5 — la agregación se hace en dos pasos, sobre las claves.**
``_search_abandoned_cart`` devuelve un ``QuerySet`` con ``.distinct()`` (une
por sitio con ``|``). Agregar directamente sobre él haría que ``Sum`` contara
dos veces una fila que casara con dos ramas de la disyunción — el ``DISTINCT``
de SQL aplica a las columnas seleccionadas, no a la agregación. Se materializan
las claves primero y se agrega sobre ellas, que es inequívoco.

Aristas de porte
=================

Porte BLOQUEADO — 1 de 5 símbolos

- ``get_abandoned_carts`` (``odoo19c: :35-54``) —
  BLOQUEADO por ``ir.actions.act_window`` — devuelve una acción de navegación
  (nombre, ``view_mode``, dominio, contexto de búsqueda y un ``help`` en HTML)
  cuyo único trabajo es abrir una lista en el cliente web de Odoo. Dos piezas
  ausentes, medidas: ``find addons/ src/ -name "*.xml"`` → **0 archivos**, y
  ``grep -rn "sale_order_view_search_inherit_sale" addons/ src/`` → **0 hits**.
  La primera decide: ``:44`` resuelve ese identificador de vista con
  ``env.ref``, y en un árbol sin **ninguna** vista XML no tiene qué resolver.
  Este árbol es *headless* — la superficie la sirve DRF.

  Mismo criterio ya fijado dos veces: ``action_recovery_email_send``
  (``models/sale_order.py``) y ``account_check_printing``/
  ``action_checks_to_print``. El **dato** que la acción mostraría no se pierde:
  es el mismo ``_search_abandoned_cart`` que ya está portado y que cualquier
  vista DRF futura puede consumir. Sucesor: tarea **#570**, que es donde se
  decide la forma de las acciones de navegación para todo el addon — no una
  decisión por símbolo.
"""
from django.apps import apps
from django.db.models import Count, Sum

import fields
from orm.model_classes import extend_model


def _abandoned_carts_of(team):
    """Los carritos abandonados **recuperables** de un equipo: ``(cuenta, importe)``.

    El dominio de la fuente (``odoo19c: :24-28``), con sus tres condiciones y
    el comentario que las explica (``:20-22``): *"abandoned carts to recover
    are draft sales orders that have no order lines, a partner other than the
    public user, and created over an hour ago and the recovery mail was not yet
    sent"*.

    Las dos primeras las aporta ``_search_abandoned_cart``, que ya encapsula el
    borrador, la fecha de corte por sitio, el comprador distinto del público y
    la exigencia de líneas. Aquí se añaden las dos que faltan: el correo aún no
    enviado y la atribución a **este** equipo.

    El guard de la fuente (``:23``) va primero: un equipo que no es salesteam
    de ningún sitio devuelve ``(0, 0)`` sin consultar.
    """
    # ≙ ``website_teams = self.filtered(lambda team: team.website_ids)``.
    # ``websites`` es el ``related_name`` de ``WebsiteSaleSettings.salesteam``
    # (D-1); cada fila es la política de un sitio, y hay exactamente una por
    # sitio, así que "tiene sitios" y "tiene políticas" son la misma pregunta.
    if not team.websites.exists():
        return 0, 0

    # ``apps.get_model`` y no un ``import`` al top: ``_search_abandoned_cart``
    # no vive en la clase de ``sale``, se la cuelga
    # ``apply_website_sale_order_extensions()`` en ``ready()``. Resolver el
    # modelo en tiempo de llamada es lo que garantiza que ya esté puesto — el
    # mismo motivo por el que ``models/website.py`` lo hace así.
    sale_order_model = apps.get_model('sale', 'SaleOrder')

    abandoned = sale_order_model._search_abandoned_cart('in', [True]).filter(
        website_sale_info__cart_recovery_email_sent=False,
        team=team,
    )
    # D-5: se materializan las claves antes de agregar. El ``QuerySet`` viene
    # con ``.distinct()`` sobre una disyunción por sitio, y ``Sum`` sobre él
    # contaría dos veces una fila que casara con dos ramas.
    pks = list(abandoned.values_list('pk', flat=True))
    if not pks:
        return 0, 0
    agregado = sale_order_model.objects.filter(pk__in=pks).aggregate(
        total=Sum('amount_total'), count=Count('id'),
    )
    # ≙ ``counts.get(team.id, 0)`` / ``amounts.get(team.id, 0)`` (``:32-33``):
    # la agregación vacía devuelve ``None``, que es su "no apareció".
    return agregado['count'] or 0, agregado['total'] or 0


def _compute_abandoned_carts(self):
    """≙ ``_compute_abandoned_carts`` (``odoo19c: :19-33``).

    Escribe **los dos** campos, como la fuente, en una sola consulta (D-3): el
    segundo que se lea ya lo encuentra puesto en la instancia.

    D-2: opera sobre un registro, no sobre un recordset — la agrupación por
    ``team_id`` de la fuente se colapsa en una agregación de una fila.

    :return: la pareja ``(cuenta, importe)`` que acaba de asignar.
    """
    count, amount = _abandoned_carts_of(self)
    self.abandoned_carts_count = count
    self.abandoned_carts_amount = amount
    return count, amount


def _default_abandoned_carts_count(team):
    """``default`` del ``NonStored`` ``abandoned_carts_count``."""
    return _compute_abandoned_carts(team)[0]


def _default_abandoned_carts_amount(team):
    """``default`` del ``NonStored`` ``abandoned_carts_amount``."""
    return _compute_abandoned_carts(team)[1]


def apply_website_sale_crm_team_extensions():
    """Cuelga sobre ``crm.team`` el contador de carritos — ≙ ``_inherit``.

    Se invoca desde ``WebsiteSaleConfig.ready()``: en tiempo de import el
    registro de modelos aún no está poblado.

    El destino se nombra con el par de Django y no con ``'crm.team'`` porque
    ``sales_team.CrmTeam`` no declara ``_name`` — la misma medición y el mismo
    motivo que ``models/sale_order.py`` deja escritos para ``sale.SaleOrder``.
    Completar su cabecera toca ``addons/sales_team``, fuera de este pase.
    """
    extend_model('sales_team', 'CrmTeam', campos={
        # Los dos son ``compute`` **sin** ``store=True`` en la fuente
        # (``:12-17``): no generan columna, y por eso este archivo no trae
        # migración. Es la misma forma que ``is_abandoned_cart`` en
        # ``models/sale_order.py``.
        'abandoned_carts_count': fields.NonStored(
            default=_default_abandoned_carts_count,
            help_text='Carritos abandonados aún recuperables de este equipo '
                      '(Odoo abandoned_carts_count, store=False).',
        ),
        'abandoned_carts_amount': fields.NonStored(
            default=_default_abandoned_carts_amount,
            help_text='Importe total de esos carritos (Odoo '
                      'abandoned_carts_amount, store=False). D-4: conserva la '
                      'precisión monetaria; la fuente lo trunca a entero.',
        ),
    }, metodos={
        '_compute_abandoned_carts': _compute_abandoned_carts,
    })


__all__ = ['apply_website_sale_crm_team_extensions']

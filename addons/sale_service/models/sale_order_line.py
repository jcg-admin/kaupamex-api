"""Extensión ``sale_service`` de ``sale.order.line`` — líneas de servicio.

Adaptación fiel de Odoo ``sale_service/models/sale_order_line.py``
(``odoo19c:``, LGPL-3, ``odoo-tools@622ddc2a``; presente también en
``odoo18c:`` — gobierna 19). Allá el addon inyecta en ``sale.order.line``:

- ``is_service`` (:20) — computado almacenado: ``product_id.type == 'service'``.
- ``_domain_sale_line_service`` (:22-34) — el dominio genérico de servicios,
  con hojas desactivables por kwarg (``check_state=False`` …).
- ``_auto_init`` / índice parcial / ``name_search`` — maquinaria de
  rendimiento del ORM de Odoo (columna pre-creada para no computar en masa,
  índice ``WHERE is_service``, atajo de búsqueda). **No se porta**: es
  optimización del compute almacenado, y aquí el valor se deriva en vivo —
  no existe la columna que esa maquinaria protege.
- ``_additional_name_per_id`` — decoración del display name en el buscador
  de Odoo; sin ese buscador aquí, no hay consumidor.

Como módulo-extensión sin estado propio (el valor es una derivación pura del
producto), este addon es **behavior-only** (precedente ``sale_stock_margin``):
funciones sobre el modelo existente, sin tabla.
"""
from addons.product.models.product_template import TYPE_SERVICE


def is_service(line) -> bool:
    """``_compute_is_service`` de la fuente: el tipo del producto es servicio.

    Derivación en vivo — la fuente la almacena por rendimiento
    (``store=True`` + columna pre-creada); aquí se lee del producto.
    """
    template = getattr(line.product, 'product_tmpl', None) if line.product else None
    return bool(template) and template.type == TYPE_SERVICE


def service_lines(queryset, check_state=True):
    """``_domain_sale_line_service``: las líneas de servicio de un queryset.

    Réplica del dominio de la fuente con sus hojas desactivables:

    - ``is_service`` — siempre (la fuente no permite apagarla).
    - ``check_state`` — sólo órdenes confirmadas (``state='sale'``).
    - ``check_is_expense`` — **no se porta**: ``is_expense`` lo declara la
      familia ``hr_expense`` (``sale_expense``), ausente aquí — regla del
      puente (``analisis-gap-sale-contra-ambos-arboles``): la hoja entra
      cuando su campo aterrice.

    El filtro por tipo de producto va en SQL (join a la plantilla); el resto
    del contrato es idéntico al dominio de la fuente.
    """
    queryset = queryset.filter(product__product_tmpl__type=TYPE_SERVICE)
    if check_state:
        queryset = queryset.filter(order__state='sale')
    return queryset

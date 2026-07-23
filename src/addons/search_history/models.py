"""
Models — addons.search_history.

``search_history`` queda como **paquete controlador delgado** (views/urls/
serializers) del historial de búsqueda. **No tiene modelos propios.**

El único modelo, ``SearchEntry`` (telemetría append-only de búsquedas por
usuario, UC-SRCH-03), se movió a su hogar fiel ``addons.website``: en Odoo el
rastreo de comportamiento del visitante del storefront vive en el módulo
``website`` (``website.visitor``/``website.track``). Los consumidores importan
``SearchEntry`` desde ``addons.website.models``.
"""

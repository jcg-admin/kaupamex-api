"""Mixin ``TimeStampedModel`` — marcas de creación y actualización.

En la referencia el ORM auto-inyecta ``create_date``/``write_date``/
``create_uid``/``write_uid`` (``LOG_ACCESS_COLUMNS``) y el archivado es el
campo ``active``; no hay mixin de app equivalente. Aquí se adapta al patrón
Django. El end-state totalmente fiel (auto-inyección en la capa ``orm/``, sin
mixin) queda como alternativa diferida en DEC-09 de
``adoptar-arquitectura-server-service-odoo``.

**Un archivo por mixin**, como ``image_mixin.py`` / ``avatar_mixin.py`` /
``properties_base_definition_mixin.py`` en la referencia. Antes los seis
vivían juntos en ``mixins.py``, agrupados por naturaleza ("son mixins") —
agrupación que la referencia no hace.

Equivale al log-access de la referencia: ``create_date`` → ``created_at``,
``write_date`` → ``updated_at``.
"""
from django.db import models


class TimeStampedModel(models.Model):
    """
    Clase base abstracta que provee created_at y updated_at a todos
    los modelos que hereden de ella.

    Usar en TODOS los modelos concretos del proyecto excepto User.
    No incluye ordering — cada modelo define el suyo.
    No incluye db_index en created_at — los modelos que requieren
    índice por volumen (inventario, órdenes) lo declaran directamente.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        abstract      = True
        get_latest_by = 'created_at'

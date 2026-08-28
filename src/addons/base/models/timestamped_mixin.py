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

**Es también el hogar de lo que la referencia cuelga de ``BaseModel``.**
``RecordLoaderMixin`` (``orm/models.py``) porta ``_load_records`` y su cadena,
que allá **todo** modelo tiene porque viven en ``BaseModel``
(``odoo19c: odoo/orm/models.py:5054-5108``). Aquí ``models.Model`` es el de
Django y no es nuestro para colgarle nada, así que el mecanismo viaja por la
base común del proyecto — la clase que este archivo declara "usar en TODOS los
modelos concretos". Sin esa adopción el cargador de datos XML
(``tools/convert.py``) sólo podría cargar los modelos que declararan el mixin a
mano, y un archivo de datos de la referencia nombra veinticuatro modelos
distintos sólo en ``base``.

``RecordLoaderMixin`` extiende ``FieldSqlMixin``, así que una clase que ya
declaraba ``FieldSqlMixin`` **antes** de ``TimeStampedModel`` en sus bases
rompe el MRO (precedencia local contradictoria). Esas declaraciones se
retiran: la heredan por aquí.
"""
from django.db import models

from orm.models import RecordLoaderMixin


class TimeStampedModel(RecordLoaderMixin, models.Model):
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

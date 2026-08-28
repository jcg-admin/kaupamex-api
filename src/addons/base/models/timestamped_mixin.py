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

``DisplayNameMixin`` (``orm/models.py``) viaja por la misma vía y por la misma
razón: la fuente declara ``display_name`` y su bloque en ``BaseModel``
(``odoo19c: odoo/orm/models.py:473,1421-1543``), así que allá **todo** modelo
tiene etiqueta sin declarar nada. Aquí la base común cubre 284 de los 374
modelos concretos nuestros; los 90 que no la heredan la reciben de
``orm.model_classes.adopt_display_name``, en ``class_prepared``. Dos vías, la
misma razón que ``H-API-577``.

``RecordLoaderMixin`` extiende ``FieldSqlMixin``, así que una clase que ya
declaraba ``FieldSqlMixin`` **antes** de ``TimeStampedModel`` en sus bases
rompe el MRO (precedencia local contradictoria). Esas declaraciones se
retiran: la heredan por aquí.
"""
from django.db import models

from orm.models import DisplayNameMixin, RecordLoaderMixin


class TimeStampedModel(RecordLoaderMixin, DisplayNameMixin, models.Model):
    """
    Clase base abstracta que provee created_at y updated_at a todos
    los modelos que hereden de ella.

    Usar en TODOS los modelos concretos del proyecto excepto User.
    No incluye ordering — cada modelo define el suyo.
    No incluye db_index en created_at — los modelos que requieren
    índice por volumen (inventario, órdenes) lo declaran directamente.
    """
    #: Las cuatro formas de permiso NO se declaran aquí — y el intento está
    #: medido. ``check_access``, ``has_access``, ``_check_access`` y
    #: ``_filtered_access`` cuelgan de ``BaseModel``
    #: (``odoo19c: odoo/orm/models.py:4100-4135``), así que allá **todo**
    #: modelo las tiene. Recuperar esa universalidad colgando aquí un
    #: ``objects = AccessManager()`` parece el sitio natural y **rompe el
    #: árbol**: ``Options.managers`` recorre el MRO por profundidad y se queda
    #: con el **primer** manager de cada nombre
    #: (``django/db/models/options.py``, ``seen_managers``), así que este
    #: ``objects`` eclipsaba al de toda base declarada más abajo. Medido:
    #: ``ContactMessage`` resolvía ``ManagerFromAccessQuerySet`` en vez de
    #: ``SoftDeleteManager``, y una fila borrada seguía visible — 8 casos de
    #: integración en rojo.
    #:
    #: La universalidad la da ``adopt_access_manager``
    #: (``orm/model_classes.py``), que sólo sustituye el manager que Django
    #: auto-creó: un modelo sin manager propio lo recibe, y uno que declara el
    #: suyo lo conserva. Ver :ref:`h-api-876`.

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        abstract      = True
        get_latest_by = 'created_at'

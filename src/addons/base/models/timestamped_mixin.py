"""Mixin ``TimeStampedModel`` — marcas de creación y actualización.

En la referencia el ORM auto-inyecta ``create_date``/``write_date``/
``create_uid``/``write_uid`` (``LOG_ACCESS_COLUMNS``) y el archivado es el
campo ``active``; no hay mixin de app equivalente. Esta base las declara y
``orm.model_classes.adopt_log_access`` las copia en ``class_prepared`` a todo
modelo que no la hereda (DEC-09, ``base/0110``). ``copy`` y su cadena no
vienen de aquí: los entrega ``adopt_copy`` (``designs/copy-universality.md``).

**Un archivo por mixin**, como ``image_mixin.py`` / ``avatar_mixin.py`` /
``properties_base_definition_mixin.py`` en la referencia. Antes los seis
vivían juntos en ``mixins.py``, agrupados por naturaleza ("son mixins") —
agrupación que la referencia no hace.

Equivale al log-access de la referencia: ``create_date`` → ``create_date``,
``write_date`` → ``write_date``.

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

``CheckCompanyMixin`` (``orm/models.py``) viaja por la misma vía y por la misma
razón que los dos anteriores: la fuente declara ``_check_company_auto``,
``_check_company_domain`` y ``_check_company`` en ``BaseModel``
(``odoo19c: odoo/orm/models.py:451, 3997, 4009``), así que allá **todo** modelo
los tiene, con el interruptor apagado por defecto. Aquí también: el mixin
declara ``_check_company_auto = False`` y su ``save()`` sólo verifica cuando
el modelo lo enciende, que es lo que la fuente hace en ``write`` (``:4516``) y
``create`` (``:4744``).

**No cuesta nada al que no lo enciende** — una lectura de atributo por
guardado— y **no genera migración**: el mixin no declara ningún campo, igual
que ``DefaultGetMixin``.
"""

from django.db import models

from orm.fields_temporal import (
    SAVE_NOW,
    SAVE_USING,
    LogAccessUserField,
    TransactionClockSaveMixin,
    TransactionDateTimeField,
    record_transaction_now,
    transaction_now,
)
from orm.models import (
    ArchiveMixin,
    BaseUrlMixin,
    CheckCompanyMixin,
    DisplayNameMixin,
    OrderMixin,
    RecordLoaderMixin,
)

#: El reloj vive en ``orm.fields_temporal``; se reexporta aquí porque los
#: consumidores lo importaban de este módulo.
__all__ = [
    'SAVE_NOW', 'SAVE_USING', 'TimeStampedModel',
    'TransactionClockSaveMixin', 'TransactionDateTimeField',
    'record_transaction_now', 'transaction_now',
]


class TimeStampedModel(
    TransactionClockSaveMixin,
    RecordLoaderMixin,
    DisplayNameMixin,
    OrderMixin,
    CheckCompanyMixin,
    BaseUrlMixin,
    ArchiveMixin,
    models.Model,
):
    """
    Clase base abstracta que provee create_date y write_date a todos
    los modelos que hereden de ella.

    Usar en TODOS los modelos concretos del proyecto excepto User.
    No incluye ordering — cada modelo define el suyo.
    No incluye db_index en create_date — los modelos que requieren
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

    create_date = TransactionDateTimeField(
        auto_now_add=True,
    )
    write_date = TransactionDateTimeField(
        auto_now=True,
    )
    #: ≙ ``create_uid``/``write_uid`` de ``_log_access`` (``odoo19c:
    #: odoo/orm/models.py:283-292``): ``Many2one('res.users')`` sin
    #: ``required`` ni ``ondelete``, cuyo defecto es ``set null``
    #: (``fields_relational.py:274-282``), sin inverso y sin índice.
    create_uid = LogAccessUserField(
        'base.ResUsers', models.SET_NULL, null=True, blank=True,
        editable=False, related_name='+', db_index=False,
        db_column='create_uid',
        stamp_on_create_only=True,
    )
    write_uid = LogAccessUserField(
        'base.ResUsers', models.SET_NULL, null=True, blank=True,
        editable=False, related_name='+', db_index=False,
        db_column='write_uid',
    )

    class Meta:
        abstract = True
        get_latest_by = 'create_date'

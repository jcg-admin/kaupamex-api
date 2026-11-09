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

from django.db import connections, models, router

from orm.models import (
    ArchiveMixin,
    BaseUrlMixin,
    CheckCompanyMixin,
    DisplayNameMixin,
    OrderMixin,
    RecordLoaderMixin,
)


def transaction_now(using):
    """La hora de la transacción en curso — ≙ ``Cursor.now()``.

    ``odoo19c: odoo/sql_db.py:271-278``: *"Return the transaction's timestamp
    NOW() AT TIME ZONE 'UTC'"*. La fuente la memoriza en el cursor; aquí la
    memoria la da PostgreSQL, porque ``now()`` es constante dentro de una
    transacción. No se memoriza por bloque ``atomic``: un
    ``@transaction.atomic`` usado como decorador reutiliza el mismo objeto en
    cada llamada y serviría la hora de una transacción anterior.
    """
    with connections[using or 'default'].cursor() as cursor:
        cursor.execute('SELECT now()')
        return cursor.fetchone()[0]


#: La lectura de ``now()`` que comparten las fechas de un mismo guardado, y el
#: alias que ``save`` recibió. Los limpia :meth:`TimeStampedModel.save`.
SAVE_NOW = '_orm_save_now'
SAVE_USING = '_orm_save_using'


def _write_alias(instance):
    """La base donde ``save`` escribe la fila.

    Durante el INSERT ``_state.db`` aún es ``None``: Django lo fija después
    de escribir. El destino es el ``using`` explícito de ``save`` o, sin él,
    ``router.db_for_write`` — la misma regla que ``Model.save``.
    """
    return (instance.__dict__.get(SAVE_USING) or instance._state.db
            or router.db_for_write(type(instance), instance=instance))


class TransactionDateTimeField(models.DateTimeField):
    """``auto_now``/``auto_now_add`` con la hora de la transacción.

    ``create`` y ``write`` de la fuente fechan con ``cr.now()``
    (``odoo19c: odoo/orm/models.py:4396,4803-4805``): todo lo escrito en una
    transacción lleva la misma fecha y un ``write`` en la transacción del
    ``create`` no mueve ``write_date``. ``DateTimeField`` de Django usa
    ``timezone.now()`` en cada ``pre_save``, que difiere entre guardados.

    Se deconstruye como ``DateTimeField``: la columna es la misma y las
    migraciones de los modelos no cambian.
    """

    def pre_save(self, model_instance, add):
        if self.auto_now or (self.auto_now_add and add):
            value = model_instance.__dict__.get(SAVE_NOW)
            if value is None:
                # Una sola lectura por guardado: la fuente fija las dos
                # fechas de un alta con el mismo ``cr.now()``
                # (``models.py:4803-4805``). Fuera de ``atomic`` (autocommit)
                # dos ``SELECT now()`` son dos transacciones y diferirían.
                value = transaction_now(_write_alias(model_instance))
                model_instance.__dict__[SAVE_NOW] = value
            setattr(model_instance, self.attname, value)
            return value
        return super().pre_save(model_instance, add)

    def deconstruct(self):
        name, _path, args, kwargs = super().deconstruct()
        return name, 'django.db.models.DateTimeField', args, kwargs


class TimeStampedModel(
    RecordLoaderMixin,
    DisplayNameMixin,
    OrderMixin,
    CheckCompanyMixin,
    BaseUrlMixin,
    ArchiveMixin,
    models.Model,
):
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

    def save(self, *args, **kwargs):
        """Delimita la lectura de reloj compartida por las dos fechas.

        La memoria vive en la instancia sólo mientras dura este guardado: un
        ``save`` posterior, en otra transacción, vuelve a leer ``now()``.
        """
        self.__dict__.pop(SAVE_NOW, None)
        self.__dict__[SAVE_USING] = kwargs.get('using')
        try:
            return super().save(*args, **kwargs)
        finally:
            self.__dict__.pop(SAVE_NOW, None)
            self.__dict__.pop(SAVE_USING, None)

    created_at = TransactionDateTimeField(
        auto_now_add=True,
    )
    updated_at = TransactionDateTimeField(
        auto_now=True,
    )

    class Meta:
        abstract = True
        get_latest_by = 'created_at'

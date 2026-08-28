"""Campo dependiente de empresa — ≙ el ``company_dependent=True`` de la fuente.

En Odoo un campo puede declararse ``company_dependent=True``: **una fila, un
valor por empresa**. No es una columna escalar sino un ``jsonb`` con la forma
``{id_de_empresa: valor}``, y leerlo devuelve el valor de la empresa activa —
o, si esa empresa no tiene el suyo, el default de ``ir.default``.

El caso canónico de la referencia: ``res.partner.barcode``
(``odoo19c: addons/base/models/res_partner.py``). El mismo contacto lleva un
código de barras distinto en cada empresa del grupo, y ninguna ve el de la
otra. Con una columna escalar eso no se puede expresar: o se duplica el
contacto por empresa, o las empresas se pisan el valor.

Qué construye este módulo, y por qué hacía falta
================================================

Django no lo tiene: un ``models.Field`` es **una** columna con **un** valor
por fila. La pieza que faltaba no es un tipo de dato —``JSONField`` ya
existe— sino la **indirección de lectura**: que ``partner.barcode`` devuelva
el valor de la empresa activa y no el mapa entero.

Tres piezas, y las tres tienen contraparte en la fuente:

.. list-table::
   :header-rows: 1

   * - Aquí
     - En la referencia
   * - ``CompanyDependent`` (columna ``jsonb``)
     - ``column_type`` → ``('jsonb', 'jsonb')`` cuando ``company_dependent``
       (``odoo19c: odoo/orm/fields.py:783``)
   * - ``_CompanyDependentAttribute`` (el descriptor de lectura/escritura)
     - la capa de caché por ``(company,)`` del ORM: ``_depends_context =
       ('company',)`` (``:476``)
   * - ``get_company_dependent_fallback``
     - ídem, mismo nombre (``:794-801``)

Cómo se declara — con la firma de la fuente
===========================================

::

    barcode = fields.Char(company_dependent=True, max_length=64)

El despachador de ``orm/fields_textual.py`` devuelve un ``CompanyDependent``
en vez de un ``CharField``, el mismo patrón que ya usa para ``store=False``.
El sitio de declaración queda **idéntico al de la fuente**.

El discriminador de la escritura, y por qué es sólido
=====================================================

El descriptor tiene que distinguir dos asignaciones que llegan al mismo
atributo:

- ``partner.barcode = 'ABC'`` — el valor **de la empresa activa**;
- ``partner.barcode = {'1': 'ABC'}`` — el **mapa crudo**, que es lo que
  Django asigna al hidratar la fila desde la base.

Se distinguen por el tipo: ``dict`` (o ``None``) es el mapa, cualquier otra
cosa es el valor. Eso es sólido **porque el universo de tipos admitidos lo
excluye**: ``COMPANY_DEPENDENT_FIELDS`` de la referencia
(``odoo19c: odoo/orm/fields.py:42-44``) son ``char``, ``float``, ``boolean``,
``integer``, ``text``, ``many2one``, ``date``, ``datetime``, ``selection`` y
``html`` — ninguno es un dict. No es una heurística sobre datos arbitrarios:
es una partición sobre una lista cerrada que la fuente declara.

Alcance: la clase es genérica, el despachador todavía no
========================================================

La clase acepta cualquiera de los diez tipos —recibe el campo base y de él
saca el tipo de columna para el ``CAST``—. Lo que **no** está cableado son
nueve de los diez despachadores: hoy sólo ``Char`` lo es, que es el que tiene
consumidor (``res.partner.barcode``). Los otros nueve —``Text``, ``Integer``,
``Float``, ``Boolean``, ``Date``, ``Datetime``, ``Selection``, ``Html``,
``Many2one``— son alias pelados de Django (``Text = models.TextField``), y
convertirlos en funciones es un cambio ancho sin ningún campo que lo pida.

No es una divergencia declarada: es **trabajo con sucesor registrado**,
tarea **#129**. Se paga cuando un campo de esos tipos se declare
``company_dependent``, que es el mismo criterio prospectivo de
``atributos-de-clase-de-modelo.md``.

Este archivo NO existe en la referencia
=======================================

Allá ``company_dependent`` es un **atributo** de la clase ``Field``, no un
tipo aparte: ``odoo/orm/fields.py`` lo declara en la línea 291 y ramifica en
``column_type``, ``to_sql`` y ``convert_to_column``. Aquí la clase base de
todo campo es ``django.db.models.Field``, y un ``CharField`` no puede cambiar
su tipo de columna a ``jsonb`` según un parámetro: hay que devolver otra
clase.

Es la misma situación que ``orm/fields_nonstored.py`` —y el mismo veredicto:
mecanismo legítimamente construido (``porte-completo-no-parcial.md``: *si el
stack no trae el mecanismo, se construye*), en un archivo que la raíz
espejada no tiene. Se declara aquí por lo mismo que aquél lo declara.
"""
from django.apps import apps
from django.db import models
from django.db.models.query_utils import DeferredAttribute

from orm.environments import get_current_company
from tools.sql import SQL

__all__ = ['COMPANY_DEPENDENT_FIELDS', 'CompanyDependent']

#: ≙ ``COMPANY_DEPENDENT_FIELDS`` (``odoo19c: odoo/orm/fields.py:42-44``). Los
#: diez tipos que la fuente admite; declararlo en otro tipo es un aviso allá.
COMPANY_DEPENDENT_FIELDS = (
    'char', 'float', 'boolean', 'integer', 'text', 'many2one', 'date',
    'datetime', 'selection', 'html',
)

#: Tipo de columna de PostgreSQL por tipo de la fuente — es el ``CAST`` que
#: ``to_sql`` necesita para devolver el ``jsonb`` como el escalar que era.
_SQL_CAST = {
    'char': 'varchar', 'text': 'text', 'html': 'text',
    'selection': 'varchar', 'integer': 'integer', 'float': 'double precision',
    'boolean': 'boolean', 'date': 'date', 'datetime': 'timestamp',
    'many2one': 'integer',
}


class _CompanyDependentAttribute(DeferredAttribute):
    """El descriptor que hace la indirección — una fila, un valor por empresa.

    ``DeferredAttribute`` es el descriptor con que Django resuelve un campo
    aplazado (``only()``/``defer()``); heredarlo conserva ese comportamiento y
    añade el `__set__` que convierte al descriptor en uno de datos, para que
    la asignación pase por aquí y no por el ``__dict__`` directo.
    """

    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        stored = instance.__dict__.get(self.field.attname)
        if stored is None:
            stored = super().__get__(instance, cls)
        return self.field.value_for_current_company(stored, instance)

    def __set__(self, instance, value):
        # Ver "El discriminador de la escritura" en la cabecera del módulo.
        if value is None or isinstance(value, dict):
            instance.__dict__[self.field.attname] = value
            return
        company_id = get_current_company()
        if company_id is None:
            raise ValueError(
                f'No hay empresa activa: {self.field.name!r} es dependiente '
                f'de empresa y no se puede escribir sin saber a cuál.')
        stored = instance.__dict__.get(self.field.attname) or {}
        instance.__dict__[self.field.attname] = {
            **stored, str(company_id): value}


class CompanyDependent(models.JSONField):
    """Un campo cuyo valor depende de la empresa activa.

    La columna es ``jsonb`` —igual que en la fuente
    (``odoo19c: odoo/orm/fields.py:783``)— y guarda ``{empresa: valor}``.
    """

    #: ≙ el atributo homónimo de la clase ``Field`` (``:291``). Lo lee
    #: ``Field.to_sql`` para tomar su rama, igual que allá.
    company_dependent = True

    # ``descriptor_class`` se queda en el ``DeferredAttribute`` de Django, a
    # proposito: es el que Django instala sobre ``attname``, y ese atributo
    # guarda el MAPA. El descriptor de la indireccion lo cuelga
    # :meth:`contribute_to_class` sobre ``name``. Ponerlo aqui haria que
    # ``refresh_from_db`` —que copia por ``attname``— leyera el escalar y
    # borrara el mapa; medido, es exactamente lo que pasaba.

    #: Sufijo del atributo que guarda el MAPA crudo. Ver
    #: :meth:`get_attname` — es la separación entre caché y columna.
    RAW_ATTNAME_SUFFIX = '_company_values'

    def get_attname(self):
        """El atributo interno guarda el MAPA; el público, el valor por empresa.

        Django reserva ``attname`` para el valor **tal como viaja a la
        columna**, y ``name`` para el atributo público. Un campo normal los
        iguala; un ``ForeignKey`` no (``parent`` frente a ``parent_id``), y
        aquí pasa lo mismo por la misma razón: lo que viaja a la columna es el
        mapa ``{empresa: valor}`` y lo que se lee es un escalar.

        **Separarlos no es cosmético — sin ello el mapa se pierde.**
        ``Model.refresh_from_db`` y ``Model.from_db`` copian el valor con
        ``setattr(inst, field.attname, ...)``: con ``attname == name`` esa
        copia pasa por el descriptor, que devuelve el escalar de la empresa
        activa, y la fila recargada se queda con un escalar donde había un
        mapa. Medido: recargar un contacto fuera de un ``company_scope``
        borraba el mapa entero, porque el escalar leído era ``None``.

        Allá el problema no existe porque la separación ya está hecha en otro
        sitio: el ORM guarda el valor por empresa en su caché
        (``_depends_context = ('company',)``, ``odoo19c: odoo/orm/fields.py:
        476``) y la columna la escribe ``convert_to_column_update``. Aquí no
        hay caché propia, así que la frontera se declara en ``attname``.
        """
        return f'{self.name}{self.RAW_ATTNAME_SUFFIX}'

    def set_attributes_from_name(self, name):
        """La columna conserva el nombre del campo, no el del atributo crudo.

        ``Field.set_attributes_from_name`` deriva ``column`` de ``attname``.
        Con los dos separados eso daría una columna ``barcode_company_values``,
        que no es la de la fuente: allá la columna se llama como el campo.
        """
        super().set_attributes_from_name(name)
        self.column = self.db_column or self.name

    def contribute_to_class(self, cls, name, private_only=False):
        """Cuelga el descriptor del nombre PÚBLICO, además del interno.

        ``Field.contribute_to_class`` instala ``descriptor_class`` sobre
        ``attname`` — que aquí es el atributo del mapa crudo. El descriptor de
        la indirección tiene que colgar de ``name``, que es lo que el código
        de aplicación escribe (``partner.barcode``).
        """
        super().contribute_to_class(cls, name, private_only=private_only)
        setattr(cls, self.name, _CompanyDependentAttribute(self))

    def __init__(self, *args, base_type='char', comodel=None, **kwargs):
        if base_type not in COMPANY_DEPENDENT_FIELDS:
            raise ValueError(
                f'company_dependent field of type {base_type!r} is not one of '
                f'the allowed types {COMPANY_DEPENDENT_FIELDS}')
        # ≙ los dos avisos de la fuente (``:466-470``). Aquí son errores, no
        # avisos: un campo requerido dependiente de empresa no tiene sentido
        # —la columna guarda un mapa, y estar "no vacío" no dice nada de la
        # empresa activa— y dejarlo pasar produce una restricción que no
        # protege lo que su nombre promete.
        if kwargs.get('required'):
            raise ValueError('company_dependent field cannot be required')
        if kwargs.pop('translate', None):
            raise ValueError('company_dependent field cannot be translated')
        self.base_type = base_type
        #: Etiqueta del modelo apuntado cuando ``base_type == 'many2one'``. Es
        #: lo que ``registry.many2one_company_dependents`` indexa: un
        #: ``jsonb`` guarda el id, así que el catálogo de FK no ve la
        #: referencia y hay que declararla aquí.
        self.company_dependent_comodel = comodel
        # ≙ ``attrs['copy'] = attrs.get('copy', False)`` (``:473``): el valor
        # es de la empresa, no del registro, así que no viaja en una copia.
        kwargs.setdefault('null', True)
        kwargs.setdefault('blank', True)
        kwargs.setdefault('default', dict)
        # Los argumentos del campo base que no aplican a una columna jsonb.
        for scalar_only in ('max_length', 'choices', 'max_digits',
                            'decimal_places'):
            kwargs.pop(scalar_only, None)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        """Django serializa el campo para la migración; ``base_type`` va con él."""
        name, path, args, kwargs = super().deconstruct()
        if self.base_type != 'char':
            kwargs['base_type'] = self.base_type
        if self.company_dependent_comodel is not None:
            kwargs['comodel'] = self.company_dependent_comodel
        return name, path, args, kwargs

    @property
    def sql_cast_type(self):
        """El tipo al que ``to_sql`` castea el ``jsonb`` de vuelta."""
        return _SQL_CAST[self.base_type]

    def get_company_dependent_fallback(self, record):
        """El default de ``ir.default`` cuando la empresa no tiene valor propio.

        ≙ ``get_company_dependent_fallback`` (``odoo19c: odoo/orm/fields.py:
        794-801``). La fuente lo pide con ``SUPERUSER_ID`` y la empresa
        activa; aquí ``_get_model_defaults`` es un ``classmethod`` sin usuario
        —el default global y el de empresa son los que aplican a un campo
        dependiente de empresa, no el de un usuario concreto—.
        """
        IrDefault = apps.get_model('base', 'IrDefault')
        defaults = IrDefault._get_model_defaults(
            type(record)._meta.label, company_id=get_current_company())
        return defaults.get(self.name)

    def get_company_dependent_fallback_sql(self, model):
        """El fallback como fragmento ``SQL``, para la rama de ``to_sql``.

        NO tiene contraparte con este nombre: allá ``to_sql`` obtiene el valor
        con ``get_company_dependent_fallback`` y lo pasa por
        ``convert_to_column``, dos pasos que aquí colapsan en uno porque el
        parámetro viaja adaptado por psycopg. El ``CAST`` explícito es el
        mismo que la fuente emite (``odoo19c: odoo/orm/fields.py:1229``): sin
        él PostgreSQL no sabe con qué tipo comparar las dos ramas del
        ``COALESCE``.
        """
        IrDefault = apps.get_model('base', 'IrDefault')
        defaults = IrDefault._get_model_defaults(
            model._meta.label, company_id=get_current_company())
        return SQL("%s::" + self.sql_cast_type, defaults.get(self.name))

    def value_for_current_company(self, stored, record):
        """El valor de la empresa activa, o el fallback de ``ir.default``."""
        company_id = get_current_company()
        if isinstance(stored, dict) and company_id is not None:
            if str(company_id) in stored:
                return stored[str(company_id)]
        return self.get_company_dependent_fallback(record)

    def raw_company_values(self, record):
        """El mapa crudo ``{empresa: valor}``, sin la indirección de lectura.

        No tiene contraparte con este nombre: allá el mapa se llega por la
        capa de caché del ORM. Aquí el descriptor **es** la indirección, así
        que hace falta una puerta para ver lo que hay debajo — la usan las
        migraciones de datos y ``base_partner_merge``, que trabajan sobre
        todas las empresas a la vez.
        """
        return record.__dict__.get(self.attname) or {}

    def set_for_company(self, record, company_id, value):
        """Escribe el valor de UNA empresa, sin depender de cuál esté activa.

        Contraparte de ``raw_company_values`` para el lado de escritura: la
        fusión de contactos reasigna valores de empresas que no son la activa.
        """
        stored = dict(self.raw_company_values(record))
        stored[str(company_id)] = value
        record.__dict__[self.attname] = stored

    def pre_save(self, model_instance, add):
        """Lo que Django persiste es el MAPA, no el valor de la empresa activa.

        ``Field.pre_save`` de Django devuelve ``getattr(instancia, attname)``,
        y aquí ese atributo pasa por el descriptor — que devuelve el valor de
        la empresa activa, un escalar. Sin esta rama el ``INSERT`` intentaría
        guardar ``'ABC'`` en una columna ``jsonb`` y ``get_prep_value`` lo
        rechazaría con razón.

        No tiene contraparte con este nombre: allá la separación entre el
        valor cacheado por empresa y la columna la hace
        ``convert_to_column_update`` sobre el ``Field`` (``odoo19c:
        odoo/orm/fields.py``), porque el ORM ya distingue caché de columna.
        Aquí el descriptor **es** la indirección, así que la separación tiene
        que declararse en el enganche que Django usa para escribir.
        """
        return self.raw_company_values(model_instance)

    def value_from_object(self, obj):
        """El mapa crudo también para serializar (``dumpdata``, formularios)."""
        return self.raw_company_values(obj)

    def get_prep_value(self, value):
        """Lo que va a la base es siempre el mapa, nunca el valor de una empresa.

        Devuelve el ``dict`` **sin serializar**: en Django 6 la serialización
        la hace ``get_db_prep_value`` llamando a
        ``connection.ops.adapt_json_value`` (``json.py:99-102`` del paquete
        instalado). Un ``json.dumps`` aquí la duplica — la columna acaba
        guardando la *cadena* JSON como valor jsonb, y al releerla vuelve un
        ``str`` en vez del mapa. Medido: con el ``dumps`` puesto, el viaje de
        ida y vuelta a la base rompe al hidratar la fila.
        """
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError(
                f'{self.name!r} guarda un mapa por empresa; recibió '
                f'{type(value).__name__}. Asigne por el atributo para escribir '
                f'el valor de la empresa activa.')
        return value

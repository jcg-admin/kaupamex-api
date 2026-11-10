"""Base del ORM — fiel a ``odoo/orm/models.py`` (Odoo 19).

En Odoo 19 la clase base ``BaseModel``/``Model`` se define en
``odoo/orm/models.py`` y ``odoo/models/__init__.py`` la re-exporta. Aquí, con el
prefijo ``odoo.`` eliminado (``orm`` ≙ ``odoo/orm``), esta es la **definición**;
``src/models.py`` (top-level, ≙ ``odoo/models/__init__.py``) la re-exporta para
que un addon escriba ``import models`` / ``class X(models.Model)``.

Respaldo: ``models`` ES la ORM de Django — se re-exporta ``django.db.models``
completo (``Model``, ``Manager``, ``UniqueConstraint``, ``Index``, ``CASCADE``/
``SET_NULL``/``PROTECT``, ``Q``, ``Sum``, ``F``…). No se interpone una capa;
sólo se expone bajo el nombre Odoo para que el addon lea igual que su fuente.

La resolución de permiso vive aquí, como allá
==============================================

``_check_access`` y sus tres formas públicas (``check_access``, ``has_access``,
``_filtered_access``) se declaran en **este archivo** en la referencia
(``odoo19c: odoo/orm/models.py:4099-4158``), sobre ``BaseModel``. Por eso están
aquí y no en un archivo nuevo: ``odoo/orm/`` no tiene ningún ``access.py``
—verificado con ``ls``—, y crear uno repetiría :ref:`h-api-578`.

**La divergencia, y es de forma:** allá ``self`` es un *recordset*, así que los
cuatro símbolos son métodos de todo modelo. Aquí el recordset es un
``QuerySet``, y **``models.Model`` de Django no es nuestro** para colgarle
métodos. Cuelgan de un ``QuerySet`` — que es el mismo objeto, con otro nombre —
y un modelo los adopta declarando ``objects = AccessManager()``.

Consecuencia que conviene saber: en la fuente **todo** modelo los tiene; aquí
sólo los que adopten el manager. Qué modelos lo adoptan, y en qué orden, es
trabajo aparte — tarea **#96**.

Dos mecanismos de este archivo viven en un módulo hermano
==========================================================

La referencia declara los dos **aquí dentro**; aquí se extrajeron a su propio
archivo y este hogar los apunta, para que se lleguen navegando desde donde la
fuente los pone y no por casualidad:

- ``orm/inherits.py`` — ``_inherits``, la delegación por Many2one nombrado.
  Medido en la referencia: **8** ocurrencias en ``odoo19c: odoo/orm/models.py``
  y presencia en otros cuatro módulos de ``odoo/orm/`` (``fields.py``,
  ``fields_relational.py``, ``model_classes.py``, ``registry.py``). Es decir:
  el mecanismo **sí** existe allá y **no** tiene archivo propio.
- ``orm/method_chain.py`` — ``chain_method``, el relevo entre overrides que
  cuelgan por ``setattr`` desde ``AppConfig.ready()``. Éste **no** tiene
  contraparte: la referencia no lo necesita porque ``_inherit`` le construye
  una MRO real y cada override llama a ``super()``.

La forma es la misma que ``service/model.py`` ya usa para ``service/retry.py``.
Ver :ref:`h-api-855` para el veredicto por archivo de las raíces espejadas.
"""
import collections
import collections.abc
import contextlib
import functools
import itertools
import logging
import re
import warnings
from operator import itemgetter

from django.apps import apps
from django.db.models import *          # noqa: F401,F403  (re-export ORM completo)
from django.db.models import (  # noqa: F401
    ForeignKey, Manager, Model, QuerySet,
)
# ``checks`` viene del mismo módulo que lo usa en ``Model.check``.
from django.db.models.base import ModelState, checks
from django.db.models.fields import related_descriptors as _related_descriptors
from django.db.models.signals import (class_prepared, m2m_changed, post_init,
                                      pre_delete, pre_init, pre_save)
from django.dispatch import receiver
from psycopg import errors as pg_errors
import uuid
import datetime
import json
import pytz
import babel
import babel.dates
from contextvars import ContextVar

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import DatabaseError
from django.db import DEFAULT_DB_ALIAS, connections

import api

from exceptions import AccessError, LockError, MissingError, UserError
from orm.environments import (
    context_scope, env, execute_query, get_context, get_current_company,
    get_current_cr,
    get_current_uid, get_current_user, get_transaction, is_su,
    sudo as elevate_privileges,
)
from orm.commands import (_DJANGO_X2MANY_GET, Command, ManyToManyLink,
                          ManyToManySet,
                          One2manyChild, apply_many2many_commands,
                          apply_one2many_commands,
                          is_command_list, related_manager)
from orm import registry
from orm.domains import Domain, to_q
from orm.model_classes import LOG_ACCESS_COLUMNS, extend_model, parent_name_of
from orm.fields_relational import (
    One2many as DeclaredOne2many,
    _multi_comodel_domain as multi_comodel_domain,
    _m2m_relation as m2m_relation,
    _queryset_subselect as queryset_subselect,
    django_comodel_rows,
)
from orm.fields import (PENDING_INVERSE_FIELDS, WRITING_VALUES, determine,
                        FieldDescriptor, StoredMany2oneIdDescriptor,
                        _field_cache_record_id,
                        convert_to_display_name, determine_inverse,
                        null_record_value)
from orm.fields_textual import BASE_LANG, Char
from orm.fields_temporal import Date, Datetime
from orm.identifiers import NewId
from orm.fields_nonstored import non_stored_fields
from orm.fields_properties import Properties, check_property_field_value_name
from orm.utils import (COLLECTION_TYPES, SQL_OPERATORS,
                       READ_GROUP_ALL_TIME_GRANULARITY,
                       READ_GROUP_NUMBER_GRANULARITY,
                       READ_GROUP_TIME_GRANULARITY,
                       FieldRegistryDescriptor, OriginIds,
                       as_record_list, browse, check_object_name,
                       model_field_registry, parse_field_expr, record_ids)
from service.db import Savepoint
from tools import date_utils
from tools.cache import ormcache
from tools.constants import PREFETCH_MAX
from tools.misc import (OrderedSet, ReadonlyDict, groupby, partition,
                        split_every, unique, unquote, get_lang,
                        DEFAULT_SERVER_DATE_FORMAT,
                        DEFAULT_SERVER_DATETIME_FORMAT)
from tools.query import Query
from tools.sql import SQL
from tools.i18n import format_list
from loglevels import exception_to_unicode

_logger = logging.getLogger(__name__)


#: Las tres claves que **referencian** a un registro en vez de nombrar un
#: campo — ≙ ``REFERENCING_FIELDS`` de ``odoo19c:
#: addons/base/models/ir_fields.py:16``. Se declaran aquí además de allá
#: porque ``_extract_records`` las necesita para validar la cabecera del
#: archivo, y este módulo no puede importar ``ir_fields`` sin cerrar ciclo.
REFERENCING_FIELD_NAMES = frozenset({None, 'id', '.id'})


def fix_import_export_id_paths(fieldname):
    """≙ ``fix_import_export_id_paths``
    (``odoo19c: odoo/orm/models.py:145-156``).

    «Fixes the id fields in import and exports, and splits field paths on
    ``/``.»

    Las dos sustituciones no son cosmética: la cabecera de un CSV escribe
    ``partner_id/.id`` o ``partner_id:id`` según de dónde venga, y ambas
    significan lo mismo — el subcampo que referencia. Se normalizan a la forma
    con barra antes de partir, así que el resto del cargador ve una sola forma.
    """
    fixed_db_id = re.sub(r'([^/])\.id', r'\1/.id', fieldname)
    fixed_external_id = re.sub(r'([^/]):id', r'\1/id', fixed_db_id)
    return fixed_external_id.split('/')


def to_record_ids(arg) -> list:
    """≙ ``to_record_ids`` (``odoo19c: odoo/orm/models.py:159-166``).

    «Return the record ids of ``arg``, which may be a recordset, an integer or
    a list of integers.»

    Las tres formas se normalizan a una lista de ids reales, y las tres
    descartan el id falso — pero **no por el mismo camino**, y la diferencia es
    de la fuente, no de este puerto:

    ========= ========================== ============================
    Forma     La fuente                  Aquí
    ========= ========================== ============================
    recordset ``arg.ids``                ``OriginIds(record_ids(…))``
    entero    ``[arg] if arg else []``   igual
    iterable  ``[i for i in arg if i]``  igual
    ========= ========================== ============================

    **Divergencia de mecanismo en la primera fila, no de contrato.** Aquí no
    hay recordset: un conjunto de filas es una instancia de modelo o un
    ``QuerySet``, así que ``arg.ids`` no existe y su equivalente es
    :func:`~orm.utils.record_ids`. Lo que ``.ids`` hace en la fuente
    (``odoo19c: odoo/orm/models.py:5905-5909``) es envolver sus ids en
    :class:`~orm.utils.OriginIds`, y por eso el puerto también lo envuelve: sin
    esa envoltura una fila sin guardar aportaría ``None`` a la lista.

    **La asimetría que esto deja es la de la fuente y se conserva.** Un
    :class:`~orm.identifiers.NewId` **con origen** dentro de una fila se
    resuelve a su origen; el mismo ``NewId`` dentro de una lista suelta se
    descarta, porque la rama del iterable filtra por verdad y ``NewId`` es
    falso. No se corrige: quien pasa una lista pasa ids, no registros.
    """
    if isinstance(arg, (Model, QuerySet)):
        return list(OriginIds(record_ids(arg)))
    if isinstance(arg, int):
        return [arg] if arg else []
    return [id_ for id_ in arg if id_]


def itemgetter_tuple(items):
    """≙ ``itemgetter_tuple`` (``odoo19c: odoo/orm/models.py:7097-7105``).

    «Fixes itemgetter inconsistency (useful in some cases) of not returning a
    tuple if ``len(items) == 1``: always returns an n-tuple where
    ``n = len(items)``.»
    """
    if len(items) == 0:
        return lambda a: ()
    if len(items) == 1:
        return lambda gettable: (gettable[items[0]],)
    return itemgetter(*items)


def get_columns_from_sql_diagnostics(connection, diagnostics, *,
                                     check_registry=False):
    """≙ ``get_columns_from_sql_diagnostics`` (``odoo19c: :7108-7130``).

    «Given the diagnostics of an error, return the affected column names by the
    constraint. Return an empty list if we cannot determine the columns.»

    Sirve para atribuir un error de restricción a **su** columna en el informe
    de importación. Cuando el diagnóstico no la nombra, la saca del catálogo de
    PostgreSQL —``pg_constraint`` cruzado con ``pg_attribute``—, que es donde
    vive la lista de columnas de una restricción compuesta.

    :param connection: la conexión sobre la que consultar el catálogo; ≙ el
        ``cr`` de la fuente.
    """
    if column := diagnostics.column_name:
        return [column]
    if not check_registry:
        return []
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                ARRAY(
                    SELECT attname FROM pg_attribute
                    WHERE attrelid = conrelid
                    AND attnum = ANY(conkey)
                ) as "columns"
            FROM pg_constraint
            JOIN pg_class t ON t.oid = conrelid
            WHERE conname = %s
                AND t.relname = %s
                AND t.relnamespace = current_schema::regnamespace
        """, [diagnostics.constraint_name, diagnostics.table_name])
        columns = cursor.fetchone()
    return columns[0] if columns else []


def _database_error(exc):
    """El error de psycopg detrás de ``exc``: Django lo envuelve en su
    ``DatabaseError`` y lo deja en ``__cause__`` (``django/db/utils.py``,
    ``DatabaseErrorWrapper.__exit__``). Uno que ya es de psycopg se
    devuelve tal cual."""
    cause = getattr(exc, '__cause__', None)
    return cause if getattr(cause, 'diag', None) is not None else exc


def _model_name(model):
    """El ``_name`` de la referencia, o la etiqueta de Django si no lo
    declara."""
    return getattr(model, '_name', None) or model._meta.label_lower


def _table_object(model, constraint_name):
    """El objeto de tabla de ``model`` con ese nombre: ≙
    ``self._table_objects.get(constraint_name)``. Aquí su hogar es
    ``Meta.constraints``."""
    if not constraint_name:
        return None
    return next((cons for cons in model._meta.constraints
                 if cons.name == constraint_name), None)


def _table_object_message(cons, model, diagnostics):
    """≙ ``cons.get_error_message(self, exc.diag)`` (``odoo19c:
    odoo/orm/table_objects.py:60-69``): el mensaje que el objeto declara, o
    ``None``. En Django es el ``violation_error_message``; el que Django pone
    por defecto no es una declaración."""
    message = cons.violation_error_message
    if message is None or message == cons.default_violation_error_message:
        return None
    return cons.get_violation_error_message()


#: ≙ ``self.env.cr.cache['export_properties_cache']`` de ``_export_rows``
#: (``odoo19c: odoo/orm/models.py:687-690``): la caché de propiedades de una
#: exportación de primer nivel, compartida con sus llamadas recursivas.
_EXPORT_PROPERTIES_CACHE: ContextVar = ContextVar('export_properties_cache')


def _relation_value_ids(value):
    """Los ids de un valor relacional leído: un recordset, una fila de
    Django, su manager o ``QuerySet``, o nada."""
    if isinstance(value, BaseModel):
        return value._ids
    if value is None:
        return ()
    if hasattr(value, 'all'):
        return tuple(value.all().values_list('pk', flat=True))
    return (value.pk,)


def _acting_user(user):
    """El usuario que actúa — ``self.env.user`` de la referencia."""
    return get_current_user() if user is None else user


class AccessQuerySet(QuerySet):
    """Un recordset que sabe resolver su propio permiso.

    Las cuatro formas de la fuente, con la misma semántica y el mismo orden:
    primero la ACL del **modelo** (``ir.model.access``), y sólo si pasa, las
    reglas de **fila** (``ir.rule``).
    """

    def _check_access(self, operation, user=None):
        """``None`` si puede; si no, ``(prohibidos, fábrica de error)``.

        Fiel a ``odoo19c: odoo/orm/models.py:4135``. Las dos mitades y su
        orden:

        1. ``ir.model.access.check(model, operation)`` — sin permiso de modelo
           los prohibidos son **todos**, y las reglas **ni se evalúan**. La
           fuente hace ``return`` ahí mismo.
        2. Sólo entonces, ``ir.rule`` acota las filas; los prohibidos son los
           que el dominio combinado no devuelve.

        El orden no es cosmético: una regla permisiva sobre un modelo cuya ACL
        deniega devolvería "nada prohibido" si se evaluara primero.
        """
        Access = apps.get_model('base', 'IrModelAccess')
        label = self.model._meta.label
        actor = _acting_user(user)
        if not Access.check(label, operation, raise_exception=False,
                            user=actor):
            return self, functools.partial(
                Access._make_access_error, label, operation)

        Rule = apps.get_model('base', 'IrRule')
        group_ids = list(actor._get_group_ids()) if actor is not None else []
        forbidden = Rule._get_failing(
            self, mode=operation, group_ids=tuple(group_ids), user=actor)
        if forbidden.exists():
            return forbidden, functools.partial(
                Rule._make_access_error, operation, forbidden,
                group_ids=tuple(group_ids), user=actor)
        return None

    def check_access(self, operation, user=None):
        """Levanta ``AccessError`` si no puede — ``check_access``.

        ``odoo19c: odoo/orm/models.py:4100``. Bajo elevación no comprueba nada:
        ``if not self.env.su and (result := self._check_access(operation))``.
        """
        if is_su():
            return None
        result = self._check_access(operation, user=user)
        if result:
            raise result[1]()
        return None

    def has_access(self, operation, user=None):
        """Lo mismo, como booleano — ``has_access`` (``:4117``)."""
        return is_su() or not self._check_access(operation, user=user)

    def _filtered_access(self, operation, user=None):
        """El subconjunto permitido — ``_filtered_access`` (``:4123``).

        La fuente hace ``self - result[0]``; aquí la resta de recordsets es un
        ``exclude`` por PK, que es la misma operación sobre el mismo conjunto.
        """
        if not self or is_su():
            return self
        result = self._check_access(operation, user=user)
        if result:
            return self.exclude(pk__in=result[0].values_list('pk', flat=True))
        return self

    def _get_redirect_suggested_company(self, user=None):
        """La empresa que sugerir al redirigir a estos registros —
        ``:5825-5839``.

        La fuente lo declara en ``BaseModel`` y lo usa
        ``ir.rule._make_access_error`` para distinguir *"no tienes permiso"* de
        *"tienes permiso pero con otra empresa activa"*, que es la diferencia
        entre un 403 opaco y uno accionable. Su cuerpo es un ``if`` de tres
        ramas sobre qué campo declara el modelo:

        .. code-block:: python

           if 'company_id' in self:
               return self.company_id
           elif 'company_ids' in self:
               return (self.company_ids & self.env.user.company_ids)[:1]
           return False

        Aquí vive en el queryset, que es lo que en este árbol hace de
        recordset. La fuente devuelve un recordset —vacío, de uno, o la unión
        de las empresas de varias filas— y aquí una **lista**: ``company_ids``
        es un M2M inverso y su intersección con las del usuario no es un
        queryset de la misma tabla.

        ``'company_id' in self`` pregunta por el **campo**, no por el valor.
        Aquí se pregunta por los dos nombres —``company`` y su ``attname``
        ``company_id``— porque este árbol declara la FK con el nombre corto
        (:ref:`h-api-874` midió la misma distinción en
        ``_add_missing_default_values``).
        """
        nombres = {f.name for f in self.model._meta.get_fields()}
        nombres |= {f.attname for f in self.model._meta.fields}
        if 'company_id' in nombres:
            field_name = 'company' if 'company' in nombres else 'company_id'
            companies = []
            for record in self:
                company = getattr(record, field_name, None)
                if company is not None and company not in companies:
                    companies.append(company)
            return companies
        if 'company_ids' in nombres:
            actor = _acting_user(user)
            if actor is None:
                return []
            suyas = set(actor.company_ids.values_list('pk', flat=True))
            for record in self:
                for company in record.company_ids.all():
                    if company.pk in suyas:
                        return [company]
            return []
        return []

    def filtered_domain(self, domain):
        """Las filas de ``self`` que cumplen el dominio, en el mismo orden.

        ≙ ``BaseModel.filtered_domain``
        (``odoo19c: odoo/orm/models.py:6252-6260``). Evalúa **en memoria**: no
        emite ``WHERE``, recorre los registros que ya están en mano. Es la
        contraparte de ``filter()``, que compila el dominio a ``Q`` y deja que
        lo resuelva PostgreSQL.

        Devuelve una **lista**, no un ``QuerySet``: filtrar en Python rompe la
        pereza por construcción, y devolver algo que parece un ``QuerySet``
        invitaría a encadenarle un ``.filter()`` que volvería al motor con el
        conjunto entero. La fuente devuelve un recordset porque allá el
        recordset ya es una lista de ids en memoria.
        """
        return filtered_domain(self, domain)

    def _get_external_ids(self):
        """Los identificadores externos de cada fila —
        ``{pk: ['modulo.nombre']}``.

        ≙ ``BaseModel._get_external_ids``
        (``odoo19c: odoo/orm/models.py:5695-5714``). Lista vacía cuando la fila
        no tiene ninguno, y **todos** los que tenga cuando tiene varios: la
        fuente los acumula en un ``defaultdict(list)`` y ordena por ``id`` de
        ``ir.model.data``, que es lo que fija cuál queda primero.

        **La divergencia es de VÍA, no de alcance**, y es la de la sección de
        permisos de este archivo: allá cuelga de ``BaseModel``, así que todo
        modelo lo tiene; aquí el **recordset** es el ``QuerySet``, y su hogar
        es esta clase, que ya aloja las cuatro formas de permiso y
        ``filtered_domain``.

        Dos precisiones de forma, ambas medidas:

        - La fuente indexa el resultado por ``record._origin.id`` porque un
          recordset puede contener registros **sin fila** (los del formulario).
          Un ``QuerySet`` no: sólo entrega filas guardadas, así que
          ``record._origin.pk == record.pk`` para todo lo que devuelve. Se
          indexa por ``pk``.
        - La columna ``model`` de ``ir.model.data`` guarda aquí la **etiqueta
          de Django** (``base.ResGroups``), no el nombre con puntos: es lo que
          escribe ``IrModelData._update_xmlids``, que es el único escritor.
        """
        Data = apps.get_model('base', 'IrModelData')
        records = list(self)
        result = collections.defaultdict(list)
        rows = Data.objects.filter(
            model=self.model._meta.label,
            res_id__in=[record.pk for record in records],
        ).order_by('pk').values_list('module', 'name', 'res_id')
        for module, name, res_id in rows:
            result[res_id].append('%s.%s' % (module, name))
        return {record.pk: result[record.pk] for record in records}

    def get_external_id(self):
        """Un identificador externo por fila — ``{pk: 'modulo.nombre'}``.

        ≙ ``BaseModel.get_external_id``
        (``odoo19c: odoo/orm/models.py:5716-5735``). Cuando una fila tiene
        varios devuelve **uno** de ellos, y cuando no tiene ninguno devuelve
        la **cadena vacía** —no ``None``—: la fuente lo dice explícitamente,
        *"to be usable as a function field"*, y quien la consume distingue el
        caso comparando contra un falsy, no contra un centinela.
        """
        results = self._get_external_ids()
        return {key: val[0] if val else ''
                for key, val in results.items()}


#: Manager que expone las cuatro formas. Un modelo las adopta con
#: ``objects = AccessManager()``; ``RuleScopedManager`` hereda de él, así que
#: los modelos que ya declaran ``scoped`` las tienen sin cambiar nada.
AccessManager = Manager.from_queryset(AccessQuerySet)


def filtered_domain(records, domain):
    """Los registros que cumplen el dominio, en el mismo orden.

    ≙ ``BaseModel.filtered_domain``
    (``odoo19c: odoo/orm/models.py:6252-6260``), como **función de módulo**
    además de método de ``AccessQuerySet``.

    **Por qué las dos superficies y no sólo el método.** Allá ``self`` es un
    recordset y un registro suelto ya es un recordset de uno, así que un solo
    método cubre los dos casos. Aquí no: un registro **sin guardar**
    —``Model(**valores)``, que es lo que ``model.new()`` construye allá— no es
    un ``QuerySet`` y no lo puede ser. Y ese caso no es marginal: es
    exactamente el de ``ir.default._evaluate_condition_with_fallback``, que
    pregunta si el valor de respaldo de un campo dependiente de empresa cumple
    una condición. Ese valor **no está en ninguna fila**, así que no hay
    ``QuerySet`` del que partir.

    La función es el mecanismo; el método de ``AccessQuerySet`` delega en ella.

    :param records: iterable de instancias del **mismo** modelo.
    :param domain: un dominio (``Domain`` o su forma de lista).
    """
    records = list(records)
    if not records or not domain:
        return records
    model = type(records[0])
    predicate = Domain(domain)._as_predicate(model)
    return [record for record in records if predicate(record)]


class OriginMixin:
    """``_origin`` — el registro **guardado** del que este proviene.

    ≙ ``BaseModel._origin`` (``odoo19c: odoo/orm/models.py:6462-6469``). Allá
    un registro en formulario lleva un ``NewId`` cuyo ``.origin`` apunta a la
    fila persistida; sobre registros ya reales el atributo devuelve ``self``
    ("already real records"). Es lo que permite a un ``@api.onchange`` comparar
    el valor que el usuario acaba de teclear con el que hay en base.

    **La divergencia, y es de forma** —la misma que declara la sección de
    permisos de este archivo—: allá ``self`` es un recordset y el atributo
    cuelga de ``BaseModel``, así que todo modelo lo tiene. Aquí
    ``models.Model`` es el de Django y no es nuestro para colgarle nada, así
    que el mecanismo es un mixin que el modelo adopta —igual que
    ``objects = AccessManager()``— y el eje que distingue "en formulario" de
    "guardado" no es el tipo del id sino el estado de la instancia: los
    atributos en memoria frente a la fila.

    Quién lo adopta, medido 2026-08-28: ``ResPartner`` —el consumidor que
    registró la tarea #112, y que hasta entonces hacía la lectura a mano— y
    ``DecimalPrecision``. Quedan **ocho** sitios más con la misma lectura
    escrita a mano; decidir uno a uno cuál de ellos ES ``_origin`` y cuál es
    otra cosa es la tarea **#136**.
    """

    @property
    def _origin(self):
        """El registro tal como está en base, o ``self`` si no hay fila.

        Sin ``pk`` no hay origen que traer —es el caso "already real records"
        invertido: la fuente devuelve ``self`` cuando no hay nada que resolver,
        y aquí tampoco lo hay—. Con ``pk``, la lectura va a la base y **no** se
        memoriza: el sentido del atributo es justamente ver lo guardado, no lo
        que esta instancia recuerda.
        """
        if self.pk is None:
            return self
        return type(self)._base_manager.using(self._state.db).get(pk=self.pk)


class DefaultGetMixin:
    """``default_get`` — los valores por defecto de un alta.

    ≙ ``BaseModel.default_get`` (``odoo19c: odoo/orm/models.py:1271-1338``).
    Responde, para los campos que se le piden, el valor con que un alta
    debería empezar. Su consumidor natural es el formulario, y aquí el
    serializer o el comando que crea el registro.

    **La divergencia de forma es la de siempre en este archivo** (ver la
    sección de permisos y ``OriginMixin``): allá cuelga de ``BaseModel`` y
    todo modelo lo tiene; aquí ``models.Model`` es el de Django y no es
    nuestro, así que es un mixin que el modelo adopta.

    Por qué hacía falta la base, habiendo ya overrides
    ==================================================

    ``IrCron`` e ``IrSequenceDateRange`` ya declaraban su ``default_get``, y
    los dos **no podían llamar a ``super()``** porque no había base a la que
    llamar. Allá los dos empiezan por ``super().default_get(fields)`` y
    encima ponen lo suyo: sin la base, cada override era la respuesta
    completa, y los cuatro primeros orígenes de valor —contexto,
    ``ir.default``, el ``default`` del campo, el respaldo por empresa— no los
    veía nadie.
    """

    #: Los cinco orígenes, en el orden de la fuente, más el paso de
    #: normalización y la delegación al padre. El orden **es** el contrato:
    #: el contexto gana sobre ``ir.default``, y el ``default`` del campo gana
    #: sobre el respaldo por empresa pero no sobre el default de usuario.
    #: Reordenarlos cambia qué valor ve el alta.
    @classmethod
    def default_get(cls, fields):
        """Los valores por defecto de los campos pedidos.

        :param fields: nombres de los campos cuyo default se quiere.
        :returns: dict ``campo -> valor``, sólo con los que tengan uno.

        Un campo que no esté en ``fields`` no se considera — la nota de la
        fuente, verbatim: *"Unrequested defaults won't be considered"*.
        """
        IrDefault = apps.get_model('base', 'IrDefault')
        defaults = {}
        parent_fields = collections.defaultdict(list)
        context = get_context()
        ir_defaults = IrDefault._get_model_defaults(
            cls._meta.label, company_id=get_current_company())

        for name in fields:
            # 1. el contexto manda sobre todo lo demás
            key = 'default_' + name
            if key in context:
                defaults[name] = context[key]
                continue

            try:
                field = cls._meta.get_field(name)
            except FieldDoesNotExist:
                continue

            company_dependent = getattr(field, 'company_dependent', False)

            # 2. el default de usuario/empresa, para el campo normal
            if not company_dependent and name in ir_defaults:
                defaults[name] = ir_defaults[name]
                continue

            # 3. el ``default`` declarado en el campo
            #
            # Allá ``field.default`` es un invocable que recibe el recordset;
            # aquí Django distingue tener default de calcularlo, y su
            # ``get_default()`` ya resuelve el invocable. ``has_default()`` es
            # el discriminador correcto: un ``default=False`` o ``default=0``
            # es un default declarado, y un ``if field.default:`` lo perdería.
            if field.has_default() and not _is_plumbing_default(field):
                defaults[name] = field.get_default()
                continue

            # 4. el respaldo, para el campo dependiente de empresa
            if company_dependent and name in ir_defaults:
                defaults[name] = ir_defaults[name]
                continue

            # 5. delegar en el modelo padre, para el campo heredado
            delegated = _delegated_origin(cls, name)
            if delegated is not None:
                parent_model, parent_name = delegated
                parent_fields[parent_model].append(parent_name)

        # 6. normalizar el valor pasandolo por el campo
        #
        # La fuente lo hace para TODO campo: ``convert_to_cache`` y luego
        # ``convert_to_write``, con el comentario de que el paso existe para
        # que un x2many salga como ``[(SET, 0, [2, 3])]`` y no como una lista
        # de ``LINK``. Aqui el par de conversion lo declaran los campos que lo
        # necesitan —``Properties`` y ``PropertiesDefinition``
        # (``orm/fields_properties.py``)—. El motivo x2many de la fuente sigue
        # sin portarse: ``Command`` ya devuelve triples, pero un default de
        # x2many no se normaliza aquí a ``[(SET, 0, ids)]`` (TASK-API-0190,
        # :ref:`h-api-589`).
        instance = cls()
        for name, value in list(defaults.items()):
            try:
                field = cls._meta.get_field(name)
            except FieldDoesNotExist:
                continue
            if not (hasattr(field, 'convert_to_cache')
                    and hasattr(field, 'convert_to_write')):
                continue
            cached = field.convert_to_cache(value, instance, validate=False)
            defaults[name] = field.convert_to_write(cached, instance)

        # 7. los defaults del padre, por el mismo camino
        for parent_model, names in parent_fields.items():
            if hasattr(parent_model, 'default_get'):
                defaults.update(parent_model.default_get(names))

        return defaults

    @classmethod
    def _add_missing_default_values(cls, values):
        """Completa ``values`` con el default de los campos que no trae.

        ≙ ``_add_missing_default_values``
        (``odoo19c: odoo/orm/models.py:1546-1596``). Es el consumidor real de
        :meth:`default_get`: sin él, ``default_get`` responde bien y nadie le
        pregunta — que es exactamente el estado en que estaba el árbol antes
        de la tarea **#113**.

        Los valores dados **siempre** ganan al default; el comentario de la
        fuente lo dice verbatim: *"override defaults with the provided
        values, never allow the other way around"*.

        :param values: el dict del alta, tal como llega.
        :returns: un dict nuevo con los defaults que faltaban ya puestos.
        """
        avoid_models = set()

        def collect_models_to_avoid(model):
            """No pisar el valor heredado cuando el padre ya viene puesto.

            El conjunto guarda **la clase**, no el nombre punteado que la
            fuente usa como llave de ``_inherits``: aquí quien responde
            :func:`_delegated_origin` es la clase, y comparar la llave contra
            ``_meta.label`` no casa nunca — ``'res.partner'`` frente a
            ``'base.ResPartner'``. Medido: el filtro no excluía nada.

            Y el FK se busca por sus **dos** nombres. ``ResUsers`` declara
            ``partner = fields.Many2one(...)``, así que ``_inherits`` dice
            ``'partner'`` y Django le pone ``attname='partner_id'``; un alta
            puede traer cualquiera de los dos y las dos formas nombran al
            mismo padre.
            """
            inherits = getattr(model, '_inherits', {})
            for _parent_name, fk_name in inherits.items():
                parent = _inherits_parent(model, fk_name)
                if parent is None:
                    continue
                try:
                    fk_field = model._meta.get_field(fk_name)
                except FieldDoesNotExist:
                    continue
                if fk_field.name in values or fk_field.attname in values:
                    avoid_models.add(parent)
                else:
                    collect_models_to_avoid(parent)

        collect_models_to_avoid(cls)

        def avoid(name):
            """¿El campo llega heredado de un padre que ya viene puesto?"""
            if not avoid_models:
                return False
            delegated = _delegated_origin(cls, name)
            if delegated is None:
                return False
            parent_model, _ = delegated
            return parent_model in avoid_models

        missing_defaults = [
            name
            for name in _field_names(cls)
            if name not in values
            if not avoid(name)
        ]

        if missing_defaults:
            defaults = cls.default_get(missing_defaults)
            defaults.update(values)
        else:
            defaults = dict(values)

        # Delegar el default de las propiedades en el propio campo.
        for field in cls._meta.get_fields():
            if hasattr(field, '_add_default_values'):
                defaults[field.name] = field._add_default_values(
                    defaults, model=cls)

        return defaults

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """Alta de registros — ≙ ``BaseModel.create`` por CONTENIDO.

        ≙ ``odoo19c: odoo/orm/models.py:4611-4770``. Recibe una **lista de
        dicts** y devuelve el conjunto de filas creadas, en el orden pedido;
        ``@api.model_create_multi`` convierte un dict suelto en ``[vals]``,
        como el decorador de la fuente (``decorators.py:357-371``).

        Hasta :ref:`h-api-1108` este método recibía ``**values`` y devolvía
        una instancia, y su docstring lo presentaba como *"se porta el paso,
        no la firma"*. La firma **es** parte del contrato: los overrides de la
        referencia llaman ``super().create(vals_list)`` con una lista y los
        llamadores desempaquetan el recordset. Con la firma cambiada ningún
        porte de un ``create`` de addon podía ser fiel.

        Los pasos, en el orden de la fuente y con su receptor aquí:

        1. ``assert`` lista/tupla; vacía → ``browse()`` vacío.
        2. ``check_access('create')`` sobre el recordset vacío —
           ``AccessQuerySet(model=cls).none()``, el mismo receptor que
           ``_check_access`` usa en ``:1903``.
        3. Los nombres de campo dados más los ``default_*`` del contexto que
           el modelo declare; un nombre que el modelo no tiene levanta
           ``ValueError("Invalid field %r in %r")``; cada uno pasa por
           ``_check_field_access(field, 'write')`` (``FieldSqlMixin``).
        4. :meth:`_prepare_create_values` — defaults, campos mágicos fuera.
        5. Clasificación por registro en ``stored`` / ``inherited`` /
           ``inversed`` / ``protected``.
        6. Padres de ``_inherits``: ``write`` sobre el padre dado, o
           ``create`` en lote de los que faltan, cuyo id cae en ``stored``.
        7. Inserción de las filas y ``modified(..., create=True)`` bajo
           ``env.protecting``.
        8. Los inversos, un grupo por método; luego ``_validate_fields``
           sobre lo invertido, excluyendo lo almacenado.
        9. ``_check_company`` si ``_check_company_auto``.
        10. La rama de importación: ``ir.model.data._update_xmlids`` cuando el
            contexto trae ``_import_current_module``.

        **Divergencias de mecanismo, declaradas** (cada una con su razón):

        - **La fila se inserta una a una por :meth:`_create_row_from_values`
          y no por un ``INSERT`` por lote de ``INSERT_BATCH_SIZE``**
          (``_create``, ``:4849-4897``). Medido antes de decidirlo
          (``probe_bulk_create_returns_ids_and_adopter_mro.py``):
          ``bulk_create`` devuelve los ids en PostgreSQL pero **salta
          ``save()``**, y los adopters lo sobreescriben —``ir_cron.py:1373``,
          ``res_partner.py:1594``, ``ir_sequence.py:282``,
          ``hr_employee.py:1554``— para hacer lo que la fuente hace en su
          propio ``create``/``write``. Un lote que los esquive crea filas
          sin ese trabajo. El precómputo (``_add_precomputed_values``) y
          ``parent_path`` viven en ``pre_save``/``save()`` de este árbol, así
          que corren por fila al insertar — es donde la fuente los hace en
          bloque (``:4808`` y ``_parent_store_create``, ``:4916``).
        - **Un muchos-a-muchos se asigna después del alta**: Django exige la
          fila antes de poblar la tabla intermedia. La fuente lo resuelve en
          ``other_fields`` de ``_create`` (``:4924-4931``), también después
          del ``INSERT``; el sitio es el mismo, el instrumento es
          ``manager.set``.
        - **El check de ``bypass_search_access`` del ``many2one``**
          (``:4686-4687``) no viaja: ningún campo de este árbol declara ese
          atributo (``grep -rn bypass_search_access src addons`` → 0), y el
          registro por nombre lo resolvería ``check_access('read')`` del
          comodelo. Se declara, no se omite: tarea sucesora en el hallazgo.
        - **``invalidate_recordset`` sobre los x2many no almacenados tras el
          inverso** (``:4737-4738``): aquí un x2many sin columna no tiene
          caché que invalidar — un campo sin columna recalcula al leer
          (:ref:`h-api-1106`).
        - **Las columnas de autoría** (``create_uid``/``write_uid``) no
          existen: ``LOG_ACCESS_COLUMNS`` de este árbol son las dos fechas de
          ``TimeStampedModel``, ``auto_now``.

        **INVENTORY:** ``cpython`` — ``collections.defaultdict``,
        ``contextlib.ExitStack`` (trae hecho); ``django`` — ``Model.__init__``
        + ``objects.create`` como INSERT ... RETURNING, ``Case/When`` para el
        orden en :func:`orm.utils.browse` (trae hecho); ``postgresql`` —
        ``RETURNING "id"`` es lo que ``objects.create`` emite (trae hecho);
        la clasificación, el lote de padres y el despacho de inversos se
        construyen aquí con esas primitivas (tiene con qué construirlo).

        :param vals_list: valores por registro, ``[{'campo': valor, ...}]``.
        :returns: las filas creadas, en el orden de ``vals_list``.
        """
        assert isinstance(vals_list, (list, tuple))
        if not vals_list:
            return cls._create_result(browse(cls))

        AccessQuerySet(model=cls).none().check_access('create')

        # Un ``fields.One2many`` declarado no es un campo de Django ni entra en
        # el registro: se aparta aquí y se aplica con la fila ya creada, como
        # ``One2many.write_real(..., create=True)``.
        declared_one2many = [
            {name: vals[name] for name in vals
             if isinstance(getattr(cls, name, None), DeclaredOne2many)}
            for vals in vals_list
        ]
        if any(declared_one2many):
            vals_list = [
                {name: value for name, value in vals.items()
                 if name not in apart}
                for vals, apart in zip(vals_list, declared_one2many)
            ]

        # check access to all user-provided fields
        context = get_context()
        field_names = OrderedSet(fname for vals in vals_list for fname in vals)
        field_names.update(
            field_name
            for context_key in context
            if context_key.startswith('default_')
            and (field_name := context_key[8:])
            and _create_field_lookup(cls, field_name) is not None
        )
        receiver = cls()
        for field_name in field_names:
            found = _create_field_lookup(cls, field_name)
            if found is None:
                raise ValueError(
                    f"Invalid field {field_name!r} in {cls._name!r}")
            receiver._check_field_access(found[0], 'write')

        new_vals_list = cls._prepare_create_values(vals_list)

        # classify fields for each record
        data_list = []
        # {inverse: fields}
        determine_inverses = collections.defaultdict(OrderedSet)

        for vals in new_vals_list:
            data = {}
            data['stored'] = stored = {}
            data['inversed'] = inversed = {}
            data['inherited'] = inherited = collections.defaultdict(dict)
            data['protected'] = protected = set()
            for key, val in vals.items():
                found = _create_field_lookup(cls, key)
                if found is None:
                    raise ValueError(
                        "Invalid field %r on model %r" % (key, cls._name))
                field, origin = found
                if origin is not None:
                    inherited[origin][key] = val
                    continue
                (store, inverse, compute, readonly,
                 precompute) = _creation_flags(field)
                if store:
                    stored[key] = val
                if inverse:
                    inversed[key] = val
                    determine_inverses[inverse].add(field)
                # protect editable computed fields and precomputed fields
                # against (re)computation
                if compute and (not readonly or precompute):
                    protected.add(field)
            data_list.append(data)

        # create or update parent records
        for _parent_name, fk_name in getattr(cls, '_inherits', {}).items():
            parent_model = _inherits_parent(cls, fk_name)
            fk_field = cls._meta.get_field(fk_name)
            parent_data_list = []
            for data in data_list:
                given = (data['stored'].get(fk_field.name)
                         or data['stored'].get(fk_field.attname))
                if not given:
                    parent_data_list.append(data)
                elif data['inherited'][parent_model]:
                    parent = (given if isinstance(given, parent_model)
                              else parent_model.objects.get(pk=given))
                    parent.write(data['inherited'][parent_model])

            if parent_data_list:
                parents = parent_model.create([
                    data['inherited'][parent_model]
                    for data in parent_data_list
                ])
                for parent, data in zip(parents, parent_data_list):
                    data['stored'].pop(fk_field.attname, None)
                    data['stored'][fk_field.name] = parent

        # create records with stored fields
        records = cls._create(data_list)
        for record, apart in zip(records, declared_one2many):
            for name, value in apart.items():
                field = getattr(cls, name)
                if field.compute:
                    # Un One2many calculado: su escritura la propaga
                    # ``inverse``, no un Many2one inverso.
                    field.__set__(record, value)
                elif is_command_list(value):
                    _, inverse = field._inverse_field()
                    apply_one2many_commands(record, inverse.remote_field,
                                            value, create=True)
                else:
                    field.__set__(record, value)

        # protect fields being written against recomputation
        with contextlib.ExitStack() as stack:
            for data in data_list:
                stack.enter_context(
                    env().protecting(data['protected'], data['record']))
            # call inverse method for each group of fields
            for fields in determine_inverses.values():
                # determine which records to inverse for those fields
                inv_names = {field.name for field in fields}
                inv_rec_ids = []
                for data in data_list:
                    if inv_names.isdisjoint(data['inversed']):
                        continue
                    record = data['record']
                    for fname, value in data['inversed'].items():
                        if fname in inv_names and fname not in data['stored']:
                            setattr(record, fname, value)
                    inv_rec_ids.append(record.pk)

                # Un modelo que deriva de ``BaseModel`` recibe el recordset de
                # la fuente (``self.browse(inv_rec_ids)``, ``:4732``); uno
                # de Django, el ``QuerySet`` de :func:`~orm.utils.browse`. Es
                # la misma distinción que ``_invoke_compute_method`` hace al
                # computar.
                if hasattr(cls, '_from_ids'):
                    ids = tuple(inv_rec_ids)
                    inv_records = cls._from_ids(env(), ids, ids)
                else:
                    inv_records = browse(cls, inv_rec_ids)
                determine_inverse(next(iter(fields)), inv_records)

        # check Python constraints for non-stored inversed fields
        for data in data_list:
            data['record']._validate_fields(data['inversed'], data['stored'])

        if cls._check_company_auto:
            for record in records:
                record._check_company()

        import_module = context.get('_import_current_module')
        if not import_module:   # not an import -> bail
            return cls._create_result(records)

        # It is to support setting xids directly in create by
        # providing an "id" key (otherwise stripped by create) during an import
        # (which should strip 'id' from the input data anyway)
        noupdate = context.get('noupdate', False)

        xids = (v.get('id') for v in vals_list)
        IrModelData = apps.get_model('base', 'IrModelData')
        IrModelData._update_xmlids([
            {
                'xml_id': (xid if '.' in xid
                           else '%s.%s' % (import_module, xid)),
                'record': rec,
                # note: this is not used when updating o2ms above...
                'noupdate': noupdate,
            }
            for rec, xid in zip(records, xids)
            if xid and isinstance(xid, str)
        ])

        return cls._create_result(records)

    @classmethod
    def _create_result(cls, records):
        """El recordset que entrega ``create`` — ≙ el ``records`` de ``:4770``.

        En la fuente ``create`` devuelve un recordset de ``BaseModel``: sobre
        él ``record.name = x`` escribe y un nombre no declarado levanta
        ``AttributeError``. Un modelo que deriva de :class:`BaseModel` recibe
        aquí esa misma forma, ``cls._from_ids(env, ids, ids)`` (la de
        ``browse``, ``:5897``), con el orden de ``vals_list``.

        El resto del árbol sigue recibiendo el ``QuerySet`` de
        :func:`~orm.utils.browse`: sus consumidores lo usan como tal, y
        cambiarlo es la adopción global de ``BaseModel`` (TASK-API-0397).
        Sobre ese ``QuerySet`` una asignación de campo se pierde sin error
        (H-API-1123).
        """
        if not issubclass(cls, BaseModel):
            return records
        ids = tuple(records.values_list('pk', flat=True))
        return cls._from_ids(env(), ids, ids)

    @classmethod
    def _prepare_create_values(cls, vals_list):
        """Completa y limpia los valores de alta — ≙
        ``_prepare_create_values``.

        ≙ ``odoo19c: odoo/orm/models.py:4771-4812``. Docstring de la fuente,
        verbatim: *"Clean up and complete the given create values, and return
        a list of new vals containing: default values, discarded forbidden
        values (magic fields), precomputed fields."*

        Los ``bad_names`` son los de la fuente —``id``, ``parent_path``, las
        columnas de acceso y los ``precompute`` de sólo lectura— y se sacan
        **después** de aplicar los defaults, como allá (``:4796-4800``). El
        ``setdefault`` de ``create_uid``/``create_date``/… (``:4801-4805``)
        no tiene columna aquí: las dos fechas de ``TimeStampedModel`` son
        ``auto_now`` y las escribe ``save()``.

        ``_add_precomputed_values(result_vals_list)`` (``:4808``) no se llama
        desde aquí: en este árbol el precómputo corre en ``pre_save`` sobre la
        instancia (``_run_precompute``), que es el único sitio desde el que
        puede asignar al descriptor de la fila. Sacar el ``precompute``
        ``readonly`` de ``vals`` es lo que lo obliga a computarse
        (:func:`_precomputable_fields`).
        """
        bad_names = ['id', 'parent_path']
        if getattr(cls, '_log_access', True):
            bad_names.extend(LOG_ACCESS_COLUMNS)

        # also discard precomputed readonly fields (to force their computation)
        bad_names.extend(
            fname
            for fname, field in model_field_registry(cls).items()
            if isinstance(field, Field) and field.precompute and field.readonly
        )

        result_vals_list = []
        for vals in vals_list:
            # add default values
            vals = cls._add_missing_default_values(vals)

            # add magic fields
            for fname in bad_names:
                vals.pop(fname, None)

            result_vals_list.append(vals)

        return result_vals_list

    @classmethod
    def _create(cls, data_list):
        """Inserta las filas de ``data_list`` — ≙ ``_create`` (``:4849-4935``).

        Docstring de la fuente, verbatim: *"Create records from the stored
        field values in ``data_list``."* Cada ``data`` sale con su
        ``'record'`` puesto, que es lo que :meth:`create` lee después
        (``data['record'] = record``, ``:4901``).

        La fila la produce :meth:`_create_row_from_values` tras
        :meth:`_load_records_coerce_vals` y el aparte de lo relacional, por
        la razón medida en el docstring de :meth:`create`: un ``INSERT`` por
        lote saltaría el ``save()`` que los adopters sobreescriben. El
        muchos-a-muchos llano —una lista de ids, no un ``Command``— se aplica
        con la fila ya real, que es el momento en que la fuente atiende sus
        ``other_fields`` (``:4924-4931``).

        ``records.modified(self._fields, create=True)`` (``:4921``) se conserva
        bajo ``env.protecting``, con los mismos campos protegidos por fila.
        """
        assert data_list
        ids = []
        for data in data_list:
            split = cls._load_records_split_relational
            scalar, relational = split(data['stored'])
            # Lo que exige la fila ya real: el muchos-a-muchos por su cara
            # directa y toda relación inversa (el ``One2many``/``Many2many``
            # reverso de la fuente) — ≙ ``other_fields`` de ``_create``.
            deferred = {}
            registry = model_field_registry(cls)
            for name in list(scalar):
                field = registry.get(name)
                if field is None:
                    continue
                if field.many_to_many or not isinstance(field, Field):
                    deferred[name] = scalar.pop(name)
            record = cls._create_row_from_values(
                cls._load_records_coerce_vals(scalar))
            if relational:
                record._load_records_apply_relational(relational)
            for name, value in deferred.items():
                field = registry.get(name)
                if getattr(field, 'many_to_many', False):
                    # ≙ ``Many2many.write_real``: los triples de ``Command``
                    # y sus abreviaturas (TASK-API-0190).
                    apply_many2many_commands(record, field, value)
                elif (getattr(field, 'one_to_many', False)
                      and is_command_list(value)):
                    # ≙ ``One2many.write_real(..., create=True)``.
                    apply_one2many_commands(record, field, value, create=True)
                else:
                    related_manager(record, name).set(value)
            data['record'] = record
            ids.append(record.pk)

        records = browse(cls, ids)
        if _maintains_parent_store(cls):
            _parent_store_create(cls, ids)

        # protect fields being written against recomputation
        with contextlib.ExitStack() as stack:
            for data in data_list:
                stack.enter_context(
                    env().protecting(data['protected'], data['record']))
            # mark computed fields as todo
            modified(records, list(model_field_registry(cls)), create=True)

        return records


def _maintains_parent_store(cls):
    """Si el ORM mantiene ``parent_path`` del modelo.

    Sólo un ``BaseModel``: los modelos productivos con ``_parent_store``
    (``res.company``, ``res.partner``, ``hr.department``…) calculan su
    ``parent_path`` en su propio ``save()``, y mantenerlo aquí también sería
    escribirlo dos veces.
    """
    return (getattr(cls, '_parent_store', False)
            and isinstance(cls, type) and issubclass(cls, BaseModel))


def _parent_column(cls):
    return cls._meta.get_field(parent_name_of(cls)).column


def _parent_store_create(cls, ids):
    """≙ ``_parent_store_create`` (``odoo19c: odoo/orm/models.py:4961-4983``).

    Docstring de la fuente, verbatim: *"Set the parent_path field on ``self``
    after its creation."* Un ``UPDATE`` que concatena la ruta del padre y el id
    propio, con el mismo SQL salvo ``IN %s`` → ``= ANY(%s)``: psycopg 3 adapta
    una lista a un arreglo y no expande una tupla.
    """
    if not ids:
        return
    execute_query(SQL(
        """ UPDATE %(table)s node
            SET parent_path=concat((
                    SELECT parent.parent_path
                    FROM %(table)s parent
                    WHERE parent.id=node.%(parent)s
                ), node.id, '/')
            WHERE node.id = ANY(%(ids)s)
            RETURNING node.id, node.parent_path """,
        table=SQL.identifier(cls._meta.db_table),
        parent=SQL.identifier(_parent_column(cls)),
        ids=list(ids),
    ))


def _reparented(record, values):
    """≙ ``_parent_store_update_prepare`` (``:4985-5018``) para una fila: si
    ``values`` cambia su padre. Se mide antes de escribir."""
    cls = type(record)
    if not _maintains_parent_store(cls):
        return False
    name = parent_name_of(cls)
    if name not in values:
        return False
    # Sólo un ``BaseModel`` llega aquí: la decisión es la de su método.
    new = getattr(values[name], 'pk', values[name]) or False
    return bool(record._parent_store_update_prepare([{name: new}]))


def _parent_store_update(record):
    """≙ ``_parent_store_update`` (``:5020-5054``) para una fila.

    Un ``BaseModel`` delega en :meth:`BaseModel._parent_store_update`, el
    porte del método de la fuente. El cuerpo por fila de abajo queda para un
    modelo de Django sin recordset que mantiene su ``parent_path`` en
    ``save()`` (``ir.ui.menu``): reescribe el prefijo de la fila y de sus
    descendientes con el mismo ``UPDATE``, tras rechazar una recursión.
    """
    if isinstance(record, BaseModel):
        record._parent_store_update()
        return
    cls = type(record)
    table = cls._meta.db_table
    parent_id = cls._base_manager.filter(pk=record.pk).values_list(
        _parent_column(cls), flat=True).first()
    prefix = ''
    if parent_id:
        prefix = cls._base_manager.filter(pk=parent_id).values_list(
            'parent_path', flat=True).first() or ''
    ancestors = {int(label) for label in prefix.split('/')[:-1]}
    if prefix and record.pk in ancestors:
        raise UserError('Recursion Detected.')
    updated = dict(execute_query(SQL(
        """ UPDATE %(table)s child
            SET parent_path = concat(%(prefix)s, substr(child.parent_path,
                    length(node.parent_path) - length(node.id || '/') + 1))
            FROM %(table)s node
            WHERE node.id = ANY(%(ids)s)
            AND child.parent_path LIKE concat(node.parent_path, %(wildcard)s)
            RETURNING child.id, child.parent_path """,
        table=SQL.identifier(table),
        prefix=prefix,
        ids=[record.pk],
        wildcard='%',
    )))
    if record.pk in updated:
        record.__dict__['parent_path'] = updated[record.pk]


def _creation_flags(field):
    """``(store, inverse, compute, readonly, precompute)`` de un campo al
    crear.

    Los cinco atributos que :meth:`DefaultGetMixin.create` lee de cada campo
    (``:4675-4684``). Un ``Field`` de Django los declara —``fields.py``
    instala los defaults de la referencia sobre ``models.Field``—; una
    **relación inversa** (``ManyToOneRel`` / ``ManyToManyRel``, el
    ``One2many`` de la fuente visto desde el hijo) no es un ``Field`` y no
    los tiene. Para ella valen los de un ``One2many`` de la referencia sin
    ``compute``: se almacena —su valor se aplica con la fila ya real, como
    ``other_fields`` en ``_create`` (``:4924``)— y no invierte ni protege.
    """
    if isinstance(field, Field):
        return (field.store, field.inverse, field.compute, field.readonly,
                field.precompute)
    return True, None, None, False, False


def _create_field_lookup(model, name):
    """El campo que ``name`` nombra en un alta, y de qué padre viene.

    Devuelve ``(campo, None)`` para un campo propio —por ``name`` o por el
    ``attname`` de un ``ForeignKey``, que es la segunda cara que Django le
    da—, ``(campo, modelo padre)`` para uno heredado por ``_inherits``, y
    ``None`` si el modelo no lo declara.

    ≙ ``self._fields.get(name)`` más ``field.inherited`` /
    ``field.related_field.model_name`` (``:4653``, ``:4675-4677``). Allá el
    campo heredado es un campo espejo del hijo que sabe de dónde viene; aquí
    ``_fields`` también lo publica (``_add_inherited_fields``), con
    ``inherited`` puesto, y su origen lo responde :func:`_delegated_origin`
    sobre el mapa de delegación: el campo que se devuelve es el del padre.
    """
    fields = model_field_registry(model)
    if name in fields and not getattr(fields[name], 'inherited', False):
        return fields[name], None
    for field in model._meta.concrete_fields:
        if field.attname == name:
            return field, None
    delegated = _delegated_origin(model, name)
    if delegated is None:
        return None
    parent_model, field_name = delegated
    return model_field_registry(parent_model)[field_name], parent_model


#: ≙ ``LOG_ACCESS_COLUMNS`` (``odoo19c: odoo/orm/models.py:296``). Allá son
#: ``create_uid``, ``create_date``, ``write_uid`` y ``write_date``; aquí el
#: mecanismo es ``TimeStampedModel``, que declara dos —``created_at`` y
#: ``updated_at``, ambas ``auto_now``— y ninguna de autoría. La divergencia es
#: del mixin, no de este archivo: quién escribió la fila no se guarda.
#: La lista se declara en ``orm.model_classes`` —que la necesita al construir
#: la clase y no puede importar este modulo— y llega aqui por el import de
#: arriba, con el nombre de la fuente.

#: ≙ ``MAGIC_COLUMNS`` (``odoo19c: odoo/orm/models.py:297``).
MAGIC_COLUMNS = ['id'] + LOG_ACCESS_COLUMNS

#: ≙ ``regex_order`` (``odoo19c: odoo/orm/models.py:93-104``), verbatim.
#: Acota la cláusula ``_order`` entera: una lista de campos separados por coma,
#: cada uno con su dirección y su tratamiento de nulos opcionales. Es lo que
#: :meth:`BaseModel._check_qorder` mide antes de dejar pasar un orden.
regex_order = re.compile(r"""
    ^
    (\s*
        (?P<term>((?P<field>[a-z0-9_]+)(\.(?P<property>[a-z0-9_]+))?(:(?P<func>[a-z_]+))?))
        (\s+(?P<direction>desc|asc))?
        (\s+(?P<nulls>nulls\ first|nulls\ last))?
        \s*
        (,|$)
    )+
    (?<!,)
    $
""", re.IGNORECASE | re.VERBOSE)


#: ≙ el nombre que la referencia usa para la empresa de un registro. Aquí la
#: convención renombró la FK: ``company`` en 76 declaraciones y ``company_id``
#: en 6 (medido sobre ``addons/`` y ``src/``), así que la búsqueda mira las
#: dos formas antes de rendirse. El orden es el de frecuencia, no el de gusto.
COMPANY_FIELD_NAMES = ('company', 'company_id')

#: Su hermano plural — ≙ ``company_ids`` de la fuente. ``ResUsers`` ya lo
#: consume en su ``_check_company_domain`` propio (``res_users.py:1387``).
COMPANIES_FIELD_NAMES = ('companies', 'company_ids')


def _first_field_name(model, candidates):
    """El primero de ``candidates`` que el modelo declara, o ``None``.

    Ni la referencia ni Django ofrecen esto: allá la pregunta es
    ``'company_id' in self``, que sobre un recordset consulta ``_fields``.
    Aquí el equivalente es ``_meta.get_field``, y hace falta el bucle porque
    el nombre no es uno solo (ver :data:`COMPANY_FIELD_NAMES`).
    """
    for name in candidates:
        try:
            model._meta.get_field(name)
        except FieldDoesNotExist:
            continue
        return name
    return None


def active_field_name(cls):
    """``_active_name`` de un modelo — ``'active'``, ``'x_active'`` o ``None``.

    ≙ el ``_active_name`` que la fuente fija en el setup del modelo
    (``odoo19c: odoo/orm/model_classes.py:444-448``). Lo comparten
    ``BaseModel._active_field_name`` y :class:`ArchiveMixin`.
    """
    declared = getattr(cls, '_active_name', None)
    if declared:
        return declared
    registry_ = model_field_registry(cls)
    for name in ('active', 'x_active'):
        if name in registry_:
            return name
    return None


class BaseUrlMixin:
    """La URL raíz desde la que se sirve un registro.

    ≙ ``BaseModel.get_base_url`` (``odoo19c: odoo/orm/models.py:3985-3995``),
    que la fuente declara justo antes de ``_check_company_domain`` — de ahí
    que aquí viva pegado a :class:`CheckCompanyMixin`, en el mismo archivo
    espejado.

    **Quién la consume.** ``ir.actions.report._get_report_url``, que arma la
    URL con que el motor resuelve los recursos de una plantilla (hojas de
    estilo, imágenes) mientras la renderiza. Sin ella el porte de ese método
    no tiene de dónde sacar la raíz.

    **La divergencia de forma es la de siempre en este archivo**: allá cuelga
    de ``BaseModel`` y todo modelo la tiene; aquí ``models.Model`` es el de
    Django, así que viaja por ``TimeStampedModel``, la base común del
    proyecto. Es un mixin sin campos ni manager a propósito — uno con manager
    eclipsaría el de toda base declarada más abajo, que es el defecto medido
    en :ref:`h-api-876`.
    """

    def get_base_url(self):
        """Devuelve la URL raíz de este registro.

        Por defecto devuelve el parámetro ``web.base.url``, pero un modelo
        puede sobreescribirla.

        ≙ ``get_base_url`` (``odoo19c: models.py:3985``). Tres notas de
        forma, ninguna recorta el contrato:

        - La fuente valida ``len(self) > 1`` porque allá el receptor es un
          conjunto de registros; aquí es una instancia y esa rama no tiene
          forma que tomar.
        - El ``sudo()`` de la fuente tampoco: ``get_param`` es un
          ``classmethod`` que lee sin pasar por reglas de fila.
        - El ``self.env['ir.config_parameter']`` de la fuente es una consulta
          al registro, tardía a propósito; aquí es
          ``registry.model_by_name('ir.config_parameter')``, que es como este
          mismo archivo ya alcanza a ``ir.fields.converter``. Importarlo al
          top invertiría la capa: ``orm`` no depende de ``addons``.

        :return: la URL base de este registro
        """
        parameters = registry.model_by_name('ir.config_parameter')
        return parameters.get_param('web.base.url') if parameters else None


class ArchiveMixin:
    """``action_archive``, ``action_unarchive`` y ``toggle_active``, por fila.

    ≙ ``BaseModel`` en ``odoo19c: odoo/orm/models.py:5790-5816``. La fuente
    recorre el recordset, se queda con los activos (o los archivados) y les
    escribe el campo por ``write``, de modo que quien redefine ``write`` ve el
    cambio. Aquí la instancia de Django es un recordset de uno: el filtro es la
    condición sobre esa fila y la escritura pasa por el mismo ``write`` que el
    modelo hereda. ``BaseModel`` conserva su versión de recordset.

    Lo adopta ``TimeStampedModel``, la misma vía que :class:`OrderMixin`.
    """

    def toggle_active(self):
        """Invierte ``active`` — ≙ ``:5790-5795``."""
        field_name = active_field_name(type(self))
        assert field_name, f"No 'active' field on model {self._meta.label}"
        if getattr(self, field_name):
            return self.action_archive()
        return self.action_unarchive()

    def action_archive(self):
        """``active = False`` si la fila está activa — ≙ ``:5797-5806``."""
        field_name = active_field_name(type(self))
        assert field_name, f"No 'active' field on model {self._meta.label}"
        if getattr(self, field_name):
            self.write({field_name: False})

    def action_unarchive(self):
        """``active = True`` si la fila está archivada — ≙ ``:5808-5817``."""
        field_name = active_field_name(type(self))
        assert field_name, f"No 'active' field on model {self._meta.label}"
        if not getattr(self, field_name):
            self.write({field_name: True})


class CheckCompanyMixin:
    """Coherencia de empresa entre un registro y aquello a lo que apunta.

    ≙ ``BaseModel._check_company_auto`` / ``_check_company_domain`` /
    ``_check_company`` (``odoo19c: odoo/orm/models.py:451, 3997, 4009``), más
    sus dos llamadas desde ``write`` (``:4516``) y ``create`` (``:4744``).

    **El problema que cierra.** ``check_company=True`` marca un campo
    relacional para que el ORM verifique que el registro apuntado pertenece a
    la misma empresa que el registro que apunta —o a ninguna, que en este
    modelo significa «compartido»—. Sin el mecanismo, la palabra clave es
    decoración: se declara y nadie la lee. Medido en la referencia sobre los
    addons que este árbol ya tiene: **282** ``Many2one``, **19** ``Many2many``
    y **5** ``One2many`` la llevan, y seis archivos nuestros la declaraban
    como bloqueo explícito (``account/models/res_company.py:47``,
    ``hr/models/hr_work_location.py:20``,
    ``certificate/models/certificate.py:218``, …).

    **La divergencia de forma es la de siempre en este archivo**: allá cuelga
    de ``BaseModel`` y todo modelo lo tiene con
    ``_check_company_auto = False``; aquí ``models.Model`` es el de Django y no
    es nuestro, así que viaja por ``TimeStampedModel`` —la base común del
    proyecto— con el mismo valor por defecto. Un modelo lo enciende declarando
    ``_check_company_auto = True``, exactamente como la fuente.

    ``_description_domain`` (``odoo19c: odoo/orm/fields_relational.py:
    130-158``) usa la misma marca para acotar el *selector*: con
    ``check_company`` publica en ``fields_get`` el dominio de coherencia que
    construye :meth:`_check_company_domain` sobre un valor simbólico
    (``unquote``). Vive en ``orm/fields_relational.py``. La interfaz del
    árbol puede pintar las vistas como la referencia, servidas por DRF, y esa
    descripción es su insumo.

    ``check_company`` sobre un ``One2many`` (5 en la referencia) tampoco tiene
    sitio de declaración: aquí un One2many es el reverso de una FK
    (``related_name``) y no un campo propio, así que la marca vive en la FK
    del otro lado, que es donde el registro apuntado guarda su empresa.
    """

    #: ≙ ``_check_company_auto: bool = False`` (``odoo19c: models.py:451``).
    #: Al guardar, ``save()`` llama a ``_check_company`` sólo si está en
    #: ``True``. El defecto es ``False`` allá y aquí: encenderlo es una
    #: decisión por modelo, y la fuente la toma en 76 clases.
    _check_company_auto = False

    @classmethod
    def _check_company_domain(cls, companies):
        """El predicado con que ESTE modelo se valida contra unas empresas.

        ≙ ``_check_company_domain`` (``odoo19c: models.py:3997-4007``). La
        fuente devuelve ``Domain('company_id','in', ids + [False])``: el
        registro vale si es de alguna de esas empresas **o si no es de
        ninguna**, que es como se expresa «compartido entre todas».

        Devuelve el ``Domain`` de la fuente, verbatim, incluida la rama
        ``unquote``: con ella ``Relational._description_domain`` publica el
        dominio simbólico ``[company_id] + [False]`` que el cliente evalúa.
        El campo se nombra por su ``attname`` (``company_id``), el nombre de
        la fuente, aunque aquí el campo se declare ``company``. Quien filtra
        un ``QuerySet`` lo compila con :func:`~orm.domains.to_q`.

        Un modelo sin campo de empresa no tiene con qué discriminar: devuelve
        ``None``, y quien llama lo lee como «este comodelo no participa».
        """
        name = _first_field_name(cls, COMPANY_FIELD_NAMES)
        if name is None:
            return None
        fname = cls._meta.get_field(name).attname
        if not companies:
            return Domain(fname, '=', False)
        if isinstance(companies, unquote):
            return Domain(fname, 'in', unquote(f'{companies} + [False]'))
        return Domain(fname, 'in', _company_ids(companies) + [False])

    def _check_company(self, fnames=None):
        """Verifica la empresa de lo que apuntan los campos marcados.

        ≙ ``_check_company`` (``odoo19c: models.py:4009-4090``). Recorre los
        campos relacionales con ``check_company`` y, para cada valor apuntado,
        exige que su empresa sea la del registro o ninguna. Acumula las
        incoherencias y lanza **una** ``UserError`` con hasta cinco, como la
        fuente — no una por campo: quien corrige un formulario quiere ver
        todo lo que está mal de una vez.

        ``fnames`` acota el recorrido a los campos escritos. Igual que allá,
        si entre ellos va el propio campo de empresa se revisan **todos**: al
        cambiar de empresa, un valor que antes era coherente puede dejar de
        serlo aunque nadie lo haya tocado.

        La segunda mitad de la fuente —los campos ``company_dependent``, que
        se validan contra la empresa del entorno y no contra la del
        registro— se porta con :func:`~orm.environments.get_current_company`,
        que es el equivalente de ``self.env.company``.
        """
        regular, dependent = self._check_company_fields(fnames)
        if not regular and not dependent:
            return

        inconsistencies = []
        own_name = _first_field_name(type(self), COMPANY_FIELD_NAMES)
        many_name = _first_field_name(type(self), COMPANIES_FIELD_NAMES)

        if regular:
            if type(self)._meta.label_lower == 'base.rescompany':
                # ≙ ``if self._name == 'res.company': companies = record``
                # (:4051). La empresa de una empresa es ella misma.
                companies = [self]
            elif own_name is not None:
                companies = [getattr(self, own_name, None)]
            elif many_name is not None:
                companies = list(related_manager(self, many_name).all())
            else:
                _logger.warning(
                    'Se omite la verificación de empresa de %s: sus campos %s '
                    'están marcados check_company pero el modelo no declara '
                    'ni %s ni %s.',
                    type(self)._meta.label, sorted(regular),
                    ' / '.join(COMPANY_FIELD_NAMES),
                    ' / '.join(COMPANIES_FIELD_NAMES),
                )
                companies = None
            if companies is not None:
                companies = [c for c in companies if c is not None]
                inconsistencies += self._company_inconsistencies(
                    regular, companies)

        if dependent:
            current = [c for c in [get_current_company()] if c is not None]
            inconsistencies += self._company_inconsistencies(
                dependent, current)

        if inconsistencies:
            raise UserError(
                self._company_inconsistency_message(inconsistencies))

    @classmethod
    def _check_company_fields(cls, fnames=None):
        """Los nombres de campo marcados, partidos en regulares y por empresa.

        ≙ el primer bloque de ``_check_company`` (``odoo19c: models.py:4029-
        4040``), extraído a su propio método porque aquí lo consumen dos
        sitios: la verificación y su prueba, que necesita poder preguntar qué
        va a mirar sin escribir nada.
        """
        campos = {f.name: f for f in cls._meta.get_fields()
                  if getattr(f, 'check_company', False)}
        company_names = set(COMPANY_FIELD_NAMES) | set(COMPANIES_FIELD_NAMES)
        if fnames is not None and not company_names & set(fnames):
            campos = {n: f for n, f in campos.items() if n in set(fnames)}
        regular, dependent = [], []
        for name, field in campos.items():
            (dependent if getattr(field, 'company_dependent', False)
             else regular).append(name)
        return regular, dependent

    def _company_inconsistencies(self, fnames, companies):
        """Las ternas ``(registro, campo, apuntado)`` que no cuadran.

        ≙ el bucle interior de ``_check_company`` (``:4055-4078``). Un campo
        vacío no se mira; uno cuyo comodelo no tiene empresa tampoco, porque
        su ``_check_company_domain`` devuelve ``None`` y no hay con qué
        discriminar.
        """
        fuera = []
        for name in fnames:
            corecords = _corecords(self, name)
            if not corecords:
                continue
            comodel = type(corecords[0])
            domain = comodel._check_company_domain(companies)
            if domain is None:
                continue
            validos = set(comodel._base_manager.filter(
                to_q(domain, comodel), pk__in=[c.pk for c in corecords],
            ).values_list('pk', flat=True))
            if any(c.pk not in validos for c in corecords):
                fuera.append((self, name, corecords))
        return fuera

    @staticmethod
    def _company_inconsistency_message(inconsistencies):
        """El texto del rechazo — ≙ ``:4080-4090``, con sus cinco primeras.

        La fuente distingue tres redacciones (empresa, registro, empresa
        raíz); aquí se conserva la del registro, que es la que aplica a los
        casos medidos. Sin ``_()``: este archivo no importa ``tools.translate``
        —medido, 0 usos— y su única ``UserError`` (``:1931``) también escribe
        el texto directo.
        """
        lines = ['Hay incoherencias de empresa:']
        for record, name, corecords in inconsistencies[:5]:
            values = ', '.join(str(c) for c in corecords)
            lines.append(
                f'- «{record}» pertenece a una empresa y «{name}» '
                f'({values}) pertenece a otra.'
            )
        return '\n'.join(lines)

    def save(self, *args, **kwargs):
        """≙ las dos llamadas de la fuente, que van **después** del escribir.

        ``write`` (``odoo19c: models.py:4516``) y ``create`` (``:4744``)
        llaman a ``_check_company`` una vez completada la escritura, no antes:
        la verificación mira el estado final del registro, incluido lo que
        hayan puesto los ``compute`` y los inversos. Aquí pasa lo mismo con
        ``save()``, y por eso la excepción llega con la fila ya escrita — como
        allá, donde la transacción es la que deshace.

        ``update_fields`` hace de ``list(vals)``: acota el recorrido a lo que
        se escribió. Sin él se revisan todos los campos marcados, que es lo
        que la fuente hace en ``create``.
        """
        super().save(*args, **kwargs)
        if self._check_company_auto:
            update_fields = kwargs.get('update_fields')
            self._check_company(
                None if update_fields is None else list(update_fields))


def _company_ids(companies):
    """Las claves primarias de ``companies``, venga como venga.

    ≙ ``to_record_ids`` (``odoo19c: odoo/orm/models.py:159-166``), que acepta
    un recordset, un entero o una lista. Aquí lo que llega es una instancia,
    un ``QuerySet``, una lista de instancias o una lista de enteros; los
    cuatro se normalizan a una lista de ``pk``, y los falsos se descartan
    igual que allá.
    """
    if companies is None:
        return []
    if hasattr(companies, 'values_list'):
        return [pk for pk in companies.values_list('pk', flat=True) if pk]
    if not isinstance(companies, (list, tuple, set)):
        companies = [companies]
    ids = []
    for c in companies:
        pk = getattr(c, 'pk', c)
        if pk:
            ids.append(pk)
    return ids


def _ancestor_company_ids(companies):
    """Los ids de ``companies`` **y de todos sus ancestros**.

    ≙ el cuerpo comun de los dos ``*_parent_of`` de la fuente
    (``odoo19c: odoo/orm/models.py:180-184`` y ``:196-200``), que recorre
    ``rec.parent_path.split('/')[:-1]`` de cada empresa.

    ``parent_path`` es la ruta materializada (``'1/4/9/'``) que
    ``ResCompany._compute_parent_path`` mantiene: la lista de ancestros mas la
    propia empresa, con separador final. El ``[:-1]`` de la fuente descarta el
    hueco que deja ese separador, no un ancestro.

    Una empresa sin ``parent_path`` poblado cae a su propio id: es la
    respuesta correcta —una raiz es su unico ancestro— y evita que una fila
    sin calcular desaparezca del dominio en silencio.
    """
    company_model = registry.MODELS_BY_NAME.get('res.company')
    ids = _company_ids(companies)
    if company_model is None or not ids:
        return ids
    ancestors = []
    for company in company_model.objects.filter(pk__in=ids):
        path = company.parent_path or ''
        segments = [seg for seg in path.split('/')[:-1] if seg]
        ancestors.extend(int(seg) for seg in segments) if segments \
            else ancestors.append(company.pk)
    return ancestors


def check_company_domain_parent_of(cls, companies):
    """Predicado de coherencia de empresa que admite a los **ancestros**.

    ≙ ``check_company_domain_parent_of``
    (``odoo19c: odoo/orm/models.py:169-184``). Docstring de la fuente,
    verbatim: *"A `_check_company_domain` function that lets a record be used
    if either: record.company_id = False (which implies that it is shared
    between all companies), or record.company_id is a parent of any of the
    given companies."*

    Es la variante **jerarquica** de
    :meth:`CheckCompanyMixin._check_company_domain`: aquella exige que la
    empresa del registro este entre las dadas; esta admite ademas cualquier
    ancestro suyo, que es como una matriz comparte catalogos con sus filiales.

    Se declara como funcion de modulo —no como metodo— porque asi la declara
    la fuente y asi la consumen los modelos:
    ``_check_company_domain = models.check_company_domain_parent_of`` es una
    **asignacion de atributo de clase**, no una sobreescritura. El primer
    parametro se llama ``cls`` y no ``self`` porque en este arbol el consumidor
    (:meth:`CheckCompanyMixin._check_company`) lo invoca sobre la clase.

    Devuelve el dominio de la fuente, verbatim, como su hermano de clase;
    quien filtra un ``QuerySet`` lo compila con :func:`~orm.domains.to_q`.
    La rama ``str`` es el dominio simbolico que publica
    ``Relational._description_domain`` y no se evalua aqui.
    """
    name = _first_field_name(cls, COMPANY_FIELD_NAMES)
    if name is None:
        return None
    fname = cls._meta.get_field(name).attname
    if isinstance(companies, str):
        return ['|', (fname, '=', False), (fname, 'parent_of', companies)]
    if not _company_ids(companies):
        return [(fname, '=', False)]
    return [(fname, 'in', _ancestor_company_ids(companies) + [False])]


def check_companies_domain_parent_of(cls, companies):
    """Su hermano plural, sobre el M2M de empresas.

    ≙ ``check_companies_domain_parent_of``
    (``odoo19c: odoo/orm/models.py:188-200``). Docstring de la fuente,
    verbatim: *"A `_check_company_domain` function that lets a record be used
    if any company in record.company_ids is a parent of any of the given
    companies."*

    **La diferencia con el singular no es cosmetica**: aqui NO hay rama de
    «compartido entre todas». La fuente devuelve ``[]`` —dominio vacio, todo
    pasa— cuando no se dan empresas, y un registro sin ninguna empresa en su
    M2M no entra en el dominio. Se conserva: ``None`` significa «este modelo no
    participa», que es otra cosa.
    """
    name = _first_field_name(cls, COMPANIES_FIELD_NAMES)
    if name is None:
        return None
    if isinstance(companies, str):
        return [(name, 'parent_of', companies)]
    if not _company_ids(companies):
        return []
    return [(name, 'in', _ancestor_company_ids(companies))]


def _corecords(record, name):
    """Los registros que ``record.<name>`` apunta, siempre como lista.

    Un Many2one da uno o ninguno; un Many2many, los que haya. La fuente no
    necesita distinguirlos porque allá todo es recordset; aquí sí, y la
    distinción se hace por el descriptor, no por el nombre del campo.
    """
    value = getattr(record, name, None)
    if value is None:
        return []
    if isinstance(value, BaseModel):
        return list(value)
    if hasattr(value, 'all'):
        return list(value.all())
    return [value]


class CopyMixin:
    """``copy`` y su cadena — duplicar un registro con sus hijos.

    ≙ los tres métodos que ``BaseModel`` declara seguidos:
    ``copy_data`` (``odoo19c: odoo/orm/models.py:5406``),
    ``copy_translations`` (``:5465``) y ``copy`` (``:5530``). Van juntos
    porque el último llama a los otros dos.

    **La divergencia de forma es la de siempre en este archivo** (ver
    ``OriginMixin``, ``FieldSqlMixin`` y ``DefaultGetMixin``): allá cuelgan de
    ``BaseModel`` y todo modelo los tiene; aquí ``models.Model`` es el de
    Django y no es nuestro, así que es un mixin que el modelo adopta.

    Qué decide qué se copia
    =======================

    El discriminador es ``field.copy``, que este árbol acaba de construir en
    ``orm/fields.py`` con la ortografía de la fuente. Sobre él van las dos
    listas de la fuente: la **negra** —:data:`MAGIC_COLUMNS` más
    ``parent_path`` y los FK de delegación— y la **blanca**, que son los
    campos propios frente a los que llegan heredados.
    """

    @classmethod
    def _copy_blacklist(cls, default):
        """Los campos que un duplicado NO lleva, con su razón.

        ≙ el bloque ``blacklist``/``whitelist``/``blacklist_given_fields``
        (``odoo19c: odoo/orm/models.py:5419-5434``). Se saca a un método
        propio porque :meth:`copy_data` lo usa una vez y el test lo mide
        aparte — allá es una clausura y no se puede interrogar.
        """
        blacklist = set(MAGIC_COLUMNS) | {'parent_path'}
        whitelist = {name for name in _field_names(cls)
                     if _delegated_origin(cls, name) is None}

        def blacklist_given_fields(model):
            """Lo que llega por delegación lo pone el padre, no la copia."""
            inherits = getattr(model, '_inherits', {})
            for _parent_name, fk_name in inherits.items():
                parent = _inherits_parent(model, fk_name)
                if parent is None:
                    continue
                try:
                    fk_field = model._meta.get_field(fk_name)
                except FieldDoesNotExist:
                    continue
                blacklist.add(fk_field.name)
                blacklist.add(fk_field.attname)
                if fk_field.name in default or fk_field.attname in default:
                    # El registro trae el padre entero: todos sus campos los
                    # da él, salvo los que el hijo redefina.
                    blacklist.update(set(_field_names(parent)) - whitelist)
                else:
                    blacklist_given_fields(parent)

        blacklist_given_fields(cls)
        return blacklist

    def copy_data(self, default=None, seen=None):
        """Los valores con que se daría de alta un duplicado de este registro.

        ≙ ``copy_data`` (``odoo19c: odoo/orm/models.py:5406-5462``).

        Docstring de la fuente, verbatim: *"Copy given record's data with all
        its fields values"*.

        :param default: valores que pisan a los del original.
        :param seen: los ya visitados, por modelo — la guarda contra la
            recursión de una relación circular. Allá viaja en el contexto
            (``__copy_data_seen``); aquí es un parámetro, porque el contexto
            de este árbol es de **sólo lectura** por diseño
            (``orm/environments.py``) y un ``defaultdict`` que se muta dentro
            no cabe en él. Es la misma guarda con otro vehículo.
        :returns: el dict de valores, o ``None`` si el registro ya se visitó.

        **Devuelve un dict, no una lista.** Allá ``self`` es un recordset y el
        método responde uno por registro; aquí es una instancia. La forma
        plural la recupera quien la necesite iterando, que es lo que
        :meth:`copy` hace.
        """
        cls = type(self)
        default = dict(default or {})
        seen = collections.defaultdict(set) if seen is None else seen

        if self.pk in seen[cls._meta.label]:
            return None
        seen[cls._meta.label].add(self.pk)

        # Por la función del mixin y no por ``cls``: un comodelo que no adopta
        # ``CopyMixin`` también se copia como hijo (``copy_children``).
        blacklist = CopyMixin._copy_blacklist.__func__(cls, default)
        values = default.copy()

        for field in cls._meta.concrete_fields:
            if not getattr(field, 'copy', True):
                continue
            if field.name in default or field.name in blacklist:
                continue
            if field.attname in default or field.attname in blacklist:
                continue
            if field.is_relation:
                # El id, no la instancia: es lo que ``objects.create`` toma, y
                # evita releer la fila apuntada.
                values[field.attname] = getattr(self, field.attname)
            else:
                values[field.name] = getattr(self, field.name)

        return values

    def copy_children(self, new, seen=None, default=None):
        """Duplica bajo ``new`` los ``One2many`` con ``copy=True`` y repone los
        enlaces de los ``Many2many``.

        ≙ las ramas ``one2many`` y ``many2many`` de ``copy_data``
        (``odoo19c: odoo/orm/models.py:5436-5462``). Qué viaja lo decide el
        atributo ``copy`` de cada campo, como allá:

        - un ``One2many`` sólo si declara ``copy=True`` —su defecto es
          ``False`` (``odoo19c: odoo/orm/fields_relational.py:869``)—. El
          reverso de un ``Many2one`` que nadie declaró como ``One2many`` no es
          un campo de la referencia y no se copia (H-API-1161);
        - un ``Many2many`` con ``copy`` conserva los enlaces que se pueden
          leer: *"copy only links that we can read, otherwise the write will
          fail"*.

        Allá las dos ramas viven **dentro** de ``copy_data`` porque sus
        ``Command`` son tuplas que el ORM aplica al crear. Aquí corren
        **después** del alta: un hijo de Django necesita la fila del padre, y
        un ``Many2many`` no entra en ``objects.create``. El efecto es el de la
        fuente: los hijos se duplican *"using the wrong (old) parent, but then
        are reassigned to the correct one"*.

        El orden **por id** no es cosmético; el comentario de la fuente lo
        dice: *"duplicate following the order of the ids because we'll rely on
        it later for copying translations"*.
        """
        cls = type(self)
        seen = collections.defaultdict(set) if seen is None else seen
        default = dict(default or {})
        blacklist = CopyMixin._copy_blacklist.__func__(cls, default)
        for name, field in model_field_registry(cls).items():
            if (getattr(field, 'type', None) != 'one2many'
                    or not getattr(field, 'copy', False)
                    or name in default or name in blacklist):
                continue
            comodel, inverse = field._inverse_field()
            for child in sorted(getattr(self, name).all(),
                                key=lambda line: line.pk):
                child_values = CopyMixin._copy_child_data(
                    child, {inverse.name: new}, seen)
                if child_values is None:
                    continue
                child_values.pop(inverse.attname, None)
                child_values[inverse.name] = new
                if issubclass(comodel, DefaultGetMixin):
                    new_child, = comodel.create([child_values])
                else:
                    new_child = comodel._default_manager.create(
                        **child_values)
                CopyMixin.copy_children(child, new_child, seen=seen)
        for field in cls._meta.many_to_many:
            if (not getattr(field, 'copy', True)
                    or field.name in default or field.name in blacklist):
                continue
            links = getattr(self, field.name).all()
            readable = getattr(links, '_filtered_access', None)
            if readable is not None:
                links = readable('read')
            getattr(new, field.name).set(links)

    @staticmethod
    def _copy_child_data(child, default, seen):
        """Los valores del duplicado de ``child``: su ``copy_data`` si adopta
        el mixin —con las sobrescrituras de su modelo, como allá—, y la del
        mixin si no."""
        if isinstance(child, CopyMixin):
            return child.copy_data(default, seen=seen)
        return CopyMixin.copy_data(child, default, seen=seen)

    def copy_translations(self, new, excluded=()):
        """Copia las traducciones del original al registro nuevo.

        ≙ ``copy_translations`` (``odoo19c: odoo/orm/models.py:5465-5528``).
        Delega en la función de módulo :func:`copy_translations`, la misma
        que todo modelo de Django recibe (TASK-GEN-0060): una sola
        implementación de la rama de los campos traducibles.
        """
        return copy_translations(self, new, excluded)

    def copy(self, default=None):
        """Duplica el registro, con sus hijos, aplicando ``default``.

        ≙ ``copy`` (``odoo19c: odoo/orm/models.py:5530-5542``).

        Docstring de la fuente, verbatim: *"Duplicate record ``self`` updating
        it with default values."*

        :param default: valores que pisan a los del original.
        :returns: el registro nuevo.

        Los tres pasos de la fuente, en su orden: ``copy_data``, el alta, y
        ``copy_translations``. El alta va por :meth:`DefaultGetMixin.create`
        cuando el modelo lo adopta —así el duplicado recibe los defaults que
        un alta normal recibiría, como allá— y por ``objects.create`` si no.

        El ``with_context(active_test=False)`` de la fuente **no** tiene
        contraparte: ese filtro implícito por ``active`` es de su ORM, y aquí
        un ``QuerySet`` no lo lleva. Sin filtro que desactivar, no hay
        contexto que poner.
        """
        cls = type(self)
        seen = collections.defaultdict(set)
        values = self.copy_data(default, seen=seen)
        if values is None:
            return None
        # ≙ ``new = self.create(vals_list)`` — un modelo que adopte
        # ``DefaultGetMixin`` pasa por el ``create`` de la fuente; el resto,
        # por el alta de Django. Un solo registro por ``copy``, como allá.
        if issubclass(cls, DefaultGetMixin):
            new, = cls.create([values])
        else:
            new = cls.objects.create(**values)
        self.copy_children(new, seen=seen, default=default)
        self.copy_translations(new, excluded=default or ())
        return new


def _is_plumbing_default(field):
    """¿El ``default`` del campo es fontanería de columna y no un default real?

    NO tiene contraparte: allá ``field.default`` es lo que el desarrollador
    escribió y nada más, así que ``if field.default:`` distingue solo. Aquí un
    ``CompanyDependent`` guarda un ``jsonb`` y su constructor pone
    ``kwargs.setdefault('default', dict)``
    (``orm/fields_company_dependent.py:286``) para que la columna arranque con
    el mapa vacío — eso **no** es un valor por defecto del campo.

    Sin este discriminador el paso 3 se comería al 4 en **todo** campo
    dependiente de empresa: ``default_get`` respondía ``{}`` y el respaldo de
    ``ir.default`` no se veía nunca. Medido con ``barcode`` de ``res.partner``.

    El ``setdefault`` es lo que hace posible distinguirlos: un default que el
    desarrollador sí escribió sobrevive y no es ``dict``.
    """
    return (getattr(field, 'company_dependent', False)
            and field.default is dict)


def _inherits_parent(model, fk_name):
    """El modelo al que apunta el FK de delegación ``fk_name``, o ``None``.

    NO tiene contraparte con este nombre: allá el padre se resuelve con
    ``self.env[parent_mname]``, porque el nombre del modelo **es** la llave
    del registro. Aquí la llave es la clase, así que se llega por el FK.
    """
    try:
        fk_field = model._meta.get_field(fk_name)
    except FieldDoesNotExist:
        return None
    return getattr(fk_field, 'related_model', None)


def _field_names(model):
    """Los nombres de campo que un alta puede recibir, incluidos los del padre.

    ≙ el recorrido de ``self._fields`` de la fuente
    (``odoo19c: odoo/orm/models.py:1571-1575``). Allá ``_fields`` ya trae los
    campos que ``_inherits`` refleja en el hijo; aquí ``_meta`` sólo conoce los
    propios, así que los del padre se añaden por el mapa de delegación —el
    mismo camino que :func:`_delegated_origin` recorre en sentido inverso.

    Se excluyen las relaciones inversas: no son valores que un alta reciba.
    """
    names = []
    seen = set()
    for field in [*model._meta.concrete_fields, *model._meta.many_to_many]:
        if field.name not in seen:
            seen.add(field.name)
            names.append(field.name)
    for parent_name, fk_name in getattr(model, '_inherits', {}).items():
        parent = _inherits_parent(model, fk_name)
        if parent is None:
            continue
        parent_fields = [*parent._meta.concrete_fields,
                         *parent._meta.many_to_many]
        for field in parent_fields:
            if field.name not in seen:
                seen.add(field.name)
                names.append(field.name)
    return names


def _delegated_origin(model, name):
    """El ``(modelo padre, campo)`` del que ``name`` se hereda, o ``None``.

    NO tiene contraparte con este nombre: allá el campo heredado lo declara
    él mismo (``field.inherited`` y ``field.related_field``), porque el ORM
    construye un campo espejo en el hijo. Aquí ese campo espejo lo publica
    :func:`orm.model_classes._add_inherited_fields` en el mapa de campos, con
    ``related='<fk>.<nombre>'``, y la respuesta se lee de ahí: es la misma
    autoridad que decide, con varios padres, que gana el último
    (``odoo19c: odoo/orm/models.py:422-425``). Antes esta función recorría
    ``_inherits`` por su cuenta y devolvía el **primer** padre que tuviera el
    nombre, así que ``create`` mandaba un nombre compartido al padre
    equivocado.

    La fuente además exige ``_has_field_access(field, 'write')`` antes de
    delegar. Aquí ese check vive en ``FieldSqlMixin``, que no todo modelo
    adopta todavía (tarea **#96**); cuando el modelo lo tenga, se aplica.
    """
    field = model_field_registry(model).get(name)
    if field is None or not getattr(field, 'inherited', False):
        return None
    reference = (getattr(field, 'related', None) or '').split('.')[0]
    for fk_field in model._meta.concrete_fields:
        if reference not in (fk_field.name, fk_field.attname):
            continue
        parent_model = getattr(fk_field, 'related_model', None)
        if parent_model is None:
            return None
        try:
            parent_model._meta.get_field(name)
        except FieldDoesNotExist:
            return None
        if hasattr(model, '_has_field_access'):
            if not model()._has_field_access(fk_field, 'write'):
                return None
        return parent_model, name
    return None


#: ≙ ``NO_ACCESS`` (``odoo19c: odoo/orm/models.py:122``). Valor sentinela de
#: ``field.groups`` que prohíbe el campo a todo el mundo, elevación aparte.
NO_ACCESS = '.'


#: ≙ ``regex_field_agg`` (``odoo19c: odoo/orm/models.py:112``), verbatim.
#: Parte una especificación de campo de ``read_group``: ``campo``,
#: ``campo:func`` o ``nombre:func(campo)``.
regex_field_agg = re.compile(r'(\w+)(?::(\w+)(?:\((\w+)\))?)?')

#: ≙ ``regex_read_group_spec`` (``odoo19c: odoo/orm/models.py:113``), verbatim.
#: Parte una especificación de agrupamiento en sus tres piezas: el campo, el
#: nombre de propiedad opcional tras el punto, y el agregado o granularidad
#: opcional tras los dos puntos.
regex_read_group_spec = re.compile(r'(\w+)(\.([\w\.]+))?(?::(\w+))?$')

#: Una parte del orden de ``_read_group`` — ≙ ``regex_order_part_read_group``
#: (``odoo19c: odoo/orm/models.py:105-111``), verbatim: el término (campo,
#: ruta y función opcionales), la dirección y los nulos.
regex_order_part_read_group = re.compile(r"""
    \s*
    (?P<term>(?P<field>[a-z0-9_]+)(\.([\w\.]+))?(:(?P<func>[a-z_]+))?)
    (\s+(?P<direction>desc|asc))?
    (\s+(?P<nulls>nulls\ first|nulls\ last))?
    \s*
""", re.IGNORECASE | re.VERBOSE)


def parse_read_group_spec(spec):
    """El triplete ``(campo, propiedad, agregado)`` de ``spec``.

    ≙ ``parse_read_group_spec`` (``odoo19c: odoo/orm/models.py:125-136``).
    Docstring de la fuente: *"Return a triplet corresponding to the given
    field/property_name/aggregate specification."*

    El patrón captura cuatro grupos y la fuente devuelve el 0, el 2 y el 3 —
    el 1 es el punto con su contenido, que sólo existe para delimitar al 2.

    La guarda **no es cosmética**: sin ella un ``spec`` que no parsea deja
    ``res_match`` en ``None`` y el acceso a ``.groups()`` revienta con
    ``AttributeError`` en vez del ``ValueError`` explicado que la fuente
    promete a quien escribió el agrupamiento.
    """
    res_match = regex_read_group_spec.match(spec)
    if not res_match:
        raise ValueError(
            f'Invalid aggregate/groupby specification {spec!r}.\n'
            '- Valid aggregate specification looks like "<field_name>:<agg>" '
            'example: "quantity:sum".\n'
            '- Valid groupby specification looks like '
            '"<no_datish_field_name>" '
            'or "<datish_field_name>:<granularity>" example: "date:month" or '
            '"<properties_field_name>.<property>:<granularity>".'
        )

    groups = res_match.groups()
    return groups[0], groups[2], groups[3]


#: Funciones de agregación SQL válidas — ≙ ``READ_GROUP_AGGREGATE``
#: (``odoo19c: odoo/orm/models.py:300-313``). Cada entrada recibe la tabla y
#: la expresión del campo; los agregados ``recordset`` se convierten después
#: en recordsets.
READ_GROUP_AGGREGATE = {
    'sum': lambda table, expr: SQL('SUM(%s)', expr),
    'avg': lambda table, expr: SQL('AVG(%s)', expr),
    'max': lambda table, expr: SQL('MAX(%s)', expr),
    'min': lambda table, expr: SQL('MIN(%s)', expr),
    'bool_and': lambda table, expr: SQL('BOOL_AND(%s)', expr),
    'bool_or': lambda table, expr: SQL('BOOL_OR(%s)', expr),
    'array_agg': lambda table, expr: SQL(
        'ARRAY_AGG(%s ORDER BY %s)', expr, SQL.identifier(table, 'id')),
    'array_agg_distinct': lambda table, expr: SQL(
        'ARRAY_AGG(DISTINCT %s ORDER BY %s)', expr, expr),
    # los agregados 'recordset' se post-procesan para volverse recordsets
    'recordset': lambda table, expr: SQL(
        'ARRAY_AGG(%s ORDER BY %s)', expr, SQL.identifier(table, 'id')),
    'count': lambda table, expr: SQL('COUNT(%s)', expr),
    'count_distinct': lambda table, expr: SQL('COUNT(DISTINCT %s)', expr),
}

READ_GROUP_DISPLAY_FORMAT = {
    # Cuidado con los formatos de semana/año:
    #  - yyyy (minúscula) se usa siempre, *salvo* en los de semana+año
    #  - YYYY (mayúscula) se usa siempre en el formato semana+año
    #         p. ej. 2006-01-01 es W52 2005 en algunas locales (de_DE),
    #                           y W1 2006 en otras
    #
    # Mezclar los dos, p. ej. 'MMM YYYY', daría resultados erróneos, como
    # 2006-01-01 formateado como "January 2005" en algunas locales.
    # Ver: http://babel.pocoo.org/en/latest/dates.html#date-fields
    'hour': 'HH:00 dd MMM',
    'day': 'dd MMM yyyy',  # yyyy = año normal
    'week': "'W'w YYYY",  # w YYYY = año-semana ISO
    'month': 'MMMM yyyy',
    'quarter': 'QQQ yyyy',
    'year': 'yyyy',
}


def _read_group_recordset(env, model, ids, prefetch_ids):
    """Los registros ``ids`` de ``model`` — ≙ ``Model(self.env, ids,
    prefetch_ids)`` de los posprocesos de ``_read_group``
    (``odoo19c: odoo/orm/models.py``).

    Adaptación declarada: ``env[name]`` devuelve aquí la clase. Un
    ``BaseModel`` construye su terna con ``_from_ids``; un modelo de Django
    usa :func:`~orm.utils.browse`, cuyo ``QuerySet`` no lleva ``prefetch``.
    """
    if hasattr(model, '_from_ids'):
        return model._from_ids(env, tuple(ids), tuple(prefetch_ids))
    return browse(model, tuple(ids))


def raise_on_invalid_object_name(name):
    """La mitad que lanza de :func:`~orm.utils.check_object_name`.

    ≙ ``raise_on_invalid_object_name``
    (``odoo19c: odoo/orm/models.py:139-142``). El hermano devuelve un booleano
    y éste lo convierte en el rechazo que el cargador de modelos necesita: un
    ``_name`` inválido no puede seguir adelante en silencio.
    """
    if not check_object_name(name):
        msg = "The _name attribute %s is not valid." % name
        raise ValueError(msg)


class FieldSqlMixin:
    """``_field_to_sql`` y su cadena — la puerta del motor de consultas.

    ≙ los cuatro métodos que ``BaseModel`` declara en ``odoo19c:
    odoo/orm/models.py``: ``_field_to_sql`` (``:2910``),
    ``_traverse_related_sql`` (``:2889``), ``_check_field_access`` (``:3384``)
    y ``_has_field_access`` (``:3370``). Los cuatro van juntos porque el
    primero llama a los otros tres.

    **La divergencia, y es la que este archivo ya declara dos veces** (la
    sección de permisos y ``OriginMixin``): allá cuelgan de ``BaseModel``, así
    que todo modelo los tiene; aquí ``models.Model`` es el de Django y no es
    nuestro para colgarle nada, así que el mecanismo es un mixin que el modelo
    adopta. Qué modelos lo adoptan, y en qué orden, es el mismo trabajo
    abierto que la adopción de ``AccessManager`` — tarea **#96**.

    Por qué no se adjunta a ``models.Model`` como ``to_sql`` a ``Field``
    ===================================================================

    ``orm/fields.py`` sí adjunta a la clase de Django, y aquí no: la asimetría
    es deliberada. Un ``Field`` es una pieza interna del ORM que nadie hereda;
    ``models.Model`` es la base que **toda** la aplicación hereda, incluidos
    los modelos de Django (``auth``, ``contenttypes``, ``sessions``) y los de
    cualquier paquete de terceros. Colgarle cuatro métodos con guion bajo
    cambia la superficie de clases que no son del proyecto — que es
    exactamente la colisión que la tarea **#98** barre. El mixin da lo mismo
    donde se pide y nada donde no.

    Qué resuelve, en una línea
    ==========================

    Una expresión de campo —``'name'`` o ``'properties.color'``— contra un
    alias de tabla, devuelta como ``SQL`` y con la lectura del campo
    comprobada. Es el punto por el que pasa todo lo que compone SQL crudo: el
    ORDER BY de un ``_order_field_to_sql``, la condición de un dominio, la
    exportación de un campo sin columna.
    """

    #: Los campos del modelo por nombre — ≙ ``BaseModel._fields``.
    #:
    #: Allá es el registro que el ORM construye al cargar la clase; aquí lo
    #: provee ``_meta``, que es el registro equivalente de Django. Entran
    #: **todos**, como allá: el mapa es el registro del modelo, no el de sus
    #: columnas.
    #:
    #: > **Ensanchado (tarea #215, H-API-953).** Hasta hoy filtraba por
    #: > ``concrete``, y ese filtro era un contrato **más estrecho** que el de
    #: > la fuente sin que nadie hubiera comparado los dos alcances. Lo
    #: > destapó ``setup_related`` (``odoo19c: :604``), que recorre
    #: > ``model._fields[name]`` por una cadena punteada que puede atravesar
    #: > un ``One2many`` — que no es concreto. Con el mapa estrecho esa cadena
    #: > no se puede recorrer.
    #: >
    #: > Medido sobre ``ResPartner``: **107** campos en total, **66**
    #: > concretos, **41** no. El filtro escondía el 38 %.
    #: >
    #: > Los cinco consumidores se midieron uno a uno antes de ensanchar.
    #: > Cuatro filtran por su cuenta —dos exigen ``ForeignKey``, dos exigen
    #: > ``Properties``— así que el filtro no era suyo. El quinto,
    #: > ``_field_to_sql``, SÍ lo usaba: un nombre no concreto quedaba fuera
    #: > del mapa y producía su ``ValueError`` limpio. Ese rechazo se conserva
    #: > **en su sitio**, que es donde pertenece — quien compone SQL es quien
    #: > sabe qué puede convertir.
    #:
    #: > **Ensanchado otra vez (tarea #301, :ref:`h-api-1025`).** La ceguera
    #: > que la versión anterior declaraba abajo —*"ciega al campo sin
    #: columna"*—
    #: > no era una nota al pie: era la mitad que faltaba. El campo sin
    #: > columna **es un campo del modelo** en la fuente, y dejarlo fuera
    #: > volvía a hacer el mapa más estrecho que allá, sólo que por otro eje.
    #: > Lo destapó ``_address_fields()``, que desde ``base_address_extended``
    #: > devuelve ``city_id`` —sin columna aquí, DEC-SALE-01— y hacía reventar
    #: > a ``_convert_fields_to_values`` sobre 35 casos de
    #: > ``tests/integration/base``.
    #: >
    #: > Los seis consumidores se re-midieron uno a uno antes de ensanchar, y
    #: > ninguno cambia de conducta: cuatro filtran por ``Properties`` o
    #: > ``ForeignKey``, uno lee ``ondelete`` con ``getattr`` y el sexto
    #: > —``_field_to_sql``— exige ``concrete``, que un campo sin columna no
    #: > declara. Ahí el nombre pasa de dar ``None`` a dar el descriptor, y el
    #: > mismo ``ValueError`` sale por la misma rama.
    #:
    #: *Métrica:* ``_meta.get_fields()`` unido a los descriptores
    #: el descriptor sin columna (retirado en TASK-API-0418) que el MRO de la
    #: clase
    #: declara.
    #: *Ciega a:* un campo de la fuente que aquí no se declare ni como campo
    #: de Django ni como campo sin columna — una ``property`` pelada, por
    #: ejemplo.
    #: Esa forma existe en el árbol y su barrido es la tarea **#302**.
    #:
    #: **Es un descriptor y no una ``property`` (tarea #342).** La fuente
    #: declara ``_fields`` en la clase de registro, asi que ``Model._fields``
    #: y ``record._fields`` devuelven el mismo mapa; ``check_indexes``
    #: (``odoo19c: odoo/orm/registry.py:813``) lo lee por la clase. Una
    #: ``property`` sobre la clase devuelve el objeto descriptor, no el mapa,
    #: y ese hueco lo tapaba :func:`~orm.utils.model_field_registry` llamada a
    #: mano en once sitios. El protocolo de descriptor de CPython ya distingue
    #: los dos accesos, asi que el mecanismo no se trae de fuera: se usa.
    _fields = FieldRegistryDescriptor()

    def _has_field_access(self, field, operation) -> bool:
        """Si el usuario puede leer o escribir este campo.

        ≙ ``_has_field_access`` (``odoo19c: odoo/orm/models.py:3370-3382``).
        Un campo sin ``groups`` es accesible; bajo elevación, también.
        ``NO_ACCESS`` lo prohíbe siempre.

        ``field.groups`` se lee con ``getattr``: los campos de Django no lo
        declaran, así que hoy la respuesta es ``True`` para todos salvo que
        alguien lo asigne. No es una laxitud inventada — es el mismo
        ``if not field.groups`` de la fuente, que allá también deja pasar todo
        campo que no declare grupos.
        """
        groups = getattr(field, 'groups', None)
        if not groups or is_su():
            return True
        if groups == NO_ACCESS:
            return False
        user = get_current_user()
        return user is not None and user.has_groups(groups)

    def _check_field_access(self, field, operation) -> None:
        """Levanta ``AccessError`` si el usuario no puede — ≙ ``:3384-3424``.

        Cuatro piezas, como la fuente: campo, descripción del modelo, operación
        y —sólo para quien pueda verlo— **qué grupos lo abrirían**. Esa cuarta
        es la que convierte un 403 opaco en accionable, y va condicionada a
        ``base.group_no_one`` igual que allá: el nombre de un grupo que
        concede acceso a un campo es en sí mismo información.

        Las tres ramas del tramo de grupos son las de la fuente
        (``:3411-3418``) y no son intercambiables: ``NO_ACCESS`` significa
        *prohibido siempre* y no *«pide el grupo»*; un campo sin ``groups`` que
        aun así se denegó sólo puede deberse a una regla a medida.
        """
        if self._has_field_access(field, operation):
            return

        _logger.info(
            'Access Denied by ACLs for operation: %s, uid: %s, model: %s, '
            'field: %s',
            operation, get_current_uid(), self._meta.label, field.name)

        description = self._model_description()
        message = (
            f'No tiene permisos suficientes para acceder al campo '
            f'"{field.name}" en {description} '
            f'({self._meta.label}). Contacte a su administrador.'
            f'\n\nOperación: {operation}'
        )
        user = get_current_user()
        if user is not None and user.has_group('base.group_no_one'):
            message += (f'\nUsuario: {get_current_uid()}'
                        f'\nGrupos: {self._allowed_groups_message(field)}')
        raise AccessError(message)

    def _model_description(self):
        """El nombre informal del modelo — ≙
        ``self.env['ir.model']._get(name).name``.

        La fuente lo lee de ``ir.model`` y cae al nombre técnico si no hay
        fila; aquí igual, con el ``verbose_name`` de Django como último
        respaldo — que es lo que este árbol declara siempre y ``ir.model`` no
        necesariamente tiene sembrado.
        """
        IrModel = apps.get_model('base', 'IrModel')
        return (IrModel.objects.filter(model=self._meta.label)
                .values_list('name', flat=True).first()
                or self._meta.verbose_name or self._meta.label)

    @staticmethod
    def _allowed_groups_message(field):
        """El tramo *"Groups: …"* del error de campo — ≙ ``:3411-3418``."""
        groups = getattr(field, 'groups', None)
        if groups == NO_ACCESS:
            return 'prohibido siempre'
        if not groups:
            return 'reglas de acceso de campo a medida'
        # ≙ ``[self.env.ref(g) for g in field.groups.split(',')]`` ordenado
        # por id: el identificador externo se resuelve por ``ir.model.data``,
        # que es el mismo canal que ``has_group``. Un xmlid que no resuelve se
        # deja verbatim en vez de desaparecer — si el campo lo declara, quien
        # lea el error necesita verlo aunque el grupo no esté sembrado.
        IrModelData = apps.get_model('base', 'IrModelData')
        ResGroups = apps.get_model('base', 'ResGroups')
        resueltos = []
        for xmlid in (g.strip() for g in groups.split(',')):
            group = IrModelData.ref(xmlid, raise_if_not_found=False)
            if isinstance(group, ResGroups):
                resueltos.append((group.pk, str(group)))
            else:
                resueltos.append((None, xmlid))
        resueltos.sort(key=lambda par: (par[0] is None, par[0]))
        return 'permitido a los grupos %s' % ', '.join(
            repr(name) for _pk, name in resueltos)

    def _traverse_related_sql(self, alias, field, query):
        """Recorre el campo delegado y añade a ``query`` los JOIN que hagan
        falta.

        ≙ ``_traverse_related_sql``
        (``odoo19c: odoo/orm/models.py:2889-2908``).

        :returns: la terna ``(model, field, alias)``, donde ``field`` es el
            último campo de la secuencia, ``model`` el modelo de ese campo y
            ``alias`` el alias de su tabla.

        El ``related`` de la fuente es una ruta con puntos
        —``partner_id.name``— y aquí el mecanismo equivalente es
        ``orm/inherits.py``: ``_inherits`` instala la delegación y el camino es
        un solo salto, el de su FK. Por eso el bucle recorre
        ``field.related.split('.')`` igual que allá: la ruta de un salto es el
        caso que hoy existe, y la de varios funciona sin tocar nada el día que
        un campo la declare.
        """
        # `related`/`store` se leen con `getattr`: son atributos de la clase
        # `Field` de la referencia, y un campo de Django no los declara. Sin
        # el `getattr` la aserción no rechaza — revienta con AttributeError,
        # que no es lo mismo y esconde el motivo.
        assert (getattr(field, 'related', None)
                and not getattr(field, 'store', True))
        *path_fnames, last_fname = field.related.split('.')
        model = self
        for path_fname in path_fnames:
            path_field = model._fields[path_fname]
            if not isinstance(path_field, ForeignKey):
                raise ValueError(
                    f'Cannot convert {field} (related={field.related}) to SQL '
                    f'because {path_fname} is not a Many2one')
            comodel, alias = path_field.join(model, alias, query)
            # ``join`` devuelve la CLASE del comodelo; como en la fuente, el
            # recorrido sigue sobre un recordset (vacío) de ese modelo.
            model = (comodel._from_ids(self.env, (), ())
                     if hasattr(comodel, '_from_ids') else comodel())

        return model, model._fields[last_fname], alias

    def _field_to_sql(self, alias, field_expr, query=None):
        """El valor del campo dado desde el alias dado, como ``SQL``.

        ≙ ``_field_to_sql`` (``odoo19c: odoo/orm/models.py:2910-2932``).
        Comprueba además que el campo sea legible.

        El objeto ``query`` es necesario para los campos delegados y los
        Many2one: es donde se añaden los JOIN.
        """
        fname, property_name = parse_field_expr(field_expr)
        field = self._fields.get(fname)
        if (field and getattr(field, 'related', None)
                and not getattr(field, 'store', True)):
            # Un ``related`` sin columna se resuelve recorriendo su camino,
            # como en la fuente; por eso esta rama va antes del rechazo.
            model, field, alias = self._traverse_related_sql(
                alias, field, query)
            related_expr = (field.name if not property_name
                            else f"{field.name}.{property_name}")
            return model._field_to_sql(alias, related_expr, query)

        if not field or not getattr(field, 'concrete', False):
            # El rechazo del campo sin columna vive AQUÍ y no en ``_fields``:
            # quien compone SQL es quien sabe qué puede convertir. Antes lo
            # hacía el mapa, filtrando por ``concrete``, y con eso el registro
            # del modelo quedaba más estrecho que el de la fuente para todos
            # sus consumidores — no sólo para éste (tarea #215).
            raise ValueError(
                f"Invalid field {fname!r} on model {self._meta.label!r}")

        self._check_field_access(field, 'read')

        sql = field.to_sql(self, alias)
        if property_name:
            sql = field.property_to_sql(sql, property_name, self, alias, query)
        return sql


class RecordLoaderMixin(FieldSqlMixin):
    """``_load_records`` y su cadena — el lado ORM del cargador de datos.

    ≙ los cuatro métodos que ``BaseModel`` declara en ``odoo19c:
    odoo/orm/models.py``: ``_clean_properties`` (``:5054``),
    ``_load_records_write`` (``:5085``), ``_load_records_create`` (``:5102``) y
    ``_load_records`` (``:5108``). Van juntos porque el último llama a los
    otros tres.

    **La divergencia es de VÍA, no de alcance.** Allá cuelgan de ``BaseModel``,
    así que todo modelo los tiene; aquí ``models.Model`` es el de Django y no
    es nuestro para colgarle nada. La universalidad se recupera adoptando este
    mixin en ``addons.base.models.timestamped_mixin.TimeStampedModel``, que es
    la base común del proyecto ("usar en TODOS los modelos concretos", dice su
    propio docstring) — así todo modelo concreto tiene ``_load_records`` sin
    declararlo, igual que en la fuente.

    No es lo mismo que ``FieldSqlMixin`` ni que ``AccessManager``, que siguen
    adoptándose modelo a modelo (tarea **#96**): aquéllos cambian **cómo se
    consulta** un modelo concreto, y el cargador de datos no admite esa
    gradualidad — un archivo de datos de la referencia nombra veinticuatro
    modelos distintos sólo en ``base``, y el cargador falla con
    ``AttributeError`` en el primero que no lo declare.

    Qué resuelve, en una línea
    ==========================

    Un archivo de datos declara registros con su identificador externo; este
    mixin decide, por cada uno, si **crear**, **actualizar** o **saltar**, y
    deja el identificador asignado. Es lo que ``tools/convert.py`` llama al
    leer un ``<record>``, y por tanto lo que estaba bloqueando a
    ``ResPartner._load_records_create``.

    Las tres decisiones, y de dónde salen
    =====================================

    La partición de la fuente se porta entera y en su orden:

    - **Sin ``xml_id``**: con ``values['id']`` se actualiza ese registro; sin
      él, se crea — salvo que sea una actualización de módulo, donde no hay
      forma de saber a qué registro se refiere y se rechaza.
    - **Con ``xml_id`` sin fila**: se crea.
    - **Con ``xml_id`` y fila viva** (``r_id``): se actualiza, salvo que sea
      actualización de módulo **y** la fila lleve ``noupdate`` — la bandera que
      protege el dato que alguien tocó a mano.
    - **Con ``xml_id`` y fila huérfana** (el registro ya no está): la fila se
      borra y el registro se crea de nuevo.

    El modelo de la fila tiene que coincidir con el de este mixin; si no, se
    rechaza con el mensaje de la fuente. Es la guarda que impide que un
    ``xml_id`` reutilizado entre módulos apunte a la tabla equivocada.

    DIVERGENCIA DE FORMA, declarada: la fuente es método de recordset y aquí de
    clase
    =====================================================================

    ``_load_records`` y ``_load_records_create`` son **classmethods**: allá
    ``self`` es un recordset vacío que sólo aporta el modelo (``self.browse()``
    en la primera línea), y aquí ese papel lo cumple la clase. ``self.create``
    pasa a ser ``cls.objects.create``, ``self.browse(id)`` a un
    ``filter(pk=)``, y el ``original_self.concat(...)`` del final a la lista de
    registros en el orden de ``data_list``, que es lo que la fuente promete
    devolver.

    ``_load_records_write`` y ``_clean_properties`` sí son de instancia: la
    fuente empieza con ``self.ensure_one()``, es decir, opera sobre **un**
    registro.

    Por qué hereda de ``FieldSqlMixin``
    ===================================

    Los dos métodos de instancia recorren ``self._fields``, que allá es un
    atributo de ``BaseModel`` y aquí lo porta ``FieldSqlMixin``. Heredarlo
    reproduce el hecho de la fuente —los ocho símbolos cuelgan del **mismo**
    objeto— en vez de pedirle al modelo que adopte dos mixins y recuerde el
    orden. Un modelo que adopte éste obtiene los dos, que es lo que allá
    obtiene por herencia de ``BaseModel``.
    """

    # -- Propiedades ---------------------------------------------------------

    def get_property_definition(self, full_name):
        """≙ ``get_property_definition``
        (``odoo19c: odoo/orm/models.py:3043``).

        Docstring de la fuente, verbatim: *"Return the definition of the given
        property"*, con ``full_name`` = *"Name of the field / property (e.g.
        'property.integer')"*.

        Su consumidor es ``domains._optimize_properties_date_datetime``, que
        necesita saber de qué **tipo** es una propiedad para convertir el valor
        de la condición antes de compilarla: sin el tipo no puede distinguir
        una propiedad de fecha de una de texto, y la comparación se haría
        contra la cadena cruda.

        **La divergencia de mecanismo, declarada.** La fuente arma un
        ``SELECT`` con ``jsonb_array_elements`` sobre la tabla del registro de
        definición y filtra en SQL por ``definition->>'name'``
        (``:3060-3067``). Aquí la lista ya la resuelve
        ``Properties._get_properties_definition(record)`` —el mismo camino que
        ``_clean_properties`` usa—, así que la selección por nombre se hace
        sobre esa lista en vez de emitir una segunda consulta. El resultado es
        el mismo: la definición que coincide, o ``{}`` cuando no hay ninguna,
        que es el ``LIMIT 1`` sin filas de allá.

        Se conserva de la fuente: la comprobación de lectura sobre el recordset
        vacío, el ``ValueError`` cuando el campo no existe, y la validación del
        nombre de la propiedad con
        :func:`~orm.fields_properties.check_property_field_value_name`
        **antes** de interpolarlo en el SQL.

        **Es independiente del registro, como la fuente.** Su primera versión
        leía la definición con ``field._get_properties_definition(self)`` —el
        camino que usa :meth:`_clean_properties`— y eso NO es lo mismo: aquel
        camino resuelve el contenedor **de un registro concreto**, y aquí no
        hay ninguno. El único consumidor es
        ``domains._optimize_properties_date_datetime``, que llama sobre el
        **modelo**: con la versión por registro no habría podido resolver nada.
        Es el sub-patrón D de ``metrica-decide-la-conclusion.md`` aplicado a un
        mecanismo — construido, sin control que lo midiera contra su
        consumidor.

        **La divergencia de mecanismo, declarada:** allá el recordset vacío
        llega por ``self.browse()``; aquí se construye el ``AccessQuerySet``
        explícitamente, porque su adopción por modelo aún está en curso
        (tarea #96) y el manager por omisión puede no traerlo. La comprobación
        se hace igual — no se omite por no estar adoptada.
        """
        AccessQuerySet(model=type(self)).none().check_access('read')
        field_name, property_name = parse_field_expr(full_name)
        field = self._fields.get(field_name)
        if not field:
            raise ValueError(
                f'Campo inválido {field_name!r} en el modelo '
                f'{getattr(self, "_name", type(self).__name__)!r}')
        check_property_field_value_name(property_name)

        if not isinstance(field, Properties):
            return {}
        definition = self._meta.get_field(field.definition_record)
        target_model = definition.related_model
        column = target_model._meta.get_field(
            field.definition_record_field).column
        result = env().execute_query_dict(SQL(
            """ SELECT definition
                  FROM %(table)s, jsonb_array_elements(%(field)s) definition
                 WHERE %(field)s IS NOT NULL AND definition->>'name' = %(name)s
                 LIMIT 1 """,
            table=SQL.identifier(target_model._meta.db_table),
            field=SQL.identifier(column),
            name=property_name,
        ))
        if not result:
            return {}
        definition = result[0]['definition']
        # Django carga ``jsonb`` como texto (lo decodifica ``from_db_value``
        # de su ``JSONField``); en una consulta cruda llega la cadena. La
        # fuente recibe ya el ``dict`` del cursor.
        if isinstance(definition, str):
            definition = json.loads(definition)
        return definition

    def _clean_properties(self):
        """≙ ``_clean_properties`` (``odoo19c: odoo/orm/models.py:5054-5068``).

        «Remove all properties of ``self`` that are no longer in the related
        definition.»

        El discriminador de tipo es ``isinstance(field, Properties)`` y no
        ``field.type != 'properties'`` — la forma que este árbol fijó para el
        mismo problema en ``fields_textual.Html`` (H-API-700); ver el docstring
        de ``orm/fields_properties.Properties``.

        La fuente itera ``for record in self`` porque su ``self`` es un
        recordset; aquí es un registro, así que el bucle exterior desaparece y
        queda el cuerpo. Escribe con ``save(update_fields=...)`` para no tocar
        columnas que no cambiaron.
        """
        changed = []
        for fname, field in self._fields.items():
            if not isinstance(field, Properties):
                continue
            old_value = getattr(self, fname, None)
            if not old_value:
                continue

            definitions = field._get_properties_definition(self)
            if not definitions:
                continue
            all_names = {definition['name'] for definition in definitions}
            new_values = {name: value for name, value in old_value.items()
                          if name in all_names}
            if len(new_values) != len(old_value):
                setattr(self, fname, new_values)
                changed.append(fname)
        if changed:
            self.save(update_fields=changed)

    # -- Enganches de extensión de la definición de propiedades --------------
    #
    # ≙ los cuatro que ``BaseModel`` declara junto a ``_clean_properties``
    # (``odoo19c: odoo/orm/models.py:5070-5084``). Los cuatro cuerpos son los
    # de la fuente: existen para que un addon los sobreescriba, no para hacer
    # nada por sí mismos. Su llamador es ``PropertiesDefinition`` en
    # ``orm/fields_properties.py``, que allá los pide a ``env["base"]`` y aquí
    # al registro — ver su docstring.

    def _validate_properties_definition(self, properties_definition, field):
        """Allow to validate additional properties attributes."""

    def _additional_allowed_keys_properties_definition(self):
        """Allow to add more allowed key for properties."""
        return ()

    def _convert_to_cache_properties_definition(self, value):
        """Allow to patch `convert_to_cache` of the properties definition."""
        return value

    def _convert_to_column_properties_definition(self, value):
        """Allow to patch `convert_to_column` of the properties definition."""
        return value

    # -- Escritura y creación ------------------------------------------------

    @classmethod
    def _load_records_coerce_vals(cls, values):
        """El id de un ``Many2one`` entra por su columna, no por el atributo.

        **Divergencia de stack, no de mecanismo.** En la referencia un
        ``Many2one`` se escribe con el id y ya: ``{'parent_id': 42}`` es lo que
        el archivo de datos produce y lo que ``create``/``write`` aceptan.
        Django separa las dos caras de una FK — ``parent`` quiere la
        **instancia** y ``parent_id`` (su ``attname``) quiere la **clave**—, y
        asignar un entero al primero levanta ``ValueError: Cannot assign
        "42": "ResPartner.parent" must be a "ResPartner" instance``.

        Aquí se traduce el nombre del campo a su ``attname`` cuando el valor no
        es ya una instancia. El sitio es el mixin del cargador y no
        ``tools/convert.py`` porque el que decide es el ORM: es la frontera
        ``create``/``write``, la misma que en la fuente acepta el id.

        Un nombre que el modelo no declara se deja pasar tal cual — quien
        levante el error es Django, con su mensaje, y no un ``KeyError`` de
        aquí que oculte cuál era el campo.
        """
        coerced = {}
        for fname, value in values.items():
            try:
                field = cls._meta.get_field(fname)
            except FieldDoesNotExist:
                coerced[fname] = value
                continue
            attname = getattr(field, 'attname', None)
            if (field.is_relation and field.many_to_one and attname
                    and attname != fname and not isinstance(value, Model)):
                coerced[attname] = value
            elif (isinstance(field, IntegerField)
                  and not isinstance(field, AutoField)):
                # ≙ el valor escrito pasa por ``convert_to_cache`` y se lee con
                # ``convert_to_record``: un entero escrito como texto se lee
                # como entero y ``False`` como ``0`` (``odoo19c:
                # odoo/orm/fields_numeric.py:35-42``). Sólo ``Integer``: el
                # resto de tipos sigue sin esa conversión en la escritura.
                coerced[fname] = field.convert_to_record(
                    field.convert_to_cache(value, None), None)
            else:
                coerced[fname] = value
        return coerced

    def _load_records_write(self, values):
        """≙ ``_load_records_write`` (``odoo19c: :5085-5100``).

        Escribe los valores de un registro que ya existe. Los campos de
        propiedades se **difieren**: se sacan del lote, se escribe el resto, y
        sólo entonces se escriben mezclados con lo que ya había. El comentario
        de la fuente dice por qué —*"Deferred the write to avoid using the old
        definition if it changed"*—: si en el mismo lote viene una definición
        nueva, mezclar antes usaría la vieja.

        Tras escribirlos se limpia, con la razón de la fuente verbatim:
        *"Because we don't know which properties was linked to which
        definition, we can know clean properties"*.
        """
        # Deferred the write to avoid using the old definition if it changed
        to_write = {}
        for fname in list(values):
            field = self._fields.get(fname)
            if not isinstance(field, Properties):
                continue
            field_converter = field.convert_to_cache
            to_write[fname] = dict(
                getattr(self, fname, None) or {},
                **(field_converter(values.pop(fname), self, validate=False)
                   or {}))

        self.write(values)
        if to_write:
            self.write(to_write)
            # Because we don't know which properties was linked to which
            # definition, we can know clean properties (note that it is not
            # mandatory, we can wait that client change the record in a Form
            # view)
            self._clean_properties()

    def write(self, values):
        """Escribe los valores y guarda — el ``write`` que la fuente supone.

        La referencia lo tiene en ``BaseModel``; aquí ``models.Model`` es el de
        Django, así que el mixin lo aporta para el modelo que lo adopte. Un
        modelo que ya declare su propio ``write`` —``ir_config_parameter``,
        ``properties_base_definition``— gana el suyo por MRO y éste no
        interfiere.

        La clave primaria se **descarta**, y es lo que la fuente hace de hecho:
        ``_load_records`` le pasa ``data['values']`` entero, ``'id'`` incluido,
        porque ese ``id`` es lo que acaba de **seleccionar** el registro.
        Reescribirlo es un no-op allá y aquí un ``ValueError`` de Django, así
        que se filtra en un solo sitio en vez de en cada llamador.
        """
        # ``odoo19c: odoo/orm/models.py:4379-4383``: un nombre que no es campo
        # se rechaza antes de escribir nada. Sin esto ``setattr`` lo colgaba
        # como atributo suelto y ``update_fields`` lo descartaba en silencio.
        declared = type(self)._fields
        for fname in values:
            if fname not in declared:
                model_name = getattr(type(self), '_name', self._meta.label)
                raise ValueError(
                    f"Invalid field {fname!r} in {model_name!r}")
        pk_name = self._meta.pk.name
        values = {fname: value for fname, value in values.items()
                  if fname not in (pk_name, 'id')}
        if not values:
            return True
        determine_inverses = self._group_written_inverses(values)
        self._warm_x2many_before_inverse(determine_inverses)
        protected = self._protected_while_writing(values)
        to_compute = [field.name for field in protected
                      if getattr(field, 'compute', None)
                      and field.name not in values]
        if to_compute:
            # ``:4433-4437`` — fuerza el cálculo de los campos que se computan
            # junto a los asignados pero que nadie asignó: dentro del alcance
            # de protección ya no se computarían.
            self._recompute_recordset(to_compute)
        many2many = self._pop_many2many_values(values)
        one2many = self._pop_one2many_values(values)
        reparented = _reparented(self, values)
        values, relational = self._load_records_split_relational(values)
        values = self._load_records_coerce_vals(values)
        with env().protecting(protected, self):
            if many2many:
                # La fila ya existe, así que la relación se escribe ANTES de
                # guardar: la comprobación de empresa de ``save`` ve entonces
                # todos los valores nuevos a la vez, como en la fuente.
                registry_ = model_field_registry(type(self))
                for fname, value in many2many.items():
                    apply_many2many_commands(self, registry_[fname], value)
                check_company = getattr(type(self), '_check_company_auto',
                                        False)
                if not values and check_company:
                    self._check_company(list(many2many))
            if values:
                # La fuente escribe todos los valores y comprueba la empresa
                # una vez (``BaseModel.write``); la comprobación de la
                # asignación suelta (``StoredMany2oneIdDescriptor``) se
                # suspende mientras dure este reparto.
                # ``:4459`` y ``:4484`` — los campos de ``protected`` entran en
                # la rama protegida de ``FieldDescriptor.__set__``, que escribe
                # sin anunciar; se anuncian aquí, y sólo ellos: los demás ya se
                # anuncian en ``__set__`` y la fuente no los cuenta dos veces.
                fields_written = model_field_registry(type(self))
                silenced = [fname for fname in values
                            if fields_written.get(fname) in protected]
                silenced_relations = [
                    fname for fname in silenced
                    if getattr(fields_written[fname], 'relational', False)]
                if silenced_relations:
                    self.modified(silenced_relations, before=True)
                self.__dict__[WRITING_VALUES] = True
                try:
                    for fname, value in values.items():
                        setattr(self, fname, value)
                finally:
                    self.__dict__.pop(WRITING_VALUES, None)
                # ``update_fields`` sólo admite lo que Django sabe escribir:
                # su propio ``Model.save`` valida contra este conjunto y lanza
                # *"The following fields do not exist in this model, are m2m
                # fields, primary keys, or are non-concrete fields"* ante
                # cualquier otro nombre. Un campo sin columna llega aquí por
                # ``_load_records_split_relational``, que reparte por TIPO DE
                # VALOR y no por tipo de campo, así que un ``Many2one`` sin
                # columna aterriza en ``values``. Se filtra con el mismo
                # conjunto que Django valida —no con una copia— para que no
                # haya dos fuentes de verdad.
                writable = self._meta._non_pk_concrete_field_names
                update_fields = [fname for fname in values
                                 if fname in writable]
                # ≙ ``vals.setdefault('write_date', ...)`` (``odoo19c:
                # odoo/orm/models.py:4394-4396``): con ``_log_access`` toda
                # escritura se fecha. Aquí la fecha es ``auto_now`` y la pone
                # ``pre_save``, pero un ``save`` con ``update_fields`` sólo
                # guarda lo nombrado, así que la columna se nombra.
                if (getattr(type(self), '_log_access', True)
                        and 'updated_at' in writable
                        and 'updated_at' not in update_fields):
                    update_fields.append('updated_at')
                self.save(update_fields=update_fields)
                if silenced:
                    self.modified(silenced)
            if reparented:
                _parent_store_update(self)
            if relational:
                self._load_records_apply_relational(relational)
            for rel, commands in one2many:
                # ≙ ``One2many.write_real``: la fila ya existe.
                apply_one2many_commands(self, rel, commands)
            # ``:4493`` — el inverso se despacha DENTRO del alcance de
            # protección, una vez por grupo.
            for fields in determine_inverses.values():
                fields[0].determine_inverse(self)
        return True

    def _pop_many2many_values(self, values):
        """Retira de ``values`` los ``Many2many`` escritos en la forma de la
        fuente.

        Una lista de triples de ``Command``, una lista de ids o ``False`` no se
        pueden asignar sobre el lado directo de un muchos-a-muchos de Django;
        se aplican tras guardar la fila con :func:`apply_many2many_commands`.
        Los portadores diferidos del cargador (``ManyToManySet``,
        ``ManyToManyLink``) siguen su camino propio.
        """
        registry_ = model_field_registry(type(self))
        popped = {}
        for fname in list(values):
            field = registry_.get(fname)
            value = values[fname]
            # El lado directo: un ``ManyToManyField`` (nunca ``concrete`` en
            # Django, que no tiene columna); el inverso es un
            # ``ManyToManyRel``.
            if (isinstance(field, ManyToManyField)
                    and not isinstance(value, (ManyToManySet, ManyToManyLink))
                    and (value is False or value is None
                         or is_command_list(value)
                         or isinstance(value, (list, tuple)))):
                popped[field.name] = values.pop(fname)
        return popped

    def _pop_one2many_values(self, values):
        """Retira de ``values`` los One2many escritos como lista de comandos.

        El One2many de la fuente es aquí la relación inversa de Django (un
        ``ManyToOneRel``), que no se asigna: sus comandos los aplica
        :func:`~orm.commands.apply_one2many_commands` sobre el ``Many2one``
        del comodelo, tras guardar la fila.
        """
        registry_ = model_field_registry(type(self))
        popped = []
        for fname in list(values):
            field = registry_.get(fname)
            # Sólo la relación inversa de Django: un ``fields.One2many``
            # declarado (``type == 'one2many'``) aplica sus comandos con su
            # propio descriptor al asignarse, y desde que figura en
            # ``_fields`` también aparecería aquí.
            if (getattr(field, 'one_to_many', False)
                    and not isinstance(field, Field)
                    and getattr(field, 'type', None) != 'one2many'
                    and is_command_list(values[fname])):
                popped.append((field, values.pop(fname)))
        return popped

    def _warm_x2many_before_inverse(self, determine_inverses):
        """Deja en caché el valor actual de un x2many antes de escribirlo.

        ≙ ``:4408-4416``, con su razón verbatim: *"The written value is a list
        of commands that must applied on the field's current value. Because the
        field is protected while being written, the field's current value will
        not be computed and default to an empty recordset. So make sure the
        field's value is in cache before writing, in order to avoid an
        inconsistent update."*
        """
        for fields in determine_inverses.values():
            for field in fields:
                if getattr(field, 'type', None) in ('one2many', 'many2many'):
                    getattr(self, field.name, None)

    def _protected_while_writing(self, values):
        """Los campos que no deben recomputarse mientras se escriben.

        ≙ ``protected`` (``odoo19c: odoo/orm/models.py:4401,4419-4430``), con
        su condición verbatim —``field.inverse or (field.compute and not
        field.readonly)``, acotada por ``field.store or field.type not in
        ('one2many', 'many2many')``— y su comentario: *"Protect the field from
        being recomputed while being inversed."*

        **Sin esto el inverso se despacharía dos veces**, y no por un defecto
        de la fuente sino por una divergencia nuestra: allá ``write`` asigna
        con ``field.write(self, value)`` (``:4470``) y aquí con ``setattr``,
        que entra en :meth:`~orm.fields.ComputedFieldDescriptor.__set__`. Con
        la fila ya persistida ese descriptor cae en el cubo de fila real y
        anota el inverso como pendiente; el ``save()`` de la línea siguiente lo
        despacharía, y el bucle explícito del final lo repetiría. Dentro de
        este alcance el descriptor cae en ``is_protected`` —*"no business
        logic"*— y no anota nada, así que el único despacho es el explícito.
        """
        fields_of = model_field_registry(type(self))
        protected = set()
        for fname in values:
            field = fields_of.get(fname)
            if field is None:
                continue
            if not (getattr(field, 'inverse', None)
                    or (getattr(field, 'compute', None)
                        and not getattr(field, 'readonly', False))):
                continue
            if (getattr(field, 'store', False)
                    or getattr(field, 'type', None)
                    not in ('one2many', 'many2many')):
                protected.update(
                    registry.field_computed[field]
                    if field in registry.field_computed else [field])
        return protected

    def save(self, *args, **kwargs):
        """Persiste la fila y despacha el inverso que quedó anotado.

        ≙ la mitad de ``write`` que despacha el inverso
        (``odoo19c: odoo/orm/models.py:4491-4493``), traída al único momento
        en que este stack puede ejecutarla: **después** de que la fila llegue
        a la base.

        Por qué no vive en ``write``
        ============================

        Porque la asignación directa —``company.country = mx``— nunca pasa por
        ``write``. Allá sí: ``Field.__set__`` manda la fila persistida a
        ``records.write({name: value})`` (``:1841``), así que toda escritura
        desemboca en el mismo cuerpo. Aquí el descriptor **no** puede hacerlo
        —``write`` llama a ``save()`` y emitiría un UPDATE donde la asignación
        de Django no emite ninguno (divergencia ya declarada en
        ``ComputedFieldDescriptor.__set__``)—, de modo que anota el campo y el
        despacho aterriza aquí.

        El conjunto se **saca** antes de despachar, no después: ``ResCompany``
        llama a ``super().save(update_fields=['parent_path'])`` una segunda vez
        para materializar su ruta, y sin el retiro previo ese segundo paso
        volvería a invertir lo mismo.

        Divergencia de alcance declarada: ``bulk_create`` y ``QuerySet.update``
        no pasan por aquí y por tanto no despachan inversos — como tampoco lo
        hace el ``super().write()`` de la fuente, que existe justo para
        saltarse esa mitad. Y ``BaseModel`` no hereda este mixin (``BaseModel``
        extiende ``DefaultGetMixin``, no ``RecordLoaderMixin``), así que un
        modelo construido sobre él no recoge la anotación: es la tarea
        **#318**.
        """
        super().save(*args, **kwargs)
        pending = self.__dict__.pop(PENDING_INVERSE_FIELDS, None)
        if not pending:
            return
        fields_of = model_field_registry(type(self))
        determine_inverses = collections.defaultdict(list)
        for fname in sorted(pending):
            field = fields_of.get(fname)
            if field is not None and getattr(field, 'inverse', None):
                determine_inverses[field.inverse].append(field)
        for fields in determine_inverses.values():
            fields[0].determine_inverse(self)

    def _group_written_inverses(self, values):
        """Los campos escritos que declaran inverso, agrupados POR METODO.

        ≙ ``determine_inverses = defaultdict(list)  # {inverse: fields}``
        (``odoo19c: odoo/orm/models.py:4399``), poblado en ``:4416`` con
        ``determine_inverses[field.inverse].append(field)``.

        La agrupacion no es cosmetica: la fuente llama al inverso **una vez por
        grupo** —``fields[0].determine_inverse(real_recs)`` (``:4493``)— porque
        un mismo metodo puede invertir varios campos a la vez y llamarlo N
        veces repetiria su efecto. Escribir ``email_from`` y ``phone`` en la
        misma llamada da dos grupos y dos invocaciones; si ambos declararan el
        mismo metodo, daria una.

        Se calcula **antes** de partir los valores en columna y relacion,
        porque la fuente recorre ``vals`` entero: un campo relacional con
        inverso cuenta igual que uno con columna.

        DIVERGENCIA DE MECANISMO declarada: la fuente lee ``self._fields``;
        aqui el registro equivalente es
        :func:`~orm.utils.model_field_registry`, que ya cubre el campo con
        columna y el que no la tiene. Y donde ella lanza ``ValueError`` ante un
        nombre desconocido, aqui se ignora: ``write`` de este arbol acepta
        nombres que ``save``/``_load_records_apply_relational`` resuelven por
        otras vias, y adelantar ese rechazo cambiaria el contrato de un metodo
        que no es el de esta tarea.
        """
        fields_of = model_field_registry(type(self))
        determine_inverses = collections.defaultdict(list)
        for fname in values:
            field = fields_of.get(fname)
            if field is not None and getattr(field, 'inverse', None):
                determine_inverses[field.inverse].append(field)
        return determine_inverses

    @classmethod
    def _write_rows_skipping_save(cls, queryset, values):
        """Escribe ``values`` sobre las filas de ``queryset`` sin pasar por
        ``save()`` — ≙ el ``super().write(vals)`` de la fuente.

        Por qué existe, y por qué no basta ``QuerySet.update()``
        =======================================================

        La fuente usa ``super().write(...)`` cuando quiere escribir **sin**
        re-entrar en el ``write`` sobrecargado que volvería a sincronizar
        (``odoo19c: res_partner.py:677-683`` es el caso de manual). Su análogo
        en este stack es ``QuerySet.update()``: no invoca ``save()`` ni emite
        señales.

        Pero ``update()`` compone un ``UPDATE`` y por tanto **sólo sabe de
        columnas**: un campo sin columna —el ``store=False`` de la fuente, aquí
        el descriptor sin columna (retirado en TASK-API-0418)— le levanta
        ``FieldDoesNotExist``. Allá no hay tal frontera: ``write`` acepta todo
        campo del modelo, tenga columna o no. Sin esta separación, cualquier
        addon que añada un campo sin columna a una lista que luego se escribe
        en bloque revienta a su consumidor — que es lo que ``city_id`` de
        ``base_address_extended`` hizo sobre 35 casos (:ref:`h-api-1025`).

        El reparto es por registro, no por SQL: el descriptor de un campo sin
        columna sabe dónde vive su valor, y escribirlo por ``setattr`` es
        llamarlo. Eso no re-entra en ``save()`` del modelo que se está
        escribiendo, así que la garantía de la fuente —no volver a
        sincronizar— se conserva.
        """
        without_column = non_stored_fields(cls)
        columns = {name: value for name, value in values.items()
                   if name not in without_column}
        projected = {name: value for name, value in values.items()
                     if name in without_column}
        if columns:
            queryset.update(**columns)
        if projected:
            for record in queryset:
                for name, value in projected.items():
                    setattr(record, name, value)

    @classmethod
    def _create_row_from_values(cls, values, using=None):
        """Crea la fila aceptando **todo** campo del modelo — ≙
        ``create(vals)``.

        Es la cara de alta de la misma frontera que
        :meth:`_write_rows_skipping_save` cubre en la escritura. El
        ``Model.__init__`` de Django rechaza con ``TypeError`` cualquier
        argumento que no sea una columna suya, y allá ``create`` acepta todo
        campo declarado — un ``store=False`` incluido. Sin esta separación,
        pasarle a ``objects.create`` un diccionario derivado de una lista de
        campos —``_address_fields()``, por ejemplo— revienta en cuanto un addon
        mete en esa lista un campo que aquí no tiene columna
        (:ref:`h-api-1025`).

        El orden importa y es el de la fuente: la fila se crea primero con lo
        que tiene columna, y el campo sin columna se escribe **después**, con
        la fila ya real. Su descriptor puede necesitar la clave para colgar de
        ella lo que respalda su valor, igual que un ``One2many`` necesita el
        padre guardado.
        """
        without_column = non_stored_fields(cls)
        columns = {name: value for name, value in values.items()
                   if name not in without_column}
        projected = {name: value for name, value in values.items()
                     if name in without_column}
        # Sin alias pedido, la base del entorno activo (``env.cr``); fuera de
        # todo entorno con alias, ``default`` como antes.
        using = using or get_current_cr() or DEFAULT_DB_ALIAS
        record = cls.objects.using(using).create(**columns)
        for name, value in projected.items():
            setattr(record, name, value)
        return record

    @classmethod
    def _load_records_split_relational(cls, values):
        """Separa lo que se escribe en la fila de lo que se escribe
        **después**.

        Es la contraparte de la divergencia que ``ir_fields`` declara: la
        fuente devuelve ``Command`` diferidos y su ``write`` los interpreta; el
        ``Command`` de este árbol es ejecutivo (:ref:`h-api-589`, tarea
        **TASK-API-0190**), así que el valor viaja en
        :class:`~orm.commands.ManyToManySet`,
        :class:`~orm.commands.ManyToManyLink` y
        :class:`~orm.commands.One2manyChild`, y es aquí donde se aparta.

        El aparte no es una comodidad: Django **exige** que la fila exista
        antes de tocar una relación de muchos (``Direct assignment to the
        forward side of a many-to-many set is prohibited``). Lo mismo vale para
        el hijo de un ``One2many``, que necesita la clave del padre.
        """
        scalar, relational = {}, {}
        for fname, value in values.items():
            if isinstance(value, (ManyToManySet, ManyToManyLink)):
                relational[fname] = value
            elif (isinstance(value, list) and value
                    and all(isinstance(item, One2manyChild)
                            for item in value)):
                relational[fname] = value
            else:
                scalar[fname] = value
        return scalar, relational

    def _load_records_apply_relational(self, relational):
        """Aplica lo que la fila ya existente admite: el conjunto y los hijos.

        Los tres verbos son los de ``Command`` en la fuente, con el del ORM de
        este lado: ``set`` reemplaza el conjunto, ``add`` lo amplía, y un hijo
        con id se **actualiza** mientras que uno sin id se **crea** apuntando
        al padre.
        """
        for fname, value in relational.items():
            manager = getattr(self, fname)
            if isinstance(value, ManyToManySet):
                manager.set([id for id in value if id])
            elif isinstance(value, ManyToManyLink):
                manager.add(*[id for id in value if id])
            else:
                for child in value:
                    if child.id:
                        existing = manager.get(pk=child.id)
                        existing.write(child.values)
                    else:
                        coerce = manager.model._load_records_coerce_vals
                        manager.create(**coerce(child.values))

    @classmethod
    def _load_records_create(cls, vals_list, using=DEFAULT_DB_ALIAS):
        """≙ ``_load_records_create`` (``odoo19c: :5102-5106``).

        Crea los registros y, si el modelo tiene algún campo de propiedades,
        los limpia. La guarda ``any(...)`` de la fuente se conserva: recorrer
        los campos una vez es más barato que llamar a ``_clean_properties`` por
        registro cuando el modelo no tiene ninguno.

        Es el símbolo que ``ResPartner._load_records_create`` sobreescribe
        (``odoo19c: res_partner.py:988``): el enganche que el cargador ofrece
        para que un modelo intervenga en la creación desde datos.
        """
        records = []
        for vals in vals_list:
            scalar, relational = cls._load_records_split_relational(vals)
            record = cls.objects.using(using).create(
                **cls._load_records_coerce_vals(scalar))
            if relational:
                record._load_records_apply_relational(relational)
            records.append(record)
        if any(isinstance(field, Properties)
               for field in cls._meta.get_fields()):
            for record in records:
                record._clean_properties()
        return records

    # -- El cargador de archivos ---------------------------------------------

    @classmethod
    def _sql_error_to_message(cls, exc):
        """≙ ``_sql_error_to_message`` (``odoo19c: :3269-3285``).

        «Convert a database exception to a user error message depending on the
        model.»

        El orden de la fuente: si la restricción violada es un objeto de tabla
        de este modelo, primero el mensaje que su fila de
        ``ir.model.constraint`` registra para este modelo, después el que el
        objeto declara; si no, el mensaje genérico.

        El error llega aquí como el ``DatabaseError`` de Django, y el
        diagnóstico de PostgreSQL vive en su ``__cause__``
        (:func:`_database_error`): leer ``exc.diag`` no veía nunca el nombre
        de la restricción. Los objetos de tabla tienen su hogar en
        ``Meta.constraints`` (``atributos-de-clase-de-modelo.md``).
        """
        diag = getattr(_database_error(exc), 'diag', None)
        constraint_name = getattr(diag, 'constraint_name', None)
        cons = _table_object(cls, constraint_name)
        if cons is not None:
            IrModelConstraint = apps.get_model('base', 'IrModelConstraint')
            message = IrModelConstraint.objects.filter(
                name=constraint_name, model__model=_model_name(cls),
            ).values_list('message', flat=True).first()
            if message:
                return message
            # get the message from the object
            if message := _table_object_message(cons, cls, diag):
                return message
        return cls._sql_error_to_message_generic(exc)

    @classmethod
    def _sql_error_to_message_generic(cls, exc):
        """ Convert a database exception to a generic user error message. —
        ≙ ``_sql_error_to_message_generic`` (``odoo19c: :3287-3339``)

        Copia adaptada. El modelo se nombra por ``ir.model`` o por su
        ``_description``, la columna por el campo cuya ``column`` es la del
        diagnóstico —aquí el nombre del campo y el de su columna pueden
        diferir (``privilege`` y ``privilege_id``)—, y la clase del error se
        pregunta al error de psycopg, no al envoltorio de Django.
        """
        error = _database_error(exc)
        diag = error.diag
        environment = env()
        unknown = environment._('Unknown')
        name = _model_name(cls)
        IrModel = apps.get_model('base', 'IrModel')
        ir_model = IrModel._get(name)
        model_string = (ir_model and ir_model.name) or getattr(
            cls, '_description', None) or cls._meta.verbose_name
        info = {
            'model_display': f"'{model_string}' ({name})",
            'table_name': diag.table_name,
            'constraint_name': diag.constraint_name,
        }
        connection = connections[cls.objects.db]
        if cls._meta.db_table == diag.table_name:
            columns = get_columns_from_sql_diagnostics(
                connection, diag, check_registry=True)
        else:
            columns = get_columns_from_sql_diagnostics(connection, diag)
            info['model_display'] = unknown
        fields = {field.column: field
                  for field in cls._meta.concrete_fields}
        if not columns:
            info['field_display'] = unknown
        elif len(columns) == 1 and (field := fields.get(columns[0])):
            field_string = field._description_string(environment)
            info['field_display'] = f"'{field_string}' ({field.name})"
        else:
            info['field_display'] = f"'{format_list(environment, columns)}'"

        if isinstance(error, pg_errors.NotNullViolation):
            return environment._(
                "Missing required value for the field %(field_display)s.\n"
                "Model: %(model_display)s\n"
                "- create/update: a mandatory field is not set\n"
                "- delete: another model requires the record being deleted, "
                "you can archive it instead\n",
                **info,
            )

        if isinstance(error, pg_errors.ForeignKeyViolation):
            if len(columns) != 1:
                info['field_display'] = info['constraint_name']
            return environment._(
                "Another model is using the record you are trying to "
                "delete.\n\n"
                "The troublemaker is: %(model_display)s\n"
                "Thanks to the following constraint: %(field_display)s\n"
                "How about archiving the record instead?",
                **info,
            )

        if isinstance(error, pg_errors.UniqueViolation) and columns:
            column_names = [fields[f].string if f in fields else f
                            for f in columns]
            info['field_display'] = (
                f"'{', '.join(columns)}' "
                f"({format_list(environment, column_names)})")
            # contains conflicting key and value
            info['detail'] = diag.message_detail
            return environment._(
                "The value for %(field_display)s already exists.\n\n"
                "Detail: %(detail)s\n", **info)

        # No good message can be created for psycopg2.errors.CheckViolation

        # fallback
        return exception_to_unicode(error)

    @classmethod
    def _extract_records(cls, field_paths, data, log=lambda a: None,
                         limit=float('inf')):
        """≙ ``_extract_records`` (``odoo19c: :1075-1195``).

        «Generates record dicts from the data sequence.»

        Recorre la matriz **por filas** y devuelve un dict por registro. Lo que
        hace no trivial este método es que un registro puede ocupar **varias
        filas**: las que siguen a la suya con valores sólo en columnas
        ``One2many`` le pertenecen. Esa es la regla que ``only_o2m_values``
        codifica y por la que el avance del índice es ``len(record_span)`` y no
        uno.

        Las tres claves especiales de la fuente se conservan: ``None`` es la
        etiqueta visible del registro, ``id`` su identificador externo y
        ``.id`` su id de base.
        """
        fields = {field.name: field for field in cls._meta.get_fields()
                  if hasattr(field, 'name')}

        def is_one2many(fname):
            field = fields.get(fname)
            return field is not None and getattr(field, 'one_to_many', False)

        get_o2m_values = itemgetter_tuple([
            index
            for index, fnames in enumerate(field_paths)
            if is_one2many(fnames[0])
        ])
        get_nono2m_values = itemgetter_tuple([
            index
            for index, fnames in enumerate(field_paths)
            if not is_one2many(fnames[0])
        ])

        # Checks if the provided row has any non-empty one2many fields
        def only_o2m_values(row):
            return any(get_o2m_values(row)) and not any(get_nono2m_values(row))

        for fname, *__ in field_paths:
            if not fname or '.' in fname:
                continue
            if fname not in fields and fname not in REFERENCING_FIELD_NAMES:
                raise ValueError(f'Invalid field name {fname!r}')

        # m2o fields can't be on multiple lines so don't take it in account
        # for only_o2m_values rows filter, but special-case it later on to
        # be handled with relational fields (as it can have subfields).
        def is_relational(fname):
            field = fields.get(fname)
            return field is not None and field.is_relation

        index = 0
        while index < len(data) and index < limit:
            row = data[index]

            # copy non-relational fields to record dict
            record = {
                fnames[0]: value
                for fnames, value in zip(field_paths, row)
                if not is_relational(fnames[0])
            }

            # Get all following rows which have relational values attached to
            # the current record (no non-relational values)
            record_span = itertools.takewhile(
                only_o2m_values,
                (data[j] for j in range(index + 1, len(data))),
            )
            # stitch record row back on for relational fields
            record_span = list(itertools.chain([row], record_span))

            for relfield, *__ in field_paths:
                if not is_relational(relfield):
                    continue

                comodel = fields[relfield].related_model

                # get only cells for this sub-field, should be strictly
                # non-empty, field path [None] is for display_name field
                indices, subfields = zip(*(
                    (position, fnames[1:] or [None])
                    for position, fnames in enumerate(field_paths)
                    if fnames[0] == relfield))

                # return all rows which have at least one value for the
                # subfields of relfield
                relfield_data = [it for it
                                 in map(itemgetter_tuple(indices), record_span)
                                 if any(it)]
                record[relfield] = [
                    subrecord
                    for subrecord, _subinfo
                    in comodel._extract_records(subfields, relfield_data,
                                                log=log)
                ]

            yield record, {'rows': {
                'from': index,
                'to': index + len(record_span) - 1,
            }}
            index += len(record_span)

    @classmethod
    def _convert_records(cls, records, *, log=lambda a: None, savepoint):
        """≙ ``_convert_records`` (``odoo19c: :1198-1251``).

        «Converts records from the source iterable (recursive dicts of strings)
        into forms which can be written to the database.»

        :returns: una tupla ``(dbid, xid, convertido, info)`` por registro.

        El ``.id`` se valida **contra la base** antes de aceptarlo: la fuente
        registra un error y lo descarta si el registro no existe, en vez de
        dejar que el fallo salga como violación de clave ajena tres pasos más
        tarde.
        """
        converter_cls = registry.model_by_name('ir.fields.converter')
        field_names = {field.name: str(getattr(field, 'verbose_name',
                                               field.name))
                       for field in cls._meta.get_fields()
                       if hasattr(field, 'name')}

        convert = converter_cls.for_model(cls, savepoint=savepoint)

        def _log(base, record, field, exception):
            type = 'warning' if isinstance(exception, Warning) else 'error'
            # logs the logical (not human-readable) field name for automated
            # processing of response, but injects human readable in message
            field_name = field_names.get(field, field)
            exc_vals = dict(base, record=record, field=field_name)
            record = dict(base, type=type, record=record, field=field,
                          message=str(exception.args[0]) % exc_vals)
            if len(exception.args) > 1:
                info = {}
                if exception.args[1] and isinstance(exception.args[1], dict):
                    info = exception.args[1]
                # ensure field_name is added to the exception. Used in import
                # to concatenate multiple errors in the same block
                info['field_name'] = field_name
                record.update(info)
            log(record)

        for stream_index, (record, extras) in enumerate(records):
            # xid
            xid = record.get('id', False)
            # dbid
            dbid = False
            if record.get('.id'):
                try:
                    dbid = int(record['.id'])
                except ValueError:
                    # in case of overridden id column
                    dbid = record['.id']
                if not cls.objects.filter(pk=dbid).exists():
                    log(dict(extras,
                             type='error',
                             record=stream_index,
                             field='.id',
                             message="Identificador de base desconocido '%s'"
                                     % dbid))
                    dbid = False

            converted = convert(record,
                                functools.partial(_log, extras, stream_index))

            yield dbid, xid, converted, dict(extras, record=stream_index)

    @classmethod
    def load(cls, fields, data, using=DEFAULT_DB_ALIAS):
        """≙ ``load`` (``odoo19c: :895-1073``).

        «Attempts to load the data matrix, and returns a list of ids (or
        ``False`` if there was an error and no id could be generated) and a
        list of messages.»

        :param fields: los campos a importar, en el orden de las columnas.
        :param data: la matriz de datos, por filas. :returns:
        ``{'ids': [...] | False, 'messages': [...], 'nextrow': int}``.

        Las tres decisiones de la fuente que definen su comportamiento:

        - **Se intenta en lote y, si falla, uno por uno.** El lote es el camino
          rápido; el recorrido fila a fila es el que puede decir *cuál* falló.
          El error del lote se guarda y se antepone al informe si el segundo
          intento tampoco crea nada, porque a veces sólo el conjunto es
          inválido.
        - **Cada fallo vuelve al punto de retorno.** Sin eso la transacción
          queda abortada en PostgreSQL y el resto del archivo ya no se puede
          importar — es lo que :class:`service.db.Savepoint` existe para dar.
        - **El recorrido se corta a los diez errores** si además hay más de uno
          por cada diez filas, con el aviso de la fuente: un archivo con el
          formato equivocado produciría un informe ilegible.

        Si hubo **algún** error, se deshace todo y ``ids`` es ``False``: una
        importación es completa o no es.
        """
        converter_cls = registry.model_by_name('ir.fields.converter')
        converter_cls._selection_translation_cache.clear()

        context = get_context()
        # determine values of mode, current_module and noupdate
        mode = context.get('mode', 'init')
        current_module = context.get('module', '__import__')
        noupdate = context.get('noupdate', False)

        connection = connections[using]
        savepoint = Savepoint(connection)

        fields = [fix_import_export_id_paths(f) for f in fields]

        ids = []
        messages = []

        # list of (xid, vals, info) for records to be created in batch
        batch = []
        batch_xml_ids = set()
        # models in which we may have created / modified data, therefore might
        # require flushing in order to name_search: the root model and any o2m
        creatable_models = {cls}
        for field_path in fields:
            if field_path[0] in (None, 'id', '.id'):
                continue
            model = cls
            for field_name in field_path:
                if field_name in (None, 'id', '.id'):
                    break
                try:
                    field = model._meta.get_field(field_name)
                except (FieldDoesNotExist, AttributeError):
                    break
                if getattr(field, 'one_to_many', False):
                    model = field.related_model
                    creatable_models.add(model)

        def flush(*, xml_id=None, model=None):
            if not batch:
                return

            assert not (xml_id and model), (
                'flush can specify *either* an external id or a model, '
                'not both')

            if model and model not in creatable_models:
                return

            data_list = [
                dict(xml_id=xid, values=vals, info=info, noupdate=noupdate)
                for xid, vals, info in batch
            ]
            batch.clear()
            batch_xml_ids.clear()

            # try to create in batch
            global_error_message = None
            try:
                with Savepoint(connection):
                    recs = cls._load_records(data_list, mode == 'update',
                                             using=using)
                    ids.extend(record.pk for record in recs)
                return
            except UserError as exc:
                global_error_message = dict(data_list[0]['info'], type='error',
                                            message=str(exc))
            except Exception:
                # silent OK because el lote es el camino rápido y su fallo NO
                # es el resultado: el recorrido fila a fila de abajo vuelve a
                # intentarlo y es el que puede decir CUÁL falló. Tragarlo aquí
                # es lo que la fuente hace, y por eso mismo
                # (``odoo19c: odoo/orm/models.py:980-981``).
                pass

            errors = 0
            # try again, this time record by record
            for i, rec_data in enumerate(data_list, 1):
                try:
                    [rec] = cls._load_records([rec_data], mode == 'update',
                                              using=using)
                    ids.append(rec.pk)
                except DatabaseError as exc:
                    savepoint.rollback()
                    info = rec_data['info']
                    pg_error_info = {'message': cls._sql_error_to_message(exc)}
                    diag = getattr(exc.__cause__, 'diag', None)
                    if (diag is not None
                            and diag.table_name == cls._meta.db_table):
                        e_fields = get_columns_from_sql_diagnostics(
                            connection, diag, check_registry=True)
                        if len(e_fields) == 1:
                            pg_error_info['field'] = e_fields[0]
                    messages.append(dict(info, type='error', **pg_error_info))
                    # Failed to write, log to messages, rollback savepoint (to
                    # avoid broken transaction) and keep going
                    errors += 1
                except UserError as exc:
                    savepoint.rollback()
                    messages.append(dict(rec_data['info'], type='error',
                                         message=str(exc)))
                    errors += 1
                except Exception as exc:
                    savepoint.rollback()
                    _logger.debug('Error while loading record', exc_info=True)
                    messages.append(dict(
                        rec_data['info'], type='error',
                        message='Error desconocido durante la importación: '
                                '%s: %s' % (exc.__class__, exc),
                        moreinfo='Resuelve los otros errores primero'))
                    # Failed for some reason, perhaps due to invalid data
                    # supplied, rollback savepoint and keep going
                    errors += 1
                if errors >= 10 and (errors >= i / 10):
                    messages.append({
                        'type': 'warning',
                        'message': 'Más de 10 errores y más de uno por '
                                   'cada 10 registros: se interrumpe para '
                                   'no mostrar demasiados errores.',
                    })
                    break
            if errors > 0 and global_error_message \
                    and global_error_message not in messages:
                # If we cannot create the records 1 by 1, we display the error
                # raised when we created the records simultaneously
                messages.insert(0, global_error_message)

        # make 'flush' available to the methods below, in the case where XMLID
        # resolution fails, for instance
        limit = context.get('_import_limit')
        if limit is None:
            limit = float('inf')

        with context_scope(_import_current_module=current_module,
                           import_flush=flush, import_cache={}):
            extracted = cls._extract_records(fields, data,
                                             log=messages.append, limit=limit)
            converted = list(cls._convert_records(
                extracted, log=messages.append, savepoint=savepoint))

            info = {'rows': {'to': -1}}
            for id, xid, record, info in converted:
                if xid:
                    if '.' not in xid:
                        xid = '%s.%s' % (current_module, xid)
                    batch_xml_ids.add(xid)
                elif id:
                    record['id'] = id
                batch.append((xid, record, info))

            flush()

        if any(message['type'] == 'error' for message in messages):
            savepoint.rollback()
            ids = False
        savepoint.close(rollback=False)

        nextrow = info['rows']['to'] + 1
        if nextrow < limit:
            nextrow = 0
        return {
            'ids': ids,
            'messages': messages,
            'nextrow': nextrow,
        }

    # -- El cargador ---------------------------------------------------------

    @classmethod
    def _load_records(cls, data_list, update=False, using=DEFAULT_DB_ALIAS):
        """≙ ``_load_records`` (``odoo19c: :5108-5213``).

        Docstring de la fuente, verbatim: *"Create or update records of this
        model, and assign XMLIDs."*

        :param data_list: lista de dicts con ``xml_id`` (el identificador a
            asignar), ``noupdate`` (su bandera) y ``values`` (los valores).
        :param update: ``True`` al **actualizar** un módulo.
        :return: los registros correspondientes a ``data_list``.

        Los dos avisos de contexto de la fuente se portan y siguen leyendo del
        contexto, que aquí es ``tools.misc``/``orm.environments`` en vez del
        ``env.context``: ``install_module`` (avisa de un ``xml_id`` de otro
        módulo) e ``import_file`` (rechaza un prefijo que coincida con un
        módulo instalado, porque la próxima actualización borraría el
        registro).
        """
        IrModelData = apps.get_model('base', 'IrModelData')

        # determine existing xml_ids
        xml_ids = [data['xml_id'] for data in data_list if data.get('xml_id')]
        existing = {
            ('%s.%s' % row[1:3]): row
            for row in IrModelData._lookup_xmlids(xml_ids, cls, using=using)
        }

        # determine which records to create and update
        to_create = []                  # list of data
        to_update = []                  # list of data
        imd_data_list = []              # list of data for _update_xmlids()

        for data in data_list:
            xml_id = data.get('xml_id')
            if not xml_id:
                vals = data['values']
                if vals.get('id'):
                    data['record'] = cls.objects.using(using).get(
                        pk=vals['id'])
                    to_update.append(data)
                elif not update:
                    to_create.append(data)
                else:
                    raise ValidationError(
                        'Cannot update a record without specifying its id or '
                        'xml_id')
                continue
            row = existing.get(xml_id)
            if not row:
                to_create.append(data)
                continue
            d_id, _d_module, _d_name, d_model, d_res_id, d_noupdate, r_id = row
            if cls._meta.label != d_model:
                raise ValidationError(
                    f'For external id {xml_id} '
                    f'when trying to create/update a record of model '
                    f'{cls._meta.label} '
                    f'found record of different model {d_model} ({d_id})')
            if r_id:
                data['record'] = cls.objects.using(using).get(pk=d_res_id)
                imd_data_list.append(data)
                if not (update and d_noupdate):
                    to_update.append(data)
            else:
                IrModelData.objects.using(using).filter(pk=d_id).delete()
                to_create.append(data)

        # update existing records
        for data in to_update:
            data['record']._load_records_write(data['values'])

        # check for records to create with an XMLID from another module
        context = get_context()
        module = context.get('install_module')
        if module:
            prefix = module + '.'
            for data in to_create:
                xml_id = data.get('xml_id')
                if (xml_id and not xml_id.startswith(prefix)
                        and not context.get('foreign_record_to_create')):
                    _logger.warning('Creating record %s in module %s.',
                                    data['xml_id'], module)

        if context.get('import_file'):
            IrModule = apps.get_model('base', 'IrModule')
            existing_modules = set(IrModule.objects.using(using).values_list(
                'name', flat=True))
            for data in to_create:
                xml_id = data.get('xml_id')
                if xml_id and not data.get('noupdate'):
                    module_name, sep, record_id = xml_id.partition('.')
                    if sep and module_name in existing_modules:
                        raise UserError(
                            f'The record {xml_id} has the module prefix '
                            f'{module_name}. This is the part before the "." '
                            f'in the external id. Because the prefix refers '
                            f'to an existing module, the record would be '
                            f'deleted '
                            f'when the module is upgraded. Use either no '
                            f'prefix and no dot or a prefix that is not an '
                            f'existing module. For example, __import__, '
                            f'resulting in the external id '
                            f'__import__.{record_id}.')

        # create records
        if to_create:
            records = cls._load_records_create(
                [data['values'] for data in to_create], using=using)
            for data, record in zip(to_create, records):
                data['record'] = record
                if data.get('xml_id'):
                    # add XML ids for parent records that have just been
                    # created ``_inherits`` se lee del atributo de clase, que
                    # es donde la referencia lo declara y donde este árbol lo
                    # porta verbatim (tarea #385).
                    for parent_model, parent_field in getattr(
                            cls, '_inherits', {}).items():
                        if not data['values'].get(parent_field):
                            imd_data_list.append({
                                'xml_id': f"{data['xml_id']}_"
                                          f"{parent_model.replace('.', '_')}",
                                'record': getattr(record, parent_field),
                                'noupdate': data.get('noupdate', False),
                            })
                    imd_data_list.append(data)

        # create or update XMLIDs
        IrModelData._update_xmlids(imd_data_list, update, using=using)

        return [data['record'] for data in data_list]

    @classmethod
    def _check_parent_path(cls):
        """≙ ``BaseModel._check_parent_path`` (``odoo19c: odoo/orm/models.py:
        3255-3260``), con sus dos mensajes verbatim.

        La referencia los registra en el log desde ``_auto_init``; aquí son
        ``checks.Error`` de Django, que es donde este árbol valida un modelo
        al cargar. Divergencia declarada: bloquean ``manage.py check``,
        porque un ``_parent_store`` sin columna rompe ``child_of``.
        """
        name = getattr(cls, '_name', None) or cls._meta.label_lower
        try:
            field = cls._meta.get_field('parent_path')
        except FieldDoesNotExist:
            return [checks.Error(
                "add a field parent_path on model %r: `parent_path = "
                "fields.Char(index=True)`." % name, obj=cls,
                id='orm.E101')]
        if not (getattr(field, 'index', None) or field.db_index):
            return [checks.Error(
                "parent_path field on model %r should be indexed! Add "
                "index=True to the field definition." % name, obj=cls,
                id='orm.E102')]
        return []

    @classmethod
    def check(cls, **kwargs):
        """El ``check`` de Django más ``_check_parent_path`` para un modelo
        con ``_parent_store`` — el punto de ``_auto_init`` (``:3214``)."""
        errors = super().check(**kwargs)
        if getattr(cls, '_parent_store', False):
            errors += cls._check_parent_path()
        return errors


def search_display_name(model_cls, operator, value):
    """La implementación base de ``_search_display_name``, como función.

    Existe por una divergencia **de vía**, no de alcance. En la fuente el
    método cuelga de ``BaseModel``, así que una sobrescritura delega con
    ``super()`` y siempre lo encuentra. Aquí el bloque ``display_name`` llega
    por dos caminos distintos —herencia de :class:`DisplayNameMixin` para la
    mayoría, e inyección de :func:`orm.model_classes.adopt_display_name` para
    los que declaran su propia base— y en el segundo **``super()`` no lo ve**:
    el mixin no está en el MRO.

    Medido: de los tres modelos que sobrescriben este método en ``base``, dos
    —``ResBank`` y ``ResCurrencyRate``— tienen el bloque inyectado y sólo uno
    lo hereda. Una delegación con ``super()`` funcionaría en un tercio de los
    casos, que es peor que no funcionar en ninguno: falla sólo para algunos
    operadores de algunos modelos.

    Por eso la implementación base es una función y el ``classmethod`` la
    invoca. Una sobrescritura que quiera delegar la llama por su nombre, y
    funciona por los dos caminos.
    """
    cls = model_cls
    rec_names = getattr(cls, '_rec_names_search', None)
    if isinstance(rec_names, property):
        # La fuente lo declara a veces como propiedad (``sale.order``,
        # ``odoo19c: sale_order.py:46-50``) y la lee sobre el recordset. Aquí
        # el método recibe la clase, que es lo que ``env['x']`` devuelve, y
        # leer el atributo sobre la clase da el objeto ``property``: la
        # búsqueda moría con ``'property' object is not iterable``. Se evalúa
        # sobre la clase; el cuerpo de la fuente sólo lee el contexto.
        rec_names = rec_names.fget(cls)
    search_fnames = (rec_names
                     or ([cls._rec_name] if getattr(cls, '_rec_name', None)
                         else []))
    if not search_fnames:
        _logger.warning(
            'No se puede buscar por display_name: %s no declara _rec_name '
            'ni _rec_names_search', cls._meta.label)
        return Domain.TRUE
    # ≙ ``Domain.NEGATIVE_OPERATORS``: incluye ``not in``, que la tercera
    # copia local de abajo no lleva y que combina con AND, no con OR
    negative = operator in Domain.NEGATIVE_OPERATORS
    if operator.endswith('like') and not value and '=' not in operator:
        return Domain.FALSE if negative else Domain.TRUE

    combine = Domain.AND if negative else Domain.OR
    record = cls.browse(()) if hasattr(cls, '_from_ids') else None
    domains = []
    for field_name in search_fnames:
        # un camino ``partner_id.name``: el campo es el último del camino
        model = cls
        try:
            for fname in field_name.split('.'):
                # un modelo de Django sin ``_fields`` lo resuelve por ``_meta``
                fields = getattr(model, '_fields', None)
                field = (fields[fname]
                         if fields is not None and fname in fields
                         else model._meta.get_field(fname))
                model = getattr(field, 'related_model', None)
        except (KeyError, AttributeError, FieldDoesNotExist):
            # silent OK because el nombre llega por delegación de ``_inherits``
            # (``res.users.name`` es del partner) y no es campo de este
            # modelo: la condición va sin convertir y la resuelve el dominio
            domains.append(Domain(field_name, operator, value))
            continue
        # según el operador el valor se convierte al tipo del campo, y el
        # que no convierte se descarta
        if getattr(field, 'is_relation', False):
            # un relacional busca por el ``display_name`` del comodelo
            domains.append(Domain(field_name + '.display_name', operator,
                                  value))
        elif operator.endswith('like'):
            domains.append(Domain(field_name, operator, value))
        elif isinstance(value, COLLECTION_TYPES):
            typed_value = []
            for item in value:
                with contextlib.suppress(ValueError, TypeError):
                    typed_value.append(field.convert_to_write(item, record))
            domains.append(Domain(field_name, operator, typed_value))
        else:
            with contextlib.suppress(ValueError):
                typed_value = field.convert_to_write(value, record)
                domains.append(Domain(field_name, operator, typed_value))
            continue
        with contextlib.suppress(ValueError, TypeError):
            # se descarta si el valor entero no es del tipo del campo
            # con ``like`` sobre un texto la condición se añade dos veces,
            # como en la fuente: su ``Domain.OR`` no las reduce al construir
            domains.append(Domain(field_name, operator,
                                  field.convert_to_write(value, record)))
    return combine(domains)


class OrderMixin:
    """``_check_qorder`` — la cláusula de orden se valida antes de usarse.

    ≙ ``BaseModel._check_qorder`` (``odoo19c: odoo/orm/models.py:5215-5222``).
    Su única razón de existir es que un ``_order`` llega como **texto** —de una
    fila de ``ir.model``, de un contexto, de un parámetro— y acaba interpolado
    en un ``ORDER BY``. La comprobación es lo que separa un nombre de campo de
    una inyección.

    **La divergencia es de VÍA, no de alcance**, y es la misma que
    :class:`DisplayNameMixin` y :class:`FieldSqlMixin` ya declaran: allá cuelga
    de ``BaseModel``, así que todo modelo lo tiene; aquí ``models.Model`` es el
    de Django y no es nuestro para colgarle nada. Lo adopta
    ``TimeStampedModel``, que es la base común del proyecto, y también
    :class:`BaseModel`: su ``_search`` ordena con :meth:`_order_to_sql`, y un
    modelo que hereda de ``BaseModel`` sin ``TimeStampedModel``
    (``ir.attachment``) se quedaba sin él.
    """

    def _check_qorder(self, word):
        """Levanta ``UserError`` si ``word`` no es una cláusula de orden
        válida.

        Cuerpo verbatim de la fuente, con su mensaje: *"Invalid 'order'
        specified (%s). A valid 'order' specification is a comma-separated list
        of valid field names (optionally followed by asc/desc for the
        direction)"*.
        """
        if not regex_order.match(word):
            raise UserError(
                'Orden inválido (%s). Un orden válido es una lista de nombres '
                'de campo separados por coma, cada uno seguido opcionalmente '
                'de asc o desc.' % word)

    def _order_to_sql(self, order, query, alias=None, reverse=False):
        """ Return an :class:`SQL` object that represents the given ORDER BY
        clause, without the ORDER BY keyword.  The method also checks whether
        the fields in the order are accessible for reading.
        — ≙ ``odoo19c: odoo/orm/models.py:5224-5260``
        """
        order = order or self._order
        if not order:
            return SQL()
        self._check_qorder(order)

        alias = alias or self._table

        terms = []
        for order_part in order.split(','):
            order_match = regex_order.match(order_part)
            assert order_match is not None, "No match found"
            field_name = order_match['field']

            direction = (order_match['direction'] or '').upper()
            nulls = (order_match['nulls'] or '').upper()
            if reverse:
                direction = 'ASC' if direction == 'DESC' else 'DESC'
                if nulls:
                    nulls = ('NULLS LAST' if nulls == 'NULLS FIRST'
                             else 'NULLS FIRST')

            sql_direction = (SQL(direction) if direction in ('ASC', 'DESC')
                             else SQL())
            sql_nulls = (SQL(nulls) if nulls in ('NULLS FIRST', 'NULLS LAST')
                         else SQL())

            if property_name := order_match['property']:
                # field_name es una expresión
                field_name = f"{field_name}.{property_name}"
            term = self._order_field_to_sql(
                alias, field_name, sql_direction, sql_nulls, query)
            if term:
                terms.append(term)

        return SQL(", ").join(terms)

    def _order_field_to_sql(self, alias, field_name, direction, nulls, query):
        """ Return an :class:`SQL` object that represents the ordering by
        the given field.  The method also checks whether the field is
        accessible for reading. — ≙ ``odoo19c: odoo/orm/models.py:5262-5322``

        :param direction: one of ``SQL("ASC")``, ``SQL("DESC")``, ``SQL()``
        :param nulls: one of ``SQL("NULLS FIRST")``, ``SQL("NULLS LAST")``,
            ``SQL()``
        """
        # field_name es una expresión
        fname, property_name = parse_field_expr(field_name)
        field = self._fields.get(fname)
        if not field:
            raise ValueError(
                f"Invalid field {fname!r} on model {self._name!r}")

        if field.type == 'many2one':
            seen = self.env.context.get('__m2o_order_seen', ())
            if field in seen:
                return SQL()
            self = self.with_context(
                __m2o_order_seen=frozenset((field, *seen)))

            # el orden aplicable al many2one; ``x_id.id`` no recorre el
            # comodelo de ``x_id``
            # ``env[nombre]`` es aquí la clase; el orden se delega en el
            # recordset vacío del comodelo en el mismo entorno.
            comodel = self.env[field.comodel_name]._from_ids(self.env, (), ())
            if property_name == 'id':
                coorder = 'id'
                sql_field = self._field_to_sql(alias, fname, query)
            else:
                coorder = comodel._order
                sql_field = self._field_to_sql(alias, field_name, query)

            if coorder == 'id':
                query._order_groupby.append(sql_field)
                return SQL("%s %s %s", sql_field, direction, nulls)

            # en vez del valor crudo, el orden del comodelo sobre los valores
            terms = []
            if nulls.code == 'NULLS FIRST':
                terms.append(SQL("%s IS NOT NULL", sql_field))
            elif nulls.code == 'NULLS LAST':
                terms.append(SQL("%s IS NULL", sql_field))

            # LEFT JOIN de la tabla del comodelo, para incluir también NULL
            _comodel, coalias = field.join(self, alias, query)

            # se delega el orden en el comodelo
            reverse = direction.code == 'DESC'
            term = comodel._order_to_sql(
                coorder, query, alias=coalias, reverse=reverse)
            if term:
                terms.append(term)
            return SQL(", ").join(terms)

        sql_field = self._field_to_sql(alias, field_name, query)
        if field.type == 'boolean':
            sql_field = SQL("COALESCE(%s, FALSE)", sql_field)

        query._order_groupby.append(sql_field)

        return SQL("%s %s %s", sql_field, direction, nulls)


class DisplayNameMixin:
    """``display_name`` y su bloque — la etiqueta de un registro, universal.

    ≙ el bloque que ``BaseModel`` declara bajo el comentario
    *"display_name, name_create, name_search"* (``odoo19c:
    odoo/orm/models.py:1421-1543``): el campo ``display_name`` (``:473``), su
    ``_compute_display_name`` (``:1425``), su ``_search_display_name``
    (``:1442``), ``name_create`` (``:1493``) y ``name_search`` (``:1512``).

    **La divergencia es de VÍA, no de alcance**, y es la misma que
    :class:`RecordLoaderMixin` declara: allá cuelgan de ``BaseModel``, así que
    **todo** modelo los tiene sin declarar nada; aquí ``models.Model`` es el de
    Django y no es nuestro. La universalidad se recupera por dos caminos, que
    son los de ``H-API-577``:

    - este mixin lo adopta ``TimeStampedModel``, la base común del proyecto —
      **284 de los 374 modelos concretos nuestros** lo heredan (medido);
    - los **90** restantes lo reciben de
      :func:`orm.model_classes.adopt_display_name`, que corre en
      ``class_prepared`` y en un barrido, igual que el manager de permisos.

    Por qué no basta con la base común: 90 modelos no la heredan, y **el olvido
    no falla** — un modelo sin ``display_name`` cae al ``__str__`` de Django y
    nada lo delata. Es la misma clase de defecto silencioso que ``H-API-876``
    registró para el manager.

    Tres divergencias de FORMA, todas heredadas del árbol y ninguna nueva
    ======================================================================

    Las tres ya las ejercían los cinco modelos que declaraban su
    ``_compute_display_name`` antes de esta tarea (``res_bank``,
    ``res_partner``, ``ir_model``, ``properties_base_definition``,
    ``res_currency``), así que cambiarlas ahora rompería lo que ya funciona:

    1. **``_compute_display_name`` asigna la etiqueta**, como la fuente, y
       conserva además el retorno para los llamadores directos existentes.
       El retorno no sustituye la asignación exigida por el descriptor.
    2. **``name_create`` y ``name_search`` reciben y devuelven lo de Django.**
       ``name_search`` acota con un ``Q`` y no con un dominio extra, que es la
       forma que sus llamadores de este árbol ya usaban.
    3. **``name_create`` y ``name_search`` son ``classmethod``**: allá son
       ``@api.model``, es decir métodos sobre un recordset vacío que sólo
       aporta el modelo. Ese papel lo cumple la clase.

    Lo que DEJÓ de ser divergencia: la forma de ``_search_display_name``
    ======================================================================

    Hasta ``api@4f898d9e`` este bloque declaraba una tercera divergencia —
    ``_search_display_name`` devolvía un ``QuerySet``— con el argumento de que
    era *"lo que el llamador de este árbol sabe consumir"*. El argumento era
    medible y quedó falso al llegar el segundo llamador: el optimizador de
    dominios necesita un ``Domain``, y la diferencia no es de estilo. Un
    dominio **se compone** —cabe dentro de un ``any``, se niega sin
    materializar, se optimiza con el resto—; un ``QuerySet`` no. Ahora
    devuelve ``Domain``, como la fuente, y ``name_search`` lo convierte con
    ``to_q`` para seguir acotando en Django.

    Lo que NO es divergencia: la asignación sigue permitida
    ======================================================

    ``display_name`` es un campo sin columna, no una ``property``. Su
    descriptor admite la asignación en memoria y la caché vigente conserva
    el valor hasta que se invalidan sus dependencias.
    """

    #: ≙ la declaración de la fuente, verbatim salvo el nombre del argumento
    #: de la etiqueta (``odoo19c: odoo/orm/models.py:473-477``)::
    #:
    #:     display_name = Char(
    #:         string='Display Name',
    #:         compute='_compute_display_name',
    #:         search='_search_display_name',
    #:     )
    #:
    #: Sin ``store=``, el bloque ``compute`` de la fuente deriva
    #: ``store=False`` (``odoo19c: odoo/orm/fields.py:443-450``, portado en
    #: :func:`orm.fields_nonstored.apply_source_defaults`), así que el
    #: campo se contribuye como privado, sin columna — igual que allá.
    #:
    #: La etiqueta va en el primer posicional porque es ``verbose_name`` en
    #: Django y ``string`` en la fuente; antes viajaba en ``help_text=``, que
    #: es el alias de ``help=`` y no de ``string=``.
    #:
    #: Hasta ``TASK-API-0415`` el cómputo se cableaba por ``default=`` con una
    #: función que lo envolvía: el descriptor guardaba ``compute`` y nadie lo
    #: despachaba. Hoy lo despacha su tercera rama de lectura.
    display_name = Char('Display Name',
                        compute='_compute_display_name',
                        search='_search_display_name')

    @api.depends(lambda model: (model._rec_name,)
                 if getattr(model, '_rec_name', None) else ())
    def _compute_display_name(self):
        """La etiqueta del registro — ≙ ``_compute_display_name`` (``:1425``).

        Con ``_rec_name`` resuelto, el valor de ese campo pasado por
        :func:`orm.fields.convert_to_display_name`; sin él, ``modelo,id``,
        verbatim el ``f"{record._name},{record.id}"`` de la fuente.

        La dependencia invocable conserva el campo de nombre de cada modelo.
        Se asigna mediante el descriptor existente para poblar su caché; el
        retorno adicional conserva los consumidores que llaman directamente.
        """
        rec_name = getattr(type(self), '_rec_name', None)
        if not rec_name:
            name = getattr(type(self), '_name', None) or self._meta.label
            label = f'{name},{self.pk}'
        else:
            try:
                field = self._meta.get_field(rec_name)
            except FieldDoesNotExist:
                field = None
            label = convert_to_display_name(
                field, getattr(self, rec_name), self)
            # Conservar el respaldo técnico de la adaptación para nombres
            # vacíos.
            if not label:
                name = getattr(type(self), '_name', None) or self._meta.label
                label = f'{name},{self.pk}'
        self.display_name = label
        return label

    @classmethod
    def _search_display_name(cls, operator, value):
        """Los registros cuya etiqueta coincide — ≙ ``:1442``.

        Busca sobre ``_rec_names_search`` o, en su defecto, sobre
        ``_rec_name``: la misma preferencia y el mismo orden de la fuente.
        Sin ninguno de los dos **avisa y no restringe** — ``Domain.TRUE`` allá,
        ``objects.all()`` aquí—, que es la conducta de la fuente y no un
        atajo: restringir a cero sería inventar una negativa que la fuente no
        da.

        ``_rec_names_search`` admite rutas con punto (``partner_id.name``); se
        traducen al ``__`` de Django, que es el mismo recorrido de relación.
        Un campo relacional busca sobre el ``display_name`` del otro lado en la
        fuente; aquí sobre su ``_rec_name``, que es de donde ese
        ``display_name`` sale.

        El corto-circuito del ``like ''`` de la fuente se porta: con valor
        vacío y operador positivo devuelve todo, y con uno negativo, nada.
        """
        return search_display_name(cls, operator, value)

    @classmethod
    def name_create(cls, name):
        """Crea el registro a partir de su sola etiqueta — ≙ ``:1493-1510``.

        Escribe ``name`` en el campo que ``_rec_name`` nombra y devuelve el par
        ``(id, display_name)``. Sin ``_rec_name`` avisa y devuelve ``False``,
        verbatim — con su ``TODO`` incluido: la fuente misma anota que debería
        lanzar un error en vez de devolver un falso.
        """
        rec_name = getattr(cls, '_rec_name', None)
        if not rec_name:
            _logger.warning(
                'No se puede ejecutar name_create: %s no declara _rec_name',
                cls._meta.label)
            return False
        # el alta de la fuente: defaults, contexto y acceso; un modelo sin
        # ``create`` propio (no adopta DefaultGetMixin) usa el de Django
        if hasattr(cls, 'create'):
            record = cls.create({rec_name: name})
        else:
            record = cls.objects.create(**{rec_name: name})
        return record.id, record.display_name

    @classmethod
    def name_search(cls, name='', domain=None, operator='ilike', limit=100):
        """Los pares ``(id, etiqueta)`` que coinciden — ≙ ``:1512``.

        En un modelo de recordset (``BaseModel``) con un dominio de Odoo es el
        flujo de la fuente: ``Domain('display_name', operator, name)`` y el
        ``domain`` extra, ``search_fetch(['display_name'], limit=limit)`` —que
        aplica acceso, reglas y ``_order``— y los pares leídos bajo
        ``sudo()``, que sólo eleva la lectura de la etiqueta de lo que la
        búsqueda ya seleccionó.

        **Divergencia declarada, la anterior forma del puerto:** un ``Q`` de
        Django como ``domain``, o un modelo sin ``search_fetch``, siguen por
        un ``QuerySet`` sin elevar nada, porque ahí la selección no filtra por
        permiso y elevar sería conceder un permiso que nadie otorgó.
        """
        if not isinstance(domain, Q) and hasattr(cls, 'search_fetch'):
            full = (Domain('display_name', operator, name)
                    & Domain(domain or Domain.TRUE))
            records = cls.search_fetch(full, ['display_name'], limit=limit)
            return [(record.id, record.display_name)
                    for record in records.sudo()]
        queryset = cls.objects.filter(
            to_q(Domain('display_name', operator, name), cls))
        if domain is not None:
            queryset = queryset.filter(
                domain if isinstance(domain, Q) else to_q(Domain(domain), cls))
        return [(record.pk, record.display_name)
                for record in queryset[:limit]]


#: Los operadores de semántica negativa que :meth:`_search_display_name`
#: atiende — ≙ el ``Domain.NEGATIVE_OPERATORS`` que la fuente consulta
#: (``odoo19c: odoo/orm/models.py:1462``). Es la tercera copia del mismo
#: conjunto en este árbol; unificar las tres en un hogar compartido es la
#: tarea **#380**, que ``orm/fields.py`` ya declara para las suyas.
NEGATIVE_DISPLAY_NAME_OPERATORS = frozenset([
    'not like', 'not ilike', 'not =like', 'not =ilike', '!=', '<>',
])


# ═══════════════════════════════════════════════════════════════════════════
# El acceso por clave — ≙ ``odoo19c: odoo/orm/models.py:6669-6698``
# ═══════════════════════════════════════════════════════════════════════════
#
# Es la primitiva de la que cuelga la familia ``related=`` de ``Field``:
# ``_compute_related`` escribe ``record[self.name] = ...`` e
# ``_inverse_related`` lo lee. Sin ella el porte de esa familia sería código
# que no puede correr.
#
# Medido antes de construir: ``django.db.models.Model`` no responde a
# ``__getitem__`` ni a ``__setitem__``. No hay colisión que respetar.
#
# **Se porta SÓLO su rama de cadena.** La fuente sobrecarga ``__getitem__``
# con tres significados —``inst[3]`` da el cuarto registro, ``inst[10:20]`` un
# subconjunto, ``rs['name']`` un valor— porque allá un recordset ES un
# contenedor de filas. Aquí una instancia de modelo es UNA fila, y el
# contenedor es el ``QuerySet``, que ya responde a ``[3]`` y a ``[10:20]`` con
# la semántica de Django. Portar esas dos ramas sobre la instancia inventaría
# un significado que el contenedor ya tiene en otro sitio; la rama de cadena,
# en cambio, no existe en ninguno de los dos.
#
# **Por qué NO consulta ``_fields``.** El árbol ya declara un ``_fields``
# (``FieldToSqlMixin``, arriba) y su contrato es más estrecho que el de la
# fuente: filtra por ``concrete``, porque quien lo consume compone SQL. La
# fuente incluye TODOS los campos. Instalar un segundo ``_fields`` con la
# semántica ancha crearía dos fuentes de verdad del mismo mapa —el defecto que
# ``calibration-verified-numbers.md`` prohíbe—, y ensancharlo en el sitio
# cambiaría el alcance de todo consumidor de ``_field_to_sql``. Así que el
# acceso por clave pregunta a ``_meta``, que es el registro que todo modelo
# tiene, y la reconciliación de los dos contratos queda como decisión con su
# medición: tarea **#215**.


def _model_getitem(self, key):
    """≙ ``BaseModel.__getitem__``, rama de cadena (``:6674``) — «read the
    field ``key``».

    La fuente llama al **getter del campo**, no a ``getattr`` a secas, y su
    comentario lo subraya: *«important: one must call the field's getter»*.
    Aquí el getter del campo ES el descriptor que Django instaló, así que
    ``getattr`` lo invoca — la indirección es la misma, sólo que quien aloja
    el descriptor es Django.

    Un nombre que el modelo no declara levanta ``KeyError`` y no
    ``AttributeError``: es acceso por clave, y quien lo escribe espera el
    error del mapa.
    """
    if not isinstance(key, str):
        raise TypeError(
            f'{type(self).__name__}[{key!r}]: sólo se accede por nombre de '
            'campo. El contenedor de filas es el QuerySet, no la instancia.')
    try:
        field = self._meta.get_field(key)
    except FieldDoesNotExist:
        raise KeyError(key) from None
    # ``get_field`` también responde al ``attname`` de una FK
    # (``partner_id``), y ``getattr`` con ese nombre leería el id crudo. El
    # getter del campo es el de su nombre, que devuelve el registro.
    return getattr(self, getattr(field, 'name', None) or key)


def _model_setitem(self, key, value):
    """≙ ``BaseModel.__setitem__`` (``:6694``) — «assign the field ``key`` to
    ``value``». Mismo criterio que el getter, con el setter del descriptor."""
    try:
        self._meta.get_field(key)
    except FieldDoesNotExist:
        raise KeyError(key) from None
    setattr(self, key, value)


Model.__getitem__ = _model_getitem
Model.__setitem__ = _model_setitem


# ═══════════════════════════════════════════════════════════════════════════
# Capa C de #273 — ``modified()``: quien recorre el grafo y marca el recalculo
# ═══════════════════════════════════════════════════════════════════════════
#
# ≙ ``BaseModel.modified``, ``_modified``, ``_modified_triggers``,
# ``_recompute_model``, ``_recompute_recordset`` y ``_recompute_field``
# (``odoo19c: odoo/orm/models.py:6756-6959``).
#
# Las tres capas de #273, en una linea cada una:
#
# - **A** (``orm/fields.py``) — el campo sabe recalcularse y cachear su valor.
# - **B** (``orm/registry.py``) — el grafo sabe QUE campos dependen de cual, y
#   por que camino llegar a las filas afectadas.
# - **C** (aqui) — alguien recorre ese grafo cuando un valor cambia, y marca.
#
# **Divergencia de mecanismo transversal, declarada una vez:** la fuente opera
# sobre *recordsets* y aqui la unidad es la **instancia** o el ``QuerySet``.
# Donde ella escribe ``records.browse(ids)`` para rehacer un conjunto, aqui se
# lleva una **lista de instancias**: no hay recordset que rehacer, y filtrar la
# lista es la misma operacion sin la indireccion. Es la misma adaptacion que
# ``orm.utils.record_ids`` y ``orm.utils.as_record_list`` ya declaran.


def _model_of_records(records):
    """La clase de modelo de ``records`` — clase, instancia, lista o
    ``QuerySet``.

    La rama de la CLASE existe porque la fuente llama a esta familia sobre un
    recordset vacio del modelo (``self.env[nombre]``), que allá lleva su modelo
    consigo. Aqui el equivalente que llega desde el eje de esquema es la propia
    clase, y ``as_record_list`` no la puede recorrer: ``list(ModelBase)`` es un
    ``TypeError``. Sus dos consumidores —``flush_model`` y
    ``_recompute_model``— ya escribian la guarda
    ``or (self if isinstance(self, type) else None)``, asi que **declaraban**
    admitir la clase; lo que faltaba era que esta funcion llegara a devolverla
    en vez de reventar antes.
    """
    if isinstance(records, type):
        return records
    if isinstance(records, QuerySet):
        return records.model
    rows = as_record_list(records)
    return type(rows[0]) if rows else None


def _new_records(rows):
    """Las filas aun sin persistir — ≙ el ``NewId`` de la fuente.

    Alla un registro sin guardar lleva un id-falso y ``bool(NewId)`` es
    ``False``; aqui Django deja ``pk is None`` hasta el ``save()``. Es el mismo
    predicado con otro portador (``orm/identifiers.py`` lo declara).
    """
    return [row for row in rows if row.pk is None]


def _inverse_accessor(inverse):
    """El nombre por el que se navega ``inverse`` desde una instancia.

    **No es ``inverse.name``**, y la diferencia es medible: en un
    ``ManyToOneRel`` sin ``related_name`` el ``name`` es el del modelo en
    minusculas y el atributo real es ``<modelo>_set``. La fuente no tiene esta
    distincion porque su lado inverso es un campo declarado con su nombre; aqui
    Django separa el nombre del registro del nombre del atributo, asi que se
    pregunta por el segundo.
    """
    accessor = getattr(inverse, 'get_accessor_name', None)
    return accessor() if accessor is not None else inverse.name


def _traverse_inverse(rows, inverse):
    """Las filas a las que ``rows`` llega por ``inverse``.

    ≙ ``self[invf.name]`` de la fuente (``:6892``). El acceso a un lado inverso
    en Django devuelve un *related manager*, no el conjunto: se materializa
    aqui, y un lado directo devuelve la instancia o ``None``.
    """
    name = _inverse_accessor(inverse)
    reached = []
    seen = set()
    for row in rows:
        if isinstance(row, Model) and not row._is_pk_set():
            descriptor = getattr(type(row), name, None)
            if type(descriptor) in (
                    _related_descriptors.ReverseManyToOneDescriptor,
                    _related_descriptors.ManyToManyDescriptor):
                # Native collection managers require a PK even for cached
                # querysets. New rows cannot have persisted inverse links.
                # Direct cached relations and custom descriptors still walk.
                continue
        value = getattr(row, name, None)
        if value is None:
            continue
        found = (list(value) if isinstance(value, BaseModel)
                 else list(value.all()) if hasattr(value, 'all') else [value])
        for item in found:
            key = (type(item), item.pk) if item.pk is not None else id(item)
            if key not in seen:
                seen.add(key)
                reached.append(item)
    return reached


def _records_pointing_at(model, field, rows):
    """Las filas de ``model`` cuyo ``field`` apunta a alguna de ``rows``.

    ≙ el ``else`` del ``for`` de ``:6903-6913``: cuando ningun inverso sirve,
    la fuente busca por dominio. Aqui la busqueda es un ``filter`` con
    ``__in``, y las filas aun sin persistir se resuelven por el cache del
    campo — que es donde su valor vive hasta el ``save()``.
    """
    new_rows = _new_records(rows)
    real_ids = [row.pk for row in rows if row.pk is not None]
    found = []
    if real_ids:
        found = list(model.objects.filter(
            **{f'{field.name}__in': real_ids}).order_by('pk'))
    if new_rows:
        cached_ids = field._get_cache(env())
        new_keys = {id(row) for row in new_rows}
        for candidate in model.objects.filter(pk__in=list(cached_ids)):
            value = getattr(candidate, field.name, None)
            if value is not None and id(value) in new_keys:
                found.append(candidate)
    return found


def _modified_triggers(self, tree, create=False):
    """Recorre el arbol de disparo hacia atras, cediendo que recalcular.

    ≙ ``BaseModel._modified_triggers`` (``:6862-6918``). Cede tuplas
    ``(campo, filas, creado)``.
    """
    rows = as_record_list(self)
    if not rows:
        return

    #: Primero lo que hay que calcular sobre estas mismas filas.
    for field in tree.root:
        yield field, rows, create

    #: Luego se baja por cada dependencia, invirtiendola.
    for field, subtree in tree.items():
        #: Al crear, ninguna otra fila puede tener todavia una referencia a
        #: estas — ≙ ``:6884-6886``.
        many2one_types = ('many2one', 'many2one_reference')
        if create and (getattr(field, 'many_to_one', False)
                       or getattr(field, 'type', None) in many2one_types):
            continue

        model = getattr(field, 'model', None)
        if model is None:
            continue

        records = None
        for inverse in registry.field_inverses[field]:
            #: Un inverso con dominio no sirve para la vuelta: su conjunto no
            #: es el de todas las filas que apuntan aqui — ≙ ``:6889``.
            if getattr(inverse, 'domain', None) and (
                    getattr(inverse, 'one_to_many', False)
                    or getattr(inverse, 'many_to_many', False)):
                continue
            records = _traverse_inverse(rows, inverse)
            break

        if records is None:
            records = _records_pointing_at(model, field, rows)

        if records:
            yield from _modified_triggers(records, subtree)


def _modified(self, fields, create):
    """Los disparos que ``fields`` provoca sobre ``self``.

    ≙ ``BaseModel._modified`` (``:6840-6860``). El ``select`` descarta del
    arbol fusionado las ramas que solo contienen campos sin columna y sin nada
    en cache: recorrerlas costaria consultas para no invalidar nada.
    """
    environment = env()

    def select(field):
        return bool((field.compute and field.store)
                    or field._get_all_cache_ids(environment))

    tree = registry.get_trigger_tree(fields, select=select)
    if not tree:
        return ()

    #: La fuente eleva y desactiva el filtro por activo para el recorrido; aqui
    #: la elevacion es un bloque de contexto, no un metodo del recordset, asi
    #: que se abre alrededor de la construccion del iterador. Materializar es
    #: deliberado: un generador perezoso saldria del bloque antes de recorrer.
    with elevate_privileges(), context_scope(active_test=False):
        return list(_modified_triggers(self, tree, create))


def modified(self, fnames, create=False, before=False):
    """Anuncia que ``fnames`` va a cambiar o cambio sobre ``self``.

    ≙ ``BaseModel.modified`` (``:6756-6838``). Invalida el cache donde toca y
    prepara el recalculo de los campos almacenados que dependan.

    Docstring de la fuente, verbatim: *"Notify that fields will be or have been
    modified on ``self``. This invalidates the cache where necessary, and
    prepares the recomputation of dependent stored fields"*.

    :param fnames: nombres de campo modificados sobre ``self``
    :param create: si se llama en el contexto de una creacion
    :param before: si se llama ANTES de modificar

    El arbol de disparo de un campo F contiene los campos que dependen de F,
    junto con los campos a invertir para saber que filas recalcular. Si G
    depende de F, H de X.F, I de W.X.F y J de Y.F, el arbol de F es::

                                  [G]
                                X/   \\Y
                              [H]     [J]
                            W/
                          [I]

    y al modificar F sobre unas filas se marca G sobre ellas, H sobre
    ``inverso(X, filas)``, I sobre ``inverso(W, inverso(X, filas))`` y J sobre
    ``inverso(Y, filas)``.
    """
    rows = as_record_list(self)
    if not rows or not fnames:
        return

    transaction = get_transaction()
    if before:
        #: Antes de modificar hay que ver que depende de ``self`` **ahora**, y
        #: eso no debe recalcularse antes del cambio: solo se acumula.
        marked = transaction.tocompute
        tomark = collections.defaultdict(OrderedSet)
    else:
        #: Despues, el recorrido hacia atras tiene que contar con todo lo que
        #: ya se sabe pendiente, asi que se marca cuanto antes.
        marked = {}
        tomark = transaction.tocompute

    registry_of_model = model_field_registry(type(rows[0]))
    fields = [registry_of_model[fname] for fname in fnames]
    todo = [_modified(rows, fields, create)]

    environment = env()
    for field, records, created in itertools.chain.from_iterable(todo):
        protected_ids = environment.protected(field)
        records = [row for row in records if row.pk not in protected_ids]
        if not records:
            continue

        if field.recursive:
            #: Descarta lo ya procesado, para no entrar en ciclo — ``:6813``.
            if field.compute and field.store:
                seen = (set(marked.get(field) or ())
                        | set(tomark.get(field) or ()))
                records = [row for row in records if row.pk not in seen]
            else:
                #: Sin columna solo interesan las filas con valor en cache: las
                #: demas no tienen nada que invalidar.
                in_cache = field._get_all_cache_ids(environment)
                records = [row for row in records
                           if _field_cache_record_id(field, row) in in_cache]
            if not records:
                continue
            todo.append(_modified(records, [field], created))

        if field.compute and field.store:
            tomark[field].update(record_ids(records))
        else:
            #: Un calculado sin columna no se fuerza a recalcular: basta con
            #: retirar su valor del cache — ``:6828-6831``.
            # Contextual nonstored fields already use NewId cache keys on
            # unsaved Django rows. Keep the descriptor identity rather than
            # the persistence PK (None), without changing transaction IDs.
            field._invalidate_cache(environment, tuple(
                _field_cache_record_id(field, row) for row in records))

    if before:
        for field, ids in tomark.items():
            environment.add_to_compute(field, ids)


_M2M_CLEAR_OWNERS = '_orm_m2m_clear_owners'


@receiver(m2m_changed, dispatch_uid='orm.models.notify_m2m_modified')
def _notify_m2m_modified(sender, instance, action, reverse, model,
                         pk_set=None, using=None, **_ignored):
    """Notifica al motor existente los cambios de relación hechos por Django.

    El manager M2M escribe su tabla sin pasar por Field.__set__. La señal
    pública conserva ese flujo y entrega la invalidación a modified(). En
    clear inverso hay que recordar los propietarios antes de borrar enlaces;
    el dato temporal vive sólo en la instancia entre las dos señales.
    """
    if action not in {'post_add', 'post_remove', 'pre_clear', 'post_clear'}:
        return
    owner = model if reverse else type(instance)
    if not hasattr(owner, 'modified'):
        return
    for field in owner._meta.many_to_many:
        if field.remote_field.through is not sender:
            continue
        key = (sender, field.name, using)
        symmetrical = field.remote_field.symmetrical
        if action == 'pre_clear':
            if reverse:
                previous = owner._base_manager.using(using).filter(
                    **{field.name: instance.pk}).values_list('pk', flat=True)
            elif symmetrical:
                related = getattr(instance, field.name).using(using)
                previous = related.values_list('pk', flat=True)
            else:
                continue
            owners = instance.__dict__.setdefault(_M2M_CLEAR_OWNERS, {})
            owners[key] = tuple(previous)
            continue
        if action == 'post_clear':
            snapshots = instance.__dict__.get(_M2M_CLEAR_OWNERS, {})
            owner_ids = set(snapshots.pop(key, ()))
            if not snapshots:
                instance.__dict__.pop(_M2M_CLEAR_OWNERS, None)
        else:
            if not pk_set:
                continue
            owner_ids = set(pk_set) if reverse or symmetrical else set()
        if not reverse or symmetrical:
            owner_ids.add(instance.pk)
        if not owner_ids:
            continue
        if reverse or symmetrical:
            records = owner._base_manager.using(using).filter(pk__in=owner_ids)
        else:
            records = (instance,)
        for record in records:
            record.modified([field.name])


def _recompute_field(self, field, ids=None):
    """Procesa el recalculo pendiente de ``field``.

    ≙ ``BaseModel._recompute_field`` (``:6948-6959``).
    """
    pending = get_transaction().tocompute.get(field) or ()
    ids = pending if ids is None else [i for i in ids if i in pending]
    if not ids:
        return
    #: No se fuerza sobre las filas aun sin persistir: esas se recalculan al
    #: leer el campo — ``:6955-6957``.
    model = _model_of_records(self) or getattr(field, 'model', None)
    if model is None:
        return
    persisted_ids = [record_id for record_id in ids if record_id]
    rows_by_id = {
        row.pk: row
        for row in model._base_manager.filter(pk__in=persisted_ids)
    }
    records = [
        rows_by_id[record_id]
        for record_id in dict.fromkeys(persisted_ids)
        if record_id in rows_by_id
    ]
    missing_ids = set(persisted_ids).difference(rows_by_id)
    field.recompute(records)
    # TASK-GEN-0559: Django excluye las filas ausentes al consultar, sin
    # MissingError. Equivale al descarte de apply_except_missing de la fuente
    # (odoo19c: odoo/orm/fields.py:1859-1874), después de computar con éxito.
    # Se conserva el trabajo virtual y el ajeno al alcance solicitado.
    if missing_ids:
        for computed in registry.field_computed[field]:
            env().remove_to_compute(computed, missing_ids)


def _recompute_model(self, fnames=None):
    """Procesa los calculos pendientes de los campos del MODELO de ``self``.

    ≙ ``BaseModel._recompute_model`` (``:6920-6932``). Sin acotar por fila: se
    procesa todo lo pendiente de cada campo.
    """
    model = _model_of_records(self) or (
        self if isinstance(self, type) else None)
    if model is None:
        return
    registry_of_model = model_field_registry(model)
    fields = (registry_of_model.values() if fnames is None
              else [registry_of_model[fname] for fname in fnames])
    for field in fields:
        if getattr(field, 'compute', None) and getattr(field, 'store', False):
            _recompute_field(self, field)


def _recompute_recordset(self, fnames=None):
    """Procesa los calculos pendientes de las FILAS de ``self``.

    ≙ ``BaseModel._recompute_recordset`` (``:6934-6946``). La diferencia con
    ``_recompute_model`` es el alcance: aqui solo estas filas.
    """
    rows = as_record_list(self)
    if not rows:
        return
    registry_of_model = model_field_registry(type(rows[0]))
    fields = (registry_of_model.values() if fnames is None
              else [registry_of_model[fname] for fname in fnames])
    for field in fields:
        if getattr(field, 'compute', None) and getattr(field, 'store', False):
            _recompute_field(self, field, record_ids(rows))


def _flush(self):
    """Escribe a la base lo que el calculo dejo sucio en el cache.

    ≙ ``BaseModel._flush`` (``odoo19c: odoo/orm/models.py:6386-6400``). La
    fuente saca del cache los campos sucios con sus ids, arma un
    ``vals_list`` por lotes y lo entrega a ``_write_multi``; aqui igual, y
    el enunciado de ``_write_multi`` es ``save(update_fields=...)``
    (TASK-API-0510).

    El cache lo puebla ``orm.fields._cache_computed_values``, que corre al
    final de cada ``compute_value``: sin el, ``field_dirty`` estaria siempre
    vacio y este metodo no tendria de donde saber que columna escribir.

    **El alcance es el MODELO, no las filas de ``self``** — corregido con la
    tarea #324. La version anterior arrancaba con
    ``rows = as_record_list(self)`` y ``if not rows: return``, asi que sobre un
    recordset vacio no escribia nada; y ``flush_model``, que es quien lo llama
    sin filas, se volvia un verde que no discrimina: corria, no volcaba, y
    nadie lo notaba. La fuente recorre ``self._fields.values()`` y **saca**
    (``pop``) los ids sucios de cada uno, sin mirar ``self._ids``: por eso su
    ``flush_model`` sobre un recordset vacio si vuelca el modelo entero.

    La firma tambien vuelve a la de la fuente: ``_flush(self)``, sin
    ``fnames``. Quien acota por nombre es el llamador —``flush_model`` decide
    si vale la pena volcar— y allá el volcado, una vez decidido, es completo.
    """
    model = _model_of_records(self) or (
        self if isinstance(self, type) else None)
    if model is None:
        return
    dirty = get_transaction().field_dirty
    dirty_field_ids = {}
    for field in model_field_registry(model).values():
        ids = dirty.pop(field, None)
        if ids:
            dirty_field_ids[field] = ids
    if not dirty_field_ids:
        return

    #: Solo las filas ya persistidas: un id que no es entero es una fila
    #: virtual, que se recalcula al leerla y no tiene columna que escribir.
    #: Orden de la fuente (``:6402-6412``): los ids con el mismo conjunto de
    #: campos sucios quedan juntos, por su máscara de bits.
    dirty_ids = sorted(
        OrderedSet(record_id for ids in dirty_field_ids.values()
                   for record_id in ids if isinstance(record_id, int)),
        key=lambda record_id: sum(
            1 << field_index
            for field_index, ids in enumerate(dirty_field_ids.values())
            if record_id in ids
        ),
    )

    # lotes de la fuente, para acotar la memoria
    BATCH_SIZE = 1000
    cache = {field: field._get_cache(env()) for field in dirty_field_ids}
    for some_ids in split_every(BATCH_SIZE, dirty_ids):
        ids = []
        vals_list = []
        for record_id in some_ids:
            vals = {
                field.name: cache[field][record_id]
                for field, field_ids in dirty_field_ids.items()
                if record_id in field_ids and record_id in cache[field]
            }
            if vals:
                ids.append(record_id)
                vals_list.append(vals)
        if issubclass(model, BaseModel):
            model.browse(ids)._write_multi(vals_list)
        else:
            # un modelo de Django sin recordset no tiene ``_write_multi``: su
            # escritura es la misma, sin la capa de ``parent_path``
            _write_rows(model, ids, vals_list)


def _write_rows(model, ids, vals_list):
    """Escribe ``vals_list`` sobre las filas físicas ``ids`` de ``model``.

    Es la escritura de :meth:`BaseModel._write_multi` y la de :func:`_flush`
    para un modelo de Django sin recordset: una sola implementación. Las filas
    se piden al ``_base_manager`` —el gestor físico, no el público con filtro
    de visibilidad— en una consulta por lote, y una fila que ya no existe no
    se recrea. Cada fila se guarda con ``save(update_fields=...)``: es la
    divergencia de enunciado declarada en ``designs/write-multi-flush.md``.
    """
    fields_of = model_field_registry(model)
    writable = model._meta._non_pk_concrete_field_names
    log_access = (getattr(model, '_log_access', True)
                  and 'updated_at' in writable)
    rows = {row.pk: row
            for row in model._base_manager.filter(pk__in=list(ids))}
    for record_id, vals in zip(ids, vals_list):
        row = rows.get(record_id)
        if row is None:
            # silent OK because la fila se borró antes de escribirla: la
            # fuente emite un UPDATE que no casa ninguna fila, sin error.
            continue
        names = []
        for fname, value in vals.items():
            field = fields_of[fname]
            if getattr(field, 'many_to_many', False):
                _flush_m2m(row, field, value)
                continue
            attname = getattr(field, 'attname', field.name)
            setattr(row, attname, value)
            names.append(attname)
        if names:
            # ≙ ``log_vals | vals``: la fecha la pone ``auto_now`` en
            # ``pre_save``, pero sólo se guarda lo nombrado.
            if log_access and 'updated_at' not in names:
                names.append('updated_at')
            row.save(update_fields=names)


def _flush_m2m(row, field, value):
    """Vuelca un campo muchos-a-muchos calculado — la rama que #313 anade.

    Un M2M no es una columna y no admite ``setattr``: Django lanza
    ``TypeError: Direct assignment to the forward side of a many-to-many set
    is prohibited``. Tampoco cabe en ``update_fields``, que nombra columnas.
    Por eso la rama existe: el mismo valor calculado se entrega al manager
    relacional, que resuelve el diff contra la tabla intermedia.

    ``.set()`` y no un ``bulk_create`` sobre un ``through`` propio: las
    relaciones que hoy declaran computo son de **configuracion** —etiquetas de
    una cuenta, campos que disparan una regla—, de cardinalidad baja y
    escritura rara. Ahi lo caro es la superficie, no la ida a la base; y
    ``.set()`` emite ``m2m_changed``, que es donde vive el control de acceso
    de la relacion. La rama mira el CAMPO, no el modelo, asi que una relacion
    de operacion que manana pida otro mecanismo no queda cerrada por esto.

    Una fila sin ``pk`` no llega aqui: :func:`_flush` solo recorre las que el
    registro de sucios nombra por id, y una fila nueva no tiene ninguno.
    """
    manager = getattr(row, field.name)
    manager.set([] if value is None else value)


def flush_model(self, fnames=None):
    """Procesa los calculos y las escrituras pendientes del MODELO de ``self``.

    ≙ ``BaseModel.flush_model`` (``:6353-6365``). Docstring de la fuente,
    verbatim: *"Process the pending computations and database updates on
    ``self``'s model. When the parameter is given, the method guarantees that
    at least the given fields are flushed to the database. More fields can be
    flushed, though"*.
    """
    _recompute_model(self, fnames)
    model = _model_of_records(self) or (
        self if isinstance(self, type) else None)
    if model is None:
        return
    if fnames is None:
        _flush(self)
        return
    dirty = get_transaction().field_dirty
    registry_of_model = model_field_registry(model)
    if any(registry_of_model[fname] in dirty for fname in fnames):
        _flush(self)


def flush_recordset(self, fnames=None):
    """Procesa los calculos y las escrituras pendientes de las FILAS de
    ``self``.

    ≙ ``BaseModel.flush_recordset`` (``:6367-6384``). La diferencia con
    ``flush_model`` es el alcance: aqui solo estas filas.
    """
    rows = as_record_list(self)
    if not rows:
        return
    _recompute_recordset(rows, fnames)
    registry_of_model = model_field_registry(type(rows[0]))
    fields = (registry_of_model.values() if fnames is None
              else [registry_of_model[fname] for fname in fnames])
    ids = set(record_ids(rows))
    dirty = get_transaction().field_dirty
    if not all(ids.isdisjoint(dirty.get(field) or ()) for field in fields):
        _flush(rows)


def _invalidate_cache(self, fnames=None, ids=None):
    """Retira de la caché los campos dados, en las filas dadas o en todas.

    ≙ ``BaseModel._invalidate_cache`` (``odoo19c: odoo/orm/models.py``). Una
    lista de ids vacía no invalida nada —*"Avoid invalidating field_inverses
    for no reason"*—; ``None`` invalida el modelo entero.
    """
    if ids is not None and not ids:
        return
    fields = (self._fields.values() if fnames is None
              else [self._fields[fname] for fname in fnames])
    # La clase hace de recordset vacío y no lleva entorno propio: el suyo es
    # el activo, que es el que ``env['x']`` le daría en la fuente.
    environment = env() if isinstance(self, type) else self.env
    for field in fields:
        invalidate = getattr(field, '_invalidate_cache', None)
        if invalidate is not None:
            invalidate(environment, ids)


def invalidate_model(self, fnames=None, flush=True):
    """Invalida la caché de todas las filas del modelo de ``self``.

    ≙ ``BaseModel.invalidate_model`` (``odoo19c: odoo/orm/models.py``).
    Docstring de la fuente: para cuando lo cacheado ya no corresponde a la
    base; con ``flush`` (el defecto) se vuelca antes lo pendiente, que es lo
    que garantiza la coherencia.
    """
    if flush:
        flush_model(self, fnames)
    _invalidate_cache(self, fnames)


def invalidate_recordset(self, fnames=None, flush=True):
    """Invalida la caché de las filas de ``self``.

    ≙ ``BaseModel.invalidate_recordset`` (``odoo19c: odoo/orm/models.py``).
    Mismo contrato que :func:`invalidate_model`, acotado a estas filas.
    """
    if flush:
        flush_recordset(self, fnames)
    _invalidate_cache(self, fnames, tuple(record_ids(as_record_list(self))))


# ═══════════════════════════════════════════════════════════════════════════
# Traducciones por campo — ≙ ``update_field_translations``,
# ``_update_field_translations``, ``get_field_translations`` y la rama de
# traducción de ``copy_translations`` (``odoo19c: odoo/orm/models.py:
# 3492-3703``, ``:5465-5528``) — TASK-GEN-0060
# ═══════════════════════════════════════════════════════════════════════════
#
# Allá cuelgan de ``BaseModel`` y todo modelo los tiene. Aquí los 12 modelos
# con campos traducibles son de Django, no ``BaseModel``, así que se cuelgan de
# ``Model`` como los métodos de motor de arriba; ``BaseModel`` los hereda.
#
# Divergencias declaradas: la rama de términos (``translate`` invocable) no
# tiene receptor —el despachador lleva ``translate`` a ``bool``—, y el
# ``self[field_name] = self[field_name]`` final de la fuente, que dispara las
# sobrecargas de ``write``, no tiene contraparte sobre una fila de Django: el
# anuncio a los cómputos lo hace ``modified``.


def _installed_langs():
    """Los idiomas válidos: los instalados más ``en_US`` (``:3562``)."""
    return ({code for code, _ in env()['res.lang'].get_installed()}
            | {'en_US'})


def _record_connection(record):
    return connections[record._state.db or DEFAULT_DB_ALIAS]


def update_field_translations(self, field_name, translations,
                              source_lang=''):
    """Update the translations for a given field. — ≙
    ``update_field_translations`` (``:3492-3502``)"""
    return self._update_field_translations(
        field_name, translations, source_lang=source_lang)


def _update_field_translations(self, field_name, translations, digest=None,
                               source_lang=''):
    """Update the translations for a given field. — ≙
    ``_update_field_translations`` (``:3505-3660``)

    ``{idioma: valor}``: un ``str`` es la traducción nueva; ``False`` retira
    la del idioma y la lectura cae al ``en_US``.
    """
    if hasattr(self, 'ensure_one'):
        self.ensure_one()
    if hasattr(self, 'check_access'):
        self.check_access('write')
    field = type(self)._meta.get_field(field_name)
    if hasattr(self, '_check_field_access'):
        self._check_field_access(field, 'write')

    valid_langs = _installed_langs()
    source_lang = source_lang or 'en_US'
    missing_langs = (set(translations) | {source_lang}) - valid_langs
    if missing_langs:
        raise UserError(
            'The following languages are not activated: %s'
            % ', '.join(sorted(missing_langs)))

    if not getattr(field, 'translate', False):
        return False
    related = getattr(field, 'related', None)
    if (not getattr(field, 'store', True) and not related
            and getattr(field, 'compute', None)):
        return False
    if related and not getattr(field, 'store', True):
        related_path, field_name = related.rsplit('.', 1)
        return self.mapped(related_path)._update_field_translations(
            field_name, translations, digest)
    if field.translate is not True:
        # los términos no tienen receptor; ver la cabecera de la sección
        return False

    if any(translation and not isinstance(translation, str)
           for translation in translations.values()):
        raise UserError('Translations for model translated fields only'
                        ' accept falsy values and str')
    translations = dict(translations)
    english_value = translations.get('en_US', True)
    if not english_value and english_value != '':
        translations.pop('en_US')
    translations = {
        lang: translation if isinstance(translation, str) else None
        for lang, translation in translations.items()
    }
    if not translations:
        return False

    lang = env().lang
    if translations.get('en_US') is not None:
        fallback = translations['en_US']
    elif translations.get(lang) is not None:
        fallback = translations[lang]
    else:
        fallback = next(
            (v for v in translations.values() if v is not None), None)
    # ``self.invalidate_recordset([field_name])`` de la fuente; una fila de
    # Django no lleva entorno propio, así que se usa el activo.
    field._invalidate_cache(env(), (self.pk,))
    query = SQL(
        """ UPDATE %(table)s
            SET %(field)s = NULLIF(
                jsonb_strip_nulls(%(fallback)s::jsonb
                    || COALESCE(%(field)s, '{}'::jsonb) || %(value)s::jsonb),
                '{}'::jsonb)
            WHERE id = %(id)s
            RETURNING %(field)s
        """,
        table=SQL.identifier(type(self)._meta.db_table),
        field=SQL.identifier(field.column),
        fallback=json.dumps({BASE_LANG: fallback}),
        value=json.dumps(translations),
        id=self.pk,
    )
    with _record_connection(self).cursor() as cr:
        cr.execute(query.code, query.params)
        row = cr.fetchone()
    value = row[0] if row else None
    if isinstance(value, str):
        value = json.loads(value)
    # La fila en memoria se queda con el mapa nuevo, como la caché de la
    # fuente tras su invalidación y relectura.
    self.__dict__[field.attname] = value
    self.modified([field_name])
    return True


def get_field_translations(self, field_name, langs=None):
    """Get model/model_term translations for records. — ≙
    ``get_field_translations`` (``:3664-3703``)

    :return: ``(translations, context)``: una entrada ``{lang, source,
        value}`` por idioma, y el contexto de presentación.
    """
    if hasattr(self, 'ensure_one'):
        self.ensure_one()
    field = type(self)._meta.get_field(field_name)
    langs = set(langs or [code for code, _ in
                          env()['res.lang'].get_installed()])
    translate = getattr(field, 'translate', False)
    if not translate:
        translations = []
    else:
        stored = field._get_stored_translations(self) or {}
        english_value = field.translated_value(stored, 'en_US')
        translations = [{
            'lang': lang,
            'source': english_value,
            'value': field.translated_value(stored, lang),
        } for lang in langs]
    context = {
        'translation_type': ('text' if getattr(field, 'type', None)
                             in ('text', 'html') else 'char'),
        'translation_show_source': callable(translate),
    }
    return translations, context


def _copy_field_translation(old, new, field, valid_langs, lang):
    """La rama de un campo traducible de ``copy_translations``
    (``:5508-5514``): copia los idiomas guardados salvo el activo, que ya
    copió ``copy_data``."""
    if not getattr(old, field.name):
        return
    stored = field._get_stored_translations(old)
    if not stored:
        return
    new.update_field_translations(field.name, {
        k: v for k, v in stored.items() if k in valid_langs and k != lang})


def copy_translations(self, new, excluded=()):
    """Recursively copy the translations from original to new record. — ≙
    ``copy_translations`` (``:5465-5528``) sobre una fila de Django.

    Divergencia declarada: sin ``_fields`` ni ``One2many`` propios, sólo se
    copia la rama de los campos traducibles; la recursión por líneas es la
    de :meth:`BaseModel.copy_translations`.
    """
    valid_langs = _installed_langs()
    lang = env().lang or 'en_US'
    for field in type(self)._meta.concrete_fields:
        if (getattr(field, 'translate', False) is True and _copies(field)
                and field.name not in excluded):
            _copy_field_translation(self, new, field, valid_langs, lang)


for _engine_method in (modified, _modified, _modified_triggers,
                       _recompute_model, _recompute_recordset,
                       _recompute_field, _flush, flush_model,
                       flush_recordset, _invalidate_cache, invalidate_model,
                       invalidate_recordset):
    setattr(Model, _engine_method.__name__, _engine_method)
    setattr(QuerySet, _engine_method.__name__, _engine_method)

for _translation_method in (update_field_translations,
                            _update_field_translations,
                            get_field_translations, copy_translations):
    setattr(Model, _translation_method.__name__, _translation_method)


# ═══════════════════════════════════════════════════════════════════════════
# ``precompute`` — el cálculo que se adelanta al INSERT
#     ≙ ``BaseModel._prepare_create_values`` (``odoo19c: odoo/orm/models.py:
#     4786-4791``) y ``BaseModel._add_precomputed_values`` (``:4814-4846``)
# ═══════════════════════════════════════════════════════════════════════════
#
# Hasta aquí ``precompute`` sólo se **validaba**: ``resolve_depends`` avisa y
# lo apaga cuando la cadena de dependencia no lo sostiene
# (``orm/fields.py:2181-2189``), y ``_apply_precompute_block`` rechaza el
# atributo sobre un campo que no es calculado, no es almacenado o es un M2M
# (``orm/fields_nonstored.py:369-406``). Nadie lo **corría**: los nueve campos
# vivos que lo declaran se computaban a mano desde el ``save()`` de su modelo.
#
# Qué hace la fuente, y en qué se traduce aquí
# --------------------------------------------
#
# ``_prepare_create_values`` descarta de ``vals`` los precompute **readonly**
# —para forzar su cómputo aunque el llamador haya pasado un valor— y
# ``_add_precomputed_values`` computa todo precompute cuyo nombre ``fname not
# in vals``, leyéndolo con ``record[fname]`` sobre un ``self.new(vals)``.
#
# Las dos mitades exigen saber **qué nombres dio el llamador**, y ahí está la
# diferencia de este stack: la fuente tiene el diccionario ``vals`` delante;
# una instancia de Django llega al ``pre_save`` con TODOS sus campos poblados
# —los dados y los que tomaron su ``default``— y ya no distingue unos de
# otros. El dato existe un instante antes: ``Model.__init__`` emite
# ``pre_init`` con los ``args`` y ``kwargs`` del llamador **verbatim**
# (``django/db/models/base.py:491``). Eso es ``vals``.
#
# Veredicto por el criterio de las dos categorías: **el stack tiene con qué
# construirlo**. No hay símbolo hecho —Django no tiene la noción de un campo
# que se calcule antes del INSERT— pero las tres primitivas son nativas y
# ninguna viene de fuera del INVENTORY: ``pre_init``/``post_init`` capturan lo
# que el llamador nombró y ``pre_save`` corre antes de ``_do_insert``, las tres
# en ``('django', 'evaluación y control de flujo')``.


#: Los nombres que el llamador pasó a ``__init__``, apilados mientras el
#: constructor corre. Es una **pila** y no una casilla porque ``__init__``
#: anida: un ``default`` que construye otra instancia mete la suya en medio, y
#: con una sola casilla la de fuera se perdería.
#:
#: Si un ``__init__`` revienta entre las dos señales, su entrada se queda en la
#: pila. Eso NO corrompe a la siguiente instancia —``post_init`` saca la
#: **última**, que es la suya— sino que deja una entrada huérfana al fondo: una
#: fuga acotada a un ``frozenset`` por constructor fallido.
_EXPLICIT_VALUES = []


def _explicit_value_names(sender, args, kwargs):
    """Los campos que el llamador nombró al construir la fila.

    Es la traducción de ``fname not in vals`` (``odoo19c: :4842``) al
    constructor de Django, que admite las dos formas de pasar un valor:

    - por palabra clave, que es el caso corriente y el que da ``kwargs``;
    - por **posición**, que Django resuelve contra ``_meta.concrete_fields`` en
      orden (``django/db/models/base.py:496``). Sin esta mitad, una fila
      construida posicionalmente llegaría con el conjunto vacío y todo
      precompute se recalcularía encima del valor que el llamador sí dio.

    Se registran el ``name`` y el ``attname`` porque una FK responde a los dos
    (``company`` y ``company_id``) y el llamador elige cuál usa.
    """
    names = set(kwargs)
    if args:
        for field, _value in zip(sender._meta.concrete_fields, args):
            names.add(field.name)
            names.add(field.attname)
    return frozenset(names)


@receiver(pre_init, dispatch_uid='orm.models.stack_explicit_values')
def _stack_explicit_values(sender, args, kwargs, **_ignored):
    """Apila lo que el llamador nombró, antes de que ``__init__`` lo mezcle."""
    _EXPLICIT_VALUES.append(_explicit_value_names(sender, args, kwargs))


@receiver(post_init, dispatch_uid='orm.models.attach_explicit_values')
def _attach_explicit_values(sender, instance, **_ignored):
    """Cuelga de la instancia lo que su constructor apiló."""
    instance._explicit_values = (
        _EXPLICIT_VALUES.pop() if _EXPLICIT_VALUES else frozenset())


def _precomputable_fields(instance):
    """Los precompute de este modelo que hay que calcular en esta fila.

    ≙ el ``precomputable`` de ``_add_precomputed_values`` (``:4820``) ya
    cruzado con las dos exclusiones que la fuente reparte en dos sitios:

    - el precompute **readonly** se computa siempre, porque la fuente lo saca
      de ``vals`` antes de mirarlo (``:4786-4791``);
    - el precompute **escribible** respeta el valor que el llamador dio, que es
      el ``fname not in vals`` de ``:4842``.
    """
    given = getattr(instance, '_explicit_values', None) or frozenset()
    pending = {}
    for name, field in model_field_registry(type(instance)).items():
        if not getattr(field, 'precompute', False):
            continue
        if not getattr(field, 'readonly', False):
            if name in given or getattr(field, 'attname', name) in given:
                continue
        pending[name] = field
    return pending


def _run_precompute_field(instance, name, pending, done, chain):
    """Corre el cómputo de ``name``, y antes el de los precompute que lee.

    **Esto es la mitad que la fuente obtiene gratis y aquí hay que construir.**
    Allá el pase es perezoso: ``record[fname]`` sobre un registro virtual
    dispara el cómputo *al leerlo*, así que un cómputo que lee otro precompute
    lo resuelve por el camino y el orden de declaración da igual.

    Aquí el cómputo se invoca, no se lee, y el orden de declaración **no** es
    el
    de dependencia. Medido en el árbol: ``SaleOrderLine`` declara
    ``price_reduce_taxexcl`` (``:309``) y ``price_reduce_taxinc`` (``:317``)
    ANTES de ``price_subtotal`` (``:417``), ``price_tax`` (``:425``) y
    ``price_total`` (``:433``), y sus dos cómputos leen justamente lo que
    ``_compute_amount`` escribe. Un pase en orden de declaración los calcularía
    contra el ``default``.

    Así que la pereza se hace explícita: antes de correr el cómputo de un campo
    se corren los de los precompute del **mismo modelo** que su
    ``@api.depends``
    nombra. ``chain`` corta el ciclo —un campo recursivo se nombra a sí mismo—
    y
    ``done`` lleva los **métodos** ya invocados, no los campos:
    ``_compute_amount``
    escribe tres y correrlo tres veces repetiría su efecto.
    """
    field = pending[name]
    if field.compute in done:
        return
    chain = chain + (name,)
    for dotted in registry.field_depends[field]:
        head = dotted.split('.')[0]
        other = pending.get(head)
        if (other is not None and head not in chain
                and other.compute not in done):
            _run_precompute_field(instance, head, pending, done, chain)
    done.add(field.compute)
    getattr(instance, field.compute)()


def _add_precomputed_values(self):
    """Calcula los precompute que faltan, antes de que la fila se inserte.

    ≙ ``BaseModel._add_precomputed_values`` (``odoo19c: :4814-4846``).

    **Tres divergencias de mecanismo, las tres con el mismo resultado
    observable:**

    1. *El valor no se copia a un diccionario.* La fuente escribe
       ``vals[fname] = field.convert_to_write(record[fname], self)`` porque su
       INSERT se arma desde ``vals``. Aquí el cómputo asigna sobre la propia
       instancia, que es de donde Django arma el INSERT: el paso de copia no
       tiene destino.
    2. *Sin registro virtual.* La fuente computa sobre un ``self.new(vals)``
       —un registro sin fila— para no ensuciar el caché con el valor de un
       registro que aún no existe. Aquí el cómputo se invoca **directamente**
       sobre la instancia, no por ``compute_value``, por la misma razón medida
       al revés: ``record_ids`` de una fila sin guardar da ``None``, y
       ``_update_cache`` escribiría ``field_cache[None]``, que la siguiente
       fila sin guardar leería como suyo.
    3. *Sin* ``__precomputed__``. La fuente marca los campos que precomputó
       para que ``create`` **no dispare su** ``inverse`` (``:4664`` y
       ``:4681``): el valor lo puso el cómputo, no el llamador, así que
       invertirlo sería escribir hacia atrás algo que nadie pidió. Aquí ese
       riesgo no existe por construcción — el único que llama a
       ``determine_inverse`` es :meth:`write`, sobre los nombres que el
       llamador
       le pasó (:meth:`_group_written_inverses`), y este pase no pasa por ahí.
    """
    pending = _precomputable_fields(self)
    if not pending:
        return
    done = set()
    for name in list(pending):
        _run_precompute_field(self, name, pending, done, ())


@receiver(pre_save, dispatch_uid='orm.models.run_precompute')
def _run_precompute(sender, instance, raw=False, **_ignored):
    """Dispara el pase de precompute justo antes del INSERT.

    ``pre_save`` corre antes de ``_save_table`` —y por tanto antes de
    ``_do_insert``— así que el valor calculado viaja en la MISMA sentencia
    (``django/db/models/base.py:946``). Ése es el punto entero de
    ``precompute``, y la fuente lo dice: *"computed stored fields with a column
    have to be computed before create s.t. required and constraints can be
    applied on those fields"* (``:4841``).

    Dos salidas tempranas: ``raw`` es el cargador de fixtures, que escribe la
    fila tal cual viene; y una fila que ya existe es un UPDATE, donde el
    recálculo lo gobierna el motor de ``modified()``, no este pase.
    """
    if raw or not instance._state.adding:
        return
    _add_precomputed_values(instance)


def _validate_fields(self, field_names, excluded_names=()):
    """Corre las restricciones que nombran alguno de los campos tocados.

    ≙ ``_validate_fields`` (``odoo19c: odoo/orm/models.py:1252-1268``).
    Docstring de la fuente, verbatim: *"Invoke the constraint methods for which
    at least one field name is in ``field_names`` and none is in
    ``excluded_names``"*.

    **Los dos filtros son de la fuente y los dos importan.** El primero acota:
    una restriccion que no nombra ningun campo tocado no tiene por que correr.
    El segundo veta: basta con que UNO de los nombres que la restriccion
    declara este excluido para que no corra — el llamador excluye lo que sabe
    que esta a medio escribir, y una restriccion que lo mire daria un falso
    negativo.

    **Divergencia de mecanismo, no de contrato.** Alla el mapa de metodos es
    una ``@property`` memoizada en la clase (``:519-546``) y aqui es el
    colector :data:`~orm.registry.constraint_methods`, por la razon que su
    docstring declara. Y ``self.sudo()`` es alla un recordset elevado; aqui la
    elevacion es un bloque de contexto (``orm.environments.sudo``), asi que se
    envuelve la corrida en vez de recibir otro receptor.

    El comentario de la fuente sobre por que se eleva se conserva porque es la
    razon y no el como: *"run constrains just as sudoed computed-stored fields
    — see Field.compute_value()"*.
    """
    methods = registry.constraint_methods(type(self))
    if not methods:
        return
    field_names = set(field_names)
    excluded_names = set(excluded_names)
    with elevate_privileges():
        for check in methods:
            declared = check._constrains
            if (not field_names.isdisjoint(declared)
                    and excluded_names.isdisjoint(declared)):
                check(self)


def _run_ondelete_checks(self, at_uninstall=False):
    """Corre las comprobaciones marcadas antes de borrar la fila.

    ≙ el bloque de ``unlink`` que recorre ``self._ondelete_methods``
    (``odoo19c: odoo/orm/models.py:4205-4208``), con su comentario verbatim:
    *"func._ondelete is True if it should be called during uninstallation"*.

    El marcador NO es una bandera de presencia: guarda el ``at_uninstall`` que
    el decorador recibio. Un metodo con ``at_uninstall=False`` corre en el
    borrado normal y **se salta** cuando quien borra es la desinstalacion de un
    modulo — porque entonces todo lo que el modulo declaro se va de todas
    formas, y un ``UserError`` de negocio ahi solo dejaria la base a medias.
    Ese razonamiento es el del docstring de ``@api.ondelete``
    (``odoo19c: odoo/orm/decorators.py:139-149``).

    **Divergencia de mecanismo:** alla la bandera de desinstalacion viaja en el
    contexto (``MODULE_UNINSTALL_FLAG``); aqui es el argumento de esta llamada,
    porque quien borra es ``Model.delete()`` de Django y no hay contexto de
    recordset que consultar.
    """
    for check in registry.ondelete_methods(type(self)):
        if check._ondelete or not at_uninstall:
            check(self)


@receiver(pre_delete, dispatch_uid='orm.models.run_ondelete_checks')
def _run_ondelete_on_delete(sender, instance, **_ignored):
    """Dispara las comprobaciones marcadas justo antes del DELETE.

    ``pre_delete`` corre dentro de la transaccion del borrado y antes de la
    sentencia, que es donde la fuente las corre: un ``UserError`` levantado
    aqui deja la fila intacta.

    Su equivalente de ``MODULE_UNINSTALL_FLAG`` es la clave de contexto
    ``module_uninstall``, que el desinstalador activa. Con el contexto vacio
    —el caso normal— vale ``False`` y corren todas.
    """
    if not registry.ondelete_methods(sender):
        return
    _run_ondelete_checks(
        instance, at_uninstall=bool(get_context().get('module_uninstall')))


Model._add_precomputed_values = _add_precomputed_values


def _ordering(expression, direction, nulls):
    """Dirección y nulos de un término — los literales de la fuente."""
    options = {}
    if nulls == 'NULLS FIRST':
        options['nulls_first'] = True
    elif nulls == 'NULLS LAST':
        options['nulls_last'] = True
    if direction == 'DESC':
        return expression.desc(**options)
    return expression.asc(**options)


def order_to_django(model, order, reverse=False, prefix='', seen=frozenset()):
    """Una cláusula de orden de la fuente como ``order_by`` de Django.

    ≙ ``_order_to_sql`` + ``_order_field_to_sql``
    (``odoo19c: odoo/orm/models.py:5224-5322``): cada término se valida con
    ``regex_order``; ``reverse`` invierte dirección y nulos; un ``Many2one``
    se ordena por el ``_order`` de su comodelo (salvo ``x_id.id`` o un
    comodelo ordenado por ``id``), con una guarda contra ciclos y, para
    ``NULLS FIRST``/``NULLS LAST``, el término ``IS NOT NULL``/``IS NULL``
    delante. El ``LEFT JOIN`` de la fuente es el que Django emite al cruzar
    una clave anulable.

    **No portado:** el orden por una propiedad (``campo.propiedad`` sobre un
    ``Properties``) y por una función (``campo:func``); se rehúsan con
    ``ValueError`` en vez de ignorarse.
    """
    if not order:
        return []
    if not regex_order.match(order):
        raise UserError(
            'Orden inválido (%s). Un orden válido es una lista de nombres '
            'de campo separados por coma, cada uno seguido opcionalmente '
            'de asc o desc.' % order)
    registry_ = model_field_registry(model)
    terms = []
    for part in order.split(','):
        match = regex_order.match(part)
        fname = match['field']
        direction = (match['direction'] or '').upper()
        nulls = (match['nulls'] or '').upper()
        if reverse:
            direction = 'ASC' if direction == 'DESC' else 'DESC'
            if nulls:
                nulls = ('NULLS LAST' if nulls == 'NULLS FIRST'
                         else 'NULLS FIRST')
        field = registry_.get(fname)
        if field is None:
            raise ValueError(
                f'Invalid field {fname!r} on model '
                f'{registry.name_of(model) or model}')
        prop = match['property']
        if match['func'] or (prop and not isinstance(field, ForeignKey)):
            raise ValueError(f'Orden no portado: {part.strip()!r}')
        if isinstance(field, ForeignKey):
            if field in seen:
                continue
            comodel = field.related_model
            coorder = ('id' if prop == 'id'
                       else (getattr(comodel, '_order', None) or 'id'))
            if coorder == 'id':
                terms.append(_ordering(F(prefix + field.attname), direction,
                                       nulls))
                continue
            path = prefix + field.name
            if nulls == 'NULLS FIRST':
                terms.append(ExpressionWrapper(
                    Q(**{path + '__isnull': False}),
                    output_field=BooleanField()).asc())
            elif nulls == 'NULLS LAST':
                terms.append(ExpressionWrapper(
                    Q(**{path + '__isnull': True}),
                    output_field=BooleanField()).asc())
            terms.extend(order_to_django(
                comodel, coorder, reverse=direction == 'DESC',
                prefix=path + '__', seen=seen | {field}))
            continue
        column = ('pk' if fname == 'id' and not prefix
                  else prefix + getattr(field, 'attname', fname))
        terms.append(_ordering(F(column), direction, nulls))
    return terms


_DJANGO_MANY2MANY_SET = _related_descriptors.ManyToManyDescriptor.__set__


def _many2many_descriptor_set(self, instance, value):
    """Asignar un ``Many2many`` es escribirlo — ≙ ``Field.__set__``
    (``:1807``).

    En la fuente ``record.tag_ids = [Command.link(7)]`` llama a
    ``records.write({name: value})``. Django prohíbe la asignación directa
    sobre el lado directo de un muchos-a-muchos (``TypeError``); aquí, sobre
    una fila ya guardada que sabe escribirse, se entrega a ``write``, que
    interpreta los comandos y comprueba la empresa. El lado inverso y la fila
    sin guardar conservan la conducta de Django.
    """
    if not self.reverse and hasattr(instance, 'write') and _saved(instance):
        instance.write({self.field.name: value})
        return
    _DJANGO_MANY2MANY_SET(self, instance, value)


def _saved(instance):
    ids = getattr(instance, '_ids', None)
    if ids:
        return all(ids)
    return instance.__dict__.get(instance._meta.pk.attname) is not None


_related_descriptors.ManyToManyDescriptor.__set__ = _many2many_descriptor_set


def _x2many_descriptor_get(self, instance, cls=None):
    """Leer un x2many es un recordset del comodelo —
    ≙ ``_RelationalMulti.convert_to_record`` (``odoo19c: odoo/orm/
    fields_relational.py``).

    Sólo cuando el dueño y el comodelo son ``BaseModel``: los demás modelos
    del producto leen el gestor de Django y lo siguen leyendo. El orden es el
    ``_order`` del comodelo, como en la fuente. Una fila sin guardar no tiene
    relación persistida: su valor es el recordset vacío.
    """
    if instance is None:
        return _DJANGO_X2MANY_GET(self, instance, cls)
    if isinstance(self, _related_descriptors.ManyToManyDescriptor):
        comodel = (self.field.model if self.reverse
                   else self.field.related_model)
    else:
        comodel = self.rel.related_model
    if not (isinstance(instance, BaseModel) and isinstance(comodel, type)
            and issubclass(comodel, BaseModel)):
        return _DJANGO_X2MANY_GET(self, instance, cls)
    if instance.pk is None:
        return comodel._from_ids(env(), (), ())
    if (isinstance(instance.pk, NewId)
            and not isinstance(self,
                               _related_descriptors.ManyToManyDescriptor)):
        # Un registro de ``new()`` no tiene filas que apunten a él: su One2many
        # vive sólo en el caché de la transacción (``_write_new_one2many``).
        ids = env().transaction.field_data[self.rel].get(instance.pk, ())
        return comodel._from_ids(env(), ids, ids)
    if not isinstance(self, _related_descriptors.ManyToManyDescriptor):
        # El inverso puede estar pendiente de cálculo (un Many2one
        # ``compute=..., store=True``): la fuente lo vuelca antes de leer,
        # porque el One2many se resuelve con ``comodel._search`` y éste hace
        # ``flush_model`` de los campos del dominio
        # (``odoo19c: odoo/orm/fields_relational.py``, ``One2many.read``).
        flush_model(comodel, [self.rel.field.name])
    manager = _DJANGO_X2MANY_GET(self, instance, cls)
    rows = manager.all()
    order = getattr(comodel, '_order', None)
    if order:
        rows = rows.order_by(*order_to_django(comodel, order))
    ids = tuple(rows.values_list('pk', flat=True))
    if isinstance(self, _related_descriptors.ManyToManyDescriptor):
        return _many2many_lines(self, instance, comodel, ids)
    return comodel._from_ids(env(), ids, ids)


_related_descriptors.ReverseManyToOneDescriptor.__get__ = (
    _x2many_descriptor_get)
_DJANGO_X2MANY_SET = _related_descriptors.ReverseManyToOneDescriptor.__set__


def _x2many_descriptor_set(self, instance, value):
    """Asignar un One2many es fijar su conjunto — ≙ ``One2many.write_real``,
    rama ``SET`` (``odoo19c: odoo/orm/fields_relational.py:1027``).

    Sólo un One2many entre ``BaseModel`` (el reverso de un Many2one): la
    fuente admite ``record.line_ids = lines`` y aquí el descriptor de Django
    lo rechazaba («Direct assignment to the reverse side»). Un recordset, una
    lista de ids o una lista de comandos se aplican como en ``write``. El
    Many2many y los modelos de Django conservan la conducta de Django.
    """
    if isinstance(self, _related_descriptors.ManyToManyDescriptor):
        return _DJANGO_X2MANY_SET(self, instance, value)
    comodel = self.rel.related_model
    if not (isinstance(instance, BaseModel) and isinstance(comodel, type)
            and issubclass(comodel, BaseModel)):
        return _DJANGO_X2MANY_SET(self, instance, value)
    if isinstance(instance.pk, NewId):
        _write_new_one2many(self.rel, instance, value)
        return None
    if not is_command_list(value):
        ids = getattr(value, '_ids', None)
        if ids is not None and not all(ids):
            value = self.rel.convert_to_write(value, instance)
        else:
            if ids is None:
                ids = [getattr(item, 'pk', item) for item in (value or ())]
            value = [Command.set(list(ids))]
    apply_one2many_commands(instance, self.rel, value)
    return None


def _write_new_one2many(rel, owner, value):
    """El One2many de un registro de ``new()`` — ≙ ``One2many.write_new``
    (``odoo19c: odoo/orm/fields_relational.py:1121``).

    Nada se escribe en la base: el conjunto de líneas queda en el caché de la
    transacción, indexado por el ``NewId`` del dueño, y cada ``CREATE`` es una
    línea de ``new()`` cuyo inverso apunta al dueño, como en la fuente.
    """
    comodel = rel.related_model
    inverse = rel.field.name
    cache = env().transaction.field_data[rel]
    ids = list(cache.get(owner.pk, ()))
    if not is_command_list(value):
        ids = getattr(value, '_ids', None)
        if ids is None:
            ids = [getattr(item, 'pk', item) for item in (value or ())]
        cache[owner.pk] = tuple(ids)
        return
    for command in value:
        operation = command[0]
        if operation == Command.CREATE:
            line = comodel.new(dict(command[2] or {}), ref=command[1] or None)
            line._update_cache({inverse: owner}, validate=False)
            ids.append(line.id)
        elif operation == Command.UPDATE:
            comodel.browse(command[1])._update_cache(command[2],
                                                     validate=False)
        elif operation in (Command.DELETE, Command.UNLINK):
            ids = [id_ for id_ in ids if id_ != command[1]]
        elif operation == Command.LINK:
            if command[1] not in ids:
                ids.append(command[1])
        elif operation == Command.CLEAR:
            ids = []
        elif operation == Command.SET:
            ids = list(command[2])
    cache[owner.pk] = tuple(ids)


_related_descriptors.ReverseManyToOneDescriptor.__set__ = (
    _x2many_descriptor_set)
_DJANGO_FORWARD_GET_OBJECT = (
    _related_descriptors.ForwardManyToOneDescriptor.get_object)


def _forward_get_object(self, instance):
    """El valor de un Many2one hacia un ``BaseModel`` es ``browse(id)``.

    ≙ ``Many2one.convert_to_record`` (``odoo19c: odoo/orm/
    fields_relational.py:356``): leer el campo no consulta la fila del
    comodelo; el recordset se resuelve campo a campo cuando se lee. Django, en
    cambio, carga la fila entera en ``get_object``. Para un registro de
    ``new()`` esa carga ni siquiera es posible: su id es un ``NewId`` sin fila.
    Un comodelo de Django sigue su lectura nativa.
    """
    comodel = self.field.remote_field.model
    value = self.field.get_local_related_value(instance)
    if (len(value) == 1 and value[0] is not None
            and isinstance(comodel, type) and issubclass(comodel, BaseModel)):
        return comodel._from_ids(env(), value, value)
    return _DJANGO_FORWARD_GET_OBJECT(self, instance)


_related_descriptors.ForwardManyToOneDescriptor.get_object = (
    _forward_get_object)
_DJANGO_FORWARD_GET = _related_descriptors.ForwardManyToOneDescriptor.__get__


def _forward_get(self, instance, cls=None):
    """Un Many2one leído sobre varios registros es la unión de sus valores.

    ≙ ``_Relational.__get__``, rama *multi-record* (``odoo19c: odoo/orm/
    fields_relational.py:42-79``), más ``Many2one.convert_to_record_multi``
    (``:360-364``): el recordset del comodelo con los ids sin repetir y sin
    los vacíos. Aquí cada valor se lee por el registro singular, que ya sabe
    resolver una fila, un registro de ``new()`` y el caché; un recordset de
    un solo id o una fila de Django siguen la lectura de Django.
    """
    ids = getattr(instance, '_ids', None) if instance is not None else None
    comodel = self.field.remote_field.model
    to_records = isinstance(comodel, type) and issubclass(comodel, BaseModel)
    if to_records and ids is not None and not ids:
        # leído sobre un recordset vacío, el valor nulo del campo: otra vez
        # el recordset vacío del comodelo, sin consultar la base
        return comodel._from_ids(env(), (), ())
    if (ids and self.field.concrete
            and all(isinstance(id_, int) for id_ in ids)
            and self.field.attname not in instance.__dict__
            and hasattr(instance, 'check_access') and not env().su
            and not set(ids) <= set(self.field._get_cache(env()))):
        # Fallo de caché de la clave —ni en el almacén de Django ni en la
        # caché del campo— sobre registros persistidos, uno o varios. Allá
        # se lee con ``fetch``, que exige ``check_access('read')`` sobre el
        # recordset entero (``odoo19c: odoo/orm/models.py:3775-3818``); un
        # acierto no comprueba. Un hijo cuyo padre prohíben las reglas no lee
        # ni su propia clave.
        instance.check_access('read')
    if ids is None or len(ids) <= 1 or not to_records:
        value = _DJANGO_FORWARD_GET(self, instance, cls)
        # ≙ ``Many2one.convert_to_record`` (``odoo19c: odoo/orm/
        # fields_relational.py:354-358``): sin valor, el recordset vacío del
        # comodelo, no ``None``. Sólo cuando quien lee es un registro
        # ``BaseModel`` y el comodelo también: una fila de Django conserva el
        # ``None`` de Django, que es el contrato de sus consumidores.
        if (value is None and to_records
                and isinstance(instance, BaseModel)):
            return comodel._from_ids(env(), (), ())
        return value
    environment = env()
    if not environment.su and hasattr(instance, '_has_field_access'):
        if not instance._has_field_access(self.field, 'read'):
            instance._check_field_access(self.field, 'read')
    values = [getattr(record, self.field.attname) for record in instance]
    value_ids = tuple(unique(id_ for id_ in values if id_ is not None))
    return comodel._from_ids(environment, value_ids, value_ids)


_related_descriptors.ForwardManyToOneDescriptor.__get__ = _forward_get
Model._validate_fields = _validate_fields
Model._run_ondelete_checks = _run_ondelete_checks


class RecordCache(collections.abc.Mapping):
    """Los campos de una fila que están en caché, por nombre.

    ≙ ``RecordCache`` (``odoo19c: odoo/orm/models.py:7012-7043``). Docstring de
    la fuente: *"A mapping from field names to values, to read the cache of a
    record."* Es la vista que ``record._cache`` devuelve allá.

    **Dos divergencias de mecanismo, ninguna de contrato.**

    1. *El entorno es ambiente.* La fuente lee ``record.env`` —un ``__slots__``
       del recordset (``:362``)—; aquí una fila es una instancia de Django y no
       lleva entorno, así que se toma el de la transacción en curso con
       :func:`~orm.environments.env`. Es la misma adaptación que hace el resto
       de ``src/orm``.
    2. *La fila ya es una sola.* La fuente abre con ``assert len(record) == 1``
       porque allá recibe un recordset que podría traer N. Aquí el tipo del
       argumento **es** el registro único, así que ese assert no tiene qué
       comprobar; se conserva su intención comprobando que no llegue una
       colección.

    ``_fields`` sí existe con el contrato de la fuente —el registro completo
    del modelo, no sólo sus columnas (tareas #215 y #301)—, así que el
    recorrido de :meth:`__iter__` es el mismo.
    """

    __slots__ = ['_record']

    def __init__(self, record):
        assert not isinstance(record, (list, tuple, set, QuerySet)), (
            "Unexpected RecordCache(%s)" % (record,))
        self._record = record

    def __contains__(self, name):
        """¿Tiene la fila un valor en caché para el campo ``name``?"""
        record = self._record
        field = record._fields[name]
        return record.id in field._get_cache(env())

    def __getitem__(self, name):
        """El valor en caché del campo ``name`` para la fila."""
        record = self._record
        field = record._fields[name]
        return field._get_cache(env())[record.id]

    def __iter__(self):
        """Los nombres de campo que tienen valor en caché.

        **La guarda de ``_get_cache`` es la tercera divergencia**, y es del
        contrato de ``_fields``, no de esta clase. Allá el mapa sólo contiene
        objetos ``Field``, y todos tienen caché. Aquí lo provee ``_meta``, que
        incluye además los descriptores de relación **inversa** de Django
        —``ManyToOneRel``, ``OneToOneRel``, ``ManyToManyRel``—, que no son
        campos: la fuente los modela como ``One2many``, que allá sí es un
        ``Field``. Desde que ``new()`` necesita el One2many de un registro sin
        fila, el ``ManyToOneRel`` tiene caché (``fields_relational.py``,
        ``_reverse_one2many_get_cache``); ``OneToOneRel`` y ``ManyToManyRel``
        siguen sin él, y por ellos la guarda sigue.

        *Métrica (2026-08, antes de ese caché):* atributos de ``res.partner``
        en ``_fields`` con ``_get_cache``: **86 de 128**; los 42 restantes
        eran 36 ``ManyToOneRel``, 4 ``OneToOneRel`` y 2 ``ManyToManyRel``.
        *Ciega a:* un campo que tuviera caché y no la expusiera con ese nombre.
        """
        record = self._record
        id_ = record.id
        environment = env()
        for name, field in record._fields.items():
            if not hasattr(field, '_get_cache'):
                continue
            if id_ in field._get_cache(environment):
                yield name

    def __len__(self):
        """Cuántos campos tienen valor en caché."""
        return sum(1 for name in self)


class _on_empty_recordset:
    """Un método de recordset que también se llama sobre la clase.

    ``env['x']`` devuelve aquí la **clase** del modelo, no el recordset vacío
    que devuelve la fuente (``odoo19c: odoo/orm/environments.py:105``). Con
    eso ``env['x'].browse(ids)`` —la forma más corriente de la fuente— llegaba
    al método sin ``self`` y moría con ``AttributeError``. Este descriptor
    cierra esa diferencia: llamado sobre la clase, el método recibe el
    recordset vacío del entorno activo, que es exactamente lo que la fuente
    le pasa. Llamado sobre un recordset, se comporta como un método normal.

    El recordset vacío se construye al **llamar**, no al leer el atributo,
    para que inspeccionar la clase no exija un entorno activo.
    """

    def __init__(self, func):
        self.func = func
        functools.update_wrapper(self, func)

    def __get__(self, instance, owner):
        if instance is not None:
            return self.func.__get__(instance, owner)
        func = self.func

        @functools.wraps(func)
        def on_empty(*args, **kwargs):
            return func(owner._from_ids(env(), (), ()), *args, **kwargs)
        return on_empty


def _read_properties(records, field, name, data):
    """La rama ``properties`` de ``BaseModel._read_format`` (``odoo19c:
    odoo/orm/models.py:3726-3738``): los valores de todos los registros se
    convierten juntos con ``convert_to_read_multi``."""
    values_list = []
    ids = []
    for record, vals in data:
        try:
            values_list.append(record[name])
            ids.append(record.id)
        except MissingError:
            vals.clear()
    results = field.convert_to_read_multi(values_list, records.browse(ids))
    for record_read_vals, convert_result in zip(data, results):
        record_read_vals[1][name] = convert_result


def _copies(field):
    """Si ``copy`` copia el campo: su atributo ``copy``, o el default de la
    fuente por tipo — ``False`` para un ``One2many`` (``odoo19c:
    odoo/orm/fields_relational.py:869``) y ``True`` para el resto
    (``odoo/orm/fields.py:281``). Una relación inversa de Django no lleva el
    atributo."""
    return getattr(field, 'copy', field.type != 'one2many')


def _readable_ids(field, value):
    """Los ids que el usuario puede leer de un valor ``Many2many``: el
    recordset de un comodelo ``BaseModel``, o el gestor de Django de uno que
    no lo es."""
    if hasattr(value, '_filtered_access'):
        return value._filtered_access('read').ids
    rows = AccessQuerySet(model=field.related_model).filter(
        pk__in=value.values_list('pk', flat=True))
    return list(rows._filtered_access('read').values_list('pk', flat=True))


def _x2many_records(field, value):
    """El recordset del comodelo para un valor x2many: el que ya lo es, o el
    ``QuerySet`` con que se lee hoy un ``One2many`` declarado, con los mismos
    ids. Un comodelo que no es ``BaseModel`` no tiene recordset y rehúsa."""
    if hasattr(value, '_ids'):
        return value
    comodel = field.related_model
    if not (isinstance(comodel, type) and issubclass(comodel, BaseModel)):
        raise TypeError(f'{field} apunta a un modelo sin recordset: '
                        f'{comodel!r}')
    ids = tuple(value.values_list('pk', flat=True))
    return comodel._from_ids(env(), ids, ids)


def _copy_data_blacklist(records, default):
    """La lista negra de ``BaseModel.copy_data`` (``odoo19c:
    odoo/orm/models.py:5418-5434``): las columnas mágicas, ``parent_path`` y
    los FK de ``_inherits``; si el ``default`` trae el FK, también los campos
    del padre que el modelo no redefine."""
    blacklist = set(MAGIC_COLUMNS) | {'parent_path'}
    whitelist = {name for name, field in records._fields.items()
                 if not getattr(field, 'inherited', False)}

    def blacklist_given_fields(model):
        for parent_field in getattr(model, '_inherits', {}).values():
            blacklist.add(parent_field)
            parent = _inherits_parent(model, parent_field)
            if parent is None:
                continue
            if parent_field in default:
                blacklist.update(set(parent._fields) - whitelist)
            else:
                blacklist_given_fields(parent)

    blacklist_given_fields(type(records))
    return blacklist


class BaseModel(DefaultGetMixin, OrderMixin, Model):
    """El recordset — ≙ ``BaseModel`` (``odoo19c:
    odoo/orm/models.py:334-7004``).

    Docstring de la fuente, verbatim en lo que gobierna: *"Every model instance
    is a 'recordset', i.e., an ordered collection of records of the model.
    Recordsets are returned by methods like* :meth:`~.browse`, :meth:`~.search`
    *, or field accesses. Records have no explicit representation: a record is
    represented as a recordset of one record."*

    **Es una base abstracta de Django, y los modelos portados DERIVAN de ella**
    (decisión del ejecutor sobre las tres formas candidatas de
    :ref:`h-api-1083`). Eso fija tres cosas que no son elección de estilo:

    1. ``__slots__`` se declara **verbatim**. Medido
       (``scripts/workbench/basemodel-id-access-20260911T035612/outputs/abstract_base.txt``):
       ``ModelBase`` lo admite sobre una base abstracta, el modelo concreto
       conserva su ``__dict__`` —así que los tres nombres quedan como
       descriptores de ranura sobre la base y las instancias siguen admitiendo
       atributos— y una ranura sin asignar levanta ``AttributeError``, que es
       la conducta que distingue una fila de Django de un recordset.
    2. ``_abstract = True`` lo **hereda** el modelo concreto. En la fuente
    nadie
       deriva de ``BaseModel`` directamente: ``Model(AbstractModel)``
       (``odoo19c: :7049``) invierte ``_abstract``/``_auto``/``_register``.
       Aquí
       el registrante sin tabla es :class:`AbstractModel` de este mismo módulo,
       que **no se toca** (su objeción de ``registrants_without_table`` está
       medida y la gobierna la tarea **#329**).
    3. El recordset **no se construye con** ``Model.__init__``. Ver
       :meth:`_from_ids`.
    4. **Una fila que construye Django lleva la terna desde TASK-API-0402.**
       Antes no la llevaba, y seis de los ocho dunder portados reventaban
       sobre ella (medido entonces sobre ``RecordsetProbe(id=7, label='x')``:
       ``bool`` · ``len`` · ``repr`` · ``hash`` · ``str`` · ``iter`` con
       ``AttributeError: … has no attribute '_ids'``). Hoy ``__init__`` y
       ``from_db`` instalan ``(env, (pk,), (pk,))`` —la forma de ``browse``
       para un id, ``:5897``— y ``save`` la refresca cuando el pk nace. Ver
       :meth:`_install_singleton_triple`.

    **Cobertura del porte, re-derivada contra el banco** — la medición vive en
    ``scripts/workbench/basemodel-contract-20260911T030334/outputs/coverage_derived.txt``.
    Son **dos ejes**, y mezclarlos fue el defecto de la primera redacción:

    *Métodos.* El censo del banco cuenta **194 declaraciones**, no 194 nombres:
    ``__getitem__``, ``grouped`` y ``mapped`` van declarados dos veces
    (``@overload``), así que el contrato son **188 nombres únicos**. Este pase
    porta **33 de esos 188**, y declara **3 fuera del contrato**:
    :meth:`__str__` (divergencia forzada), :meth:`_from_ids` (divergencia de
    mecanismo) y :meth:`_read_field` (la guarda de tamaño, extraída).

    Los **155 sin portar**, por familia —el desglose **suma**, que es lo que la
    primera redacción no hacía—: ``read_group`` 16 · ``cache/recompute`` 16 ·
    ``CRUD`` 16 · ``schema/SQL`` 14 · ``access/check`` 11 · ``search/fetch`` 9
    ·
    ``parent_store`` 8 · ``import/export`` 8 · ``constraints`` 7 ·
    ``properties`` 6 · ``traducción`` 5 · ``name_search`` 5 · ``onchange`` 4 ·
    ``otros`` 30. Dos que este núcleo SÍ necesita están bloqueados y con
    sucesor
    acuñado: :meth:`fetch` (**TASK-API-0399**) y ``_sorted_order_to_function``
    (**TASK-API-0400**).

    *Atributos de clase.* La referencia declara **31** (3 ``ast.Assign`` + 28
    ``ast.AnnAssign``); aquí van **29 verbatim**. Los dos ausentes están
    declarados, no omitidos: ``id`` se porta como el descriptor
    :class:`IdFromIds` que instala ``class_prepared``, y ``display_name`` es un
    campo, fuera del alcance de este pase. El censo del banco publica
    ``atributos de clase: 1`` porque su recorrido sólo visita ``ast.Assign`` —
    ceguera medida, con sucesor en el board **#320**.

    Licencia de la fuente: **LGPL-3** (``odoo19c``), así que el mecanismo es
    copia + adaptación con atribución — no reimplementación.
    """

    __slots__ = ['env', '_ids', '_prefetch_ids']

    def __setattr__(self, name, value):
        """Un registro no admite atributos que su modelo no declare.

        ≙ la conducta que ``__slots__`` da en la fuente
        (``odoo19c: odoo/orm/models.py:362``): sin ``__dict__``, asignar un
        nombre que la clase no declara levanta ``AttributeError``
        (``odoo/addons/test_orm/tests/test_attributes.py``). Aquí el modelo
        concreto de Django conserva su ``__dict__`` —ver el punto 1 del
        docstring de la clase—, así que la ranura sola no lo impide.

        **Divergencia declarada:** los nombres con guion bajo se admiten,
        porque Django guarda en ellos el estado de la instancia (``_state``,
        las cachés de relación y de prelectura) y este ORM sus marcas
        internas. Un nombre público sólo se acepta si la clase lo declara:
        campo, ``attname``, propiedad o método. Lo que Django escribe con
        nombre público libre —``annotate()`` y ``Prefetch(to_attr=…)``— no
        tiene receptor sobre un registro, como no lo tiene en la fuente.
        """
        if name[:1] != '_' and not hasattr(type(self), name):
            raise AttributeError(
                f'{type(self).__name__!r} object has no attribute {name!r}')
        super().__setattr__(name, value)

    #: **Divergencia de mecanismo.** La fuente cuelga el registro completo
    #: de la
    #: clase (``pool: Registry``, ``:362``) porque su metaclase lo construye.
    #: Aquí el registro de Django vive en ``_meta.apps`` y el nuestro en
    #: :mod:`orm.registry`; la anotación se conserva para que el nombre exista
    #: en la cabecera, sin valor que la falsee.
    pool: 'registry.Registry'

    _fields__: dict
    #: ≙ ``BaseModel._fields`` (``:368``). **No se duplica el mecanismo**:
    #: es el
    #: mismo :class:`~orm.utils.FieldRegistryDescriptor` que
    #: :class:`FieldSqlMixin` ya declara en ``:1612``, respaldado por
    #: :func:`~orm.utils.model_field_registry`. Aquí es además el sitio fiel:
    #: la fuente lo declara en ``BaseModel``, no en un mixin.
    _fields = FieldRegistryDescriptor()

    _auto: bool = False
    """Whether a database table should be created."""
    _register: bool = False           #: registry visibility
    _abstract: bool = True
    """ Whether the model is *abstract*. """
    _transient: bool = False
    """ Whether the model is *transient*. """

    @classmethod
    def is_transient(cls) -> bool:
        """Devuelve si el modelo es transitorio — ≙ ``is_transient``
        (``odoo19c: odoo/orm/models.py:5738-5744``), verbatim.

        Docstring de la fuente: *"Return whether the model is transient. See
        :class:`TransientModel`."*

        Es un ``classmethod`` sobre un atributo de clase, y eso es lo que lo
        hace utilizable en una fase temprana: no toca ``env``, no necesita
        instancia ni registro poblado. Lo consume el tercer caso del default
        de ``ondelete`` (``fields_relational.py:274-282`` de la fuente), que
        pregunta por el modelo Y por su comodelo.
        """
        return cls._transient

    # : the model name (in dot-notation, module namespace)
    _name: str = None
    _description: str | None = None     #: the model's informal name
    # : the model's module (in the Odoo sense)
    _module: str | None = None
    # : should be True for custom models only
    _custom: bool = False

    _inherit: str | list | tuple = ()
    """Python-inherited models."""
    _inherits: ReadonlyDict = ReadonlyDict({})
    """dictionary {'parent_model': 'm2o_field'}; ``frozendict`` allá, ≙
    :class:`~tools.misc.ReadonlyDict`."""
    # : SQL table name used by model if :attr:`_auto`
    _table: str = ''
    # : SQL expression of the table's content (optional)
    _table_query: SQL | str | None = None
    _table_objects: ReadonlyDict = ReadonlyDict({})  #: SQL/Table objects
    _inherit_children: OrderedSet

    # : field to use for labeling records, default: ``name``
    _rec_name: str | None = None
    # : fields to consider in ``name_search``
    _rec_names_search: list | None = None
    # : default order field for searching results
    _order: str = 'id'
    # : the many2one field used as parent field
    _parent_name: str = 'parent_id'
    _parent_store: bool = False
    """set to True to compute parent_path field."""
    _active_name: str | None = None
    """field to use for active records."""
    # : field to determine folded groups in kanban views
    _fold_name: str = 'fold'

    # False disables translations export for this model
    _translate: bool = True
    _check_company_auto: bool = False
    """On write and create, call ``_check_company``."""
    _allow_sudo_commands: bool = True
    """Allow One2many and Many2many Commands targeting this model under
    ``sudo()``."""
    _depends: ReadonlyDict = ReadonlyDict({})
    """dependencies of models backed up by SQL views
    ``{model_name: field_names}``."""

    #: ``id = Id()`` (``:472``) **se porta como descriptor instalado
    #: en la clase
    #: concreta**, no como asignación en este cuerpo: ``ModelBase`` pone su
    #: propio ``DeferredAttribute`` sobre ``id`` al preparar la subclase y
    #: sombrea cualquier descriptor de la base — medido en
    #: ``outputs/id_descriptor.txt``. El porte es :class:`IdFromIds` más el
    #: receptor de ``class_prepared`` de más abajo, que lo instala DESPUÉS.
    #: Contraparte: ``odoo19c: odoo/orm/fields_misc.py:102-114``.
    #:
    #: ``display_name = Char(..., compute='_compute_display_name')`` (``:473``)
    #: es un **campo**, no parte de este núcleo: entra con el porte de campos
    #: calculados.

    class Meta:
        abstract = True

    def _valid_field_parameter(self, field, name):
        """Si ``name`` es un parámetro válido del campo — ≙ ``:479-481``.

        Verbatim de la fuente: *"Return whether the given parameter name is
        valid for the field."* Sus consumidores en la referencia son
        ``Field.__init__`` y ``Field._setup_attrs`` (``odoo19c:
        odoo/orm/fields.py:531,652``), que avisan de una clave que ningún
        modelo admite. Esa mitad de validación aquí es divergencia de
        mecanismo declarada en :func:`orm.fields._field_setup`.
        """
        return name == 'related_sudo'

    @api.model
    def _post_model_setup__(self):
        """Gancho tras el montaje del modelo — ≙ ``:483-486``.

        Verbatim de la fuente: *"Method called after the model has been
        setup."* La base no hace nada; un modelo lo redefine.
        """
        pass

    def _register_hook(self):
        """Gancho tras construir el registro — ≙ ``:5819-5820``.

        Verbatim de la fuente: *"stuff to do right after the registry is
        built"*. La base no hace nada; un modelo lo redefine. Allá lo invoca
        el registro (``odoo19c: odoo/orm/registry.py:502``); aquí ese momento
        es ``AppConfig.ready()``, divergencia de mecanismo que ya declaran
        ``res_users`` y ``base_automation``.
        """

    def _unregister_hook(self):
        """Deshace lo que hizo :meth:`_register_hook` — ≙ ``:5822-5823``.

        Verbatim de la fuente: *"Clean up what `~._register_hook` has
        done."* La base no hace nada; su punto de llamada en la fuente es
        ``registry.py:399``.
        """

    def _can_return_content(self, field_name=None, access_token=None):
        """Si se puede servir un archivo del campo aunque el registro no sea
        accesible — ≙ ``:5841-5855``.

        Verbatim de la fuente: *"Determine whether one can export a file or
        an image from a field of record ``self``, even if ``self`` is not
        accessible to the current user."* La base exige un registro y nunca
        concede: devuelve ``False``. Los modelos que conceden lo redefinen;
        el bypass por token que lo consume en ``ir.binary`` es divergencia
        declarada por DEC-11 en ``src/addons/base/models/ir_binary.py``.
        """
        self.ensure_one()
        return False

    @property
    @api.deprecated("Deprecated since 19.0, use self.env.cr directly")
    def _cr(self):
        """Alias deprecado de ``self.env.cr`` — ≙ ``:5911-5914``."""
        return self.env.cr

    @property
    @api.deprecated("Deprecated since 19.0, use self.env.uid directly")
    def _uid(self):
        """Alias deprecado de ``self.env.uid`` — ≙ ``:5916-5919``."""
        return self.env.uid

    @property
    @api.deprecated("Deprecated since 19.0, use self.env.context directly")
    def _context(self):
        """Alias deprecado de ``self.env.context`` — ≙ ``:5921-5924``."""
        return self.env.context

    @property
    def _constraint_methods(self):
        """Los métodos de ``@api.constrains`` del modelo — ≙ ``:519-546``.

        La recolección y su caché viven en
        :data:`orm.registry.constraint_methods`, con su consumidor
        ``_validate_fields``; la propiedad la expone donde la fuente la
        declara.
        """
        return list(registry.constraint_methods(type(self)))

    @property
    def _ondelete_methods(self):
        """Los métodos de ``@api.ondelete`` del modelo — ≙ ``:548-558``.

        Ver :data:`orm.registry.ondelete_methods`.
        """
        return list(registry.ondelete_methods(type(self)))

    @property
    def _onchange_methods(self):
        """Nombre de campo → métodos de ``@api.onchange`` — ≙ ``:560-593``.

        Ver :data:`orm.registry.onchange_methods`.
        """
        return dict(registry.onchange_methods(type(self)))

    def _has_onchange(self, field, other_fields):
        """ Return whether ``field`` should trigger an onchange event in the
            presence of ``other_fields``. — ≙ ``_has_onchange``
            (``odoo19c: odoo/orm/models.py``)

        El ``self.pool`` de la fuente es aquí el módulo :mod:`orm.registry`,
        que expone ``get_dependent_fields`` con la misma firma (la anotación
        ``pool`` de esta clase no lleva valor, ver su comentario).
        """
        return (field.name in self._onchange_methods) or any(
            dep in other_fields
            for dep in registry.get_dependent_fields(field.base_field)
        )

    def _apply_onchange_methods(self, field_name, result, excluded_methods=()):
        """ Apply onchange method(s) for field ``field_name`` on ``self``.
        Value assignments are applied on ``self``, while warning messages are
        put in dictionary ``result``. — ≙ ``:6975-6994``

        El despacho vive en :func:`apply_onchange_methods`, que comparte con
        ``Base.onchange`` de ``web``: allí el registro es una instancia de
        Django y sólo cambia cómo se pregunta por el campo y cómo se asigna.
        """
        apply_onchange_methods(
            self, self._onchange_methods.get(field_name, ()), result,
            excluded_methods, self._fields.__contains__, self.__setitem__,
            self.env._)

    @property
    def _table_sql(self):
        """El ``SQL`` de la tabla del modelo, o de su consulta — ≙
        ``:488-515``.

        Docstring de la fuente: *"Return an :class:`SQL` object that
        represents SQL table identifier or table query."* Si el modelo
        declara ``_depends``, los campos de esa clausura viajan como
        ``to_flush``, para que leer de la consulta vuelque antes lo que
        está pendiente en esos campos.
        """
        table_query = self._table_query
        if table_query and isinstance(table_query, SQL):
            table_sql = SQL("(%s)", table_query)
        elif table_query:
            table_sql = SQL(f"({table_query})")
        else:
            table_sql = SQL.identifier(self._table)
        if not self._depends:
            return table_sql

        fields_to_flush = []
        models = [self]
        while models:
            current_model = models.pop()
            for model_name, field_names in current_model._depends.items():
                model = self.env[model_name]
                models.append(model)
                fields_to_flush.extend(model._fields[fname]
                                       for fname in field_names)

        return SQL().join([
            table_sql,
            *(SQL(to_flush=field) for field in fields_to_flush),
        ])

    #: ≙ ``_has_field_access`` (``:3368-3381``), declarado allá en
    #: ``BaseModel``. Aquí lo implementa :class:`FieldSqlMixin`, que no está en
    #: la MRO de esta clase; se liga la misma función para que
    #: :meth:`fields_get` lo encuentre donde la fuente lo declara.
    _has_field_access = FieldSqlMixin._has_field_access

    def fields_get(self, allfields=None, attributes=None):
        """ Return the definition of each field. — ≙ ``:3343-3366``

        The returned value is a dictionary (indexed by field name) of
        dictionaries. The _inherits'd fields are included. The string, help,
        and selection (if present) attributes are translated.

        :param allfields: fields to document, all if empty or not provided
        :param attributes: attributes to return for each field, all if empty
            or not provided
        :return: dictionary mapping field names to a dictionary mapping
            attributes to values.
        """
        res = {}
        for fname, field in self._fields.items():
            if allfields and fname not in allfields:
                continue
            if not self._has_field_access(field, 'read'):
                continue

            description = field.get_description(self.env,
                                                attributes=attributes)
            if 'readonly' in description:
                description['readonly'] = (
                    description['readonly']
                    or not self._has_field_access(field, 'write'))
            res[fname] = description

        return res

    def read(self, fields=None, load='_classic_read'):
        """Los campos pedidos de cada registro de ``self``, como una lista de
        diccionarios. — ≙ ``read`` (``odoo19c: odoo/orm/models.py:3469-3490``)

        :param fields: nombres de campo; todos los legibles si se omite.
        :param load: con ``None`` no se resuelve el ``display_name`` de las
            relaciones.
        :raise AccessError: si el usuario no puede leer lo pedido.
        :raise ValueError: si un campo pedido no existe.
        """
        if not fields:
            fields = list(self.fields_get(attributes=()))
        elif not self and not self.env.su:
            # con registros, el acceso al campo lo comprueba fetch
            self._determine_fields_to_fetch(fields)
        self._origin.fetch(fields)
        return self._read_format(fnames=fields, load=load)

    def _read_format(self, fnames, load='_classic_read'):
        """Un diccionario por registro que existe, con el formato de
        :meth:`read`, tomado de lo que ya está en memoria. — ≙ ``:3709-3751``

        Un registro que levanta ``MissingError`` al leerse queda fuera. Los
        campos ``properties`` se convierten en lote con
        ``convert_to_read_multi``.
        """
        data = [(record, {'id': record.id}) for record in self]
        use_display_name = (load == '_classic_read')
        for name in fnames:
            field = self._fields[name]
            if field.type == 'properties':
                _read_properties(self, field, name, data)
                continue
            convert = field.convert_to_read
            for record, vals in data:
                # un registro ausente deja su diccionario vacío
                if not vals:
                    continue
                try:
                    vals[name] = convert(record[name], record,
                                         use_display_name)
                except MissingError:
                    vals.clear()
        return [vals for record, vals in data if vals]

    # === construcción =====================================================

    def __init__(self, *args, **kwargs):
        """La fila que Django construye ES un recordset de uno — ≙ ``:5871``.

        La fuente tiene UN constructor y siempre instala la terna
        (``self.env``, ``self._ids``, ``self._prefetch_ids``; ``:5871-5880``).
        Aquí Django aporta dos caminos más —``cls(*values)`` y ``from_db``—
        y, hasta TASK-API-0402, ninguno la instalaba: los tres son ranuras
        de ``__slots__`` y una fila que no pasaba por ``_from_ids`` reventaba
        con ``AttributeError`` en ``__bool__``, ``__len__`` y en cada lector
        de ``self._ids`` (medido: ``_prepare_related_fields_for_save`` de
        Django hace ``if not obj`` sobre el destino de una FK). La forma es la
        que ``browse`` construye para un id —``self.__class__(self.env, ids,
        ids)``, ``:5897``—: ``_ids == (pk,)`` y ``_prefetch_ids == _ids``. El
        entorno es el ambiente (:func:`~orm.environments.env`), la misma
        adaptación que :class:`RecordCache` declara.
        """
        # Una terna vacía mientras Django construye la fila: sus asignaciones
        # pasan por descriptores que leen el registro como recordset —
        # ``Many2one.convert_to_cache`` evalúa ``bool(record)`` en un campo
        # ``delegate``—, y sin ``_ids`` esa lectura moría con
        # ``AttributeError`` en todo modelo con ``_inherits``.
        object.__setattr__(self, '_ids', ())
        super().__init__(*args, **kwargs)
        self._install_singleton_triple()

    @classmethod
    def from_db(cls, db, field_names, values):
        """La fila que llega de una consulta lleva la misma terna que
        ``:5871``."""
        record = super().from_db(db, field_names, values)
        record._install_singleton_triple()
        return record

    def _install_singleton_triple(self):
        """``(env, (pk,), (pk,))`` — el recordset de uno que la fila ES."""
        self.env = env()
        self._ids = (self.pk,)
        self._prefetch_ids = self._ids

    def save(self, *args, **kwargs):
        """El pk nace al insertar y la terna lo sigue.

        ≙ ``create`` (``:4744``), que devuelve ``self.browse(ids)`` con los ids
        recién insertados: allá el recordset nuevo se construye con el id
        real; aquí la fila es la misma instancia y su terna se rehace.
        """
        super().save(*args, **kwargs)
        if self._ids != (self.pk,):
            self._install_singleton_triple()
        self._discard_persisted_dirty(kwargs.get('update_fields'))

    def _discard_persisted_dirty(self, update_fields):
        """Las columnas que este ``save`` acaba de escribir quedan limpias.

        ≙ el ``pop`` de ``_flush`` (``odoo19c: odoo/orm/models.py:6386-6400``):
        lo que se escribe en la base deja de estar sucio. Aquí escribe
        ``Model.save`` de Django, y su ``pre_save`` de un campo ``auto_now``
        asigna la fecha con ``setattr`` *dentro* del mismo guardado; esa
        asignación pasa por ``FieldDescriptor.__set__`` y marca sucio el campo
        que ya iba en el ``UPDATE``. Sin esta limpieza ``flush_all`` no
        convergía tras ninguna escritura (*"Too many iterations for flushing
        fields!"*) y la fecha en caché dejaba de ser la persistida.

        Sólo se limpia el id cuyo valor en caché es el que la fila llevaba al
        guardar: un valor sucio que no se escribió sigue pendiente.
        """
        dirty = get_transaction().field_dirty
        if not dirty or self.pk is None:
            return
        names = None if update_fields is None else set(update_fields)
        environment = env()
        for field in self._meta.concrete_fields:
            if names is not None and not {field.name, field.attname} & names:
                continue
            ids = dirty.get(field)
            if not ids or self.pk not in ids:
                continue
            cached = field._get_cache(environment)
            if (self.pk in cached
                    and cached[self.pk] == self.__dict__.get(field.attname)):
                ids.discard(self.pk)

    @classmethod
    def _from_ids(cls, env, ids, prefetch_ids):
        """Instala la terna del recordset — ≙ ``BaseModel.__init__``
        (``:5871``).

        **Divergencia de mecanismo, medida y forzada.** La fuente construye con
        ``self.__class__(self.env, ids, ids)`` (``browse``, ``:5897``) y **no
        tiene** ``_browse``: medido, 0 declaraciones y 0 llamadas en
        ``odoo19c``
        y ``odoo18c``. Aquí ``__init__`` está ocupado posicionalmente por
        Django, que construye una fila con ``new = cls(*values)``
        (``django/db/models/base.py:604``); usar la firma de la fuente
        rompería la construcción de filas.

        Por eso el recordset se construye **sin pasar por** ``Model.__init__``:
        ``object.__new__`` más las tres ranuras, y ``_state`` a mano porque es
        lo único que ``Model.__init__`` deja y que el resto de Django lee.
        """
        record = object.__new__(cls)
        record._state = ModelState()
        record.env = env
        record._ids = ids
        record._prefetch_ids = prefetch_ids
        return record

    # === agregación de read_group ======================================

    @classmethod
    def _read_group(cls, domain, groupby=(), aggregates=(), having=(),
                    offset=0, limit=None, order=None):
        """Agregados de ``aggregates`` agrupados por ``groupby`` sobre los
        registros que cumplen ``domain``.

        ≙ ``BaseModel._read_group``
        (``odoo19c: odoo/orm/models.py:1861-1952``).
        Devuelve tuplas con, en orden, los valores de agrupado y los de
        agregado; un agrupado relacional es un recordset con su ``prefetch``.

        :raise AccessError: si el usuario no puede leer lo pedido.

        Adaptación declarada: es ``classmethod`` —la forma con que este
        archivo porta los métodos de modelo, como :meth:`_search`— y toma el
        recordset vacío del entorno activo.
        """
        self = cls._from_ids(env(), (), ())
        self.browse().check_access('read')

        query = self._search(domain)
        if query.is_empty():
            if not groupby:
                # sin agrupado, PostgreSQL siempre devuelve una fila
                return [tuple(
                    self._read_group_empty_value(spec)
                    for spec in itertools.chain(groupby, aggregates)
                )]
            return []

        query.limit = limit
        query.offset = offset

        groupby_terms = {
            spec: self._read_group_groupby(self._table, spec, query)
            for spec in groupby
        }
        aggregates_terms = [
            self._read_group_select(spec, query)
            for spec in aggregates
        ]
        select_args = [*[groupby_terms[spec] for spec in groupby],
                       *aggregates_terms]
        if groupby_terms:
            query.order = self._read_group_orderby(order, groupby_terms,
                                                   query)
            query.groupby = SQL(", ").join(groupby_terms.values())
            query.having = self._read_group_having(list(having), query)

        # row_values: [(a1, b1, c1), (a2, b2, c2), ...]
        row_values = self.env.execute_query(query.select(*select_args))

        if not row_values:
            return row_values

        # posproceso columna por columna
        column_iterator = zip(*row_values)

        # column_result: [(a1, a2, ...), (b1, b2, ...), (c1, c2, ...)]
        column_result = []
        for spec in groupby:
            column = self._read_group_postprocess_groupby(
                spec, next(column_iterator))
            column_result.append(column)
        for spec in aggregates:
            column = self._read_group_postprocess_aggregate(
                spec, next(column_iterator))
            column_result.append(column)
        assert next(column_iterator, None) is None

        # [(a1, b1, c1), (a2, b2, c2), ...]
        return list(zip(*column_result))

    @classmethod
    def _read_grouping_sets(cls, domain, grouping_sets, aggregates=(),
                            order=None):
        """Varios agregados con agrupados distintos en una sola consulta.

        ≙ ``BaseModel._read_grouping_sets`` (``odoo19c:
        odoo/orm/models.py:1598-1859``). Usa ``GROUPING SETS`` de SQL como
        alternativa a llamar :meth:`_read_group` varias veces; con many2many
        puede necesitar más de una consulta, por las filas duplicadas.

        :param domain: dominio que filtra los registros antes de agrupar.
        :param grouping_sets: lista de especificaciones ``groupby``, cada una
            equivalente al ``groupby`` de :meth:`_read_group`; p. ej.
            ``[['partner_id'], ['partner_id', 'state']]``.
        :param aggregates: especificaciones ``'campo:agg'``.
        :param order: orden de los grupos, como en :meth:`search`.
        :return: una lista por conjunto, en el orden de ``grouping_sets``,
            de tuplas con los valores agrupados seguidos de los agregados.
        :raise AccessError: si el usuario no puede leer lo pedido.

        Adaptación declarada: ``classmethod`` sobre el recordset vacío del
        entorno activo, como :meth:`_read_group`.
        """
        self = cls._from_ids(env(), (), ())
        if not grouping_sets:
            raise ValueError("The 'grouping_sets' parameter cannot be empty.")

        query = self._search(domain)
        result = [[] for __ in grouping_sets]
        if query.is_empty():
            return result

        # grouping_sets: [(a, b), (a), ()]
        # all_groupby_specs: (a, b)
        all_groupby_specs = tuple(unique(
            spec for groupby in grouping_sets for spec in groupby))

        # --- many2many ---
        many2many_groupby_specs = []
        if len(grouping_sets) > 1:  # sólo aplica con varios agrupados

            def might_duplicate_rows(model, spec):
                fname, property_name, __ = parse_read_group_spec(spec)
                field = model._fields[fname]
                if field.type == 'properties':
                    definition = self.get_property_definition(
                        f"{fname}.{property_name}")
                    property_type = definition.get('type')
                    return property_type in ('tags', 'many2many')

                if property_name:
                    assert field.type == 'many2one'
                    return might_duplicate_rows(
                        self.env[field.comodel_name], property_name)

                return field.type == 'many2many'

            for spec in all_groupby_specs:
                if might_duplicate_rows(self, spec):
                    many2many_groupby_specs.append(spec)

        if (
            many2many_groupby_specs and
            # con agregados sensibles a la duplicación (sum, avg) se aíslan
            # los agrupados many2many
            any(
                not aggregate.endswith(
                    (':max', ':min', ':bool_and', ':bool_or',
                     ':array_agg_distinct', ':recordset', ':count_distinct'),
                )
                for aggregate in aggregates if aggregate != '__count'
            )
        ):
            # Descomposición recursiva: para no corromper los agregados de
            # otros conjuntos, se busca cada combinación de campos many2many
            # y se hace una subllamada con los conjuntos que la comparten.

            # ['A', 'B', 'C'] => [('A', 'B', 'C'), ('A', 'B'), ('A', 'C'),
            #                     ('B', 'C'), ('A',), ('B',), ('C',), ()]
            m2m_combinaisons = (
                groupby for i in range(len(many2many_groupby_specs), -1, -1)
                for groupby in itertools.combinations(
                    many2many_groupby_specs, i)
            )

            grouping_sets_to_process = dict(enumerate(grouping_sets))
            batched_calls = []  # [([groupby, ...], [index_result, ...])]

            for m2m_comb in m2m_combinaisons:
                if not grouping_sets_to_process:
                    break
                sub_grouping_sets = []
                sub_result_indexes = []
                for i, groupby in list(grouping_sets_to_process.items()):
                    if all(m2m in groupby for m2m in m2m_comb):
                        sub_grouping_sets.append(groupby)
                        sub_result_indexes.append(i)
                        grouping_sets_to_process.pop(i)

                if sub_grouping_sets:
                    batched_calls.append(
                        (sub_result_indexes, sub_grouping_sets))

            assert not grouping_sets_to_process
            # descompuesto: llamadas recursivas y ensamblado del resultado
            if len(batched_calls) > 1:
                for indexes, sub_grouping_sets in batched_calls:

                    sub_order_parts = []
                    all_sub_groupby = {spec for groupby in sub_grouping_sets
                                       for spec in groupby}
                    for order_part in (order or '').split(','):
                        order_part = order_part.strip()
                        if not any(
                            order_part.startswith(spec)
                            for spec in all_groupby_specs
                            if spec not in all_sub_groupby
                        ):
                            sub_order_parts.append(order_part)

                    sub_results = self._read_grouping_sets(
                        domain, sub_grouping_sets, aggregates=aggregates,
                        order=",".join(sub_order_parts),
                    )
                    for index, subresult in zip(indexes, sub_results):
                        result[index] = subresult
                return result

        elif many2many_groupby_specs and '__count' in aggregates:
            # '__count' con many2many: cuenta distinta de 'id', sin otra
            # llamada (el caso más común)
            aggregates = tuple(
                aggregate if aggregate != '__count' else 'id:count_distinct'
                for aggregate in aggregates
            )
            if order:
                order = order.replace('__count', 'id:count_distinct')

        # --- la consulta SQL ---
        groupby_terms = {
            spec: self._read_group_groupby(self._table, spec, query)
            for spec in all_groupby_specs
        }
        aggregates_terms = [
            self._read_group_select(spec, query) for spec in aggregates
        ]
        if groupby_terms:
            # grouping_select_sql: GROUPING(a, b)
            grouping_select_sql = SQL(
                "GROUPING(%s)",
                SQL(", ").join(unique(groupby_terms.values())))
        else:
            # GROUPING() no es SQL válido: se usa el literal 0
            grouping_select_sql = SQL("0")

        select_args = [grouping_select_sql, *groupby_terms.values(),
                       *aggregates_terms]

        # _read_group_orderby puede cambiar groupby_terms: va antes
        query.order = self._read_group_orderby(order, groupby_terms, query)
        # GROUPING SET ((a, b), (a), ())
        grouping_sets_sql = [
            SQL("(%s)", SQL(", ").join(
                groupby_terms[groupby_spec] for groupby_spec in grouping_set))
            for grouping_set in grouping_sets
        ]
        query.groupby = SQL("GROUPING SETS (%s)",
                            SQL(", ").join(unique(grouping_sets_sql)))

        # row_values: [(GROUPING(...), a1, b1, agregados...), ...]
        row_values = self.env.execute_query(query.select(*select_args))

        if not row_values:  # atajo
            return result

        # --- posproceso del resultado ---
        # El entero que devuelve GROUPING() es la clave que asigna cada fila
        # al conjunto que la produjo.
        aggregates_indexes = tuple(range(
            len(all_groupby_specs),
            len(all_groupby_specs) + len(aggregates)))

        # {GROUPING(...): (append_method, extractor_method)}
        mask_grouping_mapping = {}

        # El bit de cada término único de GROUP BY. Se recorren invertidos
        # porque PostgreSQL calcula la máscara de derecha a izquierda (el
        # bit menos significativo primero).
        mask_sql_mapping = {
            sql_groupby: 1 << i
            for i, sql_groupby in enumerate(
                unique(reversed(groupby_terms.values())))
        }

        # para los agrupados "duplicados"
        mask_grouping_result_indexes = collections.defaultdict(list)
        for result_index, groupby in enumerate(grouping_sets):
            # GROUPING SET ((a, b), (a), ())
            # GROUPING(a, b): a y b = 0, sólo a = 1, sólo b = 2, ninguno = 3
            sql_terms = {groupby_terms[groupby_spec]
                         for groupby_spec in groupby}
            groupby_mask = sum(
                mask for sql_term, mask in mask_sql_mapping.items()
                # cada bit vale 0 si la expresión está en el conjunto que
                # produjo la fila, y 1 si no
                if sql_term not in sql_terms
            )

            mask_grouping_result_indexes[groupby_mask].append(result_index)
            if groupby_mask not in mask_grouping_mapping:
                mask_grouping_mapping[groupby_mask] = (
                    result[result_index].append,
                    itemgetter_tuple(list(itertools.chain(
                        (all_groupby_specs.index(groupby_spec)
                         for groupby_spec in groupby),
                        aggregates_indexes,
                    ))),
                )

        aggregates_start_index = len(all_groupby_specs) + 1
        # filas a columnas, para posprocesar columna por columna
        columns = list(zip(*row_values))
        # la primera columna es la máscara
        dispatch_info = map(mask_grouping_mapping.__getitem__, columns[0])
        columns = [
            *map(self._read_group_postprocess_groupby, all_groupby_specs,
                 columns[1:aggregates_start_index]),
            *map(self._read_group_postprocess_aggregate, aggregates,
                 columns[aggregates_start_index:]),
        ]

        for (append_method, extractor), *row in zip(
                dispatch_info, *columns, strict=True):
            append_method(extractor(row))

        # los agrupados sobre las mismas columnas comparten resultado
        for duplicate_groups_indexes in mask_grouping_result_indexes.values():
            if len(duplicate_groups_indexes) < 2:
                continue
            # el primero es la fuente de los demás
            source_result_group = result[duplicate_groups_indexes[0]]
            for duplicate_group_index in duplicate_groups_indexes[1:]:
                result[duplicate_group_index] = source_result_group[:]

        return result

    def _read_group_select(self, aggregate_spec, query):
        """La expresión SQL del agregado ``aggregate_spec``.

        ≙ ``BaseModel._read_group_select``
        (``odoo19c: odoo/orm/models.py:1953-2013``). Docstring de la fuente:
        *"Return <SQL expression> corresponding to the given aggregation. The
        method also checks whether the fields used in the aggregate are
        accessible for reading."*

        Adaptación declarada: ``res.currency.rate`` es aquí un modelo de
        Django y ``env[...]`` devuelve su clase; ``_field_to_sql`` se llama
        sobre una instancia, que resuelve ``currency_id``/``company_id`` por
        su columna. El contrato del SQL no cambia.
        """
        if aggregate_spec == '__count':
            return SQL("COUNT(*)")

        fname, property_name, func = parse_read_group_spec(aggregate_spec)

        if property_name:
            raise ValueError(
                f"Invalid {aggregate_spec!r}, this dot notation is not "
                f"supported")

        if fname not in self._fields:
            raise ValueError(
                f"Invalid field {fname!r} on model {self._name!r} for "
                f"{aggregate_spec!r}.")
        if not func:
            raise ValueError(f"Aggregate method is mandatory for {fname!r}")

        field = self._fields[fname]
        if func == 'sum_currency':
            if field.type != 'monetary':
                raise ValueError(
                    f'Aggregator "sum_currency" only works on currency field '
                    f'for {fname!r}')

            CurrencyRate = self.env['res.currency.rate']()
            rate_subquery_table = SQL(
                """(SELECT DISTINCT ON (%(currency_field_sql)s)
                        %(currency_field_sql)s, %(rate_field_sql)s
                    FROM "res_currency_rate"
                    WHERE %(company_field_sql)s IS NULL
                        OR %(company_field_sql)s = %(company_id)s
                    ORDER BY
                        %(currency_field_sql)s,
                        %(company_field_sql)s,
                        CASE WHEN %(name_field_sql)s <= %(today)s
                            THEN %(name_field_sql)s END DESC,
                        CASE WHEN %(name_field_sql)s > %(today)s
                            THEN %(name_field_sql)s END ASC)
                """,
                currency_field_sql=CurrencyRate._field_to_sql(
                    CurrencyRate._table, 'currency_id'),
                rate_field_sql=CurrencyRate._field_to_sql(
                    CurrencyRate._table, 'rate'),
                company_field_sql=CurrencyRate._field_to_sql(
                    CurrencyRate._table, 'company_id'),
                company_id=self.env.company.root_id.id,
                name_field_sql=CurrencyRate._field_to_sql(
                    CurrencyRate._table, 'name'),
                today=Date.context_today(self),
            )
            currency_field_name = field.get_currency_field(self)
            alias_rate = query.make_alias(
                self._table, f'{currency_field_name}__rates')
            currency_field_sql = self._field_to_sql(
                self._table, currency_field_name, query)
            condition = SQL(
                "%s = %s", currency_field_sql,
                SQL.identifier(alias_rate, "currency_id"))
            query.add_join(
                'LEFT JOIN', alias_rate, rate_subquery_table, condition)

            return SQL(
                "SUM(%s / COALESCE(%s, 1.0))",
                self._field_to_sql(self._table, fname, query),
                SQL.identifier(alias_rate, "rate"),
            )

        if func not in READ_GROUP_AGGREGATE:
            raise ValueError(
                f"Invalid aggregate method {func!r} for {aggregate_spec!r}.")

        if func == 'recordset' and not (field.relational or fname == 'id'):
            raise ValueError(
                f"Aggregate method {func!r} can be only used on relational "
                f"field (or id) (for {aggregate_spec!r}).")

        sql_field = self._field_to_sql(self._table, fname, query)
        return READ_GROUP_AGGREGATE[func](self._table, sql_field)

    def _read_group_groupby(self, alias, groupby_spec, query):
        """La expresión SQL de un elemento de agrupado.

        ≙ ``BaseModel._read_group_groupby`` (``odoo19c:
        odoo/orm/models.py:2015-2119``). Docstring de la fuente: *"Return
        <SQL expression> corresponding to the given groupby element. The
        method also checks whether the fields used in the groupby are
        accessible for reading."*

        Adaptaciones declaradas (``designs/read-group-groupby.md``):

        - ``_search`` es aquí ``classmethod`` y no lee el contexto del
          recordset: ``with_context(active_test=False)`` y ``field.context``
          llegan como su parámetro ``active_test``, que dice lo mismo.
        - un comodelo de Django en una cadena many2one no tiene
          ``_read_group_groupby`` con que seguir bajando: se rehúsa con
          ``NotImplementedError``. En un many2many, sus filas entran como
          subconsulta con sus reglas (``django_comodel_rows``).
        """
        fname, seq_fnames, granularity = parse_read_group_spec(groupby_spec)
        if fname not in self._fields:
            raise ValueError(
                f"Invalid field {fname!r} on model {self._name!r}")

        field = self._fields[fname]

        if field.type == 'properties':
            sql_expr = self._read_group_groupby_properties(
                alias, field, seq_fnames, query)

        elif seq_fnames:
            if field.type != 'many2one':
                raise ValueError(
                    f"Only many2one path is accepted for the "
                    f"{groupby_spec!r} groupby spec")

            comodel = self.env[field.comodel_name]
            if not hasattr(comodel, '_from_ids'):
                raise NotImplementedError(
                    f"Grouping through {field.comodel_name!r}, a Django "
                    f"model without _read_group_groupby")
            comodel = comodel._from_ids(self.env, (), ())
            coquery = comodel._search([], active_test=False)
            if self.env.su or not coquery.where_clause:
                coalias = query.make_alias(alias, fname)
            else:
                coalias = query.make_alias(alias, f"{fname}__{self.env.uid}")
            condition = SQL(
                "%s = %s",
                self._field_to_sql(alias, fname, query),
                SQL.identifier(coalias, 'id'),
            )
            if coquery.where_clause:
                subselect_arg = SQL('%s.*', SQL.identifier(comodel._table))
                query.add_join('LEFT JOIN', coalias,
                               coquery.subselect(subselect_arg), condition)
            else:
                query.add_join('LEFT JOIN', coalias, comodel._table,
                               condition)
            return comodel._read_group_groupby(
                coalias,
                f"{seq_fnames}:{granularity}" if granularity
                else seq_fnames,
                query)

        elif granularity and field.type not in ('datetime', 'date',
                                                'properties'):
            raise ValueError(
                f"Granularity set on a no-datetime field or property: "
                f"{groupby_spec!r}")

        elif field.type == 'many2many':
            if getattr(field, 'related', None) and not field.store:
                _model, field, alias = self._traverse_related_sql(
                    alias, field, query)

            if not getattr(field, 'store', True):
                raise ValueError(
                    f"Group by non-stored many2many field: {groupby_spec!r}")
            # caso especial del many2many: una consulta del comodelo que se
            # inyecta como condición adicional del LEFT JOIN
            codomain = field.get_comodel_domain(self) \
                if hasattr(field, 'get_comodel_domain') \
                else multi_comodel_domain(field, self)
            context = getattr(field, 'context', None) or {}
            bypass = getattr(field, 'bypass_search_access', False)
            comodel = self.env[field.comodel_name]
            if hasattr(comodel, '_from_ids'):
                coquery = comodel._search(
                    codomain, active_test=context.get('active_test', True),
                    bypass_access=bypass)
                cofilter = coquery.subselect() \
                    if coquery.where_clause else None
            else:
                cofilter = queryset_subselect(django_comodel_rows(
                    comodel, Domain(codomain), bypass_access=bypass))
            # LEFT JOIN {field.relation} AS rel_alias ON
            #     alias.id = rel_alias.{field.column1}
            #     AND rel_alias.{field.column2} IN ({coquery})
            # tabla y columnas de la relación, en sus dos formas (campo y
            # relación inversa de Django)
            relation, column1, column2 = m2m_relation(field)
            rel_alias = query.make_alias(alias, field.name)
            condition = SQL(
                "%s = %s",
                SQL.identifier(alias, 'id'),
                SQL.identifier(rel_alias, column1),
            )
            if cofilter is not None:
                condition = SQL(
                    "%s AND %s IN %s",
                    condition,
                    SQL.identifier(rel_alias, column2),
                    cofilter,
                )
            query.add_join("LEFT JOIN", rel_alias, relation, condition)
            return SQL.identifier(rel_alias, column2)

        else:
            sql_expr = self._field_to_sql(alias, fname, query)

        if field.type in ('datetime', 'date') or (
                field.type == 'properties' and granularity):
            if not granularity:
                raise ValueError(
                    f"Granularity not set on a date(time) field: "
                    f"{groupby_spec!r}")
            if granularity not in READ_GROUP_ALL_TIME_GRANULARITY:
                raise ValueError(
                    f"Granularity specification isn't correct: "
                    f"{granularity!r}")

            if granularity in READ_GROUP_NUMBER_GRANULARITY:
                sql_expr = field.property_to_sql(
                    sql_expr, granularity, self, alias, query)
            elif field.type == 'datetime':
                # sólo se fija la zona
                sql_expr = field.property_to_sql(
                    sql_expr, 'tz', self, alias, query)

            if granularity == 'week':
                # first_week_day: 0=Monday, 1=Tuesday, ...
                first_week_day = int(get_lang(self.env).week_start) - 1
                days_offset = first_week_day and 7 - first_week_day
                interval = f"-{days_offset} DAY"
                sql_expr = SQL(
                    "(date_trunc('week', %s::timestamp - INTERVAL %s) "
                    "+ INTERVAL %s)",
                    sql_expr, interval, interval,
                )
            elif granularity in READ_GROUP_TIME_GRANULARITY:
                sql_expr = SQL("date_trunc(%s, %s::timestamp)",
                               granularity, sql_expr)

            # una parte numérica da un número (double) y no se convierte
            if (field.type == 'date'
                    and granularity not in READ_GROUP_NUMBER_GRANULARITY):
                # date_trunc devuelve timestamp: se vuelve a date
                sql_expr = SQL("%s::date", sql_expr)

        elif field.type == 'boolean':
            sql_expr = SQL("COALESCE(%s, FALSE)", sql_expr)

        return sql_expr

    def _read_group_orderby(self, order, groupby_terms, query):
        """El ``ORDER BY`` de un agrupado.

        ≙ ``BaseModel._read_group_orderby`` (``odoo19c:
        odoo/orm/models.py``). Docstring de la fuente: *"Return (<SQL
        expression>, <SQL expression>) corresponding to the given order and
        groupby terms. Note: this method may change groupby_terms"*.
        """
        if order:
            traverse_many2one = True
        else:
            order = ','.join(groupby_terms)
            traverse_many2one = False

        if not order:
            return SQL()

        orderby_terms = []

        for order_part in order.split(','):
            order_match = regex_order_part_read_group.fullmatch(order_part)
            if not order_match:
                raise ValueError(f"Invalid order {order!r} for _read_group()")
            term = order_match['term']
            direction = (order_match['direction'] or 'ASC').upper()
            nulls = (order_match['nulls'] or '').upper()

            sql_direction = SQL(direction) \
                if direction in ('ASC', 'DESC') else SQL()
            sql_nulls = SQL(nulls) \
                if nulls in ('NULLS FIRST', 'NULLS LAST') else SQL()

            if term not in groupby_terms:
                try:
                    sql_expr = self._read_group_select(term, query)
                except ValueError as e:
                    raise ValueError(
                        f"Order term {order_part!r} is not a valid aggregate "
                        f"nor valid groupby") from e
                orderby_terms.append(
                    SQL("%s %s %s", sql_expr, sql_direction, sql_nulls))
                continue

            field = self._fields.get(term)
            __, __, granularity = parse_read_group_spec(term)
            if (
                traverse_many2one and field and field.type == 'many2one'
                and self.env[field.comodel_name]._order != 'id'
            ):
                if sql_order := self._order_to_sql(
                        f'{term} {direction} {nulls}', query):
                    orderby_terms.append(sql_order)
                    if query._order_groupby:
                        groupby_terms[term] = SQL(", ").join(
                            [groupby_terms[term], *query._order_groupby])
                        query._order_groupby.clear()

            elif granularity == 'day_of_week':
                # desplazamiento respecto del primer día de la semana del
                # idioma: ((7 - first_week_day) + day_in_SQL) % 7
                first_week_day = int(get_lang(self.env).week_start)
                sql_expr = SQL("mod(7 - %s + %s::int, 7)", first_week_day,
                               groupby_terms[term])
                orderby_terms.append(
                    SQL("%s %s %s", sql_expr, sql_direction, sql_nulls))
            else:
                sql_expr = groupby_terms[term]
                orderby_terms.append(
                    SQL("%s %s %s", sql_expr, sql_direction, sql_nulls))

        return SQL(", ").join(orderby_terms)

    def _read_group_having(self, having_domain, query):
        """La expresión SQL del dominio ``HAVING``.

        ≙ ``BaseModel._read_group_having``
        (``odoo19c: odoo/orm/models.py:2121-2148``). Notación prefija como un
        dominio; los términos sueltos se unen con ``AND``.
        """
        if not having_domain:
            return SQL()

        stack = []
        SUPPORTED = ('in', 'not in', '<', '>', '<=', '>=', '=', '!=')
        for item in reversed(having_domain):
            if item == '!':
                stack.append(SQL("(NOT %s)", stack.pop()))
            elif item == '&':
                stack.append(SQL("(%s AND %s)", stack.pop(), stack.pop()))
            elif item == '|':
                stack.append(SQL("(%s OR %s)", stack.pop(), stack.pop()))
            elif isinstance(item, (list, tuple)) and len(item) == 3:
                left, operator, right = item
                if operator not in SUPPORTED:
                    raise ValueError(
                        f"Invalid having clause {item!r}: supported "
                        f"comparators are {SUPPORTED}")
                sql_left = self._read_group_select(left, query)
                stack.append(SQL(
                    "%s%s%s", sql_left, SQL_OPERATORS[operator], right))
            else:
                raise ValueError(
                    f"Invalid having clause {item!r}: it should be a "
                    f"domain-like clause")

        while len(stack) > 1:
            stack.append(SQL("(%s AND %s)", stack.pop(), stack.pop()))

        return stack[0]

    def _read_group_empty_value(self, spec):
        """El valor vacío de un spec de agrupado o de agregado.

        ≙ ``BaseModel._read_group_empty_value`` (``odoo19c:
        odoo/orm/models.py``). Docstring de la fuente: *"Return the empty
        value corresponding to the given groupby spec or aggregate spec."*
        """
        if spec == '__count':
            return 0
        # func es None, una granularidad o un agregado
        fname, chain_fnames, func = parse_read_group_spec(spec)
        if func in ('count', 'count_distinct'):
            return 0
        if func in ('array_agg', 'array_agg_distinct'):
            return []
        field = self._fields[fname]
        if ((not func or func == 'recordset')
                and (field.relational or fname == 'id')):
            if chain_fnames and field.type == 'many2one':
                groupby_seq = (f"{chain_fnames}:{func}" if func
                               else chain_fnames)
                model = self.env[field.comodel_name]
                return _read_group_recordset(
                    self.env, model, (), ())._read_group_empty_value(
                        groupby_seq)
            model = self.env[field.comodel_name if field.relational
                             else self._name]
            return _read_group_recordset(self.env, model, (), ())
        return False

    def _read_group_postprocess_groupby(self, groupby_spec, raw_values):
        """Los valores de ``groupby_spec`` en el formato de ``_read_group``.

        ≙ ``BaseModel._read_group_postprocess_groupby`` (``odoo19c:
        odoo/orm/models.py``): un relacional da recordsets con el
        ``prefetch`` correcto y un ``NULL`` da el valor vacío.
        """
        empty_value = self._read_group_empty_value(groupby_spec)

        fname, chain_fnames, granularity = parse_read_group_spec(groupby_spec)
        field = self._fields[fname]

        if field.relational or fname == 'id':
            if chain_fnames and field.relational:
                groupby_seq = (f"{chain_fnames}:{granularity}" if granularity
                               else chain_fnames)
                model = self.env[field.comodel_name]
                return _read_group_recordset(
                    self.env, model, (), ())._read_group_postprocess_groupby(
                        groupby_seq, raw_values)

            Model = self.env[field.comodel_name if field.relational
                             else self._name]
            prefetch_ids = tuple(
                raw_value for raw_value in raw_values if raw_value)

            def recordset(value):
                return (_read_group_recordset(
                    self.env, Model, (value,), prefetch_ids)
                    if value else empty_value)

            return (recordset(value) for value in raw_values)

        return ((value if value is not None else empty_value)
                for value in raw_values)

    def _read_group_postprocess_aggregate(self, aggregate_spec, raw_values):
        """Los valores de ``aggregate_spec`` en el formato de ``_read_group``.

        ≙ ``BaseModel._read_group_postprocess_aggregate`` (``odoo19c:
        odoo/orm/models.py``): un agregado ``recordset`` da recordsets con el
        ``prefetch`` correcto y un ``NULL`` da el valor vacío.
        """
        empty_value = self._read_group_empty_value(aggregate_spec)

        if aggregate_spec == '__count':
            return ((value if value is not None else empty_value)
                    for value in raw_values)

        fname, __, func = parse_read_group_spec(aggregate_spec)
        if func == 'recordset':
            field = self._fields[fname]
            Model = self.env[field.comodel_name if field.relational
                             else self._name]
            prefetch_ids = tuple(unique(
                id_
                for array_values in raw_values if array_values
                for id_ in array_values if id_
            ))

            def recordset(value):
                if not value:
                    return empty_value
                ids = tuple(unique(id_ for id_ in value if id_))
                return _read_group_recordset(
                    self.env, Model, ids, prefetch_ids)

            return (recordset(value) for value in raw_values)

        return ((value if value is not None else empty_value)
                for value in raw_values)

    def _read_group_expand_full(self, groups, domain):
        """Extiende el grupo a todos los registros del comodelo.

        ≙ ``BaseModel._read_group_expand_full`` (``odoo19c:
        odoo/orm/models.py:2310-2313``). Docstring de la fuente: *"Extend the
        group to include all target records by default."*
        """
        return groups.search([])

    def _read_group_fill_results(self, domain, groupby, annoted_aggregates,
                                 read_group_result, read_group_order=None):
        """Rellena los grupos vacíos con todos los valores posibles del campo.

        ≙ ``BaseModel._read_group_fill_results`` (``odoo19c:
        odoo/orm/models.py:2315-2385``). Docstring de la fuente: *"Helper
        method for filling in empty groups for all possible values of the
        field being grouped by"*.

        Adaptaciones declaradas, sin cambio de conducta: ``env.registry`` es
        aquí un módulo, así que el método se busca en ``type(self)``; los
        registros del comodelo se construyen con
        :func:`_read_group_recordset`; un ``QuerySet`` de Django no ofrece
        ``sudo`` ni ``_fold_name``, y se omiten sólo cuando faltan.
        """
        field_name = groupby.split('.')[0].split(':')[0]
        field = self._fields[field_name]
        if not field or not field.group_expand:
            return read_group_result

        # field.group_expand es un invocable o el nombre de un método que
        # devuelve los grupos a mostrar para este campo, como recordset o
        # como lista de valores según su tipo. Sirve, p. ej., a las vistas
        # kanban, que muestran columnas aunque no contengan registros.
        group_expand = field.group_expand
        if isinstance(group_expand, str):
            group_expand = getattr(type(self), group_expand)
        assert callable(group_expand)

        # todos los grupos que hay que devolver
        values = [line[groupby] for line in read_group_result
                  if line[groupby]]

        if field.relational:
            # groups es un recordset; el orden lo da el modelo de groups
            comodel = self.env[field.comodel_name]
            group_ids = tuple(value.id for value in values)
            groups = _read_group_recordset(
                self.env, comodel, group_ids, group_ids)
            values = group_expand(self, groups, domain)
            if hasattr(values, 'sudo'):
                values = values.sudo()
            if read_group_order == groupby + ' desc':
                # Como en la fuente, el resultado no se reasigna.
                values.browse(reversed(values._ids))

            def value2key(value):
                return value and value.id

        else:
            # groups es una lista de valores
            values = group_expand(self, values, domain)
            if read_group_order == groupby + ' desc':
                values.reverse()

            def value2key(value):
                return value

        # Fusiona los resultados actuales (lista de dicts) con todos los
        # grupos. El orden global es el de read_group_result, que se supone
        # el mismo cuando el campo es many2one.
        read_group_result_as_dict = {}
        for line in read_group_result:
            read_group_result_as_dict[value2key(line[groupby])] = line

        empty_item = {
            name: self._read_group_empty_value(spec)
            for name, spec in annoted_aggregates.items()
        }

        result = {}
        # el resultado sigue el orden de values
        for value in values:
            key = value2key(value)
            if key in read_group_result_as_dict:
                result[key] = read_group_result_as_dict.pop(key)
            else:
                result[key] = dict(empty_item, **{groupby: value})

        for line in read_group_result_as_dict.values():
            key = value2key(line[groupby])
            result[key] = line

        # información de plegado, si el comodelo la declara
        fold_name = getattr(groups, '_fold_name', None) if field.relational \
            else None
        if fold_name and fold_name in groups._fields:
            fold = {group.id: group[fold_name]
                    for group in groups.browse(key for key in result if key)}
            for key, line in result.items():
                line['__fold'] = fold.get(key, False)

        return list(result.values())

    def _read_group_fill_temporal(self, data, groupby, annoted_aggregates,
                                  fill_from=False, fill_to=False,
                                  min_groups=False):
        """Rellena los huecos de fecha/fecha-hora de un resultado agrupado.

        ≙ ``BaseModel._read_group_fill_temporal`` (``odoo19c:
        odoo/orm/models.py:2387-2552``). La fuente documenta el caso con
        gráficas: agrupado por mes con datos en junio, septiembre y
        diciembre, la gráfica junta diciembre con septiembre; con ceros
        explícitos para los meses sin datos la serie queda contigua.

        ``fill_from``/``fill_to`` (inclusivos, ``%Y-%m-%d`` o
        ``%Y-%m-%d %H:%M:%S``) acotan el tramo que se rellena; los grupos
        fuera de él no se retiran. Sin ellos, los límites son el primer y el
        último grupo existentes (se supone ``data`` ordenada por el campo).
        ``min_groups`` garantiza al menos esa cantidad de grupos contiguos
        desde ``fill_from`` (o el grupo más bajo), sin acotarse por
        ``fill_to``. Sin límites ni grupos no se devuelve ninguno.
        """
        # TODO de la fuente: retirar min_groups
        first_group = groupby[0]
        field_name = first_group.split(':')[0].split(".")[0]
        field = self._fields[field_name]
        if field.type not in ('date', 'datetime') and not (
                field.type == 'properties' and ':' in first_group):
            return data

        granularity = (first_group.split(':')[1] if ':' in first_group
                       else 'month')
        days_offset = 0
        if granularity == 'week':
            # los grupos de semana dependen del idioma, así que los
            # rellenados también, para que no se solapen.
            first_week_day = int(get_lang(self.env).week_start) - 1
            days_offset = first_week_day and 7 - first_week_day
        interval = READ_GROUP_TIME_GRANULARITY[granularity]
        tz = False
        if (field.type == 'datetime'
                and self.env.context.get('tz') in pytz.all_timezones_set):
            tz = pytz.timezone(self.env.context['tz'])

        # fechas no nulas existentes
        existing = [d[first_group] for d in data if d[first_group]] or [None]
        # supuesto: data está ordenada por el campo agrupado
        existing_from, existing_to = existing[0], existing[-1]
        if fill_from:
            fill_from = (Datetime.to_datetime(fill_from)
                         if isinstance(fill_from, datetime.datetime)
                         else Date.to_date(fill_from))
            fill_from = (date_utils.start_of(fill_from, granularity)
                         - datetime.timedelta(days=days_offset))
            if tz:
                fill_from = tz.localize(fill_from)
        elif existing_from:
            fill_from = existing_from
        if fill_to:
            fill_to = (Datetime.to_datetime(fill_to)
                       if isinstance(fill_to, datetime.datetime)
                       else Date.to_date(fill_to))
            fill_to = (date_utils.start_of(fill_to, granularity)
                       - datetime.timedelta(days=days_offset))
            if tz:
                fill_to = tz.localize(fill_to)
        elif existing_to:
            fill_to = existing_to

        if not fill_to and fill_from:
            fill_to = fill_from
        if not fill_from and fill_to:
            fill_from = fill_to
        if not fill_from and not fill_to:
            return data

        if min_groups > 0:
            fill_to = max(fill_to, fill_from + (min_groups - 1) * interval)

        if fill_to < fill_from:
            return data

        required_dates = date_utils.date_range(fill_from, fill_to, interval)

        if existing[0] is None:
            existing = list(required_dates)
        else:
            existing = sorted(set().union(existing, required_dates))

        empty_item = {
            name: self._read_group_empty_value(spec)
            for name, spec in annoted_aggregates.items()
        }
        for group in groupby[1:]:
            empty_item[group] = self._read_group_empty_value(group)

        grouped_data = collections.defaultdict(list)
        for d in data:
            grouped_data[d[first_group]].append(d)

        result = []
        for dt in existing:
            result.extend(grouped_data[dt]
                          or [dict(empty_item, **{first_group: dt})])

        if False in grouped_data:
            result.extend(grouped_data[False])

        return result

    def _read_group_format_result(self, rows_dict, lazy_groupby):
        """Formatea las filas agrupadas: dominio, rango y etiqueta.

        ≙ ``BaseModel._read_group_format_result`` (``odoo19c:
        odoo/orm/models.py:2554-2638``). Docstring de la fuente: *"Helper
        method to format the data contained in the dictionary data by adding
        the domain corresponding to its values, the groupbys in the context
        and by properly formatting the date/datetime values."*

        La rama ``properties`` delega en
        :meth:`_read_group_format_result_properties`.
        """
        for group in lazy_groupby:
            field_name = group.split(':')[0].split('.')[0]
            field = self._fields[field_name]

            if field.type in ('date', 'datetime'):
                granularity = (group.split(':')[1] if ':' in group
                               else 'month')
                if granularity in READ_GROUP_TIME_GRANULARITY:
                    locale = get_lang(self.env).code
                    fmt = (DEFAULT_SERVER_DATETIME_FORMAT
                           if field.type == 'datetime'
                           else DEFAULT_SERVER_DATE_FORMAT)
                    interval = READ_GROUP_TIME_GRANULARITY[granularity]
            elif field.type == "properties":
                self._read_group_format_result_properties(rows_dict, group)
                continue

            for row in rows_dict:
                value = row[group]

                if isinstance(value, BaseModel):
                    row[group] = ((value.id, value.sudo().display_name)
                                  if value else False)
                    value = value.id

                if not value and field.type == 'many2many':
                    additional_domain = [(field_name, 'not any', [])]
                else:
                    additional_domain = [(field_name, '=', value)]

                if field.type in ('date', 'datetime'):
                    if value and isinstance(
                            value, (datetime.date, datetime.datetime)):
                        range_start = value
                        range_end = value + interval
                        if field.type == 'datetime':
                            tzinfo = None
                            if (self.env.context.get('tz')
                                    in pytz.all_timezones_set):
                                tzinfo = pytz.timezone(self.env.context['tz'])
                                range_start = tzinfo.localize(
                                    range_start).astimezone(pytz.utc)
                                # un posible cambio de hora entre inicio y fin
                                range_end = tzinfo.localize(
                                    range_end).astimezone(pytz.utc)

                            label = babel.dates.format_datetime(
                                range_start,
                                format=READ_GROUP_DISPLAY_FORMAT[granularity],
                                tzinfo=tzinfo, locale=locale,
                            )
                        else:
                            label = babel.dates.format_date(
                                value,
                                format=READ_GROUP_DISPLAY_FORMAT[granularity],
                                locale=locale,
                            )
                        # caso especial de semana: babel está roto *y*
                        # ubuntu revirtió un cambio, así que es inconsistente
                        if granularity == 'week':
                            year, week = date_utils.weeknumber(
                                babel.Locale.parse(locale),
                                value,  # fecha sin conversión a UTC
                            )
                            label = f"W{week} {year:04}"

                        range_start = range_start.strftime(fmt)
                        range_end = range_end.strftime(fmt)
                        row[group] = label  # TODO de la fuente: dato crudo
                        row.setdefault('__range', {})[group] = {
                            'from': range_start, 'to': range_end}
                        additional_domain = [
                            '&',
                            (field_name, '>=', range_start),
                            (field_name, '<', range_end),
                        ]
                    elif (value is not None
                          and granularity in READ_GROUP_NUMBER_GRANULARITY):
                        additional_domain = [
                            (f"{field_name}.{granularity}", '=', value)]
                    elif not value:
                        # el grupo de registros sin fecha lleva __range False
                        row.setdefault('__range', {})[group] = False

                row['__domain'] &= Domain(additional_domain)
        for row in rows_dict:
            row['__domain'] = list(row['__domain'])

    def _read_group_format_result_properties(self, rows_dict, group):
        """Ajusta el resultado final de un agrupado por propiedad.

        ≙ ``BaseModel._read_group_format_result_properties`` (``odoo19c:
        odoo/orm/models.py:2638-2744``). La fuente: sustituye los ids de las
        propiedades relacionales por una tupla con su nombre, los valores
        crudos de etiquetas y selección por una lista con sus etiquetas, y
        adapta el dominio del grupo vacío — no basta ``(selection, =,
        False)``, porque en la base puede haber opciones que ya se
        retiraron del padre.
        """
        if '.' not in group:
            raise ValueError(
                'You must choose the property you want to group by.')
        fullname, __, func = group.partition(':')

        definition = self.get_property_definition(fullname)
        property_type = definition.get('type')

        if property_type == 'selection':
            options = definition.get('selection') or []
            options = tuple(option[0] for option in options)
            for row in rows_dict:
                if not row[fullname]:
                    # no basta ('selection', '=', False): en la base puede
                    # haber opciones que ya no existen
                    additional_domain = (Domain(fullname, '=', False)
                                         | Domain(fullname, 'not in', options))
                else:
                    additional_domain = Domain(fullname, '=', row[fullname])

                row['__domain'] &= additional_domain

        elif property_type == 'many2one':
            comodel = definition.get('comodel')
            prefetch_ids = tuple(row[fullname] for row in rows_dict
                                 if row[fullname])
            all_groups = tuple(row[fullname] for row in rows_dict
                               if row[fullname])
            for row in rows_dict:
                if not row[fullname]:
                    # no basta ('many2one', '=', False): en la base puede
                    # haber registros que ya no existen
                    additional_domain = (Domain(fullname, '=', False)
                                         | Domain(fullname, 'not in',
                                                  all_groups))
                else:
                    additional_domain = Domain(fullname, '=', row[fullname])
                    record = self.env[comodel].browse(
                        row[fullname]).with_prefetch(prefetch_ids)
                    row[fullname] = (row[fullname], record.display_name)

                row['__domain'] &= additional_domain

        elif property_type == 'many2many':
            comodel = definition.get('comodel')
            prefetch_ids = tuple(row[fullname] for row in rows_dict
                                 if row[fullname])
            all_groups = tuple(row[fullname] for row in rows_dict
                               if row[fullname])
            for row in rows_dict:
                if not row[fullname]:
                    if all_groups:
                        additional_domain = (
                            Domain(fullname, '=', False)
                            | Domain.AND([(fullname, 'not in', group)]
                                         for group in all_groups))
                    else:
                        additional_domain = Domain.TRUE
                else:
                    additional_domain = Domain(fullname, 'in', row[fullname])
                    record = self.env[comodel].browse(
                        row[fullname]).with_prefetch(prefetch_ids)
                    row[fullname] = (row[fullname], record.display_name)

                row['__domain'] &= additional_domain

        elif property_type == 'tags':
            tags = definition.get('tags') or []
            tags = {tag[0]: tag for tag in tags}
            for row in rows_dict:
                if not row[fullname]:
                    if tags:
                        additional_domain = (
                            Domain(fullname, '=', False)
                            | Domain.AND([(fullname, 'not in', tag)]
                                         for tag in tags))
                    else:
                        additional_domain = Domain.TRUE
                else:
                    additional_domain = Domain(fullname, 'in', row[fullname])
                    # el valor crudo de la etiqueta pasa a valor, etiqueta y
                    # color
                    row[fullname] = tags.get(row[fullname])

                row['__domain'] &= additional_domain

        elif property_type in ('date', 'datetime'):
            for row in rows_dict:
                if not row[group]:
                    row[group] = False
                    row['__domain'] &= Domain(fullname, '=', False)
                    row['__range'] = {}
                    continue

                # Date / Datetime no son JSON: se guardan como texto
                db_format = ('%Y-%m-%d' if property_type == 'date'
                             else '%Y-%m-%d %H:%M:%S')

                if func == 'week':
                    # el valor es el primer día de la semana (según idioma)
                    start = row[group].strftime(db_format)
                    end = (row[group] + datetime.timedelta(days=7)
                           ).strftime(db_format)
                else:
                    start = (date_utils.start_of(row[group], func)
                             ).strftime(db_format)
                    end = (date_utils.end_of(row[group], func)
                           + datetime.timedelta(minutes=1)
                           ).strftime(db_format)

                row['__domain'] &= (Domain(fullname, '>=', start)
                                    & Domain(fullname, '<', end))
                row['__range'] = {group: {'from': start, 'to': end}}
                row[group] = babel.dates.format_date(
                    row[group],
                    format=READ_GROUP_DISPLAY_FORMAT[func],
                    locale=get_lang(self.env).code,
                )
        else:
            for row in rows_dict:
                row['__domain'] &= Domain(fullname, '=', row[fullname])

    def _read_group_groupby_properties(self, alias, field, property_name,
                                       query):
        """La expresión SQL de agrupado de una propiedad.

        ≙ ``BaseModel._read_group_groupby_properties`` (``odoo19c:
        odoo/orm/models.py:2935-3041``).

        Adaptaciones declaradas: los mensajes se traducen con
        ``self.env._`` (la forma de este archivo) en vez de ``_``; el
        comodelo se resuelve con ``self.env.get``, que existe desde que
        ``Environment`` es un ``Mapping``, y es la clase del modelo. Su
        abstracción se lee en ``_meta.abstract``: aquí todo modelo concreto
        hereda ``_abstract = True`` de :class:`BaseModel` (divergencia
        declarada en su docstring, tarea #329), así que ``_abstract`` no
        separa un modelo concreto de uno abstracto como en la fuente.
        """
        fname = field.name
        definition = self.get_property_definition(f"{fname}.{property_name}")
        property_type = definition.get('type')
        sql_property = self._field_to_sql(
            alias, f'{fname}.{property_name}', query)

        # JOIN sobre el arreglo JSON
        if property_type in ('tags', 'many2many'):
            property_alias = query.make_alias(
                alias, f'{fname}_{property_name}')
            sql_property = SQL(
                """ CASE
                        WHEN jsonb_typeof(%(property)s) = 'array'
                        THEN %(property)s
                        ELSE '[]'::jsonb
                     END """,
                property=sql_property,
            )
            if property_type == 'tags':
                # se ignoran las etiquetas inválidas
                tags = [tag[0] for tag in definition.get('tags') or []]
                # `->>0`: de "cadena JSON" a cadena
                condition = SQL(
                    "%s->>0 = ANY(%s::text[])",
                    SQL.identifier(property_alias), tags,
                )
            else:
                comodel = self.env.get(definition.get('comodel'))
                if (comodel is None or getattr(comodel, '_transient', False)
                        or comodel._meta.abstract):
                    raise UserError(self.env._(
                        "You cannot use “%(property_name)s” because the "
                        "linked “%(model_name)s” model doesn't exist or is "
                        "invalid",
                        property_name=definition.get('string', property_name),
                        model_name=definition.get('comodel'),
                    ))

                # que el many2many exista
                condition = SQL(
                    "%s::int IN (SELECT id FROM %s)",
                    SQL.identifier(property_alias),
                    SQL.identifier(comodel._table),
                )

            query.add_join(
                "LEFT JOIN",
                property_alias,
                SQL("jsonb_array_elements(%s)", sql_property),
                condition,
            )

            return SQL.identifier(property_alias)

        elif property_type == 'selection':
            options = [option[0]
                       for option in definition.get('selection') or ()]

            # que la opción exista
            property_alias = query.make_alias(
                alias, f'{fname}_{property_name}')
            query.add_join(
                "LEFT JOIN",
                property_alias,
                SQL("(SELECT unnest(%s::text[]) %s)", options,
                    SQL.identifier(property_alias)),
                SQL("%s->>0 = %s", sql_property,
                    SQL.identifier(property_alias)),
            )

            return SQL.identifier(property_alias)

        elif property_type == 'many2one':
            comodel = self.env.get(definition.get('comodel'))
            if (comodel is None or getattr(comodel, '_transient', False)
                    or comodel._meta.abstract):
                raise UserError(self.env._(
                    "You cannot use “%(property_name)s” because the linked "
                    "“%(model_name)s” model doesn't exist or is invalid",
                    property_name=definition.get('string', property_name),
                    model_name=definition.get('comodel'),
                ))

            return SQL(
                """ CASE
                        WHEN jsonb_typeof(%(property)s) = 'number'
                         AND (%(property)s)::int IN (SELECT id FROM %(table)s)
                        THEN %(property)s
                        ELSE NULL
                     END """,
                property=sql_property,
                table=SQL.identifier(comodel._table),
            )

        elif property_type == 'date':
            return SQL(
                """ CASE
                        WHEN jsonb_typeof(%(property)s) = 'string'
                        THEN (%(property)s->>0)::DATE
                        ELSE NULL
                     END """,
                property=sql_property,
            )

        elif property_type == 'datetime':
            return SQL(
                """ CASE
                        WHEN jsonb_typeof(%(property)s) = 'string'
                        THEN to_timestamp(%(property)s->>0,
                                          'YYYY-MM-DD HH24:MI:SS')
                        ELSE NULL
                     END """,
                property=sql_property,
            )

        elif property_type == 'html':
            raise UserError(
                self.env._('Grouping by HTML properties is not supported.'))

        # sin la clave en el dict, False en vez de None
        return SQL("COALESCE(%s, 'false')", sql_property)

    @api.readonly
    @api.deprecated(
        "Since 19.0, read_group is deprecated. Please use _read_group in "
        "the backend code or formatted_read_group for a complete formatted "
        "result")
    def read_group(self, domain, fields, groupby, offset=0, limit=None,
                   orderby=False, lazy=True):
        """Obsoleto — la lista de registros agrupada por ``groupby``.

        ≙ ``BaseModel.read_group`` (``odoo19c: odoo/orm/models.py:2746-2878``).
        La fuente lo declara obsoleto desde 19.0: el código del servidor usa
        :meth:`_read_group` y quien necesita el resultado formateado,
        ``formatted_read_group``.

        :param list domain: dominio de búsqueda; ``[]`` para todos.
        :param list fields: ``campo`` (agregado por defecto), ``campo:agg`` o
            ``nombre:agg(campo)``.
        :param list groupby: especificaciones de agrupado; una fecha sin
            granularidad agrupa por mes.
        :param int offset: grupos que se saltan.
        :param int limit: máximo de grupos.
        :param str orderby: el orden, sobre grupos y agregados.
        :param bool lazy: con ``True`` agrupa sólo por el primer ``groupby``
            y deja el resto en ``__context``; con ``False``, por todos.
        :return: una lista de dicts con los valores de grupo, los agregados,
            ``<campo>_count`` o ``__count``, ``__domain``, ``__context`` y,
            para fechas, ``__range``.
        :raise AccessError: si el usuario no puede leer el modelo.
        """
        groupby = [groupby] if isinstance(groupby, str) else groupby
        lazy_groupby = groupby[:1] if lazy else groupby

        # Capa de compatibilidad con _read_group, que la fuente prevé retirar
        # en la segunda parte de su refactor:
        # - 'month' por defecto en el groupby de fechas
        # - fields como especificación de agregados de _read_group
        # - el orden compatible con la especificación de _read_group
        groupby = [groupby] if isinstance(groupby, str) else groupby
        lazy_groupby = groupby[:1] if lazy else groupby

        # clave: nombre en el resultado; valor: el groupby explícito
        annotated_groupby = {}
        for group_spec in lazy_groupby:
            field_name, property_name, granularity = parse_read_group_spec(
                group_spec)
            if field_name not in self._fields:
                raise ValueError(
                    f"Invalid field {field_name!r} on model {self._name!r}")
            field = self._fields[field_name]
            if property_name and field.type != 'properties':
                raise ValueError(
                    f"Property name {property_name!r} has to be used on a "
                    "property field.")
            if field.type in ('date', 'datetime'):
                annotated_groupby[group_spec] = (
                    f"{field_name}:{granularity or 'month'}")
            else:
                annotated_groupby[group_spec] = group_spec

        # clave: nombre en el resultado; valor: el agregado explícito
        annotated_aggregates = {
            f"{lazy_groupby[0].split(':')[0]}_count"
            if lazy and len(lazy_groupby) == 1 else '__count': '__count',
        }
        for field_spec in fields:
            if field_spec == '__count':
                continue
            match = regex_field_agg.match(field_spec)
            if not match:
                raise ValueError(
                    f"Invalid field specification {field_spec!r}.")
            name, func, fname = match.groups()

            if fname:  # la forma "field_min:min(field)"
                annotated_aggregates[name] = f"{fname}:{func}"
                continue
            if func:  # la forma "field:min"
                annotated_aggregates[name] = f"{name}:{func}"
                continue

            if name not in self._fields:
                raise ValueError(
                    f"Invalid field {name!r} on model {self._name!r}")
            field = self._fields[name]
            if (field.base_field.store and field.base_field.column_type
                    and field.aggregator
                    and field_spec not in annotated_groupby):
                annotated_aggregates[name] = f"{name}:{field.aggregator}"

        if orderby:
            new_terms = []
            for order_term in orderby.split(','):
                order_term = order_term.strip()
                for key_name, annotated in itertools.chain(
                        reversed(annotated_groupby.items()),
                        annotated_aggregates.items()):
                    key_name = key_name.split(':')[0]
                    if (order_term.startswith(f'{key_name} ')
                            or key_name == order_term):
                        order_term = order_term.replace(key_name, annotated)
                        break
                new_terms.append(order_term)
            orderby = ','.join(new_terms)
        else:
            orderby = ','.join(annotated_groupby.values())

        domain = Domain(domain)
        rows = self._read_group(
            domain, annotated_groupby.values(), annotated_aggregates.values(),
            offset=offset, limit=limit, order=orderby)
        rows_dict = [
            dict(zip(itertools.chain(annotated_groupby, annotated_aggregates),
                     row))
            for row in rows
        ]

        fill_temporal = self.env.context.get('fill_temporal')
        if (lazy_groupby and (rows_dict and fill_temporal)
                or isinstance(fill_temporal, dict)):
            # fill_temporal = {} equivale a fill_temporal = True. Con un
            # dict y sin datos puede quererse mostrar columnas vacías, así
            # que se aplica igual.
            if not isinstance(fill_temporal, dict):
                fill_temporal = {}
            # TODO de la fuente: no debería ser posible con un límite
            rows_dict = self._read_group_fill_temporal(
                rows_dict, lazy_groupby,
                annotated_aggregates, **fill_temporal,
            )

        if lazy_groupby and lazy:
            # read_group sólo rellena resultados en modo lazy (el defecto).
            # Para tener los grupos vacíos en modo eager habría que
            # reimplementar _read_group_fill_results por completo.
            # TODO de la fuente: no debería ser posible con un límite, o el
            # límite debería tenerse en cuenta.
            rows_dict = self._read_group_fill_results(
                domain, lazy_groupby[0],
                annotated_aggregates, rows_dict, read_group_order=orderby,
            )

        for row in rows_dict:
            row['__domain'] = domain
            if len(lazy_groupby) < len(groupby):
                row['__context'] = {'group_by': groupby[len(lazy_groupby):]}

        self._read_group_format_result(rows_dict, lazy_groupby)

        return rows_dict

    # === búsqueda =======================================================

    @classmethod
    def _active_field_name(cls):
        """``_active_name`` — ``'active'`` o ``'x_active'`` si el modelo lo
        declara.

        ≙ el ``_active_name`` que la fuente fija en el setup del modelo
        (``odoo19c: odoo/orm/model_classes.py``): un modelo con campo
        ``active`` filtra sus registros archivados al buscar.
        """
        return active_field_name(cls)

    @classmethod
    def _search(cls, domain, offset=0, limit=None, order=None, *,
                active_test=True, bypass_access=False):
        """El ``Query`` de los registros que cumplen ``domain`` — ≙
        ``_search`` (``odoo19c: odoo/orm/models.py:5324-5394``).

        Docstring de la fuente: *"No default order is applied when the method
        is invoked without parameter order. [...] by default the returned
        query object is not actually executed, and it can be injected as a
        value in a domain in order to generate sub-queries."*

        Los pasos y su orden son los de la fuente: ACL de lectura salvo
        elevación o ``bypass_access``; filtro de archivados salvo que el
        dominio nombre el campo o el contexto lo apague; dominio optimizado a
        ``FULL`` en el ``WHERE``; el dominio de ``ir.rule`` optimizado con el
        recordset en ``sudo()`` y ``active_test=False``; orden, límite y
        desplazamiento. La consulta no se ejecuta.

        Adaptaciones declaradas: es ``classmethod`` —la forma con que este
        archivo porta los métodos de modelo— y toma el recordset vacío con
        ``_from_ids``; ``ir.rule._compute_domain`` recibe los grupos y el
        usuario explícitos, como en :meth:`AccessQuerySet._check_access`.
        Decisión y evidencia: ``designs/search-contract-analysis.md`` del
        Workbench de ``completar-raiz-orm``.
        """
        self = cls._from_ids(env(), (), ())
        check_access = not (self.env.su or bypass_access)
        if check_access:
            self.browse().check_access('read')

        domain = Domain(domain)
        # los archivados, salvo que se pidan explícitamente
        active_name = cls._active_field_name()
        if (active_name
                and active_test
                and self.env.context.get('active_test', True)
                and not any(leaf.field_expr == active_name
                            for leaf in domain.iter_conditions())):
            domain &= Domain(active_name, '=', True)

        # la consulta
        domain = domain.optimize_full(self)
        if domain.is_false():
            return self.browse()._as_query()
        query = Query(self.env, self._table, self._table_sql)
        if not domain.is_true():
            query.add_where(domain._to_sql(self, self._table, query))

        # el dominio de acceso por fila
        if check_access:
            self_sudo = self.sudo().with_context(active_test=False)
            actor = self.env.user
            group_ids = tuple(actor._get_group_ids()) if actor else ()
            sec_domain = apps.get_model('base', 'IrRule')._compute_domain(
                cls._meta.label, 'read', group_ids=group_ids, user=actor)
            sec_domain = sec_domain.optimize_full(self_sudo)
            if sec_domain.is_false():
                return self.browse()._as_query()
            if not sec_domain.is_true():
                query.add_where(
                    sec_domain._to_sql(self_sudo, self._table, query))

        # orden y ventana
        if order:
            query.order = self._order_to_sql(order, query)

        # en RPC no existe None y se usa False para «sin límite»; True se
        # conserva por compatibilidad (vale 1)
        if limit is not None and limit is not False:
            query.limit = limit
        if offset is not None:
            query.offset = offset

        return query

    @api.private
    def unlink(self):
        """Borra los registros de ``self`` — ≙ ``unlink`` (``odoo19c:
        odoo/orm/models.py``, ``BaseModel.unlink``).

        Mismos pasos que la fuente: ACL de borrado; los cómputos pendientes
        de estas filas se descartan; se vuelca lo pendiente; se borra; y se
        invalida **toda** la caché, porque —dice la fuente— *"the orm does
        not handle all changes made in the database, like cascading
        delete"*.

        **Divergencia de mecanismo:** el ``DELETE`` lo emite el ``Collector``
        de Django (``QuerySet.delete``). Su ``pre_delete`` corre las
        comprobaciones ``@api.ondelete`` (:func:`_run_ondelete_checks`) y las
        cascadas de ``on_delete``, que aquí sustituyen al ``ON DELETE`` de las
        claves de la fuente. La limpieza de ``ir.model.data`` y
        ``ir.attachment`` sigue en manos de sus propios receptores de borrado.
        """
        if not self:
            return True
        rows = AccessQuerySet(model=type(self)).filter(pk__in=self.ids)
        rows.check_access('unlink')
        environment = env()
        registry_ = model_field_registry(type(self))
        for field in set(registry_.values()):
            environment.remove_to_compute(field, self.ids)
        environment.flush_all()
        # ≙ ``with self.env.protecting(self._fields.values(), self):
        # self.modified(self._fields, before=True)``: lo que depende de estas
        # filas se marca para recalcular ANTES de borrarlas, mientras todavía
        # se puede seguir la relación inversa (la suma de unas líneas tras
        # borrar una)
        with environment.protecting(set(registry_.values()), self):
            self.modified(list(registry_), before=True)
        rows.delete()
        environment.invalidate_all(flush=False)
        return True

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None):
        """Los registros que cumplen ``domain`` — ≙ ``search`` (``:1363``).

        Devuelve el recordset de ``BaseModel`` en el orden pedido, o en el
        ``_order`` del modelo si no se pide ninguno, como ``search_fetch``.
        """
        return cls.search_fetch(domain, [], offset=offset, limit=limit,
                                order=order)

    @classmethod
    def _rec_name_fallback(cls):
        """``_rec_name`` del modelo, o ``'id'`` si no tiene. — ≙
        ``_rec_name_fallback`` (``odoo19c: odoo/orm/models.py:1340-1343``)

        Allá es ``@api.model``; aquí, ``classmethod``, la forma con que este
        archivo porta los métodos de modelo. El comentario de la fuente
        —*"if self._rec_name is set, it belongs to self._fields"*— lo
        garantiza :func:`~orm.model_classes.resolve_rec_name`, que valida el
        declarado y deja ``None`` cuando no hay campo que lo respalde.
        """
        return cls._rec_name or 'id'

    @classmethod
    def search_count(cls, domain, limit=None):
        """Cuántos registros cumplen ``domain`` — ≙ ``search_count``
        (``:1347``)."""
        query = cls._search(domain, limit=limit)
        return len(query)

    @classmethod
    def search_fetch(cls, domain, field_names=None, offset=0, limit=None,
                     order=None):
        """Los registros que cumplen ``domain``, con ``field_names`` ya en
        memoria. — ≙ ``search_fetch``
        (``odoo19c: odoo/orm/models.py:1394-1428``)

        :raise AccessError: si el usuario no puede leer lo pedido.

        Como la fuente: el ``Query`` de :meth:`_search` (dominio, reglas,
        orden y ventana) se lee con :meth:`_fetch_query` en una sola consulta,
        y uno vacío no se ejecuta.
        """
        # primero, una consulta que satisface dominio y reglas de acceso
        query = cls._search(domain, offset=offset, limit=limit,
                            order=order or cls._order)
        found = cls._from_ids(env(), (), ())

        if query.is_empty():
            # optimización: la consulta no se ejecuta
            if not is_su():  # se comprueba el acceso a los campos
                found._determine_fields_to_fetch(field_names)
            return found

        fields_to_fetch = found._determine_fields_to_fetch(field_names)

        return found._fetch_query(query, fields_to_fetch)

    @classmethod
    def search_read(cls, domain=None, fields=None, offset=0, limit=None,
                    order=None, **read_kwargs):
        """:meth:`search_fetch` seguido de :meth:`_read_format`. — ≙
        ``search_read`` (``odoo19c: odoo/orm/models.py:6286-6329``)

        ``read_kwargs`` llega a ``_read_format``; ``load=None`` evita el
        ``display_name`` de las relaciones. La clave ``active_test`` del
        contexto sólo vale para la búsqueda principal y no se reenvía a las
        lecturas que el formato dispare.
        """
        if not fields:
            fields = list(cls.browse().fields_get(attributes=()))
        records = cls.search_fetch(domain or [], fields, offset=offset,
                                   limit=limit, order=order)
        if 'active_test' in records.env.context:
            context = dict(records.env.context)
            del context['active_test']
            records = records.with_context(context)
        return records._read_format(fnames=fields, **read_kwargs)

    def _has_cycle(self, field_name=None):
        """Si los registros de ``self`` están en un ciclo siguiendo la
        relación ``field_name``, o la del padre si se omite. — ≙
        ``_has_cycle`` (``odoo19c: odoo/orm/models.py:5624-5682``)

        Como allá, la consulta ignora ``active`` y las reglas de fila, y no
        toma un bloqueo exclusivo: transacciones concurrentes aún pueden crear
        un ciclo. **Divergencia de nombres:** la columna de un ``Many2one`` es
        su ``column`` de Django (``parent_id`` para ``parent``), y la tabla y
        las columnas de un ``Many2many`` salen de su modelo intermedio, porque
        una relación sin ``relation`` explícito conserva el nombrado de
        Django. El ``IN %s`` de la fuente es ``= ANY(%s)``: psycopg 3 adapta
        una lista a un arreglo y no expande una tupla.

        :raise ValueError: si el campo no existe o no es una relación
            ``many2one``/``many2many`` almacenada sobre el propio modelo.
        """
        if not field_name:
            field_name = parent_name_of(type(self))
        field = self._fields.get(field_name)
        if not field:
            raise ValueError(f'Invalid field_name: {field_name!r}')
        if not (field.type in ('many2many', 'many2one')
                and field.comodel_name == self._name
                and field.store):
            raise ValueError('Field must be a many2one or many2many relation '
                             f'on itself: {field_name!r}')
        if not self.ids:
            return False
        # se ignoran 'active', las reglas, etc.: consulta recursiva directa
        self.flush_model([field_name])
        if field.type == 'many2many':
            relation = field.remote_field.through._meta.db_table
            column1 = field.m2m_column_name()
            column2 = field.m2m_reverse_name()
        else:
            relation = self._table
            column1 = 'id'
            column2 = field.column
        rows = self.env.execute_query(SQL(
            """
            WITH RECURSIVE __reachability AS (
                SELECT %(col1)s AS source, %(col2)s AS destination
                FROM %(rel)s
                WHERE %(col1)s = ANY(%(ids)s) AND %(col2)s IS NOT NULL
            UNION
                SELECT r.source, t.%(col2)s
                FROM __reachability r
                JOIN %(rel)s t
                    ON r.destination = t.%(col1)s AND t.%(col2)s IS NOT NULL
            )
            SELECT 1 FROM __reachability
            WHERE source = destination
            LIMIT 1
            """,
            ids=list(self.ids),
            rel=SQL.identifier(relation),
            col1=SQL.identifier(column1),
            col2=SQL.identifier(column2),
        ))
        return bool(rows)

    @api.deprecated("Deprecated since 18.0, use _has_cycle() instead")
    def _check_recursion(self, parent=None):
        """≙ ``:5684-5686``."""
        return not self._has_cycle(parent)

    @api.deprecated("Deprecated since 18.0, use _has_cycle() instead")
    def _check_m2m_recursion(self, field_name):
        """≙ ``:5688-5690``."""
        return not self._has_cycle(field_name)

    def _get_external_ids(self):
        """Los ids externos de cada registro — ``{id: ['modulo.nombre']}``.
        — ≙ ``_get_external_ids`` (``odoo19c: odoo/orm/models.py:5695-5714``)

        Todos los que tenga cada registro, en orden de ``id`` de
        ``ir.model.data``, y lista vacía si no tiene ninguno; la clave es el id
        de origen, como allá. El ``sudo()`` de la fuente es aquí el gestor de
        Django de ``ir.model.data``, que no filtra por permiso. La columna
        ``model`` guarda la etiqueta de Django —la escribe
        ``IrModelData._update_xmlids``, su único escritor—, la misma
        convención que :meth:`AccessQuerySet._get_external_ids`.
        """
        Data = apps.get_model('base', 'IrModelData')
        result = collections.defaultdict(list)
        rows = Data.objects.filter(
            model=self._meta.label, res_id__in=list(self.ids),
        ).order_by('pk').values_list('module', 'name', 'res_id')
        for module, name, res_id in rows:
            result[res_id].append('%s.%s' % (module, name))
        return {record.id: result[record._origin.id] for record in self}

    def get_external_id(self):
        """Un id externo por registro, o ``''`` — ≙ ``get_external_id``
        (``:5716-5735``): con varios, el primero de ``_get_external_ids``."""
        results = self._get_external_ids()
        return {key: val[0] if val else ''
                for key, val in results.items()}

    def get_metadata(self):
        """Return some metadata about the given records.
        — ≙ ``get_metadata`` (``odoo19c: odoo/orm/models.py``)

        :returns: list of ownership dictionaries for each requested record
            with the keys ``id``, the ``_log_access`` columns, ``xmlid``,
            ``xmlids`` and ``noupdate``.

        **Divergencia declarada, la de** ``LOG_ACCESS_COLUMNS``: allá son
        los dos usuarios y las dos fechas; aquí, las dos fechas que el árbol
        declara (``orm/model_classes.py``). Se leen sólo si el modelo las
        tiene, porque ``_log_access`` no las crea: son campos declarados.
        El ``sudo()`` sobre ``ir.model.data`` es el gestor de Django, que no
        filtra por permiso, como en :meth:`_get_external_ids`.
        """
        Data = apps.get_model('base', 'IrModelData')
        fields_ = self._fields
        if (getattr(type(self), '_log_access', True)
                and all(name in fields_ for name in LOG_ACCESS_COLUMNS)):
            res = self.read(LOG_ACCESS_COLUMNS)
        else:
            res = [{'id': x} for x in self.ids]

        xml_data = collections.defaultdict(list)
        imds = Data.objects.filter(
            model=self._meta.label, res_id__in=list(self.ids),
        ).order_by('-pk').values('res_id', 'noupdate', 'module', 'name')
        for imd in imds:
            xml_data[imd['res_id']].append({
                'xmlid': "%s.%s" % (imd['module'], imd['name']),
                'noupdate': imd['noupdate'],
            })

        for r in res:
            main = xml_data.get(r['id'], [{}])[-1]
            r['xmlid'] = main.get('xmlid', False)
            r['noupdate'] = main.get('noupdate', False)
            r['xmlids'] = xml_data.get(r['id'], [])[::-1]
        return res

    def lock_for_update(self, *, allow_referencing=False):
        """Bloquea en exclusiva todas las filas de ``self`` o lanza
        ``LockError``. — ≙ ``lock_for_update``
        (``odoo19c: odoo/orm/models.py:5564-5588``)

        :param allow_referencing: un bloqueo que deja a otras transacciones
            referenciar la fila; sólo para cambiar valores que no son
            identificadores.
        :raises LockError: si alguna fila no se pudo bloquear.

        Como allá, ``SKIP LOCKED`` y no ``NOWAIT``: el segundo aborta la
        transacción. Los registros sin id real —los de ``new()``— no se
        bloquean. El ``IN %s`` de la fuente es ``= ANY(%s)`` por la misma
        razón que en :meth:`try_lock_for_update`.
        """
        ids = {id_ for id_ in self._ids if id_}
        if not ids:
            return
        query = Query(self.env, self._table, self._table_sql)
        query.add_where(SQL('%s = ANY(%s)',
                            SQL.identifier(self._table, 'id'), list(ids)))
        if allow_referencing:
            lock_sql = SQL('FOR NO KEY UPDATE SKIP LOCKED')
        else:
            lock_sql = SQL('FOR UPDATE SKIP LOCKED')
        rows = self.env.execute_query(SQL('%s %s', query.select(), lock_sql))
        if len(rows) != len(ids):
            raise LockError(self.env._('Cannot grab a lock on records'))

    def try_lock_for_update(self, *, allow_referencing=False, limit=None):
        """Bloquea en exclusiva las filas de ``self`` que pueda, salta las
        bloqueadas y devuelve el recordset de las bloqueadas. — ≙
        ``try_lock_for_update`` (``odoo19c: odoo/orm/models.py:5592-5622``)

        :param allow_referencing: un bloqueo que deja a otras transacciones
            referenciar la fila; sólo para cambiar valores que no son
            identificadores.
        :param limit: cuántas filas bloquear como máximo.

        Los registros nuevos no se bloquean y se devuelven siempre, como
        allá. El ``IN %s`` de la fuente es ``= ANY(%s)``: psycopg 3 adapta una
        lista a un arreglo y no expande una tupla.
        """
        new_ids, ids = partition(lambda i: isinstance(i, NewId), self._ids)
        if limit is not None:
            if len(new_ids) >= limit:
                return self.browse(new_ids[:limit])
            # se conserva el orden de los ids al intentar el bloqueo
            query = self.browse(ids)._as_query(ordered=True)
            query.limit = limit - len(new_ids)
        else:
            query = Query(self.env, self._table, self._table_sql)
            query.add_where(SQL('%s = ANY(%s)',
                                SQL.identifier(self._table, 'id'), list(ids)))
        if not ids:
            return self
        if allow_referencing:
            lock_sql = SQL('FOR NO KEY UPDATE SKIP LOCKED')
        else:
            lock_sql = SQL('FOR UPDATE SKIP LOCKED')
        sql = SQL('%s %s', query.select(), lock_sql)
        real_ids = (id_ for [id_] in self.env.execute_query(sql))
        valid_ids = {*real_ids, *new_ids}
        return self.browse(i for i in self._ids if i in valid_ids)

    def copy_data(self, default=None):
        """Copy given record's data with all its fields values. — ≙
        ``copy_data`` (``odoo19c: odoo/orm/models.py:5406-5463``)

        :param default: valores que pisan a los del registro copiado.
        :returns: un dict por registro, o ``None`` por uno ya visitado.

        Es el flujo de la fuente sobre el recordset; :class:`CopyMixin` porta
        la variante por instancia que adoptan los modelos de
        ``TimeStampedModel``. La guarda de recursión viaja en el contexto,
        como allá: el contexto congela sus claves, no el ``defaultdict`` que
        guarda.

        **Divergencias declaradas.** ``_fields`` incluye aquí las relaciones
        inversas de Django, que la fuente no declara: sin atributo ``copy``
        rige el default de la fuente por tipo (:func:`_copies`), así que un
        ``ManyToOneRel`` no se copia y un ``ManyToManyRel`` sí, como un
        ``Many2many`` declarado; un inverso automático de ``Many2many`` no se
        distingue de un espejo declarado. Un ``Many2many`` hacia un modelo que
        no es ``BaseModel`` se lee como el gestor de Django, y sus enlaces
        legibles salen de :class:`AccessQuerySet` (:func:`_readable_ids`). Un
        ``One2many`` declarado se lee hoy como ``AccessQuerySet`` y no como el
        recordset del comodelo; :func:`_x2many_records` lo convierte.
        """
        vals_list = []
        default = dict(default or {})
        # se evita recorrer de nuevo lo ya copiado en una relación circular
        if '__copy_data_seen' not in self.env.context:
            self = self.with_context(
                __copy_data_seen=collections.defaultdict(set))
        blacklist = _copy_data_blacklist(self, default)
        fields_to_copy = {
            name: field for name, field in self._fields.items()
            if _copies(field) and name not in default and name not in blacklist
        }
        for record in self:
            seen_map = self.env.context['__copy_data_seen']
            if record.id in seen_map[record._name]:
                vals_list.append(None)
                continue
            seen_map[record._name].add(record.id)
            vals = default.copy()
            for name, field in fields_to_copy.items():
                if field.type == 'one2many':
                    # en orden de id: copy_translations empareja por él
                    lines = _x2many_records(field, record[name]).sorted(
                        key='id').copy_data()
                    vals[name] = [Command.create(line)
                                  for line in lines if line]
                elif field.type == 'many2many':
                    # sólo los enlaces legibles, o la escritura fallaría
                    vals[name] = [Command.set(
                        _readable_ids(field, record[name]))]
                else:
                    vals[name] = field.convert_to_write(record[name], record)
            vals_list.append(vals)
        return vals_list

    def copy_translations(self, new, excluded=()):
        """Recursively copy the translations from original to new record.
        — ≙ ``copy_translations`` (``odoo19c: odoo/orm/models.py:5465-5528``)

        Se portan la guarda, la exclusión de lo heredado de un padre dado, la
        recursión por las líneas ``One2many`` emparejadas por id y la rama de
        los campos traducibles (TASK-GEN-0060), compartida con las filas de
        Django en :func:`_copy_field_translation`.
        """
        old = self
        if '__copy_translations_seen' not in old.env.context:
            old = old.with_context(
                __copy_translations_seen=collections.defaultdict(set))
        seen_map = old.env.context['__copy_translations_seen']
        if old.id in seen_map[old._name]:
            return
        seen_map[old._name].add(old.id)
        valid_langs = _installed_langs()
        lang = self.env.lang or 'en_US'
        for name, field in old._fields.items():
            if not _copies(field):
                continue
            related = getattr(field, 'related', None)
            if (getattr(field, 'inherited', False) and related
                    and related.split('.')[0] in excluded):
                # lo heredado de un padre dado por el usuario no es copia
                continue
            if field.type == 'one2many' and field.name not in excluded:
                old_lines = _x2many_records(field, old[name]).sorted(key='id')
                new_lines = _x2many_records(field, new[name]).sorted(key='id')
                for old_line, new_line in zip(old_lines, new_lines):
                    old_line.copy_translations(new_line)
            elif (getattr(field, 'translate', False) is True
                  and getattr(field, 'store', True)
                  and name not in excluded):
                _copy_field_translation(old, new, field, valid_langs, lang)

    def copy(self, default=None):
        """Duplicate record ``self`` updating it with default values. — ≙
        ``copy`` (``odoo19c: odoo/orm/models.py:5530-5545``)

        :param default: valores que pisan a los del registro copiado.
        :returns: los registros nuevos, en el orden de ``self``.
        """
        vals_list = self.with_context(active_test=False).copy_data(default)
        new_records = self.create(vals_list)
        for old_record, new_record in zip(self, new_records):
            old_record.copy_translations(new_record, excluded=default or ())
        return new_records

    #: ``env['x'].flush_model()`` / ``env['x'].invalidate_model()`` — la forma
    #: corriente de la fuente — llega aquí sobre la clase; el descriptor le
    #: da el recordset vacío del entorno activo, como a ``browse``.
    flush_model = _on_empty_recordset(flush_model)
    invalidate_model = _on_empty_recordset(invalidate_model)

    def _compute_field_value(self, field):
        """Calcula ``field`` sobre ``self`` y valida lo calculado. — ≙
        ``_compute_field_value`` (``odoo19c: odoo/orm/models.py``)

        Dos mitades, como en la fuente: ``determine(field.compute, self)`` y,
        si el campo se almacena y hay filas guardadas, las restricciones de
        los campos que calcula el mismo método (``field_computed[field]``).
        Sin la segunda, una ``@api.constrains`` sobre un campo calculado
        almacenado sólo se comprobaba al escribirlo y no al recalcularlo
        (H-API-1165).
        """
        determine(field.compute, self)
        if field.store and any(self._ids):
            fnames = [f.name for f in registry.field_computed[field]]
            self.filtered(lambda record: record.id)._validate_fields(fnames)

    @_on_empty_recordset
    def _write(self, vals):
        """Escritura de bajo nivel: los mismos ``vals`` en cada registro.

        ≙ ``BaseModel._write`` (``odoo19c: odoo/orm/models.py:4520-4522``).
        """
        self._write_multi([vals] * len(self))

    def _write_multi(self, vals_list):
        """Escritura de bajo nivel: un diccionario de valores por registro.

        ≙ ``BaseModel._write_multi`` (``odoo19c:
        odoo/orm/models.py:4524-4608``): prepara el ``parent_path``, fecha la
        fila con ``_log_access``, escribe, y reescribe el subárbol al final.
        Su único llamador en la fuente es :func:`_flush`.

        Divergencia de enunciado declarada (``designs/write-multi-flush.md``):
        la escritura es ``save(update_fields=...)`` por fila, no un
        ``UPDATE … FROM (VALUES …)`` por lotes. En este árbol ``save()`` y sus
        señales alojan los cómputos y las automatizaciones que la fuente aloja
        en el grafo de ``@api.depends`` y en el parche de
        ``_compute_field_value``; un ``UPDATE`` crudo los saltaría. Las ramas
        ``translate`` y ``company_dependent`` de la expresión SQL no tienen
        contraparte en ese enunciado: ``translate=True`` aún no traduce y
        ``company_dependent`` escribe por su descriptor.
        """
        assert len(self) == len(vals_list)

        if not self:
            return

        # registros que deben reescribir su parent_path
        parent_records = self._parent_store_update_prepare(vals_list)

        _write_rows(type(self), self._ids, vals_list)

        # parent_path de los registros y sus descendientes
        if parent_records:
            parent_records._parent_store_update()

    def _parent_store_update_prepare(self, vals_list):
        """Los registros de ``self`` que deben reescribir su ``parent_path``.

        ≙ ``BaseModel._parent_store_update_prepare`` (``odoo19c:
        odoo/orm/models.py:4985-5018``). Docstring de la fuente: *"Return the
        records in self that must update their parent_path field. This must
        be called before updating the parent field."*

        Adaptación declarada: ``id = ANY(%s)`` con una lista en vez de
        ``"id" IN %s`` con una tupla — psycopg 3 adapta una lista a un
        arreglo y no expande una tupla (la misma de
        :func:`_parent_store_create`).
        """
        if not self._parent_store:
            return self.browse()

        # cada padre nuevo con los ids que lo reciben
        parent_to_ids = collections.defaultdict(list)
        for id_, vals in zip(self._ids, vals_list):
            if self._parent_name in vals:
                parent_to_ids[vals[self._parent_name]].append(id_)

        if not parent_to_ids:
            return self.browse()

        self.flush_recordset([self._parent_name])

        # los registros cuyo padre cambia de verdad
        sql_parent = SQL.identifier(_parent_column(type(self)))
        conditions = []
        for parent_id, ids in parent_to_ids.items():
            if parent_id:
                condition = SQL('(%s != %s OR %s IS NULL)', sql_parent,
                                parent_id, sql_parent)
            else:
                condition = SQL('%s IS NOT NULL', sql_parent)
            conditions.append(SQL('("id" = ANY(%s) AND %s)', list(ids),
                                  condition))

        rows = self.env.execute_query(SQL(
            "SELECT id FROM %s WHERE %s ORDER BY id",
            SQL.identifier(self._table),
            SQL(" OR ").join(conditions),
        ))
        return self.browse(row[0] for row in rows)

    def _parent_store_update(self):
        """Reescribe el ``parent_path`` de ``self`` y de sus descendientes.

        ≙ ``BaseModel._parent_store_update`` (``odoo19c:
        odoo/orm/models.py:5020-5054``): por cada padre, el prefijo nuevo es
        su ``parent_path``; un padre que ya cuelga de alguno de los registros
        es una recursión. Adaptación declarada: ``= ANY(%s)`` como en
        :meth:`_parent_store_update_prepare`.
        """
        for parent, records in self.grouped(self._parent_name).items():
            # el prefijo nuevo de parent_path
            prefix = parent.parent_path or ""

            # recursión
            if prefix:
                parent_ids = {int(label) for label in prefix.split('/')[:-1]}
                if not parent_ids.isdisjoint(records._ids):
                    raise UserError(self.env._("Recursion Detected."))

            # parent_path de los registros y sus descendientes
            updated = dict(self.env.execute_query(SQL(
                """ UPDATE %(table)s child
                    SET parent_path = concat(%(prefix)s,
                        substr(child.parent_path,
                               length(node.parent_path)
                               - length(node.id || '/') + 1))
                    FROM %(table)s node
                    WHERE node.id = ANY(%(ids)s)
                    AND child.parent_path LIKE concat(node.parent_path,
                                                      %(wildcard)s)
                    RETURNING child.id, child.parent_path """,
                table=SQL.identifier(self._table),
                prefix=prefix,
                ids=list(records.ids),
                wildcard='%',
            )))
            # el caché de los nodos reescritos, y lo que hay que recalcular
            field = self._fields['parent_path']
            for id_, path in updated.items():
                field._update_cache(self.browse(id_), path)
            records = self.browse(updated)
            records.modified(['parent_path'])

    def _parent_store_compute(self):
        """ Compute parent_path field from scratch. — ≙
        ``_parent_store_compute`` (``odoo19c: odoo/orm/models.py:3071-3105``)

        Cada registro guarda en ``parent_path`` la ruta desde su raíz: los
        ids de los nodos, cada uno seguido de una barra (``42/63/84/``). La
        barra final hace que ``42/63/`` no sea prefijo de ``42/630/``. El SQL
        es el de la fuente; la columna del padre la resuelve
        :func:`_parent_column`, porque aquí el nombre del campo y el de la
        columna pueden diferir.
        """
        cls = type(self)
        if not getattr(cls, '_parent_store', False):
            return
        _logger.info('Computing parent_path for table %s...', cls._table)
        execute_query(SQL(
            """ WITH RECURSIVE __parent_store_compute(id, parent_path) AS (
                    SELECT row.id, concat(row.id, '/')
                    FROM %(table)s row
                    WHERE row.%(parent)s IS NULL
                UNION
                    SELECT row.id, concat(comp.parent_path, row.id, '/')
                    FROM %(table)s row, __parent_store_compute comp
                    WHERE row.%(parent)s = comp.id
                )
                UPDATE %(table)s row SET parent_path = comp.parent_path
                FROM __parent_store_compute comp
                WHERE row.id = comp.id """,
            table=SQL.identifier(cls._table),
            parent=SQL.identifier(_parent_column(cls)),
        ))
        self.invalidate_model(['parent_path'])

    @_on_empty_recordset
    @api.private
    def browse(self, ids=()):
        """Return a recordset for the ids provided as parameter in the current
        environment.

        ≙ ``:5882``. El ``self.__class__(self.env, ids, ids)`` de la fuente es
        aquí :meth:`_from_ids` por la divergencia declarada en ese método.
        """
        if not ids:
            ids = ()
        elif ids.__class__ is int:
            ids = (ids,)
        else:
            ids = tuple(ids)
        return self._from_ids(self.env, ids, ids)

    # === identidad y tamaño ===============================================

    @property
    def ids(self):
        """ Return the list of actual record ids corresponding to ``self``. —
        ≙ ``:5904`` """
        if all(self._ids):
            return list(self._ids)  # already real records
        return list(OriginIds(self._ids))

    @api.private
    def ensure_one(self):
        """Verify that the current recordset holds a single record. — ≙
        ``:5930``

        :raise ValueError: ``len(self) != 1``

        El mensaje interpola el ``repr`` del recordset. La fuente escribe
        ``%s``, y allí ``str`` cae en ``__repr__``; aquí un modelo puede
        declarar el ``__str__`` de Django (``IrAttachment`` devuelve su
        ``name``), que sobre cero o dos registros devuelve un no-texto o
        recurre, y convertía el ``ValueError`` en ``TypeError`` o
        ``RecursionError``. El texto resultante es el de la fuente.
        """
        try:
            # unpack to ensure there is only one value is faster than len when
            # true and
            # has a significant impact as this check is largely called
            _id, = self._ids
            return self
        except ValueError:
            raise ValueError("Expected singleton: %r" % (self,))

    def __bool__(self):
        """ Test whether ``self`` is nonempty. — ≙ ``:6475`` """
        return True if self._ids else False  # fast version of bool(self._ids)

    def __len__(self):
        """ Return the size of ``self``. — ≙ ``:6479`` """
        return len(self._ids)

    def __int__(self):
        """ ≙ ``:6656`` """
        return self.id or 0

    def __repr__(self):
        """ ≙ ``:6659`` """
        return f"{self._name}{self._ids!r}"

    def __deepcopy__(self, memo):
        """≙ ``:6665-6666`` — un recordset se copia a sí mismo.

        Un recordset nombra filas, no las contiene: copiarlo en profundidad no
        debe duplicar el objeto. Sin este método rige la copia por defecto
        que Django hereda de ``object``, que construye otra instancia.
        """
        return self

    def __str__(self):
        """Rutea a :meth:`__repr__`.

        **Divergencia forzada por Django, no elección.** La fuente no declara
        ``__str__``: ahí ``str()`` cae en ``__repr__`` por el default de
        ``object``. Aquí ``Model.__str__`` existe y devuelve
        ``'%s object (%s)' % (self.__class__.__name__, self.pk)``, que lee
        ``self.pk`` → el descriptor :class:`IdFromIds` → ``ValueError`` sobre
        un
        recordset de N. Sin este override, ``ensure_one`` no puede interpolar
        ``%s`` de su propio mensaje.
        """
        return self.__repr__()

    def __hash__(self):
        """ ≙ ``:6662`` """
        return hash((self._name, frozenset(self._ids)))

    def __eq__(self, other):
        """ Test whether two recordsets are equivalent (up to reordering). — ≙
        ``:6608`` """
        try:
            return (self._name == other._name
                    and set(self._ids) == set(other._ids))
        except AttributeError:
            if other:
                warnings.warn(
                    f"unsupported operand type(s) for \"==\": "
                    f"'{self._name}()' == '{other!r}'",
                    stacklevel=2)
        return NotImplemented

    def __lt__(self, other):
        """ ≙ ``:6617`` """
        try:
            if self._name == other._name:
                return set(self._ids) < set(other._ids)
        except AttributeError:
            # silent OK because el operando no es un recordset: la fuente cae
            # deliberadamente a ``NotImplemented`` para que Python pruebe el
            # reflejado y levante ``TypeError`` con su mensaje propio.
            pass
        return NotImplemented

    def __le__(self, other):
        """ ≙ ``:6625`` """
        try:
            if self._name == other._name:
                # these are much cheaper checks than a proper subset check, so
                # optimise for checking if a null or singleton are subsets of a
                # recordset
                if not self or self in other:
                    return True
                return set(self._ids) <= set(other._ids)
        except AttributeError:
            # silent OK because el operando no es un recordset — misma razon
            # que en ``__lt__``: la fuente cae deliberadamente a
            # ``NotImplemented`` para que Python pruebe el reflejado.
            pass
        return NotImplemented

    def __gt__(self, other):
        """ ≙ ``:6638`` """
        try:
            if self._name == other._name:
                return set(self._ids) > set(other._ids)
        except AttributeError:
            # silent OK because el operando no es un recordset — misma razon
            # que en ``__lt__``: la fuente cae deliberadamente a
            # ``NotImplemented`` para que Python pruebe el reflejado.
            pass
        return NotImplemented

    def __ge__(self, other):
        """ ≙ ``:6646`` """
        try:
            if self._name == other._name:
                if not other or other in self:
                    return True
                return set(self._ids) >= set(other._ids)
        except AttributeError:
            # silent OK because el operando no es un recordset — misma razon
            # que en ``__lt__``: la fuente cae deliberadamente a
            # ``NotImplemented`` para que Python pruebe el reflejado.
            pass
        return NotImplemented

    # === recorrido y lectura ==============================================

    def __iter__(self):
        """ Return an iterator over ``self``. — ≙ ``:6483`` """
        ids = self._ids
        size = len(ids)
        if size <= 1:
            # detect and handle small recordsets (single `1f`)
            # early return if no records and avoid allocation if we have a one
            if size == 1:
                yield self
            return
        env_ = self.env
        prefetch_ids = self._prefetch_ids
        if size > PREFETCH_MAX and prefetch_ids is ids:
            for sub_ids in split_every(PREFETCH_MAX, ids):
                for id_ in sub_ids:
                    yield self._from_ids(env_, (id_,), sub_ids)
        else:
            for id_ in ids:
                yield self._from_ids(env_, (id_,), prefetch_ids)

    def __contains__(self, item):
        """ Test whether ``item`` (record or field name) is an element of
        ``self``. — ≙ ``:6525`` """
        try:
            if self._name == item._name:
                return len(item) == 1 and item.id in self._ids
            raise TypeError(f"inconsistent models in: {item} in {self}")
        except AttributeError:
            if isinstance(item, str):
                return item in self._fields
            raise TypeError(
                f"unsupported operand types in: {item!r} in {self}")

    def __getitem__(self, key):
        """ If ``key`` is an integer or a slice, return the corresponding
        record
            selection as an instance (attached to ``self.env``).
            Otherwise read the field ``key`` of the first record in ``self``.
            — ≙ ``:6674``
        """
        if isinstance(key, str):
            # important: one must call the field's getter
            return self._read_field(self._fields[key])
        elif isinstance(key, slice):
            return self.browse(self._ids[key])
        else:
            return self.browse((self._ids[key],))

    def __setitem__(self, key, value):
        """ Assign the field ``key`` to ``value`` in record ``self``.
        — ≙ ``:6694``

        La fuente delega en ``Field.__set__`` (``odoo19c:
        odoo/orm/fields.py:1807-1841``), que reparte los ids en tres cubos.
        Aquí ese reparto se escribe en el registro y no en el descriptor:
        :class:`~orm.fields.FieldDescriptor` es el ``__set__`` de una
        **instancia** de Django, cuyo cubo real no emite SQL (divergencia
        declarada en su docstring). La asignación por clave es la del
        *recordset*, y en ella el cubo real va a ``write``, como en la fuente.
        """
        field = self._fields[key]
        protected_map = self.env._protected
        protected_ids = protected_map[field] if field in protected_map else ()
        protected, new, other = [], [], []
        for record_id in self._ids:
            if record_id in protected_ids:
                protected.append(record_id)
            elif not record_id:
                new.append(record_id)
            else:
                other.append(record_id)

        if protected:
            # filas en cómputo: sin lógica de negocio ni recálculo
            field.write(self.browse(tuple(protected)), value)

        if new:
            # filas nuevas: sin lógica de negocio. El cubo lo porta
            # ``FieldDescriptor.__set__`` —protección, ``modified`` y
            # ``field.write``—, y se le delega por fila porque la instancia
            # de Django también guarda el valor: escribir sólo la caché del
            # entorno dejaba la instancia que llama con el valor anterior.
            new_records = (self if len(new) == len(self._ids)
                           else self.browse(tuple(new)))
            for record in new_records:
                setattr(record, key, value)

        if other:
            # caso base: lógica de negocio completa
            records = self.browse(tuple(other))
            records.write({key: field.convert_to_write(value, records)})

    @api.private
    def update(self, values):
        """ Update the records in ``self`` with ``values``. — ≙ ``:6347`` """
        for name, value in values.items():
            self[name] = value

    def _read_field(self, field):
        """Lee ``field`` sobre ``self`` aplicando la guarda de tamaño de la
        fuente.

        **Es el porte de la guarda de** ``Field.__get__``
        (``odoo19c: odoo/orm/fields.py:1641-1661``), verbatim en su decisión::

            record_len = len(record._ids)
            if record_len != 1:
                if record_len:
                    record.ensure_one()
                    assert False, "unreachable"
                value = self.convert_to_cache(False, record, validate=False)
                return self.convert_to_record(value, record)

        **Divergencia de mecanismo, medida.** La fuente escribe
        ``self._fields[key].__get__(self)`` porque allá el mapa contiene
        objetos
        ``Field`` **suyos**, que son descriptores. Aquí ``_fields`` devuelve
        ``Field`` de Django, que **no tiene** ``__get__``, y
        :class:`~orm.fields.FieldDescriptor` sólo se instala donde el campo
        declara ``compute`` —medido 42.6 ns contra 132.9 ns (**3.12×**) si se
        hiciera descriptor de datos en todos—. Así que el campo se resuelve a
        su
        descriptor por el nombre de atributo y se le pide su ``__get__``.

        El valor del recordset vacío es el nulo de LECTURA del campo,
        :func:`~orm.fields.null_record_value` —``convert_to_record`` de
        ``convert_to_cache(False, …)`` allá—, no su ``falsy_value``: para una
        cadena el primero es ``False`` y el segundo ``''``.

        **Lo que este método no cierra:** la guarda sólo actúa por esta vía y
        por :meth:`__getitem__`. El acceso llano ``rs.label`` sobre un
        recordset
        de N sigue cayendo en el ``DeferredAttribute`` de Django, que ignora
        ``_ids``. Extenderlo cuesta los 3.12× medidos, así que es decisión del
        ejecutor: tarea **TASK-API-0401**. El docstring de
        ``orm/fields.py:1236`` declara hoy que la rama ``record_len != 1`` *"no
        tiene receptor"*; con este núcleo sí lo tiene, y esa nota queda rancia
        (misma tarea).
        """
        if len(self._ids) > 1 and getattr(field, 'relational', False):
            # ≙ el caso de varios registros de ``_Relational.__get__``
            # (``odoo19c: odoo/orm/fields_relational.py:42-79``)
            return self._read_relational_multi(field)
        size = len(self._ids)
        if size != 1:
            if size:
                self.ensure_one()
                raise AssertionError("unreachable")
            return null_record_value(field)
        # ``:1663-1667`` — con UNA fila la fuente devuelve el valor del campo
        # convertido a registro: sobre un ``Many2one`` es el corecord, nunca
        # su id. Aquí el descriptor que devuelve la fila cuelga de
        # ``field.name`` (``ForwardManyToOneDescriptor``); el de ``attname``
        # es la COLUMNA y devuelve el entero — medido en la sonda A4
        # (``probe_related_resolves_after_setup_phase.py``: ``partner`` leído
        # por ``partner_id`` daba ``int`` y ``_end_of_chain`` levantaba
        # ``TypeError``). El descriptor de cómputo se instala bajo ``attname``
        # (``orm/fields.py:1848``), que coincide con ``name`` en un campo sin
        # columna; se prefiere sólo cuando es el nuestro.
        attname = getattr(field, 'attname', None) or field.name
        descriptor = getattr(type(self), attname, None)
        # El descriptor del id de un Many2one almacenado también es un
        # ``FieldDescriptor`` y devuelve el entero; la fila la da el de
        # ``field.name``.
        if (not isinstance(descriptor, FieldDescriptor)
                or isinstance(descriptor, StoredMany2oneIdDescriptor)):
            descriptor = getattr(type(self), field.name, None)
        if descriptor is None or not hasattr(descriptor, '__get__'):
            return getattr(self, field.name)
        return descriptor.__get__(self, type(self))

    @property
    def _cache(self):
        """ Return the cache of ``self``, mapping field names to values. — ≙
        ``:6703`` """
        return RecordCache(self)

    def _update_cache(self, values, validate=True):
        """ Update the cache of ``self`` with ``values``. — ≙ ``:6066``

            :param values: dict of field values, in any format.
            :param validate: whether values must be checked
        """
        self.ensure_one()
        fields = self._fields
        try:
            field_values = [(fields[name], value)
                            for name, value in values.items() if name != 'id']
        except KeyError as e:
            raise ValueError("Invalid field %r on model %r"
                             % (e.args[0], self._name))

        # convert monetary fields after other columns for correct value
        # rounding
        for field, value in sorted(
                field_values, key=lambda item: item[0].write_sequence):
            value = field.convert_to_cache(value, self, validate)
            field._update_cache(self, value)

            # set inverse fields on new records in the comodel
            if field.relational:
                corecords = self[field.name]
                if not hasattr(corecords, 'filtered'):
                    # Un comodelo de Django devuelve una fila, que ya existe,
                    # o ``None``: no hay registro nuevo cuyo inverso ajustar.
                    continue
                inv_recs = corecords.filtered(lambda r: not r.id)
                if not inv_recs:
                    continue
                # we need to adapt the value of the inverse fields to
                # integrate self into it:
                # x2many fields should add self, while many2one fields should
                # replace with self
                for invf in registry.field_inverses[field]:
                    invf._update_inverse(inv_recs, self)

    def _convert_to_record(self, values):
        """ Convert the ``values`` dictionary from the cache format to the
        record format. — ≙ ``:6094-6101`` """
        return {
            name: self._fields[name].convert_to_record(value, self)
            for name, value in values.items()
        }

    def _convert_to_write(self, values):
        """ Convert the ``values`` dictionary into the format of
        :meth:`write`. — ≙ ``:6103`` """
        fields = self._fields
        result = {}
        for name, value in values.items():
            if name in fields:
                field = fields[name]
                value = field.convert_to_write(value, self)
                if not isinstance(value, NewId):
                    result[name] = value
        return result

    @_on_empty_recordset
    def new(self, values=None, origin=None, ref=None):
        """ Return a new record instance attached to the current environment
        and
        initialized with the provided ``value``. The record is *not* created
        in database, it only exists in memory. — ≙ ``:6441``

        One can pass an ``origin`` record, which is the actual record behind
        the
        result. It is retrieved as ``record._origin``. Two new records with the
        same origin record are considered equal.

        One can also pass a ``ref`` value to identify the record among other
        new
        records. The reference is encapsulated in the ``id`` of the record.
        """
        if values is None:
            values = {}
        if origin is not None:
            origin = origin.id
        record = self.browse((NewId(origin, ref),))
        record._update_cache(values, validate=False)

        return record

    @property
    def _origin(self):
        """ Return the actual records corresponding to ``self``. — ≙ ``:6462``
        """
        if all(self._ids):
            return self  # already real records
        ids = tuple(OriginIds(self._ids))
        prefetch_ids = OriginIds(self._prefetch_ids)
        return self._from_ids(self.env, ids, prefetch_ids)

    # === derivación de entorno ============================================

    @api.private
    def with_env(self, env):
        """Return a new version of this recordset attached to the provided
        environment.

        ≙ ``:5944``. The returned recordset has the same prefetch object as
        ``self``.
        """
        return self._from_ids(env, self._ids, self._prefetch_ids)

    @api.private
    def sudo(self, flag=True):
        """ Return a new version of this recordset with superuser mode enabled
        or
        disabled, depending on `flag`. — ≙ ``:5953``
        """
        assert isinstance(flag, bool)
        if flag == self.env.su:
            return self
        return self.with_env(self.env(su=flag))

    @api.private
    def with_user(self, user):
        """ Return a new version of this recordset attached to the given user.
        — ≙ ``:5980`` """
        if not user:
            return self
        return self.with_env(self.env(user=user, su=False))

    @api.private
    def with_company(self, company):
        """ Return a new version of this recordset with a modified context. —
        ≙ ``:5990`` """
        if not company:
            # With company = None/False/0/[]/empty recordset: keep current
            # environment
            return self

        company_id = int(company)
        allowed_company_ids = self.env.context.get('allowed_company_ids') or []
        if allowed_company_ids and company_id == allowed_company_ids[0]:
            return self
        # Copy the allowed_company_ids list
        # to avoid modifying the context of the current environment.
        allowed_company_ids = list(allowed_company_ids)
        if company_id in allowed_company_ids:
            allowed_company_ids.remove(company_id)
        allowed_company_ids.insert(0, company_id)

        return self.with_context(allowed_company_ids=allowed_company_ids)

    @api.private
    def with_context(self, ctx=None, /, **overrides):
        """ Return a new version of this recordset attached to an extended
        context. — ≙ ``:6020``

        La fuente avisa aquí de dos claves de contexto retiradas en 19
        (``force_company``, ``company``); se portan los dos avisos verbatim.
        """
        context = dict(ctx if ctx is not None else self.env.context,
                       **overrides)
        if 'force_company' in context:
            warnings.warn(
                "Since 19.0, context key 'force_company' is no longer "
                "supported. "
                "Use with_company(company) instead.",
                DeprecationWarning,
            )
        if 'company' in context:
            warnings.warn(
                "Context key 'company' is not recommended, because "
                "of its special meaning in @depends_context.",
            )
        if ('allowed_company_ids' not in context
                and 'allowed_company_ids' in self.env.context):
            # Force 'allowed_company_ids' to be kept when context is overridden
            # without 'allowed_company_ids'
            context['allowed_company_ids'] = (
                self.env.context['allowed_company_ids'])
        return self.with_env(self.env(context=context))

    @api.private
    def with_prefetch(self, prefetch_ids=None):
        """ Return a new version of this recordset that uses the given
        prefetch ids,
        or ``self``'s ids if not given. — ≙ ``:6057``
        """
        if prefetch_ids is None:
            prefetch_ids = self._ids
        return self._from_ids(self.env, self._ids, prefetch_ids)

    # === operaciones de conjunto ==========================================

    def __add__(self, other):
        """ Return the concatenation of two recordsets. — ≙ ``:6544`` """
        return self.concat(other)

    @api.private
    def concat(self, *args):
        """ Return the concatenation of ``self`` with all the arguments (in
            linear time complexity). — ≙ ``:6548``
        """
        ids = list(self._ids)
        for arg in args:
            try:
                if arg._name != self._name:
                    raise TypeError(f"inconsistent models in: {self} + {arg}")
                ids.extend(arg._ids)
            except AttributeError:
                raise TypeError(
                    f"unsupported operand types in: {self} + {arg!r}")
        return self.browse(ids)

    def __sub__(self, other):
        """ Return the recordset of all the records in ``self`` that are not in
            ``other``. Note that recordset order is preserved. — ≙ ``:6563``
        """
        try:
            if self._name != other._name:
                raise TypeError(f"inconsistent models in: {self} - {other}")
            other_ids = set(other._ids)
            return self.browse(id_ for id_ in self._ids
                               if id_ not in other_ids)
        except AttributeError:
            raise TypeError(
                f"unsupported operand types in: {self} - {other!r}")

    def __and__(self, other):
        """ Return the intersection of two recordsets.
            Note that first occurrence order is preserved. — ≙ ``:6575``
        """
        try:
            if self._name != other._name:
                raise TypeError(f"inconsistent models in: {self} & {other}")
            other_ids = set(other._ids)
            return self.browse(OrderedSet(id_ for id_ in self._ids
                                          if id_ in other_ids))
        except AttributeError:
            raise TypeError(
                f"unsupported operand types in: {self} & {other!r}")

    def __or__(self, other):
        """ Return the union of two recordsets.
            Note that first occurrence order is preserved. — ≙ ``:6587``
        """
        return self.union(other)

    def __ror__(self, other):
        """``Modelo | recordset``, con la clase del modelo a la izquierda.

        **Divergencia de mecanismo**, la misma que declara
        :class:`_on_empty_recordset`: ``env['x']`` devuelve aquí la clase y no
        el recordset vacío de la fuente, así que la forma
        ``acc = env['x']; acc |= rec`` (``odoo19c: odoo/tools/xml_utils.py``)
        llega a este método con la clase en ``other``. La clase se lee como su
        recordset vacío y la unión es la de :meth:`__or__`. Cualquier otro
        operando conserva la conducta de Python (``NotImplemented``).
        """
        if (isinstance(other, type)
                and getattr(other, '_name', None) == self._name):
            return other._from_ids(self.env, (), ()) | self
        return NotImplemented

    @api.private
    def union(self, *args):
        """ Return the union of ``self`` with all the arguments (in linear time
            complexity, with first occurrence order preserved). — ≙ ``:6593``
        """
        ids = list(self._ids)
        for arg in args:
            try:
                if arg._name != self._name:
                    raise TypeError(f"inconsistent models in: {self} | {arg}")
                ids.extend(arg._ids)
            except AttributeError:
                raise TypeError(
                    f"unsupported operand types in: {self} | {arg!r}")
        return self.browse(OrderedSet(ids))

    # === proyección =======================================================

    @api.private
    def mapped(self, func):
        """Apply ``func`` on all records in ``self``, and return the result as
        a
        list or a recordset (if ``func`` return recordsets). — ≙ ``:6127``

        Dos divergencias, las dos con sucesor acuñado y ninguna de contrato:

        * ``records.fetch([field_name])`` sobre ``PREFETCH_MAX`` — ``fetch`` no
          está portado (``odoo19c: :3775-3818``). Tarea **TASK-API-0399**.
        * la rama **relacional** devuelve allá ``getter(records)`` con el
          recordset de N: ``_Relational.__get__``
          (``odoo19c: odoo/orm/fields_relational.py:42-46``) delega en la base
          sólo con ``len(records._ids) <= 1`` y con N ids arma la unión por su
          cuenta, sin caer en la guarda de tamaño de ``Field.__get__``
          (``:1653-1661``). Aquí :class:`~orm.fields.FieldDescriptor` tiene
          la guarda de tamaño y **no** la rama multi-registro: con N ids
          levanta ``ensure_one`` en vez de devolver la unión. Tarea
          **TASK-API-0401** (extender la guarda al acceso llano).
        """
        if not func:
            return self                 # support for an empty path of fields

        if isinstance(func, str):
            # special case: sequence of field names
            *rel_field_names, field_name = func.split('.')
            records = self
            for rel_field_name in rel_field_names:
                records = records[rel_field_name]
            if len(records) > PREFETCH_MAX:
                raise NotImplementedError(
                    "mapped() sobre PREFETCH_MAX exige BaseModel.fetch, sin "
                    "portar (odoo19c: odoo/orm/models.py:3775-3818) — "
                    "TASK-API-0399")
            field = records._fields[field_name]
            if field.relational:
                # La fuente devuelve ``getter(records)`` y deja la unión a
                # ``_Relational.__get__`` (``fields_relational.py:42-46``).
                # Nuestro descriptor no tiene esa rama multi-registro: sobre N
                # ids cae en la guarda de tamaño y levanta ``ensure_one``, así
                # que la unión no se puede expresar todavía. Se rehúsa sin
                # condición hasta TASK-API-0401.
                raise NotImplementedError(
                    f"mapped() relacional sobre {field.name!r} exige la rama "
                    "multi-registro de _Relational.__get__ (odoo19c: "
                    "odoo/orm/fields_relational.py:42-46) — tarea "
                    "TASK-API-0401")
            return [record._read_field(field) for record in records]

        if self:
            vals = [func(rec) for rec in self]
            if isinstance(vals[0], BaseModel):
                return vals[0].union(*vals)
            return vals
        else:
            # we want to follow-up the comodel from the function
            # so we pass an empty recordset
            vals = func(self)
            return vals if isinstance(vals, BaseModel) else []

    @api.private
    def filtered(self, func):
        """Return the records in ``self`` satisfying ``func``. — ≙ ``:6185``

        La rama de nombre de campo suelto lee con :meth:`_read_field` en vez de
        ``self._fields[func].__get__``, por la divergencia declarada allí.
        """
        if not func:
            # align with mapped()
            return self
        if callable(func):
            # normal function
            pass
        elif isinstance(func, str):
            if '.' in func:
                return self.browse(
                    rec_id for rec_id, rec in zip(self._ids, self)
                    if any(rec.mapped(func)))
            # avoid costly mapped
            field = self._fields[func]
            return self.browse(rec_id for rec_id, rec in zip(self._ids, self)
                               if rec._read_field(field))
        elif isinstance(func, Domain):
            return self.filtered_domain(func)
        else:
            raise TypeError(
                f"Invalid function {func!r} to filter on {self._name}")
        return self.browse(rec_id for rec_id, rec in zip(self._ids, self)
                           if func(rec))

    @api.private
    def filtered_domain(self, domain):
        """Return the records in ``self`` satisfying the domain and keeping
        the same order. — ≙ ``:6251`` """
        if not self or not domain:
            return self
        predicate = Domain(domain)._as_predicate(self)
        return self.browse(rec_id for rec_id, rec in zip(self._ids, self)
                           if predicate(rec))

    @api.private
    def grouped(self, key):
        """Eagerly groups the records of ``self`` by the ``key``, returning a
        dict from the ``key``'s result to recordsets. All the resulting
        recordsets are guaranteed to be part of the same prefetch-set. — ≙
        ``:6225``
        """
        if isinstance(key, str):
            key = itemgetter(key)

        collator = collections.defaultdict(list)
        for record in self:
            collator[key(record)].extend(record._ids)

        browse = functools.partial(type(self)._from_ids, self.env,
                                   prefetch_ids=self._prefetch_ids)
        return {key: browse(tuple(ids)) for key, ids in collator.items()}

    @api.private
    def sorted(self, key=None, reverse=False):
        """Return the recordset ``self`` ordered by ``key``. — ≙ ``:6262``

        Las tres ramas de la fuente, y ninguna más: ``key`` invocable se pasa
        tal cual al ``sorted`` de CPython; ``key`` cadena y ``key`` ``None``
        pasan antes por :meth:`_sorted_order_to_function`, que construye la
        función de clave.
        """
        if len(self) < 2:
            return self
        if isinstance(key, str):
            key = self._sorted_order_to_function(key)
        elif key is None:
            key = self._sorted_order_to_function(self._order)
        ids = tuple(item.id for item in sorted(self, key=key, reverse=reverse))
        return self._from_ids(self.env, ids, self._prefetch_ids)

    def _sorted_order_to_function(self, order):
        """La función de clave que ``sorted()`` consume. — ≙ ``:6294-6344``

        **No ordena.** Construye la ``key``; el orden estable lo pone Timsort,
        que el stack trae hecho. Lo que hay que construir es el envoltorio que
        hace comparables valores de tipos mixtos con ``None``, y ése es
        :class:`ReversibleComparator`, ya portado.

        Las cinco ramas de ``order_to_function``, en el orden de la fuente:

        1. ``regex_order`` no casa → ``ValueError``.
        2. ``many2one`` sin propiedad, o con ``.id`` → **recurre** al comodelo
           con su ``_order``, protegido de un ciclo por la clave de contexto
           ``__m2o_order_seen_sorted``.
        3. otro campo relacional → ``ValueError``.
        4. ``boolean`` → el getter tal cual: ``False`` es un valor legítimo
           que debe ordenar antes que ``True``, no un nulo.
        5. el resto → el mismo getter con ``False`` normalizado a ``None``.

        La regla de los nulos es la de PostgreSQL, reproducida en memoria para
        que ``sorted()`` y ``search()`` no discrepen: sin ``NULLS`` explícito,
        ``nulls_first = reverse``.
        """
        def order_to_function(order_part):
            order_match = regex_order.match(order_part)
            if not order_match:
                raise ValueError(f"Invalid order {order!r} to sort")
            field_name = order_match['field']
            property_name = order_match['property']
            reverse = (order_match['direction'] or '').upper() == 'DESC'
            nulls = (order_match['nulls'] or '').upper()
            if nulls:
                nulls_first = nulls == 'NULLS FIRST'
            else:
                nulls_first = reverse

            field = self._fields[field_name]
            field_expr = (f'{field_name}.{property_name}' if property_name
                          else field_name)
            if field.type == 'many2one' and (not property_name
                                             or property_name == 'id'):
                seen = self.env.context.get('__m2o_order_seen_sorted', ())
                if field in seen:
                    return lambda _: None
                # **Adaptación de la divergencia ya declarada en
                # ``Environment.__getitem__``.** La fuente escribe
                # ``self.env[field.comodel_name].with_context(...)`` porque
                # allá
                # ``env[name]`` devuelve ``self.registry[name](self, (), ())``,
                # o sea un recordset VACÍO. Aquí ``env[name]`` devuelve la
                # **clase** del modelo —divergencia declarada en su propio
                # docstring—, y ``with_context`` sobre una clase es un método
                # sin ligar: ``missing 1 required positional argument:
                # 'self'``.
                # El recordset vacío se construye aquí, que es lo que la fuente
                # obtiene de su indexador.
                comodel = self.env[field.comodel_name]._from_ids(
                    self.env, (), ()).with_context(
                    __m2o_order_seen_sorted=frozenset((field, *seen)))
                func_comodel = comodel._sorted_order_to_function(
                    property_name or comodel._order)

                def getter(rec):
                    value = rec[field_name]
                    if not value:
                        return None
                    return func_comodel(value)
            elif field.relational:
                raise ValueError(
                    f"Invalid order on relational field {order_part!r} "
                    "to sort")
            elif field.type == 'boolean':
                getter = field.expression_getter(field_expr)
            else:
                raw_getter = field.expression_getter(field_expr)

                def getter(rec):
                    value = raw_getter(rec)
                    return value if value is not False else None

            comparator = functools.partial(
                ReversibleComparator,
                reverse=reverse,
                none_first=nulls_first,
            )
            return lambda rec: comparator(getter(rec))

        item_makers = [
            order_to_function(order_part)
            for order_part in order.split(',')
        ]
        return lambda rec: tuple(fn(rec) for fn in item_makers)

    # === existencia =======================================================

    def check_access(self, operation):
        """Levanta ``AccessError`` si el usuario no puede hacer ``operation``
        sobre todos los registros de ``self`` — ≙ ``odoo19c:
        odoo/orm/models.py:4100-4115``.

        Con ``self`` vacío comprueba el permiso sobre el modelo en general.
        """
        if not self.env.su and (result := self._check_access(operation)):
            raise result[1]()

    def has_access(self, operation):
        """Lo mismo que :meth:`check_access`, como booleano —
        ≙ ``:4117-4121``."""
        return self.env.su or not self._check_access(operation)

    def _filtered_access(self, operation):
        """El subconjunto de ``self`` sobre el que se puede ``operation`` —
        ≙ ``:4123-4129``."""
        if self and not self.env.su and (
                result := self._check_access(operation)):
            return self - result[0]
        return self

    @_on_empty_recordset
    @api.deprecated("check_access_rights() is deprecated since 18.0; "
                    "use check_access() instead.")
    def check_access_rights(self, operation, raise_exception=True):
        """Permiso del usuario sobre el modelo — ≙ ``odoo19c:
        odoo/orm/models.py:4161-4173``. Obsoleto desde 18.0."""
        if raise_exception:
            return self.browse().check_access(operation)
        return self.browse().has_access(operation)

    @api.deprecated("check_access_rule() is deprecated since 18.0; "
                    "use check_access() instead.")
    def check_access_rule(self, operation):
        """Permiso según ``ir.rule`` — ≙ ``:4175-4183``. Obsoleto desde
        18.0."""
        self.check_access(operation)

    @api.deprecated("_filter_access_rules() is deprecated since 18.0; "
                    "use _filtered_access() instead.")
    def _filter_access_rules(self, operation):
        """El subconjunto permitido — ≙ ``:4185-4188``. Obsoleto desde 18.0."""
        return self._filtered_access(operation)

    @api.deprecated("_filter_access_rules_python() is deprecated since 18.0; "
                    "use _filtered_access() instead.")
    def _filter_access_rules_python(self, operation):
        """≙ ``:4190-4192``. Obsoleto desde 18.0."""
        return self._filtered_access(operation)

    def _check_access(self, operation):
        """``None`` si se puede; si no, (prohibidos, fábrica de error).

        ≙ ``odoo19c: odoo/orm/models.py:4131-4149``: primero la ACL del
        modelo, y sólo si pasa, las reglas de fila sobre los registros reales
        (los nuevos no se mezclan). La evaluación es la de
        :class:`AccessQuerySet` sobre los mismos ids, que ya porta las dos
        mitades: aquí sólo se traduce el resultado al recordset.
        """
        real_ids = [record_id for record_id in self._ids
                    if isinstance(record_id, int)]
        queryset = type(self)._default_manager.filter(pk__in=real_ids)
        result = queryset._check_access(operation, user=self.env.user)
        if result is None:
            return None
        forbidden, make_error = result
        if forbidden is queryset:
            return self, make_error
        return self.browse(list(forbidden.values_list('pk', flat=True))), \
            make_error

    def write(self, vals):
        """Escribe ``vals`` en todos los registros de ``self`` — la entrada de
        ``BaseModel.write`` (``odoo19c: odoo/orm/models.py``, antes de
        ``_write``).

        Vacío devuelve ``True`` sin tocar nada; con registros, primero
        ``check_access('write')`` y el acceso de escritura de cada campo, y un
        nombre que no es campo levanta ``ValueError``. Después cada registro
        se escribe con la escritura de una fila que ya existe
        (:meth:`RecordLoaderMixin.write`). El volcado por lotes de la fuente
        (``_write``/``_write_multi``) sigue ausente: aquí la escritura es por
        registro.
        """
        if not self:
            return True
        self.check_access('write')
        for field_name in vals:
            try:
                self._check_field_access(self._fields[field_name], 'write')
            except KeyError as error:
                raise ValueError(
                    f"Invalid field {field_name!r} in {self._name!r}",
                ) from error
        for record in self:
            super(BaseModel, record).write(vals)
        return True

    @api.deprecated("Deprecated since 19.0, use action_archive or "
                    "action_unarchive")
    def toggle_active(self):
        """Invierte ``active`` en los registros de ``self`` — ≙ ``odoo19c:
        odoo/orm/models.py:5788-5794``. Obsoleto desde 19.0."""
        field_name = self._active_field_name()
        assert field_name, f"No 'active' field on model {self._name}"
        active_recs = self.filtered(field_name)
        active_recs.action_archive()
        (self - active_recs).action_unarchive()

    def action_archive(self):
        """Pone ``active = False`` en los registros activos de ``self`` —
        ≙ ``:5796-5805``. Quien quiera reaccionar al cambio redefine
        ``write``, como en la fuente."""
        field_name = self._active_field_name()
        assert field_name, f"No 'active' field on model {self._name}"
        active_recs = self.filtered(lambda record: record[field_name])
        active_recs.write({field_name: False})

    def action_unarchive(self):
        """Pone ``active = True`` en los registros archivados de ``self`` —
        ≙ ``:5807-5816``."""
        field_name = self._active_field_name()
        assert field_name, f"No 'active' field on model {self._name}"
        inactive_recs = self.filtered(lambda record: not record[field_name])
        inactive_recs.write({field_name: True})

    def _get_base_lang(self):
        """El idioma base del registro — ≙ ``odoo19c:
        odoo/orm/models.py:3704-3707``. ``en_US`` salvo que un addon lo
        redefina; la pregunta es sobre un registro, de ahí ``ensure_one``.
        """
        self.ensure_one()
        return 'en_US'

    @_on_empty_recordset
    def _is_an_ordinary_table(self):
        """Si la tabla del modelo es ordinaria (``relkind = 'r'``).

        ≙ ``odoo19c: odoo/orm/models.py:596-597``: la respuesta es del
        registro de la base (``self.pool``), no del modelo. Aquí
        ``env.registry`` es el módulo, así que el registro de la base se pide
        por el alias del entorno.
        """
        return registry.Registry(self.env.db_alias).is_an_ordinary_table(
            type(self))

    @_on_empty_recordset
    def check_field_access_rights(self, operation, field_names):
        """Los campos de ``field_names`` a los que el usuario tiene acceso.

        ≙ ``odoo19c: odoo/orm/models.py:3436-3466``. Bajo elevación devuelve
        ``field_names`` o, si no se pidió ninguno, todos los campos. Sin
        elevación, sin nombres devuelve sólo los accesibles; con nombres,
        levanta ``AccessError`` por el primero prohibido. Un nombre que no es
        campo se considera accesible: no se leerá ni se escribirá.
        """
        if self.env.su:
            return field_names or list(self._fields)
        if not field_names:
            return [
                field_name
                for field_name, field in self._fields.items()
                if self._has_field_access(field, operation)
            ]
        for field_name in field_names:
            field = self._fields.get(field_name)
            if field is None:
                continue
            self._check_field_access(field, operation)
        return field_names

    def _fetch_field(self, field):
        """Lee de la base ``field`` para ``self`` y lo deja en caché.

        ≙ ``odoo19c: odoo/orm/models.py:3754-3772``. Con prelectura activa
        en el contexto y un ``field.prefetch`` verdadero, trae también los
        campos del mismo grupo de prelectura que el usuario puede leer.
        """
        if self.env.context.get('prefetch_fields', True) and field.prefetch:
            fnames = [
                name
                for name, other in self._fields.items()
                if other.prefetch == field.prefetch
                if self._has_field_access(other, 'read')
            ]
            if field.name not in fnames:
                fnames.append(field.name)
        else:
            fnames = [field.name]
        self.fetch(fnames)

    def fetch(self, field_names=None):
        """Garantiza que ``field_names`` estén en memoria para ``self``,
        trayendo de la base lo necesario.

        ≙ ``fetch`` (``odoo19c: odoo/orm/models.py:3775-3818``). Los campos
        sin columna se omiten salvo por sus dependencias almacenadas; con
        ``None`` se traen todos los legibles marcados ``prefetch=True``.

        :raise AccessError: si el usuario no puede leer lo pedido.

        Como la fuente, la consulta que satisface las reglas de acceso sale
        de :meth:`_search` y se lee con :meth:`_fetch_query`.
        """
        # se descartan los registros nuevos
        self = self._origin
        if not self or not (field_names is None or field_names):
            return

        fields_to_fetch = self._determine_fields_to_fetch(
            field_names, ignore_when_in_cache=True)

        # primero, la consulta que satisface las reglas de acceso
        if any(field.column_type for field in fields_to_fetch):
            query = self._search([('id', 'in', self.ids)],
                                 active_test=False)
        else:
            try:
                self.check_access('read')
            except MissingError:
                # fetch nunca levanta MissingError, pero check_access sí
                # puede, porque lee campos de self: se acota a lo que existe
                self = self.exists()
                self.check_access('read')
            if not fields_to_fetch:
                return
            query = self._as_query(ordered=False)

        fetched = self._fetch_query(query, fields_to_fetch)

        # lo que no se pudo leer y existe es un rechazo de acceso
        if fetched != self:
            forbidden = (self - fetched).exists()
            if forbidden:
                IrRule = registry.model_by_name('ir.rule')
                raise IrRule._make_access_error('read', forbidden)

    @_on_empty_recordset
    def _determine_fields_to_fetch(self, field_names=None,
                                   ignore_when_in_cache=False):
        """Los campos que hay que traer de la base entre ``field_names``,
        siguiendo las dependencias de los campos calculados.

        ≙ ``_determine_fields_to_fetch`` (``odoo19c: odoo/orm/models.py:
        3820-3877``). Lo usan :meth:`fetch` y ``search_fetch``.

        :param field_names: los nombres pedidos, o ``None`` para todos los
            campos legibles marcados ``prefetch=True``.
        :param ignore_when_in_cache: si se omiten los campos que ya están en
            caché para ``self``.
        :raise ValueError: ante un nombre que el modelo no declara.
        :raise AccessError: ante un campo que el usuario no puede leer.
        """
        if field_names is None:
            return [
                field for field in self._fields.values()
                if getattr(field, 'prefetch', None) is True
                and self._has_field_access(field, 'read')
            ]

        if not field_names:
            return []

        fields_to_fetch = []
        pending_fields = collections.deque()
        fields_done = {self._fields['id']}  # el id no se trae
        for field_name in field_names:
            try:
                field = self._fields[field_name]
            except KeyError as error:
                raise ValueError(
                    f'Invalid field {field_name!r} on {self._name!r}'
                ) from error
            self._check_field_access(field, 'read')
            pending_fields.append(field)

        while pending_fields:
            field = pending_fields.popleft()
            if field in fields_done:
                continue
            fields_done.add(field)
            if isinstance(field, (DeclaredOne2many, ForeignObjectRel)):
                # Un ``One2many`` declarado o el reverso de Django: allá un
                # x2many se trae con ``field.read`` dentro de
                # ``_fetch_query``; aquí sus líneas se leen al acceder al
                # campo, así que no hay nada que traer por adelantado.
                continue
            if (ignore_when_in_cache
                    and not any(field._cache_missing_ids(self))):
                continue
            if field.store:
                fields_to_fetch.append(field)
            else:
                # sólo se traen las dependencias almacenadas del cálculo
                for dotname in registry.field_depends[field]:
                    dep_field = self._fields[dotname.split('.', 1)[0]]
                    if (not dep_field.store) or (
                            getattr(dep_field, 'prefetch', None) is True
                            and self._has_field_access(dep_field, 'read')):
                        pending_fields.append(dep_field)

        return fields_to_fetch

    def _fetch_query(self, query, fields):
        """Trae ``fields`` de las filas de ``query``, los deja en caché y
        devuelve los registros obtenidos.

        ≙ ``_fetch_query`` (``odoo19c: odoo/orm/models.py:3879-3942``). Las
        columnas salen en un solo ``SELECT`` y entran en caché **sin
        sobrescribir** lo que ya había (``_insert_cache``): un valor
        pendiente de escribir gana. Los campos sin columna propia los lee su
        ``read``.
        """
        column_fields = OrderedSet()
        other_fields = OrderedSet()
        for field in fields:
            if field.name == 'id':
                continue
            assert field.store
            (column_fields if field.column_type else other_fields).add(field)

        context = get_context()

        if column_fields:
            # la consulta puede unir varias tablas: nombres calificados
            sql_terms = [SQL.identifier(self._table, 'id')]
            for field in column_fields:
                sql = self._field_to_sql(self._table, field.name, query)
                if field.type == 'binary' and (
                        context.get('bin_size')
                        or context.get('bin_size_' + field.name)):
                    sql = SQL('pg_size_pretty(length(%s)::bigint)', sql)
                elif not getattr(field, 'translate', False):
                    # el valor en_US de un campo sin traducción no exige
                    # volcar sus escrituras pendientes
                    to_flush = (f for f in sql.to_flush if f != field)
                    sql = SQL(sql.code, *sql.params, to_flush=to_flush)
                sql_terms.append(sql)

            rows = self.env.execute_query(query.select(*sql_terms))
            if not rows:
                return self.browse()

            column_values = zip(*rows)
            ids = next(column_values)
            fetched = self.browse(ids)
            for field, values in zip(column_fields, column_values,
                                     strict=True):
                field._insert_cache(fetched, values)
        else:
            fetched = self.browse(query)

        if fetched:
            for field in other_fields:
                field.read(fetched)

        return fetched

    def _as_query(self, ordered=True):
        """≙ ``_as_query`` (``odoo19c: odoo/orm/models.py:5396-5404``): la
        :class:`Query` cuyo resultado es el recordset ``self``.

        :param ordered: si la consulta debe respetar el orden de ``self``.

        Como en la fuente, la tabla de la consulta es :attr:`_table_sql`: el
        identificador para una tabla normal y la subconsulta para un modelo
        con ``_table_query``.
        """
        query = Query(self.env, self._table, self._table_sql)
        query.set_result_ids(self._ids, ordered)
        return query

    @api.private
    def exists(self):
        """ The subset of records in ``self`` that exist. — ≙ ``:5544``

        By convention, new records are returned as existing.

        **Divergencia de mecanismo.** La fuente arma ``Query(self.env,
        self._table, self._table_sql)`` y ejecuta el ``SELECT``; aquí
        :attr:`_table_sql` existe pero este camino no lo usa (ver
        ``orm/environments.py:1831``). El stack trae el mecanismo: el manager
        base del modelo emite el mismo ``id IN (…)`` sin aplicar filtros
        del manager público y devuelve los ids reales, sin SQL a mano.
        """
        new_ids, ids = partition(lambda i: isinstance(i, NewId), self._ids)
        if not ids:
            return self
        real_ids = (
            type(self)
            ._base_manager.filter(pk__in=tuple(ids))
            .values_list('pk', flat=True)
        )
        valid_ids = {*real_ids, *new_ids}
        return self.browse(i for i in self._ids if i in valid_ids)

    def __ensure_xml_id(self, skip=False):
        """ Create missing external ids for records in ``self``, and return an
            iterator of pairs ``(record, xmlid)`` for the records in ``self``.
            — ≙ ``__ensure_xml_id`` (``odoo19c: :599-676``)

        :rtype: Iterable[Model, str | None]

        Copia adaptada. Dos cambios de mecanismo, el mismo efecto: el
        ``IN %s`` de la fuente es ``= ANY(%s)`` —psycopg 3 adapta una lista,
        no una tupla—, y las filas que faltan se escriben con ``bulk_create``
        en vez de ``COPY FROM``: ``ir_model_data`` exige aquí ``created_at``,
        ``updated_at`` y ``noupdate`` sin defecto en la base, y el alta de
        Django los pone. ``ir.model.data`` es un modelo de Django sin caché
        de campos, así que la invalidación de la fuente no tiene destinatario.
        """
        if skip:
            return ((record, None) for record in self)

        if not self:
            return iter([])

        if not self._is_an_ordinary_table():
            raise Exception(
                "You can not export the column ID of model %s, because the "
                "table %s is not an ordinary table."
                % (self._name, self._table))

        modname = '__export__'

        rows = self.env.execute_query(SQL("""
            SELECT res_id, module, name
            FROM ir_model_data
            WHERE model = %s AND res_id = ANY(%s)
        """, self._name, list(self.ids)))
        xids = {
            res_id: (module, name)
            for res_id, module, name in rows
        }

        def to_xid(record_id):
            (module, name) = xids[record_id]
            return ('%s.%s' % (module, name)) if module else name

        # create missing xml ids
        missing = self.filtered(lambda r: r.id not in xids)
        if not missing:
            return (
                (record, to_xid(record.id))
                for record in self
            )

        xids.update(
            (r.id, (modname, '%s_%s_%s' % (
                r._table,
                r.id,
                uuid.uuid4().hex[:8],
            )))
            for r in missing
        )
        IrModelData = apps.get_model('base', 'IrModelData')
        IrModelData.objects.using(self.env.db_alias).bulk_create([
            IrModelData(module=modname, model=record._name,
                        name=xids[record.id][1], res_id=record.id)
            for record in missing
        ])

        return (
            (record, to_xid(record.id))
            for record in self
        )

    def _export_rows(self, fields, *, _is_toplevel_call=True):
        """ Export fields of the records in ``self``. — ≙ ``_export_rows``
        (``odoo19c: :678-878``)

        :param list fields: list of lists of fields to traverse
        :param bool _is_toplevel_call:
            used when recursing, avoid using when calling from outside
        :return: list of lists of corresponding values

        Copia adaptada. La caché de propiedades que la fuente guarda en
        ``self.env.cr.cache['export_properties_cache']`` vive aquí en
        :data:`_EXPORT_PROPERTIES_CACHE`: el ``cr`` de este árbol es un
        alias, no un cursor con diccionario propio. Sigue siendo una por
        exportación de primer nivel y compartida por las llamadas
        recursivas.
        """
        import_compatible = self.env.context.get('import_compat', True)
        lines = []

        if not _is_toplevel_call:
            # {properties_field: {property_name: [property_type,
            #  {record_id: value}]}}
            cache_properties = _EXPORT_PROPERTIES_CACHE.get()
        else:
            cache_properties = collections.defaultdict(dict)
            cache_token = _EXPORT_PROPERTIES_CACHE.set(cache_properties)

            def fill_properties_cache(records, fnames_by_path, fname):
                """ Fill the cache for the ``fname`` properties field and
                return it """
                cache_properties_field = cache_properties[
                    records._fields[fname]]

                # read properties to have all the logic of
                # Properties.convert_to_read_multi
                for row in records.read([fname]):
                    properties = row[fname]
                    if not properties:
                        continue
                    rec_id = row['id']

                    for property in properties:
                        current_prop_name = property['name']
                        if (f"{fname}.{current_prop_name}"
                                not in fnames_by_path):
                            continue
                        property_type = property['type']
                        if current_prop_name not in cache_properties_field:
                            cache_properties_field[current_prop_name] = [
                                property_type, {}]

                        __, cache_by_id = cache_properties_field[
                            current_prop_name]
                        if rec_id in cache_by_id:
                            continue

                        value = property.get('value')
                        if property_type in ('many2one', 'many2many'):
                            if not isinstance(value, list):
                                value = [value] if value else []
                            value = self.env[property['comodel']].browse(
                                [val[0] for val in value])
                        elif property_type == 'tags' and value:
                            value = ",".join(
                                next(iter(tag[1] for tag in property['tags']
                                          if tag[0] == v), '')
                                for v in value
                            )
                        elif property_type == 'selection':
                            value = dict(property['selection']).get(
                                value, '')
                        cache_by_id[rec_id] = value

            def fetch_fields(records, field_paths):
                """ Fill the cache of ``records`` for all ``field_paths``
                recursively included properties"""
                if not records:
                    return

                fnames_by_path = dict(groupby(
                    [path for path in field_paths
                     if path and path[0] not in ('id', '.id')],
                    lambda path: path[0],
                ))

                # Fetch needed fields (remove '.property_name' part)
                fnames = list(unique(
                    fname.split('.')[0] for fname in fnames_by_path))
                records.fetch(fnames)
                # Fill the cache of the properties field
                for fname in fnames:
                    field = records._fields[fname]
                    if field.type == 'properties':
                        fill_properties_cache(records, fnames_by_path, fname)

                # Call it recursively for relational field (included
                # property relational field)
                for fname, paths in fnames_by_path.items():
                    if '.' in fname:  # Properties field
                        fname, prop_name = fname.split('.')
                        field = records._fields[fname]
                        assert field.type == 'properties' and prop_name

                        property_type, property_cache = cache_properties[
                            field].get(prop_name, ('char', None))
                        if (property_type not in ('many2one', 'many2many')
                                or not property_cache):
                            continue
                        model = next(iter(property_cache.values())).browse()
                        subrecords = model.union(*[
                            property_cache[rec_id] for rec_id in records.ids
                            if rec_id in property_cache])
                    else:  # Normal field
                        field = records._fields[fname]
                        if not field.relational:
                            continue
                        subrecords = records[fname]

                    paths = [path[1:] or ['display_name'] for path in paths]
                    fetch_fields(subrecords, paths)

            fetch_fields(self, fields)

        for record in self:
            # main line of record, initially empty
            current = [''] * len(fields)
            lines.append(current)

            # list of primary fields followed by secondary field(s)
            primary_done = []

            # process column by column
            for i, path in enumerate(fields):
                if not path:
                    continue

                name = path[0]
                if name in primary_done:
                    continue

                if name == '.id':
                    current[i] = str(record.id)
                elif name == 'id':
                    current[i] = (record._name, record.id)
                else:
                    prop_name = None
                    if '.' in name:  # Properties field
                        fname, prop_name = name.split('.')
                        field = record._fields[fname]
                        field_type, cache_value = cache_properties[
                            field].get(prop_name, ('char', None))
                        value = (cache_value.get(record.id, '')
                                 if cache_value else '')
                    else:  # Normal field
                        field = record._fields[name]
                        field_type = field.type
                        value = record[name]

                    # this part could be simpler, but it has to be done this
                    # way in order to reproduce the former behavior
                    if not isinstance(value, BaseModel):
                        current[i] = field.convert_to_export(value, record)

                    elif import_compatible and field_type == 'reference':
                        current[i] = f"{value._name},{value.id}"

                    else:
                        primary_done.append(name)
                        # recursively export the fields that follow name; use
                        # 'display_name' where no subfield is exported
                        fields2 = [(p[1:] or ['display_name']
                                    if p and p[0] == name else [])
                                   for p in fields]

                        # in import_compat mode, m2m should always be
                        # exported as a comma-separated list of xids or
                        # names in a single cell
                        if import_compatible and field_type == 'many2many':
                            index = None
                            # find out which subfield the user wants & its
                            # location as we might not get it as the first
                            # column we encounter
                            for name in ['id', 'name', 'display_name']:
                                with contextlib.suppress(ValueError):
                                    index = fields2.index([name])
                                    break
                            if index is None:
                                # not found anything, assume we just want the
                                # display_name in the first column
                                name = None
                                index = i

                            if name == 'id':
                                xml_ids = [
                                    xid for _, xid in value.__ensure_xml_id()]
                                current[index] = ','.join(xml_ids)
                            else:
                                current[index] = ','.join(
                                    value.mapped('display_name')
                                ) if value else ''
                            continue

                        lines2 = value._export_rows(
                            fields2, _is_toplevel_call=False)
                        if lines2:
                            # merge first line with record's main line
                            for j, val in enumerate(lines2[0]):
                                if val or isinstance(val, (int, float)):
                                    current[j] = val
                            # append the other lines at the end
                            lines += lines2[1:]
                        else:
                            current[i] = ''

        # if any xid should be exported, only do so at toplevel
        if _is_toplevel_call and any(f[-1] == 'id' for f in fields):
            bymodels = collections.defaultdict(set)
            xidmap = collections.defaultdict(list)
            # collect all the tuples in "lines" (along with their
            # coordinates)
            for i, line in enumerate(lines):
                for j, cell in enumerate(line):
                    if isinstance(cell, tuple):
                        bymodels[cell[0]].add(cell[1])
                        xidmap[cell].append((i, j))
            # for each model, xid-export everything and inject in matrix
            for model, ids in bymodels.items():
                for record, xid in self.env[model].browse(
                        ids).__ensure_xml_id():
                    for i, j in xidmap.pop((record._name, record.id)):
                        lines[i][j] = xid
            assert not xidmap, "failed to export xids for %s" % ', '.join(
                '{}:{}' % it for it in xidmap.items())

        if _is_toplevel_call:
            _EXPORT_PROPERTIES_CACHE.reset(cache_token)

        return lines

    def export_data(self, fields_to_export):
        """ Export fields for selected objects — ≙ ``export_data``
        (``odoo19c: :880-892``)

        This method is used when exporting data via client menu

        :param list fields_to_export: list of fields
        :returns: dictionary with a *datas* matrix
        :rtype: dict
        """
        user = self.env.user
        if not (self.env.is_admin() or (
                user is not None
                and user.has_group('base.group_allow_export'))):
            raise UserError(self.env._(
                "You don't have the rights to export data. Please contact "
                "an Administrator."))
        fields_to_export = [
            fix_import_export_id_paths(f) for f in fields_to_export]
        return {'datas': self._export_rows(fields_to_export)}

    def _read_relational_multi(self, field):
        """El valor de un campo relacional sobre varios registros: la unión
        de sus valores, sin repetidos y en orden. — ≙ el caso de varios
        registros de ``_Relational.__get__`` (``odoo19c: odoo/orm/
        fields_relational.py:42-79``) con ``convert_to_record_multi``
        (``:360-364`` y ``:655-667``).

        Allá los valores salen de la caché de campo; aquí se leen registro a
        registro con :meth:`_read_field`, que ya aplica el ``active_test`` de
        cada ``One2many``. Un comodelo de Django —sin recordset— devuelve el
        ``QuerySet`` de las mismas filas, que es como este árbol representa
        un conjunto de ellas.
        """
        self._check_field_access(field, 'read')
        values = [record._read_field(field) for record in self]
        ids = tuple(unique(
            id_ for value in values for id_ in _relation_value_ids(value)))
        recordsets = [value for value in values
                      if isinstance(value, BaseModel)]
        if recordsets:
            return recordsets[0].browse(ids)
        return field.related_model._default_manager.filter(pk__in=ids)


class IdFromIds:
    """El porte de ``Id.__get__`` — ≙ ``odoo19c:
    odoo/orm/fields_misc.py:102-114``.

    La fuente declara ``id = Id()`` en el cuerpo de ``BaseModel``. Aquí eso no
    basta: ``ModelBase`` instala su propio ``DeferredAttribute`` sobre la clave
    primaria al preparar **cada** subclase concreta, y sombrea el descriptor de
    la base — medido en
    ``scripts/workbench/basemodel-id-access-20260911T035612/outputs/id_descriptor.txt``.
    Por eso el descriptor se instala con :func:`_install_id_descriptor`, que
    corre en ``class_prepared`` y por tanto DESPUÉS de ``ModelBase``.

    **``__set__`` NO se porta, y está medido** (``outputs/id_setter.txt``):
    declararlo convierte al descriptor en *descriptor de datos*, que precede al
    ``__dict__`` de la instancia; ``Model.__init__`` asigna la clave primaria
    con ``setattr``, así que ``Sujeto(id=99)`` levanta
    ``TypeError: field 'id' cannot be assigned``. Sin ``__set__`` la misma fila
    da ``.id = 99``. Es divergencia forzada por el stack, no recorte de
    alcance.

    El relevo al descriptor original es lo que mantiene viva la construcción de
    filas de Django: una instancia sin ``_ids`` no es un recordset.
    """

    __slots__ = ['fallback']

    def __init__(self, fallback):
        self.fallback = fallback

    def __get__(self, record, owner=None):
        if record is None:
            return self
        ids = getattr(record, '_ids', None)
        if ids is None:
            return self.fallback.__get__(record, owner)
        size = len(ids)
        if size == 0:
            return False
        if size == 1:
            return ids[0]
        # El mensaje NO interpola el registro: el ``__repr__``/``__str__`` de
        # un
        # modelo de Django lee ``self.pk``, que vuelve a este descriptor y
        # recursa. La fuente no lo sufre porque su ``__repr__`` es
        # ``f'{self._name}{self._ids!r}'`` y no toca ``id``.
        raise ValueError(f'Expected singleton: ids={ids!r}')


@receiver(class_prepared)
def _install_id_descriptor(sender, **kwargs):
    """Instala :class:`IdFromIds` sobre la clave primaria de cada subclase.

    El receptor vive DESPUÉS de :class:`BaseModel` porque ``class_prepared`` no
    dispara para la base abstracta —``ModelBase`` sólo lo emite al preparar un
    modelo concreto—, así que el nombre ya está definido cuando llega la
    primera señal.

    **Divergencia declarada:** la fuente nombra siempre ``id``; aquí la clave
    primaria puede llamarse de otro modo, así que el descriptor se instala
    sobre ``_meta.pk.attname`` y, si ése no es ``id``, también bajo ``id`` para
    conservar el nombre del contrato.
    """
    if not issubclass(sender, BaseModel):
        return
    attname = sender._meta.pk.attname
    actual = sender.__dict__.get(attname)
    if actual is not None and not isinstance(actual, IdFromIds):
        descriptor = IdFromIds(actual)
        setattr(sender, attname, descriptor)
        if attname != 'id':
            setattr(sender, 'id', descriptor)


class AbstractModel:
    """La base del registrante **sin tabla** — ≙ ``AbstractModel``.

    La fuente lo declara como alias de su base (``AbstractModel = BaseModel``,
    ``odoo19c: odoo/orm/models.py:7047``), que trae ``_auto = False``
    (``:370``), ``_register = False`` (``:380``), ``_abstract = True``
    (``:381``) y ``_name = None`` (``:392``). Los cuatro se declaran aquí
    verbatim.

    **Por qué no hereda de Django, que es lo que lo hace útil.** Un registrante
    sin tabla es exactamente lo que
    :func:`~orm.registry.registrants_without_table` aparta al comparar
    ``_name`` con ``db_table``: clases que declaran nombre punteado y no tienen
    ``_meta``. Heredar de ``models.Model`` les daría uno —con ``db_table``
    derivado del ``app_label``— y las sacaría de esa cuenta, que es el
    denominador que impide que un cero de divergencias se lea como «todo
    cuadra» cuando en realidad no había nada que comparar.

    **Sus dos consumidores están medidos** y hoy no lo adoptan:
    ``IrFieldsConverter`` (``ir.fields.converter``) e ``IrTemplateExpressions``
    (``ir.qweb``). Que pasen a heredar de aquí —y con ello dejen de repetir los
    cuatro atributos por su cuenta— es la tarea **#329**.
    """

    _name = None            #: el nombre del modelo, en notación de punto
    _auto = False           #: no crea tabla en la base
    _register = False       #: no visible en el registro por nombre
    _abstract = True        #: es abstracto


#: ``Model`` — ≙ ``class Model(AbstractModel)``
#: (``odoo19c: odoo/orm/models.py:7049``).
#:
#: **Ya existe, y es el de Django**: este módulo re-exporta el ORM completo
#: (``from django.db.models import *``, arriba), así que ``orm.models.Model``
#: es ``django.db.models.Model`` — *"main super-class for regular
#: database-persisted models"*, que es palabra por palabra lo que la fuente
#: dice del suyo. Lo hereda todo el árbol, y ``orm/models_transient.py:36`` lo
#: importa de aquí por su nombre.
#:
#: **Los tres atributos de clase que la fuente le declara NO se le cuelgan**, y
#: la razón está medida, no supuesta:
#:
#: - ``_auto = True`` — su equivalente es ``Meta.managed``, que Django ya
#:   declara por modelo (``atributos-de-clase-de-modelo.md``).
#: - ``_abstract = False`` — su equivalente es ``Meta.abstract``, y colgarlo
#:   como constante en la base **mentiría** sobre todo modelo que sí declara
#:   ``abstract = True``: lo heredaría en ``False``.
#: - ``_register = False`` — su equivalente es el registro por nombre
#:   ``orm.registry.MODELS_BY_NAME``, que se puebla por ``_name`` declarado.
#:
#: Y colgarle atributos a ``models.Model`` alcanza a **toda** clase que lo
#: hereda, incluidas las de Django (``auth``, ``contenttypes``, ``sessions``) y
#: las de terceros — la misma colisión que :class:`FieldSqlMixin` ya declara al
#: elegir mixin en vez de adjuntar, y que la tarea **#98** barre.


@functools.total_ordering
class ReversibleComparator:
    """Clave de orden con dirección y política de nulos **en la clave**.

    ≙ ``ReversibleComparator`` (``odoo19c: odoo/orm/models.py:7066-7094``).

    Los dos ejes son independientes, y ahí está su razón de ser: ``reverse``
    invierte la comparación entre dos valores presentes, y ``none_first``
    decide dónde va el ausente **sin** invertirse con el anterior. Un
    ``sorted(reverse=True)`` no puede expresarlo —invierte la lista entera,
    nulos incluidos— ni permite mezclar columnas ascendentes y descendentes en
    un mismo orden, que es para lo que la fuente lo usa.

    ``@functools.total_ordering`` deriva ``<=``, ``>`` y ``>=`` de
    :meth:`__lt__` y :meth:`__eq__`; la fuente cuenta con ello.
    """

    __slots__ = ('__item', '__none_first', '__reverse')

    def __init__(self, item, reverse, none_first):
        self.__item = item
        self.__reverse = reverse
        self.__none_first = none_first

    def __lt__(self, other):
        item = self.__item
        item_cmp = other.__item
        if item == item_cmp:
            return False
        if item is None:
            return self.__none_first
        if item_cmp is None:
            return not self.__none_first
        if self.__reverse:
            item, item_cmp = item_cmp, item
        return item < item_cmp

    def __eq__(self, other):
        return self.__item == other.__item

    def __hash__(self):
        return hash(self.__item)

    def __repr__(self):
        return (f"<ReversibleComparator {self.__item!r}"
                f"{' reverse' if self.__reverse else ''}>")


# ═══════════════════════════════════════════════════════════════════════════
# El esquema de una columna sobre filas que ya existen
#     ≙ ``BaseModel._init_column`` (``odoo19c: odoo/orm/models.py:3137-3161``)
#     y ``BaseModel._table_has_rows`` (``:3163-3168``)
# ═══════════════════════════════════════════════════════════════════════════
#
# Los dos son consumidores de ``Field.update_db_notnull``: cuando una columna
# nace, o cuando un campo pasa a ser obligatorio, las filas que ya estaban ahí
# tienen ``NULL`` y la restricción no las admite. La fuente resuelve eso en dos
# pasos —¿hay filas? y, si las hay, siémbrales el default— y aquí igual.
#
# **Divergencia de enlace, declarada.** La fuente los declara métodos de
# instancia porque allá un «modelo» es un recordset. Aquí el modelo es una
# clase de Django, y quien los llama —``Field.update_db``— tiene la clase, no
# una fila. Se enlazan como ``classmethod``: el contrato es el mismo y el
# receptor es el que el llamador tiene. Es la misma puerta que
# ``registry.Registry.is_an_ordinary_table`` ya declaró para el cursor.


def _init_column(cls, column_name):
    """Siembra el valor por defecto de una columna en las filas existentes.

    Docstring de la fuente, verbatim: *"Initialize the value of the given
    column for existing rows"*.

    El default se obtiene del campo y **no** de ``default_get``: la fuente lo
    explica en su comentario —*"ideally, we should use default_get(), but it
    fails due to ir.default not being ready"*— y aquí vale igual, porque este
    camino corre mientras el esquema se está construyendo.

    La guarda de ``necessary`` es de la fuente y no es cosmética: un booleano
    no obligatorio trata ``False`` y ``NULL`` como lo mismo, así que sembrarlo
    costaría un ``UPDATE`` sobre toda la tabla sin cambiar nada observable. Si
    es obligatorio sí se escribe, porque ahí el ``NOT NULL`` sí distingue.
    """
    field = model_field_registry(cls)[column_name]
    #: **Divergencia de mecanismo, no de conducta.** La fuente escribe
    #: ``if field.default: value = field.default(self)`` porque en su ORM el
    #: default, cuando existe, es SIEMPRE un invocable. En Django es un valor
    #: **o** un invocable, y el centinela de «sin default» no es la falsedad
    #: sino ``NOT_PROVIDED``: con ``default=''`` —el caso de un ``TextField``
    #: obligatorio— la guarda de la fuente daria falso y la columna nueva
    #: quedaria sin sembrar, que es justo lo contrario de lo que ella hace.
    #: El par que el stack declara para esto resuelve las dos formas:
    #: ``has_default()`` (``fields/__init__.py:1013``) y ``get_default()``
    #: (``:1021``, que envuelve el valor en un ``lambda`` cuando no es
    #: invocable).
    if field.has_default():
        value = field.get_default()
        value = field.convert_to_write(value, cls)
        value = field.convert_to_column_insert(value, cls)
    else:
        value = None
    necessary = ((value is not None)
                 if field.type != 'boolean' or field.required else value)
    if not necessary:
        return
    _logger.debug("Tabla '%s': valor por defecto de la columna nueva %s a %r",
                  cls._table, column_name, value)
    query = SQL(
        "UPDATE %(table)s SET %(field)s = %(value)s WHERE %(field)s IS NULL",
        table=SQL.identifier(cls._table),
        field=SQL.identifier(field.column),
        value=value,
    )
    with connections[DEFAULT_DB_ALIAS].cursor() as cr:
        cr.execute(query.code, query.params)


def _table_has_rows(cls) -> bool:
    """Si la tabla del modelo tiene alguna fila.

    Docstring de la fuente, verbatim: *"Return whether the model's table has
    rows. This method should only be used when updating the database schema"*.

    Memorizado con :class:`~tools.cache.ormcache` como allá: durante la
    construcción del esquema se pregunta una vez por campo y la respuesta no
    cambia dentro de ese pase. Quien siembre filas después invalida con
    ``orm.registry.clear_cache()``.
    """
    with connections[DEFAULT_DB_ALIAS].cursor() as cr:
        cr.execute(f'SELECT 1 FROM {cls._table} LIMIT 1')
        return bool(cr.fetchone())


Model._init_column = classmethod(_init_column)
Model._table_has_rows = classmethod(ormcache()(_table_has_rows))


class _EnvClassmethod(classmethod):
    """Método de clase que, pedido sobre un recordset, corre en su entorno.

    ≙ la llamada ``records.search(...)`` de la referencia, donde ``search`` es
    un método de instancia y lee ``self.env`` (``odoo19c:
    odoo/orm/models.py:1363``): el ``uid``, la elevación y el contexto que
    ``with_context``, ``sudo`` y ``with_user`` fijaron viajan con el
    recordset. Aquí ``search``, ``create`` o ``name_create`` son métodos de
    clase y leen los canales de :mod:`orm.environments`; sin esta envoltura el
    entorno del recordset se perdía en la llamada (H-API-1160).

    **Divergencia de mecanismo, declarada.** No se convierten en métodos de
    instancia: la clase sigue siendo el modelo vacío de la referencia y la
    llaman cientos de sitios sin recordset. Lo que se añade es entrar en
    ``instance.env`` —:meth:`Environment.__enter__` activa sus ejes y
    ``__exit__`` restaura los previos— cuando el método se pide desde una
    instancia. Pedido desde la clase, se comporta como un ``classmethod``.
    """

    def __init__(self, method):
        super().__init__(method.__func__)
        self.__dict__.update(getattr(method, '__dict__', {}))

    def __get__(self, instance, owner=None):
        bound = super().__get__(instance, owner)
        environment = getattr(instance, 'env', None) if instance is not None \
            else None
        if environment is None or not hasattr(environment, '__enter__'):
            return bound

        @functools.wraps(bound)
        def within_environment(*args, **kwargs):
            with environment:
                return bound(*args, **kwargs)

        return within_environment


def wrap_env_classmethods(cls, names=None):
    """Envuelve, en ``cls``, cada método de clase que resuelva por su MRO a
    un ``classmethod`` sin envolver. Los nombres con doble guion bajo se
    excluyen: son protocolo de Python (``__init_subclass__``,
    ``__class_getitem__``), no API del modelo.

    Es pública porque ``__init_subclass__`` sólo ve lo que la clase trae al
    crearse: quien cuelgue un método de clase después —
    :func:`orm.model_classes.adopt_display_name` lo hace con los de
    ``display_name``— la llama para que lo colgado también corra en el
    entorno del recordset. ``names`` acota la envoltura a lo que colgó."""
    for name in dir(cls) if names is None else names:
        if name.startswith('__'):
            continue
        for klass in cls.__mro__:
            if name in vars(klass):
                value = vars(klass)[name]
                break
        else:
            continue
        if isinstance(value, classmethod) and not isinstance(
                value, _EnvClassmethod):
            setattr(cls, name, _EnvClassmethod(value))


def _wrap_subclass_classmethods(cls, **kwargs):
    """``__init_subclass__`` de :class:`BaseModel`: todo modelo nuevo recibe
    la envoltura de sus métodos de clase al crearse."""
    super(BaseModel, cls).__init_subclass__(**kwargs)
    wrap_env_classmethods(cls)


def _wrap_existing_models(cls):
    wrap_env_classmethods(cls)
    for subclass in cls.__subclasses__():
        _wrap_existing_models(subclass)


BaseModel.__init_subclass__ = classmethod(_wrap_subclass_classmethods)
_wrap_existing_models(BaseModel)


def _many2many_lines(descriptor, instance, comodel, ids):
    """Las líneas de un ``Many2many`` como las devuelve la referencia. —
    ≙ ``Many2many.read`` (``odoo19c: odoo/orm/fields_relational.py:1370-1410``)
    seguido de ``_RelationalMulti.convert_to_record`` (``:643-653``).

    La lectura trae todos los enlaces —allá la búsqueda va con
    ``active_test=False``— y la conversión los devuelve en el entorno del
    registro, descartando los archivados salvo que el contexto del campo o el
    del registro apaguen ``active_test``. El gestor de Django ya devuelve
    todos los enlaces: lo que faltaba es el filtro y el entorno.
    """
    field_context = (getattr(descriptor.field, 'context', None) or {}
                     if not descriptor.reverse else {})
    lines = comodel._from_ids(instance.env, ids, ids)
    active = comodel._active_field_name()
    if active and field_context.get(
            'active_test', instance.env.context.get('active_test', True)):
        lines = lines.filtered(active)
    return lines


def apply_onchange_methods(record, methods, result, excluded_methods,
                           has_field, assign, translate):
    """El despacho de ``_apply_onchange_methods`` — ≙ el cuerpo de
    ``odoo19c: odoo/orm/models.py:6975-6994``.

    La referencia lo escribe como método de ``BaseModel`` porque su único
    registro es el del ORM. Aquí lo consumen dos clases de registro:
    :meth:`BaseModel._apply_onchange_methods` y ``Base.onchange`` de
    ``web``, cuyo registro es una instancia de Django. Lo que difiere entre
    las dos es cómo se pregunta si existe un campo (``has_field``) y cómo se
    asigna (``assign``); la selección, la invocación y la propagación son
    una sola, aquí.

    ``result['warnings']`` es un ``OrderedSet``, como en la referencia: un
    aviso repetido cuenta una vez. Una excepción del método sube sin
    capturarse.
    """
    for method in methods:
        if method in excluded_methods:
            continue
        res = method(record)
        if not res:
            continue
        if res.get('value'):
            for key, val in res['value'].items():
                if has_field(key) and key != 'id':
                    assign(key, val)
        if res.get('warning'):
            result['warnings'].add((
                res['warning'].get('title') or translate("Warning"),
                res['warning'].get('message') or "",
                res['warning'].get('type') or "",
            ))


def _get_placeholder_filename(self, field):
    """La imagen de relleno de ``field``: ninguna, salvo que el modelo la dé.

    ≙ ``BaseModel._get_placeholder_filename`` (``odoo19c:
    odoo/orm/models.py:6999-7004``). Docstring de la fuente: *"Returns the
    filename of the placeholder to use, set on web/static/img by default, or
    the complete path to access it (eg: module/path/to/image.png)."*

    Se cuelga de ``Model`` y no sólo de ``BaseModel``, como los métodos de
    motor: ``ir.binary`` la llama sobre cualquier registro, y aquí un
    registro puede ser un modelo de Django sin recordset (TASK-API-0513).
    """
    return False


Model._get_placeholder_filename = _get_placeholder_filename

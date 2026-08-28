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
import functools
import logging

from django.apps import apps
from django.db.models import *          # noqa: F401,F403  (re-export ORM completo)
from django.db.models import (  # noqa: F401
    ForeignKey, Manager, Model, QuerySet,
)

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import DEFAULT_DB_ALIAS

from exceptions import AccessError, UserError
from orm.environments import (
    get_context, get_current_company, get_current_uid, get_current_user, is_su,
)
from orm.domains import Domain
from orm.fields import convert_to_display_name
from orm.fields_nonstored import NonStored
from orm.fields_properties import Properties
from orm.utils import parse_field_expr

_logger = logging.getLogger(__name__)


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
        """La empresa que sugerir al redirigir a estos registros — ``:5825-5839``.

        La fuente lo declara en ``BaseModel`` y lo usa
        ``ir.rule._make_access_error`` para distinguir *"no tienes permiso"* de
        *"tienes permiso pero con otra empresa activa"*, que es la diferencia
        entre un 403 opaco y uno accionable. Su cuerpo es un ``if`` de tres
        ramas sobre qué campo declara el modelo:

        .. code-block:: python

           if 'company_id' in self:      return self.company_id
           elif 'company_ids' in self:   return (self.company_ids & self.env.user.company_ids)[:1]
           return False

        Aquí vive en el queryset, que es lo que en este árbol hace de
        recordset. La fuente devuelve un recordset —vacío, de uno, o la unión
        de las empresas de varias filas— y aquí una **lista**: ``company_ids``
        es un M2M inverso y su intersección con las del usuario no es un
        queryset de la misma tabla.

        ``'company_id' in self`` pregunta por el **campo**, no por el valor.
        Aquí se pregunta por los dos nombres —``company`` y su ``attname``
        ``company_id``— porque este árbol declara la FK con el nombre corto
        (:ref:`h-api-874` midió la misma distinción en ``_add_missing_default_values``).
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

    ≙ ``BaseModel._origin`` (``odoo19c: odoo/orm/models.py:6462-6469``). Allá un
    registro en formulario lleva un ``NewId`` cuyo ``.origin`` apunta a la fila
    persistida; sobre registros ya reales el atributo devuelve ``self`` ("already
    real records"). Es lo que permite a un ``@api.onchange`` comparar el valor
    que el usuario acaba de teclear con el que hay en base.

    **La divergencia, y es de forma** —la misma que declara la sección de
    permisos de este archivo—: allá ``self`` es un recordset y el atributo
    cuelga de ``BaseModel``, así que todo modelo lo tiene. Aquí ``models.Model``
    es el de Django y no es nuestro para colgarle nada, así que el mecanismo es
    un mixin que el modelo adopta —igual que ``objects = AccessManager()``— y
    el eje que distingue "en formulario" de "guardado" no es el tipo del id
    sino el estado de la instancia: los atributos en memoria frente a la fila.

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
        # (``orm/fields_properties.py``)—, y el motivo x2many no se puede dar:
        # nuestro ``Command`` es **ejecutivo**, escribe al llamarlo en vez de
        # devolver una tupla, asi que un default de x2many nunca es una lista
        # de comandos. Esa divergencia es de la clase entera y ya tiene su
        # registro (:ref:`h-api-589`, tarea **#345**), no se abre aqui.
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
            for _parent_name, fk_name in getattr(model, '_inherits', {}).items():
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
                defaults[field.name] = field._add_default_values(defaults)

        return defaults

    @classmethod
    def create(cls, **values):
        """Alta que aplica los defaults que faltan, como la fuente.

        ≙ la llamada ``vals = self._add_missing_default_values(vals)`` que
        ``BaseModel.create`` hace en ``odoo19c: odoo/orm/models.py:4796``.

        **La divergencia de forma, declarada:** allá ``create`` recibe una
        lista de dicts y devuelve un recordset; aquí recibe kwargs y devuelve
        una instancia, que es la firma que ya usan los seis ``create`` de
        clase del árbol (``ir_config_parameter``, ``res_currency``,
        ``ir_default``, …). Lo que se porta es **el paso**, no la firma.

        El **muchos-a-muchos se asigna después del alta**, no dentro: Django
        exige la fila antes de poblar la tabla intermedia. Allá el mismo caso
        se resuelve convirtiendo la lista de ids en ``[Command.set(value)]``
        (``:1580-1581``); aquí el equivalente es ``manager.set(...)``, porque
        nuestro ``Command`` es ejecutivo (:ref:`h-api-589`, tarea **#345**).
        """
        values = cls._add_missing_default_values(values)
        deferred = {}
        for field in cls._meta.many_to_many:
            if field.name in values:
                deferred[field.name] = values.pop(field.name)
        record = cls.objects.create(**values)
        for name, value in deferred.items():
            getattr(record, name).set(value)
        return record


#: ≙ ``LOG_ACCESS_COLUMNS`` (``odoo19c: odoo/orm/models.py:296``). Allá son
#: ``create_uid``, ``create_date``, ``write_uid`` y ``write_date``; aquí el
#: mecanismo es ``TimeStampedModel``, que declara dos —``created_at`` y
#: ``updated_at``, ambas ``auto_now``— y ninguna de autoría. La divergencia es
#: del mixin, no de este archivo: quién escribió la fila no se guarda.
LOG_ACCESS_COLUMNS = ['created_at', 'updated_at']

#: ≙ ``MAGIC_COLUMNS`` (``odoo19c: odoo/orm/models.py:297``).
MAGIC_COLUMNS = ['id'] + LOG_ACCESS_COLUMNS


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
            for _parent_name, fk_name in getattr(model, '_inherits', {}).items():
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

        blacklist = cls._copy_blacklist(default)
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

    def copy_children(self, new, seen=None):
        """Duplica los hijos ``one2many`` del original bajo el nuevo registro.

        ≙ la rama ``if field.type == 'one2many'`` de ``copy_data``
        (``odoo19c: :5450-5455``), que allá vive **dentro** del mismo método
        porque su ``Command.create`` es una tupla que el ORM aplica después.

        Aquí no puede vivir dentro: nuestro ``Command`` es **ejecutivo**
        —escribe al llamarlo (:ref:`h-api-589`, tarea **#345**)— y Django
        exige la fila del padre antes de poder colgarle un hijo. Así que el
        paso se separa y corre **después** del alta, con el padre ya con ``pk``.
        El efecto es el mismo que el de la fuente: los hijos se duplican *"using
        the wrong (old) parent, but then are reassigned to the correct one"*.

        El orden **por id** no es cosmético; el comentario de la fuente lo dice:
        *"duplicate following the order of the ids because we'll rely on it
        later for copying translations"*.
        """
        cls = type(self)
        seen = collections.defaultdict(set) if seen is None else seen
        for relation in cls._meta.related_objects:
            if not relation.one_to_many:
                continue
            accessor = relation.get_accessor_name()
            if accessor is None or not hasattr(self, accessor):
                continue
            child_model = relation.related_model
            if not issubclass(child_model, CopyMixin):
                continue
            fk_name = relation.field.name
            for child in getattr(self, accessor).order_by('id'):
                child_values = child.copy_data({fk_name: new}, seen=seen)
                if child_values is None:
                    continue
                child_values.pop(relation.field.attname, None)
                child_values[fk_name] = new
                nuevo_hijo = child_model.create(**child_values)
                child.copy_children(nuevo_hijo, seen=seen)

    def copy_translations(self, new, excluded=()):
        """BLOQUEADO por ``translate`` — el almacenamiento por idioma.

        ≙ ``copy_translations`` (``odoo19c: odoo/orm/models.py:5465-5528``).

        No es una divergencia de mecanismo ni una omisión: **no hay
        traducciones que copiar**. La referencia guarda el campo traducible
        como columna ``jsonb`` ``{lang: valor}``; aquí ``translate=True`` se
        **anota** en el campo (``field.odoo_translate``, ``orm/fields_textual``)
        y la columna sigue siendo ``varchar`` con un solo idioma. Los tres
        símbolos que el cuerpo consume —``_get_stored_translations``,
        ``update_field_translations``, ``get_translation_dictionary``— están
        medidos en **0** definiciones bajo ``src/``.

        El método existe con su firma para que :meth:`copy` lo llame donde la
        fuente lo llama: cuando #333 construya el almacenamiento, el cuerpo se
        escribe aquí y ``copy`` no cambia. Sucesor: tarea **#333**.
        """
        return None

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
        alta = cls.create if hasattr(cls, '_add_missing_default_values') \
            else cls.objects.create
        new = alta(**values)
        self.copy_children(new, seen=seen)
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
        for field in [*parent._meta.concrete_fields, *parent._meta.many_to_many]:
            if field.name not in seen:
                seen.add(field.name)
                names.append(field.name)
    return names


def _delegated_origin(model, name):
    """El ``(modelo padre, campo)`` del que ``name`` se hereda, o ``None``.

    NO tiene contraparte con este nombre: allá el campo heredado lo declara
    él mismo (``field.inherited`` y ``field.related_field``), porque el ORM
    construye un campo espejo en el hijo. Aquí ``_inherits`` cuelga los
    campos del padre por ``property`` (``orm/inherits.py``), así que la
    pregunta se responde mirando el mapa de delegación.

    La fuente además exige ``_has_field_access(field, 'write')`` antes de
    delegar. Aquí ese check vive en ``FieldSqlMixin``, que no todo modelo
    adopta todavía (tarea **#96**); cuando el modelo lo tenga, se aplica.
    """
    for parent_name, fk_name in getattr(model, '_inherits', {}).items():
        try:
            fk_field = model._meta.get_field(fk_name)
        except FieldDoesNotExist:
            continue
        parent_model = fk_field.related_model
        if parent_model is None:
            continue
        try:
            parent_model._meta.get_field(name)
        except FieldDoesNotExist:
            continue
        if hasattr(model, '_has_field_access'):
            if not model()._has_field_access(fk_field, 'write'):
                continue
        return parent_model, name
    return None


#: ≙ ``NO_ACCESS`` (``odoo19c: odoo/orm/models.py:122``). Valor sentinela de
#: ``field.groups`` que prohíbe el campo a todo el mundo, elevación aparte.
NO_ACCESS = '.'


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

    @property
    def _fields(self):
        """Los campos del modelo por nombre — ≙ ``BaseModel._fields``.

        Allá es el registro que el ORM construye al cargar la clase; aquí lo
        provee ``_meta``, que es el registro equivalente de Django. Sólo entran
        los **concretos**: son los que tienen columna, y los únicos que
        ``to_sql`` sabe convertir. Una relación inversa o un ``ManyToMany`` no
        la tiene y allá tampoco es un campo almacenado.

        *Métrica:* ``_meta.get_fields()`` filtrado por ``concrete``.
        *Ciega a:* el ``NonStored`` de ``orm/fields_nonstored.py``, que no es
        un campo de Django y por diseño no aparece en ``_meta`` — es el
        ``store=False`` de la fuente, y ``_field_to_sql`` lo rechaza por la
        misma razón que allá: no tiene columna que nombrar.
        """
        return {
            field.name: field
            for field in self._meta.get_fields()
            if getattr(field, 'concrete', False)
        }

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

        Las tres ramas del tramo de grupos son las de la fuente (``:3411-3418``)
        y no son intercambiables: ``NO_ACCESS`` significa *prohibido siempre* y
        no *«pide el grupo»*; un campo sin ``groups`` que aun así se denegó
        sólo puede deberse a una regla a medida.
        """
        if self._has_field_access(field, operation):
            return

        _logger.info(
            'Access Denied by ACLs for operation: %s, uid: %s, model: %s, field: %s',
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
        """El nombre informal del modelo — ≙ ``self.env['ir.model']._get(name).name``.

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
        """Recorre el campo delegado y añade a ``query`` los JOIN que hagan falta.

        ≙ ``_traverse_related_sql`` (``odoo19c: odoo/orm/models.py:2889-2908``).

        :returns: la terna ``(model, field, alias)``, donde ``field`` es el
            último campo de la secuencia, ``model`` el modelo de ese campo y
            ``alias`` el alias de su tabla.

        El ``related`` de la fuente es una ruta con puntos —``partner_id.name``—
        y aquí el mecanismo equivalente es ``orm/inherits.py``: ``_inherits``
        instala la delegación y el camino es un solo salto, el de su FK. Por
        eso el bucle recorre ``field.related.split('.')`` igual que allá: la
        ruta de un salto es el caso que hoy existe, y la de varios funciona sin
        tocar nada el día que un campo la declare.
        """
        # `related`/`store` se leen con `getattr`: son atributos de la clase
        # `Field` de la referencia, y un campo de Django no los declara. Sin
        # el `getattr` la aserción no rechaza — revienta con AttributeError,
        # que no es lo mismo y esconde el motivo.
        assert (getattr(field, 'related', None)
                and not getattr(field, 'store', True))
        *path_fnames, last_fname = field.related.split('.')
        model = type(self)
        for path_fname in path_fnames:
            path_field = model._fields[path_fname]
            if not isinstance(path_field, ForeignKey):
                raise ValueError(
                    f'Cannot convert {field} (related={field.related}) to SQL '
                    f'because {path_fname} is not a Many2one')
            model, alias = path_field.join(model, alias, query)

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
        if not field:
            raise ValueError(
                f"Invalid field {fname!r} on model {self._meta.label!r}")

        if getattr(field, 'related', None) and not getattr(field, 'store', True):
            model, field, alias = self._traverse_related_sql(alias, field, query)
            related_expr = (field.name if not property_name
                            else f"{field.name}.{property_name}")
            return model._field_to_sql(alias, related_expr, query)

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
    pasa a ser ``cls.objects.create``, ``self.browse(id)`` a un ``filter(pk=)``,
    y el ``original_self.concat(...)`` del final a la lista de registros en el
    orden de ``data_list``, que es lo que la fuente promete devolver.

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
        to_write = {}  # Deferred the write to avoid using the old definition if it changed
        for fname in list(values):
            field = self._fields.get(fname)
            if not isinstance(field, Properties):
                continue
            field_converter = field.convert_to_cache
            to_write[fname] = dict(
                getattr(self, fname, None) or {},
                **(field_converter(values.pop(fname), self, validate=False) or {}))

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
        pk_name = self._meta.pk.name
        values = {fname: value for fname, value in values.items()
                  if fname not in (pk_name, 'id')}
        if not values:
            return self
        values = self._load_records_coerce_vals(values)
        for fname, value in values.items():
            setattr(self, fname, value)
        self.save(update_fields=list(values))
        return self

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
        records = [cls.objects.using(using).create(
            **cls._load_records_coerce_vals(vals)) for vals in vals_list]
        if any(isinstance(field, Properties)
               for field in cls._meta.get_fields()):
            for record in records:
                record._clean_properties()
        return records

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
                    data['record'] = cls.objects.using(using).get(pk=vals['id'])
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
                if (data.get('xml_id') and not data['xml_id'].startswith(prefix)
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
                            f'in the external id. Because the prefix refers to '
                            f'an existing module, the record would be deleted '
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
                    # add XML ids for parent records that have just been created
                    # ``_inherits`` se lee del atributo de clase, que es donde
                    # la referencia lo declara y donde este árbol lo porta
                    # verbatim (tarea #385).
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



def _display_name_default(record):
    """El ``default`` del descriptor: delega en ``_compute_display_name``."""
    return record._compute_display_name()


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
    - los **90** restantes lo reciben de :func:`orm.model_classes.adopt_display_name`,
      que corre en ``class_prepared`` y en un barrido, igual que el manager de
      permisos.

    Por qué no basta con la base común: 90 modelos no la heredan, y **el olvido
    no falla** — un modelo sin ``display_name`` cae al ``__str__`` de Django y
    nada lo delata. Es la misma clase de defecto silencioso que ``H-API-876``
    registró para el manager.

    Tres divergencias de FORMA, todas heredadas del árbol y ninguna nueva
    ======================================================================

    Las tres ya las ejercían los cinco modelos que declaraban su
    ``_compute_display_name`` antes de esta tarea (``res_bank``, ``res_partner``,
    ``ir_model``, ``properties_base_definition``, ``res_currency``), así que
    cambiarlas ahora rompería lo que ya funciona:

    1. **``_compute_display_name`` DEVUELVE la etiqueta**; la fuente la
       **asigna** (``record.display_name = convert(...)``). Aquí el campo no es
       un campo del ORM con cache de cómputo, así que el valor tiene que
       volver al descriptor por el retorno.
    2. **``_search_display_name`` devuelve un ``QuerySet``**, no un ``Domain``.
       Es lo que ``res_bank`` y ``res_currency`` ya devuelven, y lo que el
       llamador de este árbol sabe consumir.
    3. **``name_create`` y ``name_search`` son ``classmethod``**: allá son
       ``@api.model``, es decir métodos sobre un recordset vacío que sólo
       aporta el modelo. Ese papel lo cumple la clase.

    Lo que NO es divergencia: la asignación sigue permitida
    ======================================================

    ``display_name`` es un :class:`orm.fields_nonstored.NonStored`, no una
    ``property``, y la diferencia es deliberada: la fuente declara un campo, y
    un campo de la fuente **se puede escribir en memoria** aunque no tenga
    columna. ``record.display_name = 'X'`` gana sobre el cómputo hasta que se
    borre, igual que allá.
    """

    #: ≙ ``display_name = Char(string='Display Name', compute=..., search=...)``
    #: (``odoo19c: odoo/orm/models.py:473``). El ``compute`` y el ``search`` de
    #: la fuente son los dos métodos de abajo; aquí el primero lo cablea el
    #: ``default`` del descriptor y el segundo lo llama ``name_search``.
    display_name = NonStored(default=_display_name_default,
                             help_text='Display Name')

    def _compute_display_name(self):
        """La etiqueta del registro — ≙ ``_compute_display_name`` (``:1425``).

        Con ``_rec_name`` resuelto, el valor de ese campo pasado por
        :func:`orm.fields.convert_to_display_name`; sin él, ``modelo,id``,
        verbatim el ``f"{record._name},{record.id}"`` de la fuente.

        El ``@api.depends(lambda self: (self._rec_name,) ...)`` de la fuente no
        se porta: declara de qué depende el cómputo para invalidar su cache, y
        aquí no hay cache que invalidar — el descriptor computa en cada
        lectura. Es divergencia de mecanismo, no un hueco.
        """
        rec_name = getattr(type(self), '_rec_name', None)
        if not rec_name:
            nombre = getattr(type(self), '_name', None) or self._meta.label
            return f'{nombre},{self.pk}'
        try:
            field = self._meta.get_field(rec_name)
        except FieldDoesNotExist:
            field = None
        etiqueta = convert_to_display_name(field, getattr(self, rec_name), self)
        # El ``False`` del default de la fuente para un campo vacío: aquí la
        # etiqueta tiene que ser texto, así que se cae al par ``modelo,id`` —
        # que es lo que la fuente da cuando NO hay ``_rec_name`` en absoluto, y
        # el único texto que identifica al registro sin inventar nada.
        if not etiqueta:
            nombre = getattr(type(self), '_name', None) or self._meta.label
            return f'{nombre},{self.pk}'
        return etiqueta

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
        search_fnames = (getattr(cls, '_rec_names_search', None)
                         or ([cls._rec_name] if getattr(cls, '_rec_name', None)
                             else []))
        if not search_fnames:
            _logger.warning(
                'No se puede buscar por display_name: %s no declara _rec_name '
                'ni _rec_names_search', cls._meta.label)
            return cls.objects.all()
        negativo = operator in NEGATIVE_DISPLAY_NAME_OPERATORS
        if operator.endswith('like') and not value and '=' not in operator:
            return cls.objects.none() if negativo else cls.objects.all()

        lookup = 'iexact' if operator in ('=', '!=', '<>') else 'icontains'
        emparejado = None
        for field_expr in search_fnames:
            ruta = field_expr.replace('.', '__')
            condicion = Q(**{f'{ruta}__{lookup}': value})
            emparejado = condicion if emparejado is None else (
                emparejado & condicion if negativo else emparejado | condicion)
        if negativo:
            return cls.objects.exclude(emparejado)
        return cls.objects.filter(emparejado)

    @classmethod
    def name_create(cls, name):
        """Crea el registro a partir de su sola etiqueta — ≙ ``:1493``.

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
        record = cls.objects.create(**{rec_name: name})
        return record.pk, record.display_name

    @classmethod
    def name_search(cls, name='', domain=None, operator='ilike', limit=100):
        """Los pares ``(id, etiqueta)`` que coinciden — ≙ ``:1512``.

        Es :meth:`_search_display_name` acotado por el ``domain`` extra y por
        ``limit``. El ``domain`` se recibe como ``Q`` de Django o ``None``,
        que es la forma que ``website_rewrite.name_search`` ya usaba en este
        árbol.

        El ``.sudo()`` del final de la fuente no se porta: allá levanta el
        permiso para poder leer la etiqueta de lo que la búsqueda ya
        seleccionó. Aquí la selección la hace un ``QuerySet`` de Django, que no
        filtra por permiso — el acotamiento por fila lo aplica
        ``AccessQuerySet`` cuando el llamador lo pide, y elevarlo aquí sería
        conceder un permiso que nadie otorgó.
        """
        queryset = cls._search_display_name(operator, name)
        if domain is not None:
            queryset = queryset.filter(domain)
        return [(record.pk, record.display_name) for record in queryset[:limit]]


#: Los operadores de semántica negativa que :meth:`_search_display_name`
#: atiende — ≙ el ``Domain.NEGATIVE_OPERATORS`` que la fuente consulta
#: (``odoo19c: odoo/orm/models.py:1462``). Es la tercera copia del mismo
#: conjunto en este árbol; unificar las tres en un hogar compartido es la
#: tarea **#380**, que ``orm/fields.py`` ya declara para las suyas.
NEGATIVE_DISPLAY_NAME_OPERATORS = frozenset([
    'not like', 'not ilike', 'not =like', 'not =ilike', '!=', '<>',
])

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
from orm.fields_properties import Properties
from orm.utils import parse_field_expr

_logger = logging.getLogger(__name__)


def _acting_user(user):
    """El usuario que actúa — ``self.env.user`` de la referencia."""
    return get_current_user() if user is None else user


def _rule_access_error(operation, forbidden):
    """El error del rechazo POR REGLA — sustituto acotado de ``_make_access_error``.

    ``ir_rule.py`` declara desde su porte que el ``_make_access_error`` de la
    fuente (68 líneas: compone el mensaje leyendo ``ir.model.data`` y la capa de
    vistas para sugerir a quién pedir acceso) **no se porta**, y sólo se porta
    ``_get_failing``, que responde *qué* filas fallan.

    El resolvedor compuesto necesita **una** fábrica de excepción para esa
    mitad, así que aquí hay la mínima que dice la verdad: qué operación, sobre
    qué modelo, y cuántas filas. El mensaje rico sigue sin portarse — tarea
    **#97**; lo que NO se hace es dejar la mitad de reglas sin error y que un
    rechazo por fila se lea igual que un permiso concedido.
    """
    return AccessError(
        f'Las reglas de registro no permiten «{operation}» sobre '
        f'{forbidden.count()} registro(s) de {forbidden.model._meta.label}.')


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
        forbidden = Rule.get_failing(
            self, mode=operation, group_ids=group_ids,
            eval_context=Rule.eval_context(user=actor))
        if forbidden.exists():
            return forbidden, functools.partial(
                _rule_access_error, operation, forbidden)
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

        La fuente compone un mensaje rico que nombra el campo, la descripción
        del modelo y los grupos permitidos, y para el último tramo consulta
        ``ir.model`` y ``res.groups``. Aquí se emiten las tres primeras piezas
        —campo, modelo, operación—; el tramo de grupos permitidos depende de
        ``_make_access_error``, que es la tarea **#97**, y hasta entonces el
        error dice qué se denegó sin decir a quién sí se permitiría.
        """
        if self._has_field_access(field, operation):
            return

        _logger.info(
            'Access Denied by ACLs for operation: %s, uid: %s, model: %s, field: %s',
            operation, get_current_uid(), self._meta.label, field.name)

        raise AccessError(
            f'No tiene permisos suficientes para acceder al campo '
            f'"{field.name}" en {self._meta.verbose_name} '
            f'({self._meta.label}). Contacte a su administrador.'
            f'\n\nOperación: {operation}'
        )

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


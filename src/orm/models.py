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
import functools
import logging

from django.apps import apps
from django.db.models import *          # noqa: F401,F403  (re-export ORM completo)
from django.db.models import (  # noqa: F401
    ForeignKey, Manager, Model, QuerySet,
)

from exceptions import AccessError
from orm.environments import get_current_uid, get_current_user, is_su
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


#: Manager que expone las cuatro formas. Un modelo las adopta con
#: ``objects = AccessManager()``; ``RuleScopedManager`` hereda de él, así que
#: los modelos que ya declaran ``scoped`` las tienen sin cambiar nada.
AccessManager = Manager.from_queryset(AccessQuerySet)


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

    Qué modelos lo adoptan, y en qué orden, es el mismo trabajo abierto que la
    adopción de ``AccessManager``.
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

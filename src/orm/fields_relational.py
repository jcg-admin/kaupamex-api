"""Campos relacionales — fiel a ``odoo/orm/fields_relational.py`` (Odoo 19).

``Many2one`` = ``ForeignKey``; ``Many2many`` = ``ManyToManyField``;
``One2many``
es el reverso de un FK en Django (``related_name``), sin clase propia.

``store=False`` — el Many2one sin columna
==========================================

La referencia declara relaciones **calculadas y no almacenadas**::

    properties_base_definition_id = fields.Many2one(
        "properties.base.definition",
        compute="_compute_properties_base_definition_id",
        search="_search_properties_base_definition_id",
    )

(``odoo19c:
odoo/addons/base/models/properties_base_definition_mixin.py:21-25``)
— un ``compute`` sin ``store`` **no tiene columna**: el valor se resuelve al
leerlo. Django no lo tiene: todo ``ForeignKey`` es una columna.

Por eso ``Many2one`` deja de ser un alias pelado y pasa a ser una **fachada**,
el mismo patrón que ya tienen ``Char`` (``orm/fields_textual.py``) y ``Float``
(``orm/fields_numeric.py``). El sitio de declaración queda **idéntico al de la
fuente**, que es el punto — la alternativa era colgar una ``property`` fuera de
la clase y repartir en el cableado lo que la referencia declara en el cuerpo.

**La fachada ya no elige clase, y ésa es la corrección de TASK-API-0417.**
Hasta
``api@2437373d`` devolvía un ``ForeignKey`` o un campo sin columna según el
valor de
``store``, que es exactamente lo que la fuente NO hace: ahí ``store`` es un
atributo del campo y nunca un tipo distinto
(``odoo19c: odoo/orm/fields.py:455``, dentro del bloque ``_get_attrs`` de
``:443-465``). Hoy la fachada construye **siempre** el tipo de Django y se
limita a tres cosas — derivar lo que ``compute=``/``related=`` implican
(:func:`~orm.fields_nonstored.apply_source_defaults`), reenviar el vocabulario
de la fuente al constructor, y anotar el resultado. La forma sin columna la
resuelve la **costura** (``orm/fields.py``): ``_field_contribute_to_class``
llama a ``contribute_to_class`` con ``private_only=True``, así que el campo no
entra en ``_meta.concrete_fields``, no genera migración y no tiene columna.

Lo que lo hizo posible: ``_field_init_with_copy`` recoge el vocabulario
declarado en ``_args__`` **antes** de delegar en Django, y retira de ``kwargs``
lo que el constructor de Django no admite. Medido en la sonda
``probe_vocabulary_reaches_args_by_type`` del workbench
``fachadas-construyen-una-vez-20260911T193801``: los **once** tipos que las
fachadas construyen recogen ``store`` y ``related``, incluidos ``ForeignKey`` y
``ManyToManyField``, que tienen ``__init__`` propio.

``join`` — el salto de un camino relacional
===========================================

``Many2one.join`` (``odoo19c: odoo/orm/fields_relational.py:466``) añade a una
consulta el LEFT JOIN que sigue este campo y devuelve el par
``(comodelo, alias)``. Lo consume ``BaseModel._traverse_related_sql``, que
recorre un campo delegado salto a salto.

Se adjunta a ``models.ForeignKey`` —la clase que ``Many2one`` devuelve— por la
misma razón de forma que ``orm/fields.py`` declara para ``to_sql``: la clase es
de Django y no es nuestra para declararla. Medido antes de adjuntar: ``join``
da ``False`` en ``hasattr(models.ForeignKey, 'join')``.

``Many2many`` **no lleva** ``company_dependent``: ``many2many`` no está en la
lista cerrada de tipos que la fuente admite
(``odoo19c: odoo/orm/fields.py:42-44``) — un ``jsonb`` guarda un valor por
empresa, no una tabla intermedia. Su rama sigue siendo un ``ValueError``.

Su ``store=False`` **dejó de ser una rama** con la retirada del enrutado: la
fachada acepta la palabra clave, la deriva igual que las otras ocho y construye
el ``ManyToManyField`` de siempre. Lo que **no** está medido es qué hace la
costura con un muchos-a-muchos bajo ``private_only``: su tabla intermedia no es
una columna del modelo, así que el mecanismo que vacía la columna de un escalar
no tiene contraparte obvia aquí. No se afirma que funcione ni que falle —
**DESCONOCIDO declarado**, y su condición de cierre es que exista un consumidor
que medir: hoy ``grep -rn "Many2many(" `` sobre ``odoo19c:`` no arroja ninguna
declaración ``store=False`` con ``compute`` sin almacenar en la familia
``base``. Sucesor: **TASK-API-0418**, que retira el descriptor sin columna como
clase y es
donde el eje ``store`` queda medido tipo por tipo.

.. note:: **Corregido.** Esta línea decía *"``Many2many`` **no** lleva el
   despachador"*, y hoy sí lo lleva: es una función, no el alias pelado
   ``Many2many = models.ManyToManyField``. Lo que sigue siendo cierto es la
   razón que el párrafo daba — ninguna de esas **dos** ramas aplica—; lo que
   cambió es que apareció una tercera palabra clave que sí, ``check_company``,
   medida en **19** declaraciones de la referencia dentro de los addons que
   este árbol ya tiene.

``company_dependent`` — el destino que cambia con la empresa (tarea #129)
=========================================================================

``Many2one`` sí lo lleva, y es el tipo que más lo usa en la referencia: **35**
de las 54 declaraciones de producto. Ver la rama en :func:`Many2one`.
"""
import collections.abc
import functools
import itertools

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models.fields.related import (RelatedField,
                                             lazy_related_operation)

from orm.commands import Command, apply_one2many_commands, is_command_list
from orm.environments import env as get_environment
from orm.fields_company_dependent import CompanyDependent
from orm.fields_nonstored import (
    _UNSET,
    annotate_related,
    apply_source_defaults,
    derive_source_attrs,
)
from exceptions import MissingError
from orm.identifiers import NewId
from orm.model_classes import is_transient
from orm.registry import (IR_MODELS, field_inverses, model_by_key, model_by_name,
                          name_of, sentinel_label)
from orm.utils import (display_name_of, model_field_registry, model_of,
                       record_ids)
from tools.misc import SENTINEL, OrderedSet, unique
from tools.sql import SQL

__all__ = ['Many2one', 'One2many', 'Many2many', 'bypass_search_access',
           'PrefetchMany2one', 'PrefetchX2many']


class One2many:
    """El conjunto de registros del comodelo cuyo inverso apunta a este — ≙ ``:843``.

    La fuente lo define en una linea: *"the recordset of all the records in
    ``comodel_name`` such that the field ``inverse_name`` is equal to the
    current record"*. Django tiene ese conjunto —es el reverso de la FK, el
    ``related_name`` del hijo— pero **no tiene donde declararlo en el padre**,
    y ese es exactamente el hueco que esta clase cierra.

    Hasta ``api@596cd2b`` este nombre valia ``None`` y estaba en el ``__all__``
    publico: ``fields.One2many(...)`` daba ``TypeError: 'NoneType' object is
    not callable``. La razon escrita —*"es el reverso de un FK en Django, sin
    clase propia"*— describia el **mecanismo de lectura**, que es correcto, y
    callaba el **sitio de declaracion**, que no lo es::

        # la fuente, en el padre                    (odoo19c: res_partner.py)
        child_ids = fields.One2many('res.partner.category', 'parent_id')

        # Django, en el hijo                        (otro archivo, otra clase)
        parent = models.ForeignKey(..., related_name='child_ids')

    Al portar un modelo padre sus ``One2many`` desaparecian de su cuerpo. Es
    el defecto de forma de :ref:`h-api-350` y del ``store=False``
    (:ref:`h-api-361`): todos los simbolos presentes, la forma cambiada — y el
    conteo, que es lo unico que el gate mide, no lo ve.

    **No reimplementa la lectura: la reusa.** El valor sale del manager que
    Django ya construyo, asi que ``.add()``, ``.create()`` y el resto del
    protocolo del reverso siguen siendo los suyos. Lo que esta clase aporta es
    el sitio de declaracion, ``copy=False`` y el rechazo por nombre.

    Poblacion que lo consume: **730** declaraciones en ``odoo19c``, **37** solo
    en ``base``. No hay que esperar al consumidor real — ya existe y esta
    contado.

    **No persiste.** Sigue el protocolo de ``contribute_to_class`` sin
    registrarse en ``_meta``, igual que la forma sin columna que la costura
    resuelve con ``private_only``: la columna es la FK del hijo, que ya existe. Un ``One2many`` en ``_meta``
    generaria migracion para una columna que nadie tiene.

    Cobertura del porte — 13 simbolos en la fuente
    ==============================================

    ``porte-completo-no-parcial.md`` exige declarar **cuantos, cuales y por
    que** cuando un porte no cierra todos los simbolos. Medido por AST contra
    ``odoo19c: odoo/orm/fields_relational.py:843``:

    ======================================= ===================================
    Simbolo de la fuente                    Desenlace
    ======================================= ===================================
    ``__init__``                            **portado**, con los cuatro
                                            parametros que su docstring
                                            documenta
    ``__get__``                             **portado** — reusa el manager del
                                            reverso de Django
    ``_additional_domain``                  **portado**; su rama polimorfica es
                                            DESCONOCIDO con condicion de
                                            cierre, tarea **#240**
    ``get_comodel_domain``                  **portado** en su composicion; el
                                            tipo de retorno esta bloqueado y
                                            medido, tarea **#241**
    ``_description_relation_field``         **portado** (aqui es ``property``,
                                            alli ``property(attrgetter(...))``)
    ``setup_nonrelated`` · ``update_db``    conducta **portada** en
                                            ``_inverse_field``, con el mensaje
                                            verbatim — pero **perezosa** donde
                                            la fuente es eager. El eje eager es
                                            la tarea **#242**
    ``write_real`` · ``write_new``          su rama ``CLEAR``/``SET`` esta
                                            **portada** en ``__set__``, con la
                                            decision de ``ondelete``. Los otros
                                            cinco comandos no pasan por el
                                            campo: ``Command`` aqui es
                                            ejecutivo (:ref:`h-api-589`, tarea
                                            **TASK-API-0190**)
    ``read``                                **divergencia de mecanismo** — la
                                            fuente llena su cache por lote; aqui
                                            la lectura es el manager del
                                            reverso, y el lote lo da
                                            ``prefetch_related``
    ``setup_inverses``                      **divergencia de mecanismo** — el
                                            mapa existe y lo mantiene Django en
                                            ``remote_field``; la fuente tiene
                                            que construirlo porque su ORM no lo
                                            guarda. Aqui lo deriva
                                            ``registry._TriggerRegistry``.
                                            Cerrado con la capa B de #273
                                            (:ref:`h-api-1032`); era
                                            DESCONOCIDO por *"este arbol no
                                            tiene cache de campos"*, y esa
                                            causa la retiro la capa A
    ``_condition_to_sql_relational``        **trabajo**, no divergencia: el lado
    ``_get_query_for_condition_value``      SQL del campo. Tarea **#243**
    ``_internal_description_domain_raw``    **trabajo**, detras de #241 porque
                                            necesita el tipo ``Domain``
    ======================================= ===================================

    Siete simbolos son propios y no tienen contraparte por nombre:
    ``__set_name__`` y ``contribute_to_class`` son el protocolo de nombre de
    Django; ``_inverse_field``, ``_deletes_the_leftover`` y ``__set__`` son el
    cuerpo de lo que la fuente resuelve dentro de ``setup_nonrelated`` y
    ``write_real``; ``__repr__`` es el que la fuente hereda de ``Field``.
    """

    #: ≙ ``type = 'one2many'`` (``odoo19c: :866``).
    type = 'one2many'

    def __init__(self, comodel_name=None, inverse_name=None, *, copy=False,
                 string=None, domain=None, context=None,
                 bypass_search_access=False, related=None, related_sudo=True,
                 compute=None, inverse=None, store=None, readonly=None,
                 compute_sudo=None, **_ignored):
        #: Se acepta con nombre para que **no** caiga en ``**_ignored``, que es
        #: como se tragaba antes: la declaración se escribía igual que la de la
        #: fuente (``fields.One2many(related='employee_id.subordinate_ids')``),
        #: pasaba sin error, y no hacía nada. Un parámetro tragado es peor que
        #: uno ausente, que es lo que el comentario de ``domain``/``context``
        #: de este mismo constructor ya decía.
        #:
        #: **Aquí NO se llama a ``apply_source_defaults``**, y es la única de
        #: las nueve fachadas donde no se llama: ``One2many`` no construye un
        #: ``models.Field``, así que no hay constructor de Django al que
        #: reenviar el vocabulario ni ``_args__`` que lo recoja. Su extremo de
        #: cadena es el manager del reverso, que no necesita comodelo ni
        #: inverso declarados — es lo que la referencia declara, sin ellos.
        self.related = related
        #: ≙ ``compute``/``inverse`` del campo (``odoo19c:
        #: odoo/orm/fields.py``): un One2many calculado no se lee por su
        #: inverso sino por su método, y su escritura la propaga ``inverse``.
        #: Se aceptaban en ``**_ignored``.
        self.compute = compute
        self.inverse = inverse
        #: ≙ ``related_sudo`` (``odoo19c: odoo/orm/fields.py``, defecto
        #: ``True``): un ``related`` sin ``sudo`` busca con la regla de cada
        #: comodelo intermedio (``any``), uno con ``sudo`` la salta (``any!``).
        self.related_sudo = bool(related_sudo)
        self.comodel_name = comodel_name
        self.inverse_name = inverse_name
        #: Los tres que la fuente documenta en su docstring (``:852-860``) y
        #: que este porte tragaba en ``**_ignored``. Un parametro tragado es
        #: peor que uno ausente: la llamada se escribe igual que la de la
        #: fuente, pasa sin error, y no hace nada.
        self.domain = domain
        self.context = context or {}
        #: *"whether access rights are bypassed on the comodel (default:
        #: ``False``)"* — ``:859-860``. El default abierto seria un hueco de
        #: permiso; lo consume ``domains._optimize_any_with_rights``.
        self.bypass_search_access = bool(bypass_search_access)
        #: ≙ ``copy: bool = False`` con su comentario verbatim: *"o2m are not
        #: copied by default"* (``:867``). Lo mira ``BaseModel.copy`` para
        #: decidir si arrastra los hijos; el default contrario duplicaria un
        #: arbol entero al copiar su raiz.
        self.copy = bool(copy)
        #: ``store``, ``readonly`` y ``compute_sudo`` con los defectos de clase
        #: de la fuente (``odoo19c: odoo/orm/fields.py``, ``Field``) y la
        #: derivación de ``compute``/``related`` (``:443-465``) por la única
        #: copia que existe, :func:`derive_source_attrs`. Sin constructor de
        #: Django no hay ``apply_source_defaults``, pero los cuatro valores que
        #: un ``related`` implica siguen siendo del campo.
        declared = {'related': related, 'compute': compute,
                    'inverse': inverse, 'related_sudo': related_sudo,
                    'store': store, 'readonly': readonly,
                    'compute_sudo': compute_sudo}
        attrs = {key: value for key, value in declared.items()
                 if value is not None}
        if copy:
            #: El defecto ``False`` no es una declaración; ``True`` sí.
            attrs['copy'] = True
        derive_source_attrs(attrs)
        self.store = attrs.get('store', True)
        self.readonly = attrs.get('readonly', False)
        self.compute_sudo = attrs.get('compute_sudo', True)
        self.copy = bool(attrs.get('copy', copy))
        self.string = string
        self.name = None

    #: Un One2many es relacional: una ruta ``campo.subcampo`` lo atraviesa.
    is_relation = True
    #: ≙ ``_Relational`` de la fuente: lo leen los optimizadores de ``any``.
    relational = True
    one_to_many = True
    many_to_many = False

    @property
    def related_model(self):
        """El comodelo — el declarado o, en un ``related``, el del último
        eslabón de la ruta (≙ ``comodel_name`` que ``setup_related`` copia
        del destino, ``odoo19c: odoo/orm/fields.py:643-647``)."""
        if self.comodel_name:
            return model_by_key(self.comodel_name) or apps.get_model(
                self.comodel_name)
        current = apps.get_model(self.model_name)
        for part in (self.related or '').split('.'):
            current = model_field_registry(current)[part].related_model
        return current

    @property
    def _description_relation_field(self):
        """La columna del hijo por la que cuelga el conjunto — ≙ ``:901``::

            _description_relation_field = property(attrgetter('inverse_name'))

        Es lo que el cliente lee en la descripcion del campo para saber por
        donde esta enlazado.
        """
        return self.inverse_name

    def _additional_domain(self, env=None):
        """El predicado extra del inverso polimorfico — ≙ ``:913-919``.

        La fuente devuelve ``Domain(inverse_field.model_field, '=',
        self.model_name)`` cuando el inverso es un ``many2one_reference``: un
        FK polimorfico guarda modelo e id en dos columnas, y sin acotar el
        modelo el conjunto traeria las filas de todos los demas.

        **DESCONOCIDO declarado, con su condicion de cierre.** Desde
        TASK-API-0485 ``Many2oneReference`` es la clase de la fuente y expone
        ``model_field``, pero ningun addon portado declara todavia un inverso
        polimorfico contra el que medir esta rama. La rama se cierra
        cuando exista el primero que medir — tarea **#240**. Hasta entonces
        devuelve el predicado vacio, que es lo que la fuente devuelve para los
        otros dos tipos de inverso (``Domain.TRUE``).
        """
        return []

    def get_comodel_domain(self, model=None):
        """El dominio declarado, mas el del inverso — ≙ ``:918-919``.

        La fuente compone ``super().get_comodel_domain(model) &
        self._additional_domain(model.env)`` y devuelve un ``Domain``.

        **El tipo de retorno esta BLOQUEADO por ``orm.domains.Domain``, y el
        bloqueo esta medido dos veces.** ``from orm.domains import Domain`` en
        la cabecera de este archivo no arranca, por dos causas independientes
        que se apilan:

        1. **Ciclo.** ``orm/domains.py:102`` importa ``orm.fields``, y
           ``orm/fields.py:77`` importa este archivo de vuelta. Medido en las
           dos direcciones, que es lo que ``no-lazy-imports.md`` excepcion #3
           exige antes de aceptar nada que no sea un refactor::

               ImportError: cannot import name 'Many2many' from partially
               initialized module 'orm.fields_relational'

        2. **Registro de apps.** Aun rompiendo el ciclo por orden, ``fields.py``
           arrastra ``fields_reference`` -> ``contenttypes`` -> ``ContentType``,
           y este archivo se carga desde ``inherits.py`` **durante**
           ``apps.populate``::

               django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet.

        La referencia no tiene ninguno de los dos: su ``odoo/orm/domains.py``
        importa ``.identifiers`` y ``.utils``, y **no** el modulo de campos
        (medido sobre sus 19 imports). La arista de vuelta la pone nuestro
        ``orm/fields.py`` al cargar el papel de fachada que la referencia
        declara en ``odoo/fields.py``.

        **No se resuelve aqui, y no por conveniencia:** retirar
        ``orm/fields.py:77`` tiene dos consumidores medidos —``__all__``, del
        que ``ir_model.FIELD_TYPES`` se deriva (``ir_model.py:213,239``), y
        ``tests/unit/orm/test_fields_facade.py:61``, que ejercita
        ``from orm.fields import *``— asi que cambia el vocabulario de
        ``IrModelFields.ttype``. Separar definidor de fachada es el alcance
        declarado de la tarea **#211**; el cambio de tipo de retorno de este
        metodo es la tarea **#241**, que la sucede.

        Lo que SI esta portado es la **composicion**, que es el contenido del
        metodo: el dominio declarado en el campo mas el del inverso.
        """
        domain = self.domain
        if callable(domain):
            # el callable puede devolver una lista, un Domain o una cadena
            domain = domain(model)
        if not domain or isinstance(domain, str):
            # una cadena sólo vale para el cliente (``fields.py:99-109``)
            declarado = []
        else:
            declarado = list(domain)
        return declarado + list(self._additional_domain())

    # -- protocolo de nombre ------------------------------------------------

    def __set_name__(self, owner, name):
        """Camino del cuerpo de clase en una clase que NO es modelo Django."""
        self.name = name

    def contribute_to_class(self, cls, name, **_kwargs):
        """Camino de ``ModelBase`` y de ``add_to_class`` — sin tocar ``_meta``."""
        self.name = name
        self.model_name = cls._meta.label
        setattr(cls, name, self)

    # -- protocolo de descriptor -------------------------------------------

    def _inverse_field(self):
        """El ``Many2one`` del comodelo que este campo invierte.

        Rechaza el inverso inexistente **por nombre**, con el mensaje de
        ``setup_nonrelated`` (``odoo19c: :889``)::

            raise ValueError(f"{self.inverse_name!r} declared in {self!r} "
                             f"does not exist on {comodel._name!r}.")

        Un ``FieldDoesNotExist`` pelado de Django no dice cual de los dos
        nombres esta mal: si el del comodelo o el del inverso.
        """
        # El comodelo viene escrito como en la fuente (``'test_orm.message'``)
        # o como label de Django; ``model_by_key`` resuelve los dos.
        comodel = model_by_key(self.comodel_name) or apps.get_model(
            self.comodel_name)
        try:
            return comodel, comodel._meta.get_field(self.inverse_name)
        except FieldDoesNotExist:
            raise ValueError(
                f'{self.inverse_name!r} declared in {self!r} does not exist '
                f'on {self.comodel_name!r}.') from None

    def _computed_key(self):
        return f'_computed_one2many_{self.name}'

    def _comodel(self):
        return model_by_key(self.comodel_name) or apps.get_model(
            self.comodel_name)

    def _get_computed(self, instance):
        """El valor de un One2many calculado: el del almacén de la fila, o el
        que deja su método — ≙ ``Field.__get__`` → ``compute_value`` de un
        campo no almacenado."""
        key = self._computed_key()
        if key not in instance.__dict__:
            instance.__dict__['_computing_one2many'] = True
            try:
                getattr(instance, self.compute)()
            finally:
                instance.__dict__.pop('_computing_one2many', None)
        value = instance.__dict__.get(key)
        if value is None:
            value = self._comodel()._from_ids(get_environment(), (), ())
        return value

    def _set_computed(self, instance, value):
        """Escribir un One2many calculado — ≙ ``write`` sobre un campo con
        ``inverse``: los comandos se aplican al valor actual, que queda en el
        almacén de la fila, y ``inverse`` lo propaga."""
        comodel = self._comodel()
        if instance.__dict__.get('_computing_one2many'):
            instance.__dict__[self._computed_key()] = value
            return
        current = list(self._get_computed(instance).ids)
        if is_command_list(value):
            for code, target, payload in value:
                if code == Command.CREATE:
                    current.append(comodel.create(payload).id)
                elif code == Command.UPDATE:
                    comodel.browse([target]).write(payload)
                elif code in (Command.DELETE, Command.UNLINK):
                    current = [i for i in current if i != target]
                    if code == Command.DELETE:
                        comodel.browse([target]).unlink()
                elif code == Command.LINK:
                    current.append(target)
                elif code == Command.CLEAR:
                    current = []
                elif code == Command.SET:
                    current = [getattr(i, 'id', i) for i in payload]
        else:
            current = list(getattr(value, '_ids', None)
                           or [getattr(i, 'pk', i) for i in (value or ())])
        ids = tuple(dict.fromkeys(current))
        instance.__dict__[self._computed_key()] = comodel._from_ids(
            get_environment(), ids, ids)
        if self.inverse:
            getattr(instance, self.inverse)()

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        if self.compute:
            return self._get_computed(instance)
        if self.related:
            return self._get_related(instance)
        comodel, inverse = self._inverse_field()
        if getattr(inverse, 'store', True) is False:
            # ≙ ``Field.to_sql`` (``odoo19c: odoo/orm/fields.py:1215-1216``):
            # el One2many se lee filtrando por su inverso, y un inverso sin
            # columna no tiene SQL que emitir.
            raise ValueError(
                f'Cannot convert {inverse} to SQL because it is not stored')
        if _reads_as_recordset(instance, comodel):
            return _read_one2many(self, instance, comodel)
        accessor = inverse.remote_field.get_accessor_name()
        if accessor is not None and hasattr(instance, accessor):
            # El manager del reverso: trae ademas la escritura (``add``,
            # ``create`` con el padre ya puesto), que un ``filter`` no da.
            return getattr(instance, accessor)
        # El inverso apunta a otro modelo, o su reverso esta suprimido con
        # ``related_name='+'``. Queda la definicion literal de la fuente.
        return comodel._default_manager.filter(**{self.inverse_name: instance})

    def _get_related(self, instance):
        """El valor de un ``related=`` — ≙ ``Field._compute_related``
        (``odoo19c: odoo/orm/fields.py``): se recorre la ruta desde el
        registro y el valor es el del último eslabón; un eslabón vacío da el
        conjunto vacío del comodelo.

        Divergencia de forma: un comodelo que no es ``BaseModel`` devuelve su
        ``QuerySet`` (el gestor del reverso, materializado con ``all()``),
        que es como este árbol representa un conjunto de esas filas.
        """
        *path, last = self.related.split('.')
        model, value = type(instance), instance
        for part in path:
            model = model._meta.get_field(part).related_model
            value = getattr(value, part) if value else None
        comodel = model._meta.get_field(last).related_model
        if not value:
            if isinstance(comodel, type) and hasattr(comodel, '_from_ids'):
                return comodel._from_ids(get_environment(), (), ())
            return comodel._default_manager.none()
        value = getattr(value, last)
        return value.all() if hasattr(value, 'get_queryset') else value

    def _deletes_the_leftover(self, inverse):
        """Que hacer con el hijo que se queda fuera — ≙ ``write_real:975-979``.

        La fuente lo decide por el ``ondelete`` del inverso, no por la
        nulabilidad de la columna::

            if getattr(comodel._fields[inverse], 'ondelete', False) == 'cascade':
                to_delete.extend(lines._ids)
            else:
                lines[inverse] = False

        Django decide por otra cosa: su ``RelatedManager.set()`` existe **si la
        FK admite nulo**, y entonces anula. Sobre una FK ``null=True`` con
        ``on_delete=CASCADE`` las dos politicas discrepan, y el porte impone la
        de la fuente.
        """
        return getattr(inverse.remote_field, 'on_delete', None) is models.CASCADE

    def __set__(self, instance, value):
        """Asignar el conjunto — ≙ el tramo ``CLEAR``/``SET`` de ``write_real``.

        La fuente los trata juntos (``command[0] in (Command.CLEAR,
        Command.SET)``, ``:1027``): el conjunto queda **exactamente** en las
        lineas dadas, y las que sobran pasan por ``unlink``. ``CLEAR`` es el
        mismo camino con la lista vacia.

        Una lista de triples de ``Command`` la interpreta
        :func:`~orm.commands.apply_one2many_commands` sobre el ``Many2one``
        inverso (:ref:`h-api-1132`).
        """
        if self.compute:
            self._set_computed(instance, value)
            return
        if self.related:
            self._set_related(instance, value)
            return
        comodel, inverse = self._inverse_field()
        if is_command_list(value):
            # Los siete comandos de la fuente — ≙ ``One2many.write_real``
            # (``odoo19c: odoo/orm/fields_relational.py:969``).
            apply_one2many_commands(instance, inverse.remote_field, value)
            return
        nuevos = list(value or ())
        vivos = [obj.pk for obj in nuevos if obj.pk is not None]
        sobrantes = (comodel._default_manager
                     .filter(**{self.inverse_name: instance})
                     .exclude(pk__in=vivos))
        if self._deletes_the_leftover(inverse):
            sobrantes.delete()
        else:
            sobrantes.update(**{inverse.attname: None})
        for obj in nuevos:
            setattr(obj, self.inverse_name, instance)
            obj.save(update_fields=[inverse.attname])

    def __repr__(self):
        return (f'One2many({self.comodel_name!r}, {self.inverse_name!r})')

    def _set_related(self, instance, value):
        """Escribir un ``related`` — ≙ ``Field._inverse_related``
        (``odoo19c: odoo/orm/fields.py:724-733``): el valor va al último
        eslabón de la cadena, que es quien lo guarda.

        Sólo con ``readonly=False``: la fuente no le cablea inverso a un
        related de sólo lectura (``:632``), así que la escritura no viaja.

        La guarda ``bool(target.id) == bool(record.id)`` es verbatim (``:732``,
        *«update 'target' only if 'record' and 'target' are both real or both
        new»*). Divergencia de mecanismo: si el extremo es el manager del
        reverso de una FK, Django prohíbe asignarlo y nombra la salida en su
        propio error, ``.set()``; si es otro ``One2many`` de este árbol, su
        propio ``__set__`` decide.
        """
        if self.readonly:
            return
        *path, last = self.related.split('.')
        target = instance
        for part in path:
            target = getattr(target, part, None) if target else None
        if not target or bool(target.pk) != bool(instance.pk):
            return
        if isinstance(getattr(type(target), last, None), One2many):
            setattr(target, last, value)
            return
        getattr(target, last).set(list(value or ()))


#: El permiso del comodelo no se aplica al atravesar este campo — ≙
#: ``_Relational.bypass_search_access`` (``odoo19c:
#: odoo/orm/fields_relational.py:39``), con su comentario verbatim: *"whether
#: access rights are bypassed on the comodel"*.
#:
#: Lo consume ``domains._optimize_any_with_rights``: un ``any`` sobre un campo
#: que lo declara se reescribe a ``any!``, la forma que salta el permiso, y de
#: ahí cuelga el resto de la cadena —
#: ``_optimize_m2o_bypass_comodel_id_lookup`` sólo actúa sobre los que
#: llevan ``!``.
#:
#: **Se declara sobre las clases de campo de Django y no se consulta con un
#: ``getattr`` de respaldo.** Es la misma decisión que la fuente toma al
#: ponerlo en ``_Relational`` y no en ``Field``: un campo escalar **no** lo
#: tiene, y preguntárselo tiene que ser un error y no un ``False`` silencioso.
#: Un respaldo haría indistinguible *"este campo no lo concede"* de *"a este
#: campo la pregunta no le aplica"*.
#:
#: Va sobre la clase porque **759** declaraciones del árbol lo necesitarían:
#: 690 pasan por la fábrica ``fields.Many2one`` y 69 son ``models.ForeignKey``
#: directas (medido con ``grep -rhoP`` sobre ``src/`` y ``addons/``). Marcarlo
#: sólo en la fábrica dejaría a esas 69 sin el atributo, que es justo el
#: agujero que el párrafo anterior prohíbe. Es un atributo **nuevo**: no
#: sobreescribe nada de Django, así que no puede alterar su comportamiento.
models.ForeignKey.bypass_search_access = False
models.ManyToManyField.bypass_search_access = False


def bypass_search_access(field, flag=True):
    """Declara que el permiso del comodelo no aplica al atravesar ``field``.

    La fuente lo recibe como palabra clave del constructor; aquí se cuelga del
    campo ya construido por la misma razón de forma que ``check_company``: la
    clase del campo es de Django y su constructor no conoce la palabra.

    Es público —sin guion bajo— porque lo llama ``orm.inherits``, que está
    fuera de este módulo: la delegación lo implica (``:257-259`` de la fuente,
    con su comentario *"self.delegate implies self.bypass_search_access"*).
    """
    field.bypass_search_access = bool(flag)
    return field


def _mark_check_company(field, check_company):
    """Marca el campo para que ``BaseModel._check_company`` lo mire.

    ≙ ``_Relational.check_company`` (``odoo19c:
    odoo/orm/fields_relational.py:40``), que allá es un atributo de clase con
    ``False`` por defecto y aquí es un atributo de instancia por la misma
    razón de forma que ``join``: la clase del campo es de Django y no es
    nuestra para declararla.

    El valor **no** llega al constructor de Django — ``ForeignKey`` no lo
    conoce y reventaría—; se cuelga del campo ya construido, que es donde
    ``_check_company`` lo lee al recorrer ``_meta.get_fields()``.
    """
    field.check_company = bool(check_company)
    return field


#: Los posicionales de ``Many2many`` en la fuente, tras el comodelo —
#: ``odoo19c: odoo/orm/fields_relational.py`` (``Many2many.__init__``):
#: ``(comodel_name, relation, column1, column2, string)``.
_MANY2MANY_SOURCE_POSITIONAL = ('relation', 'column1', 'column2', 'string')

#: ``(apps, relation) -> Many2manyField`` — el extremo que materializa la
#: tabla. Se indexa por el registro de aplicaciones porque el estado de una
#: migración construye sus propias clases con los mismos campos.
_RELATION_OWNERS = {}


def _model_keys(model):
    """Los nombres por los que se reconoce un modelo: ``_name`` y etiqueta."""
    return {name_of(model), model._meta.label_lower} - {None}


def _target_key(field):
    """El destino declarado: el ``_name`` de la fuente si lo hay.

    Mientras el destino no existe, ``remote_field.model`` es una etiqueta
    centinela (:func:`_deferred_comodel`); ``comodel_name`` conserva el nombre
    que el autor escribió.
    """
    declared = getattr(field, 'comodel_name', None)
    if declared:
        return declared
    model = field.remote_field.model
    return model.lower() if isinstance(model, str) else model._meta.label_lower


class Many2manyField(models.ManyToManyField):
    """``ManyToManyField`` con la tabla y las columnas que la fuente nombra.

    ≙ ``Many2many(comodel_name, relation, column1, column2)``: ``relation``
    es la tabla, ``column1`` la columna que apunta al modelo que declara el
    campo y ``column2`` la del comodelo. Django nombra él mismo la tabla y las
    columnas de la intermedia que genera; aquí ``relation`` se entrega como
    ``db_table`` y las dos columnas se fijan sobre esa intermedia en cuanto
    existe. ``deconstruct`` las conserva, así que el estado de una migración
    reconstruye la misma tabla.

    **Dos declaraciones, una relación.** En la fuente, dos ``Many2many`` con
    la misma ``relation``, los modelos cruzados y las columnas invertidas son
    los dos extremos de una sola tabla (``test_orm.category.discussions`` y
    ``test_orm.discussion.categories``). Django expresa eso con UN campo y su
    accesor inverso: el segundo extremo no crea tabla, y su nombre pasa a ser
    el ``related_name`` del primero.

    **Divergencias declaradas:** sin ``relation`` se conserva el nombrado de
    Django (las 87 declaraciones de un posicional del árbol ya están
    migradas así). Una tabla compartida por más de dos extremos
    (``test_orm_crew``) no se empareja y se rehúsa en los checks de Django.
    El segundo extremo exige que el primero no haya contribuido aún su
    inverso, que es el orden de declaración de la fuente.
    """

    def __init__(self, *args, relation=None, column1=None, column2=None,
                 **kwargs):
        if relation is not None:
            kwargs.setdefault('db_table', relation)
        self.relation = relation
        self.column1 = column1
        self.column2 = column2
        self.mirror_of = None
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        """Conserva ``column1``/``column2``: sin ellos la migración nombraría
        las columnas a la manera de Django."""
        name, path, args, kwargs = super().deconstruct()
        through = self.remote_field.through
        explicit = through is not None and not isinstance(through, str) and \
            not through._meta.auto_created
        if explicit or (self.column1 is None and self.column2 is None):
            # Con ``through`` explícito la tabla y las columnas son las del
            # modelo intermedio, y Django las reconstruye solo; ``db_table``
            # no puede acompañar a ``through``.
            if explicit:
                kwargs.pop('db_table', None)
            return name, path, args, kwargs
        kwargs['column1'] = self.column1
        kwargs['column2'] = self.column2
        return name, 'orm.fields_relational.Many2manyField', args, kwargs

    def _relation_key(self, cls, swapped=False):
        """La tabla y el par de columnas que identifican una relación.

        Una tabla puede servir a más de una relación (``test_orm_crew`` sirve a
        pirata↔barco y a prisionero↔barco), así que el par de columnas forma
        parte de la clave. ``swapped`` es la clave del otro extremo.
        """
        columns = ((self.column2, self.column1) if swapped
                   else (self.column1, self.column2))
        return (cls._meta.apps, self.relation, columns)

    def _explicit_through(self, cls):
        """El modelo declarado cuya tabla es ``relation``, si lo hay.

        En la fuente la tabla de un ``Many2many`` puede ser la de un modelo
        propio: ``test_orm.crew`` declara ``_table = 'test_orm_crew'`` con tres
        ``Many2one`` anulables, y ``ship.pirate_ids``/``prisoner_ids`` la usan
        con su par de columnas. En Django eso es un ``through`` explícito con
        ``through_fields``.
        """
        if self.relation is None:
            return None
        for models_of_app in cls._meta.apps.all_models.values():
            for model in models_of_app.values():
                if (model._meta.db_table == self.relation
                        and not model._meta.auto_created):
                    return model
        return None

    def _explicit_through_fields(self, through):
        """Los campos del ``through`` cuyas columnas son ``column1``/``column2``."""
        by_column = {field.column: field.name
                     for field in through._meta.local_fields
                     if isinstance(field, models.ForeignKey)}
        try:
            return by_column[self.column1], by_column[self.column2]
        except KeyError as missing:
            raise ValueError(
                f'{through._meta.label} no declara la columna {missing} que '
                f'pide la relación {self.relation!r}') from None

    def _owner_for_mirror(self, cls):
        if self.relation is None:
            return None
        owner = _RELATION_OWNERS.get(self._relation_key(cls, swapped=True))
        if owner is None or owner is self:
            return None
        crossed = (
            _target_key(owner) in _model_keys(cls)
            and _target_key(self) in _model_keys(owner.model)
            and (owner.column1, owner.column2) == (self.column2, self.column1))
        return owner if crossed else None

    def contribute_to_class(self, cls, name, *args, **kwargs):
        owner = self._owner_for_mirror(cls)
        if owner is not None:
            # El otro extremo de la misma tabla: su accesor inverso lleva este
            # nombre. Se instala cuando ``cls`` termine de registrarse.
            self.set_attributes_from_name(name)
            self.model = cls
            self.mirror_of = owner
            # ``deconstruct`` lee ``_related_name``; el accesor, ``remote_field``.
            owner.remote_field.related_name = name
            owner._related_name = name
            return
        explicit = self._explicit_through(cls)
        if explicit is not None:
            self.remote_field.through = explicit
            self.remote_field.through_fields = self._explicit_through_fields(
                explicit)
            self.db_table = None
        super().contribute_to_class(cls, name, *args, **kwargs)
        if self.relation is not None and not cls._meta.abstract:
            _RELATION_OWNERS[self._relation_key(cls)] = self
        through = self.remote_field.through
        if (self.column1 is not None and not isinstance(through, str)
                and through._meta.auto_created):
            self._name_through_columns(through, cls)

    def _name_through_columns(self, through, cls):
        """Fija ``column1``/``column2`` sobre la intermedia generada."""
        source, target = self._through_field_names(cls)
        for field_name, column in ((source, self.column1),
                                   (target, self.column2)):
            if column is None:
                continue
            field = through._meta.get_field(field_name)
            field.db_column = column
            field.set_attributes_from_name(field.name)

    def _through_field_names(self, cls):
        """Los nombres que ``create_many_to_many_intermediary_model`` usa."""
        target = self.remote_field.model
        target_name = (target.split('.')[-1] if isinstance(target, str)
                       else target._meta.model_name).lower()
        source_name = cls._meta.model_name
        if source_name == target_name:
            return 'from_%s' % source_name, 'to_%s' % target_name
        return source_name, target_name


def _source_many2many_kwargs(args, kwargs):
    """Nombra los posicionales de la fuente tras el comodelo.

    Antes llegaban a ``ManyToManyField(to, related_name, related_query_name,
    limit_choices_to)`` y la migración ``test_orm 0001`` guardó
    ``limit_choices_to='category'`` (H-API-1124).
    """
    if len(args) <= 1:
        return args, kwargs
    extra = args[1:]
    if len(extra) > len(_MANY2MANY_SOURCE_POSITIONAL):
        raise TypeError('Many2many() admite a lo sumo cinco posicionales')
    for name, value in zip(_MANY2MANY_SOURCE_POSITIONAL, extra):
        if name in kwargs:
            raise TypeError(f'Many2many() recibió {name!r} dos veces')
        kwargs[name] = value
    if 'string' in kwargs:
        kwargs.setdefault('verbose_name', kwargs.pop('string'))
    return args[:1], kwargs


def Many2many(*args, check_company=False, store=_UNSET, related=None,
              **kwargs):
    """``fields.Many2many`` — el ``ManyToManyField`` de Django, marcable.

    Era un alias pelado (``Many2many = models.ManyToManyField``) y pasa a ser
    despachador por un solo motivo medido: **19** declaraciones de la
    referencia en los addons que este árbol ya tiene la marcan
    ``check_company=True`` (contra 282 ``Many2one`` y 5 ``One2many``), y el
    alias no tenía dónde recibir la palabra clave.

    No lleva ``store=False`` ni ``company_dependent`` — ver el bloque del
    docstring del módulo, que mide por qué ninguno de los dos aplica aquí.
    """
    #: ``:452-458`` — igual que en ``Many2one``: la referencia declara
    #: ``fields.Many2many(related="lead_id.tag_ids", readonly=True)`` sin
    #: comodelo, porque el extremo de la cadena lo determina.
    if store is not _UNSET:
        kwargs['store'] = store
    #: ``compute=`` en un M2M — #313. El bloque de la fuente se aplica igual
    #: que en cualquier otro tipo; lo que cambia es el VOLCADO, no la
    #: declaración: ``orm.models._flush_m2m`` entrega el valor calculado al
    #: manager relacional en vez de asignarlo, porque Django prohíbe el
    #: ``setattr`` sobre el lado directo de un muchos-a-muchos.
    #:
    #: La bandera viaja hasta el bloque de ``precompute``: un M2M no se puede
    #: adelantar al ``INSERT`` —su tabla intermedia necesita el ``pk``—, así
    #: que ahí se apaga con aviso. ``many_to_many=True`` es lo que lo lleva al
    #: derivador, que es la única copia de los tres bloques de la fuente.
    related_attrs = apply_source_defaults(related, kwargs, many_to_many=True)
    #: El tipo se construye SIEMPRE: ``store`` es un atributo del campo, no una
    #: clase distinta (``odoo19c: odoo/orm/fields.py:455``). La forma sin
    #: columna la resuelve la costura —``contribute_to_class`` con
    #: ``private_only``— y no el enrutado de esta fachada.
    if related and not args and 'to' not in kwargs:
        #: Sin comodelo declarado, la forma de la referencia con ``related=``
        #: (``:643-647``): igual que ``Many2one``, se construye contra el
        #: propio modelo y ``_retarget_related_relation`` lo reapunta al
        #: extremo de la cadena al configurar el campo.
        args = ('self',)
    args, source_name = _translate_comodel(args)
    args, kwargs = _source_many2many_kwargs(args, kwargs)
    field_class = (Many2manyField if any(
        name in kwargs for name in ('relation', 'column1', 'column2'))
        else models.ManyToManyField)
    field = _mark_check_company(field_class(*args, **kwargs), check_company)
    if source_name is not None:
        field.comodel_name = source_name
    return annotate_related(field, related, related_attrs)


def _comodel_label(to):
    """La etiqueta ``app.Modelo`` del destino de una FK, venga como venga.

    ``registry.many2one_company_dependents`` indexa por ``_meta.label``, así
    que el comodelo hay que guardarlo con esa forma. Django admite el destino
    como cadena (``'base.ResPartner'``), como clase, o como
    ``'self'``; los tres se normalizan aquí para que el catálogo no tenga que
    saber cuál se usó en la declaración.

    ``'self'`` se conserva verbatim: en el momento de construir el campo la
    clase todavía no existe, y quien lo resuelve es la carga del modelo.
    """
    if to is None or isinstance(to, str):
        return to
    return to._meta.label


#: ≙ ``OnDelete`` (``odoo19c: odoo/orm/fields_relational.py:28``) — los tres
#: valores que la fuente admite, y su política en el vocabulario del stack.
#:
#: ``'restrict'`` va a ``models.RESTRICT`` y no a ``models.PROTECT``, y la
#: diferencia no es de estilo: ``RESTRICT`` emite el ``ON DELETE RESTRICT`` de
#: SQL —que es literalmente lo que la palabra de la fuente nombra— mientras que
#: ``PROTECT`` es una guarda de Django en el plano de Python. La fuente vive en
#: el catálogo de PostgreSQL (``:318`` compone su ``ON DELETE`` con este mismo
#: valor), así que la contraparte fiel es la del motor.
ON_DELETE_POLICY = {
    'cascade': models.CASCADE,
    'set null': models.SET_NULL,
    'restrict': models.RESTRICT,
}


def _apply_ondelete(args, kwargs):
    """Resuelve el ``ondelete`` de la fuente: su politica Y su atributo.

    ≙ ``Many2one.setup_nonrelated`` (``odoo19c: :268-295``), con sus tres casos
    portados verbatim:

    1. sin ``ondelete`` declarado → ``'restrict' if required else 'set null'``
       (``:282``);
    2. ``'set null'`` sobre un campo requerido → ``ValueError`` (``:283-288``);
    3. ``'restrict'`` hacia un modelo de :data:`~orm.fields.IR_MODELS` →
       ``ValueError`` (``:289-294``).

    **El MOMENTO diverge, y la divergencia es del stack.** La fuente resuelve en
    ``setup_nonrelated``, una fase de preparación que Django no tiene; su
    ``ForeignKey.__init__`` exige ``on_delete`` posicional, así que aquí la
    resolución ocurre al construir el campo. La política es la misma; lo que
    cambia es cuándo se aplica.

    **La rama de ``is_transient()`` NO se simula.** La fuente la consulta en
    ``:275`` —``if model.is_transient() and not comodel.is_transient()``— y
    necesita el MODELO, que en ``__init__`` todavía no existe: el campo aún no
    se ha asociado a ninguna clase. Un ``Many2one`` declarado en un modelo
    transitorio recibe por tanto el default de la rama no transitoria. Queda
    declarado aquí en vez de inventado, y su cierre es TASK-API-0405.

    Sin ``ondelete`` en ``kwargs`` la función es transparente: los 1868
    ``on_delete=`` del árbol pasan intactos.
    """
    required = not kwargs.get('null', False)
    if 'ondelete' not in kwargs:
        # La fuente resuelve la politica para TODO Many2one en
        # `setup_nonrelated` (`:274-282`), lo declare quien lo declare, y la
        # usa para componer el `ON DELETE` de la FK (`:306`). Asi que el
        # default se aplica tambien aqui — no solo el atributo.
        declared = 'restrict' if required else 'set null'
        if 'on_delete' in kwargs or (len(args) > 1
                                     and not isinstance(args[1], str)):
            # El llamador ya trajo la politica en el vocabulario del stack: son
            # las 1868 declaraciones que el arbol ya tiene, y el segundo
            # posicional de `ForeignKey` es ese mismo `on_delete`. No se pisa;
            # lo que se resuelve es el ATRIBUTO, que allá tambien existiria.
            # El llamador fijo la politica; NO es provisional.
            return args, kwargs, declared, False
        kwargs['on_delete'] = ON_DELETE_POLICY[declared]
        # Provisional: la fuente lo decide en `setup_nonrelated`, donde ya
        # tiene el modelo Y el comodelo. Aqui no hay ninguno de los dos.
        return args, kwargs, declared, True

    declared = kwargs.pop('ondelete')
    from_default = not declared
    if from_default:
        #: ``:282`` — la rama que este momento alcanza. La tercera, la
        #: transitoria de ``:276``, la decide :func:`_setup_nonrelated`
        #: cuando ambas clases existen.
        declared = 'restrict' if required else 'set null'

    if declared == 'set null' and required:
        raise ValueError(
            "The m2o field %s of model %s is required but declares its ondelete "
            "policy as being 'set null'. Only 'restrict' and 'cascade' make "
            "sense." % (kwargs.get('name', '<sin nombre>'),
                        _comodel_label(args[0]) if args else '<sin comodelo>')
        )

    #: ``:289`` verbatim — la fuente compara la CADENA declarada contra
    #: :data:`~orm.registry.IR_MODELS`, sin resolver el modelo: ``comodel_name``
    #: allá es siempre el ``_name`` punteado, porque es el único vocabulario que
    #: existe. Aquí el destino llega como esa misma cadena o como la clase ya
    #: cargada, así que la clase se reduce a su ``_name`` con
    #: :func:`~orm.registry.name_of`, que lee ``__dict__['_name']`` — un solo
    #: vocabulario, como la fuente.
    comodel = args[0] if args else None
    if comodel is None or isinstance(comodel, str):
        comodel_name = comodel
    else:
        comodel_name = name_of(comodel)
    if declared == 'restrict' and comodel_name in IR_MODELS:
        raise ValueError(
            f"Field is defined as ondelete='restrict' while having "
            f"{comodel_name} as comodel, the 'restrict' mode is not supported "
            f"for this type of field as comodel."
        )

    try:
        kwargs['on_delete'] = ON_DELETE_POLICY[declared]
    except KeyError:
        raise ValueError(
            f"ondelete={declared!r} no es uno de los tres valores que la "
            f"fuente admite: {sorted(ON_DELETE_POLICY)}"
        ) from None
    return args, kwargs, declared, from_default


def _setup_nonrelated(field, model):
    """El tercer caso del default de ``ondelete`` — ≙ ``setup_nonrelated``
    (``odoo19c: odoo/orm/fields_relational.py:267-282``).

    La fuente decide la politica de borrado en una FASE, no en el sitio de
    declaracion, y por eso puede preguntar por las dos clases::

        if model.is_transient() and not comodel.is_transient():
            # "Many2one relations from TransientModel Model are annoying
            #  because they can block deletion due to foreign keys. So unless
            #  stated otherwise, we default them to ondelete='cascade'."
            self.ondelete = 'cascade' if self.required else 'set null'
        else:
            self.ondelete = 'restrict' if self.required else 'set null'

    Solo corre cuando la politica salio del DEFAULT. Con ``ondelete``
    declarado —o con el ``on_delete`` de Django en la llamada— la fuente
    tampoco entra: su guarda es ``if not self.ondelete`` (``:273``).
    """
    if not is_transient(model) or model._meta.abstract:
        #: ``:276`` pregunta por el modelo ANTES que por el comodelo, asi que
        #: un modelo persistente no paga ninguna resolucion. Y un abstracto no
        #: tiene tabla: su politica la decide la concreta que lo herede.
        return
    comodel = field.remote_field.model
    if isinstance(comodel, str):
        #: Comodelo diferido. El stack trae hecha la fase que hace falta:
        #: ``lazy_related_operation`` agenda la funcion *"once `model` and all
        #: `related_models` have been imported and registered with the app
        #: registry"* (``django/db/models/fields/related.py``), que es lo que
        #: ``setup_nonrelated`` garantiza alla. No se construye nada.
        lazy_related_operation(
            lambda _model, _comodel, field=field: _decide_transient_ondelete(
                field, _comodel),
            model, comodel)
        return
    _decide_transient_ondelete(field, comodel)


def _decide_transient_ondelete(field, comodel):
    """La rama ``:276-279``, ya con las dos clases resueltas."""
    if is_transient(comodel):
        #: El ``else`` de ``:282``: wizard hacia wizard no es el caso molesto
        #: que el comentario de la fuente describe. La politica que dejo el
        #: default al construir ya es la correcta.
        return
    required = not field.null
    declared = 'cascade' if required else 'set null'
    field.ondelete = declared
    field.remote_field.on_delete = ON_DELETE_POLICY[declared]


def _is_source_name(value):
    """¿La cadena es un ``_name`` de la fuente, y no una etiqueta de Django?

    El discriminador es la caja, y está medido, no supuesto: los **224**
    ``_name`` del árbol son todos minúsculas, y **549** de las **580** llamadas
    con cadena literal declaran la etiqueta de Django con mayúscula en su
    segmento de modelo (``base.ResPartner``, ``account.AccountAccount``). Un
    nombre sin punto —``'self'``, el constante recursivo de Django— no es
    ninguno de los dos y sale por aquí sin tocarse.

    *Ciega a:* una etiqueta de Django escrita en forma ``label_lower``
    (``'base.respartner'``), que es legal para Django y este discriminador
    leería como ``_name``. **NO es hipotética, y no es una: son 41** — medidas
    por AST sobre ``src/``, resolubles con ``apps.get_model``, repartidas en
    **31 archivos de migración** y 3 fuera. Son legítimas: el estado de una
    migración rechaza la referencia a la clase (*"Model fields in
    ModelState.fields cannot refer to a model class"*), así que la cadena en
    minúsculas es el único camino que le queda. Por eso el discriminador de
    caja no decide solo: :func:`_deferred_comodel` pregunta después si Django
    puede resolver la cadena, y si puede la devuelve intacta.

    Los dos vocabularios **no se solapan hoy**: de las 41, **0** son además un
    ``_name`` de la fuente, así que el orden de las dos consultas de
    :func:`_deferred_comodel` no desempata nada. El día que una cadena sea las
    dos cosas, el orden pasa a ser una decisión y no un detalle.

    *Métrica:* llamadas a ``Many2one`` con primer argumento constante de
    cadena, recorridas por AST sobre ``src/`` y ``addons/`` — **549** etiquetas
    con mayúscula, **27** ``'self'``, **4** en minúsculas con un punto, **0**
    en minúsculas con dos o más. El censo por línea que precedió a este medía
    14 valores y no vio la de la migración (M20 del banco).
    """
    return '.' in value and value == value.lower()


def _translate_comodel(args):
    """Sustituye el ``_name`` punteado del primer posicional, si lo es.

    Comparten mecanismo ``Many2one`` y ``Many2many``: los dos acaban en un
    campo relacional de Django que resuelve su destino por
    ``lazy_related_operation`` (``related.py:80-86``), así que el nombre
    punteado les rompe igual y el asa los arregla igual. **No** lo comparte
    ``One2many``, que resuelve con ``apps.get_model(self.comodel_name)``
    (:func:`_one2many_comodel`) — otro mecanismo, otro puerto, sucesor
    declarado.

    Devuelve ``(args, source_name)``; ``source_name`` es ``None`` cuando no
    había nada que traducir.
    """
    if args and isinstance(args[0], str) and _is_source_name(args[0]):
        return (_deferred_comodel(args[0]),) + args[1:], args[0]
    return args, None


def _deferred_comodel(comodel):
    """Lo que se le entrega a Django en lugar del ``_name`` punteado.

    Dos caminos, uno por orden de declaración, y cada uno con su anulación:

    - **destino-primero** — el ``_name`` ya está en el registro, así que se
      entrega su **etiqueta** de Django y éste resuelve en el acto
      (``apps/registry.py:417-426``, rama ``else``). Nada queda pendiente.

    Siempre se devuelve una **cadena**, nunca la clase, y no es cosmético: el
    estado de una migración la rechaza — *"Model fields in ModelState.fields
    cannot refer to a model class"* (``django/db/migrations/state.py``) —, y
    una migración de este árbol declara sus dos campos por cadena justo por
    eso.
    - **referente-primero y auto-referencia** — el destino todavía no existe,
      así que se entrega la etiqueta centinela; la resolución la hace
      :func:`~orm.registry.flush_sentinel` cuando el destino emita
      ``class_prepared``.

    Una clase registrada con ``register_abstract`` no tiene ``_meta`` y no
    puede ser destinataria de una clave foránea: para ella también vale el
    centinela, que nunca resolverá — es el caso que el check de existencia
    porta como sucesor, no un silencio.
    """
    registered = model_by_name(comodel)
    if registered is not None and getattr(registered, '_meta', None) is not None:
        return registered._meta.label_lower
    if comodel.count('.') == 1:
        # Segunda vía del destino-primero: la cadena puede ser ya la etiqueta
        # de Django de un modelo cargado —que es como una **migración** tiene
        # que nombrarlo— y entonces no hay nada que traducir.
        # ``require_ready=False`` porque en Fase 2 ``models_ready`` aún es
        # False y el modelo ya está registrado.
        try:
            apps.get_model(comodel, require_ready=False)
        except (LookupError, ValueError):
            # silent OK because la excepcion ES la respuesta: no hay modelo de
            # Django con esa etiqueta, asi que la cadena es un ``_name`` de la
            # fuente y sigue al centinela. Propagarla convertiria una pregunta
            # en un fallo.
            pass
        else:
            return comodel
    return sentinel_label(comodel)


def Many2one(*args, store=_UNSET, company_dependent=False,
             check_company=False, related=None, **kwargs):
    """``fields.Many2one`` — ≙ el de la referencia: con columna, sin ella o por empresa.

    ``store=True`` (el defecto, y el de todos los usos previos del árbol)
    devuelve un ``models.ForeignKey`` con la firma de Django, exactamente como
    antes: el alias sigue siendo transparente para quien no nombra ``store``.

    ``store=False`` construye **el mismo** ``models.ForeignKey``: ``store`` es un
    atributo del campo, no un tipo distinto. Quien lo deja sin columna es la
    costura, que lo contribuye con ``private_only=True`` — no genera migración
    ni aparece en ``_meta.concrete_fields``, que es lo que la referencia promete
    con un ``compute`` sin ``store``.

    Y **sin comodelo declarado** —la forma que la referencia usa con
    ``related=``— el campo se construye contra su propio modelo con
    ``DO_NOTHING``, y ``_field_setup_related`` lo reapunta al destino real al
    cerrar el ``setup``. Ver el comentario de esa rama, con la sonda que la
    mide.

    ``company_dependent=True`` — el destino depende de la empresa
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tercera rama, con la firma de la fuente::

        property_account_payable_id = fields.Many2one(
            'account.account', company_dependent=True)

    Es **el tipo más usado** de la referencia con esa palabra clave: 35 de las
    54 declaraciones de producto (``odoo19c``, medido por AST). Devuelve un
    :class:`~orm.fields_company_dependent.CompanyDependent` de
    ``base_type='many2one'``, cuya columna guarda ``{empresa: id}``.

    **Deja de haber FK real, y eso es del mecanismo, no de la adaptación.**
    Allá pasa igual: el valor vive dentro del ``jsonb``, así que el catálogo de
    claves foráneas de PostgreSQL no ve la referencia y nadie la protege con
    ``ON DELETE``. Por eso la fuente lleva un índice propio —
    ``Registry.many2one_company_dependents``, portado en
    ``orm/registry.py``— y por eso el comodelo se guarda en el campo: es lo
    único que queda para responder *"¿quién apunta a este modelo?"*.

    Los argumentos que sólo tienen sentido en una FK real —``on_delete``,
    ``related_name``— se descartan aquí: sin FK no hay nada que cascadear ni
    accesor inverso que nombrar. Descartarlos en silencio sería el defecto que
    ``porte-completo-no-parcial.md`` prohíbe, así que quedan declarados.
    """
    #: ``:452-458`` — con ``related=`` y sin columna, el comodelo sobra: el
    #: extremo de la cadena lo determina, y así lo declara la referencia
    #: (``fields.Many2one(related='product_id.categ_id')``, sin comodelo).
    #: El centinela distingue «no declaró store» de «lo declaró True», que un
    #: default literal no puede.
    if store is not _UNSET:
        kwargs['store'] = store
    related_attrs = apply_source_defaults(related, kwargs,
                                         company_dependent=company_dependent)
    has_column = related_attrs['store']

    if company_dependent:
        to = args[0] if args else kwargs.pop('to', None)
        resto = args[1:]                       # el ``on_delete`` posicional
        if to is None:
            raise ValueError(
                'un Many2one dependiente de empresa necesita su modelo '
                'destino: es lo único que queda para indexarlo, porque el '
                'jsonb no deja FK que el catálogo pueda seguir.')
        for solo_fk in ('on_delete', 'related_name', 'limit_choices_to',
                        'to_field', 'db_constraint'):
            kwargs.pop(solo_fk, None)
        if resto:
            # ``Many2one('x', models.CASCADE)`` — el segundo posicional es el
            # ``on_delete`` de Django, que aquí tampoco tiene destinatario.
            resto = ()
        return _mark_check_company(
            CompanyDependent(*resto, base_type='many2one',
                             comodel=_comodel_label(to), **kwargs),
            check_company)
    #: ``required`` vale ``False`` salvo que se declare (``odoo19c: odoo/orm/
    #: fields_relational.py:282``): un ``Many2one`` sin ``null=`` es opcional,
    #: como en la fuente. Antes heredaba el ``null=False`` de ``ForeignKey`` y
    #: salía ``NOT NULL`` por omisión (:ref:`h-api-1122`); las declaraciones
    #: que deben seguir requeridas lo dicen con ``null=False``.
    if 'null' not in kwargs:
        kwargs['null'] = True
        kwargs.setdefault('blank', True)
    args, kwargs, resolved_ondelete, ondelete_from_default = \
        _apply_ondelete(args, kwargs)
    # DESPUES de ``_apply_ondelete``, y no antes: su guarda de ``:289`` compara
    # la CADENA declarada contra ``IR_MODELS``, que lleva los ``_name`` de la
    # fuente. Traducir primero la dejaria sin nada que comparar.
    args, source_name = _translate_comodel(args)
    if not has_column:
        #: **Sin columna NO hay clave foránea, así que NO hay política que
        #: aplicar** — y la que el campo hereda de :func:`_apply_ondelete` no es
        #: inocua: es ``SET_NULL`` para todo ``null=True``, y el recolector de
        #: ``delete()`` de Django sólo omite ``DO_NOTHING``
        #: (``django/db/models/deletion.py``: la rama que salta el campo es
        #: ``if field.remote_field.on_delete is DO_NOTHING``). Con cualquier
        #: otra política el recolector recorre el campo y manda a emitir un
        #: ``UPDATE`` sobre una columna que no existe.
        #:
        #: Medido, y el par discrimina: con ``SET_NULL`` borrar un ``res.country``
        #: aborta con ``FieldError: Cannot update model field <ForeignKey:
        #: country> (only concrete fields are permitted)``
        #: (``deletion.py:489 delete`` → ``query.py:1274 update``); con
        #: ``DO_NOTHING`` el mismo borrado sobrevive. Sondas
        #: ``probe_column_less_fk_with_set_null_breaks_country_delete`` y
        #: ``probe_column_less_fk_with_do_nothing_survives_country_delete``,
        #: evidencia ``scripts/evidence/ranuras2-2026-09-12T08-12-46-00{2,3}.log``.
        #:
        #: La política DECLARADA no se pierde: ``field.ondelete`` conserva el
        #: ``resolved_ondelete`` unas líneas más abajo, que es el atributo que la
        #: fuente expone y que leen ``ir.model.fields``, ``_check_inherits`` y el
        #: One2many inverso. Lo que cambia es sólo el recorrido del recolector de
        #: Django, que es un mecanismo que la fuente no tiene.
        #:
        #: ``related=`` sin destino añade su propio marcador: la referencia lo
        #: declara así —``fields.Many2one(related='product_id.categ_id')``—
        #: porque el extremo de la cadena determina el comodelo. Django exige
        #: ``to`` posicional, así que el campo se construye apuntando a su propio
        #: modelo y ``_field_setup_related`` lo reapunta al destino real al
        #: cerrar el ``setup``. Medido en ``probe_relational_related_without_to``.
        if not args and 'to' not in kwargs:
            args = ('self',)
        elif len(args) > 1:
            # ``Many2one('x', models.CASCADE)`` — el segundo posicional ES el
            # ``on_delete`` de Django, y se descarta para que el kwarg mande.
            args = args[:1]
        kwargs['on_delete'] = models.DO_NOTHING
    field = _mark_check_company(models.ForeignKey(*args, **kwargs),
                                check_company)
    # El atributo SOBREVIVE a la construccion, y no es cosmetico: la fuente lo
    # LEE desde cuatro sitios ademas de la FK — `ir.model.fields` lo refleja a
    # su columna `on_delete` (`odoo19c: ir_model.py:1164`), `_check_inherits`
    # exige `cascade` en un campo `delegate` (`model_classes.py:465`), un
    # One2many consulta el de su inverso (`fields_relational.py:987`), y la
    # suite del ORM afirma sobre el directamente
    # (`test_orm/tests/test_fields.py:4230-4256`, cuatro casos). Un porte que
    # solo tradujera el kwarg dejaria ciegos a los cuatro.
    field.ondelete = resolved_ondelete
    if ondelete_from_default:
        #: El gancho que :func:`~orm.fields._field_contribute_to_class` invoca
        #: cuando la clase ya existe. Se cuelga SOLO si la politica salio del
        #: default: su presencia ES la guarda ``if not self.ondelete`` de
        #: ``:273``, que aqui no se puede expresar dejando el atributo vacio
        #: porque Django exige ``on_delete`` posicional al construir la FK.
        field.setup_nonrelated__ = _setup_nonrelated
    if source_name is not None:
        # ``comodel_name`` es el atributo que la fuente declara
        # (``odoo19c: odoo/orm/fields_relational.py:36``) y el unico sitio donde
        # el nombre punteado sobrevive: lo que Django guarda en
        # ``remote_field.model`` es el asa, hasta que se resuelve a la clase.
        field.comodel_name = source_name
    return annotate_related(field, related, related_attrs)


def _many2one_join(self, model, alias, query):
    """``join`` — añade el LEFT JOIN de este Many2one y devuelve (modelo, alias).

    ≙ ``Many2one.join`` (``odoo19c: odoo/orm/fields_relational.py:466-478``).
    Es lo que ``BaseModel._traverse_related_sql`` invoca en cada salto de un
    camino relacional: sin él, un campo delegado no se puede resolver a SQL.

    La condición ON se compone con ``model._field_to_sql(alias, self.name,
    query)`` —el mismo punto de entrada que la fuente usa— para que la columna
    del lado izquierdo salga del mismo sitio que cualquier otra, con su
    comprobación de acceso incluida.

    Divergencias de nombre, las dos mecánicas: el comodelo se obtiene de
    ``self.related_model`` en vez de ``model.env[self.comodel_name]`` —Django
    ya lo tiene resuelto en el campo—, y su tabla de ``_meta.db_table`` en vez
    de ``_table``.
    """
    comodel = self.related_model
    coalias = query.make_alias(alias, self.name)
    query.add_join('LEFT JOIN', coalias, comodel._meta.db_table, SQL(
        "%s = %s",
        model._field_to_sql(alias, self.name, query),
        SQL.identifier(coalias, 'id'),
    ))
    return (comodel, coalias)


models.ForeignKey.join = _many2one_join


############################################################################
#
# El inverso en caché — ≙ ``odoo19c: odoo/orm/fields_relational.py:81,322,564``
#
# Cuando se escribe un lado de una relación, el **otro** lado que ya está en
# caché queda obsoleto. ``_update_inverse`` es quien lo pone al día, y lo
# consume ``Cache.patch`` (``orm/environments.py``). Vive aquí y no en
# ``orm/fields.py`` porque su base es ``_Relational`` — la fuente sólo lo
# declara para campos relacionales, y el genérico levanta
# ``NotImplementedError``.
#
# Divergencia de mecanismo, la misma de toda esta familia y por tanto declarada
# una vez: el entorno es **ambiental** (``orm.environments.env()``) en vez de
# ``records.env``; no hay recordset, así que ``records._ids`` es
# :func:`~orm.utils.record_ids` y ``record.id`` es :func:`single_record_id`.
#
############################################################################


def single_record_id(records):
    """El id de una fila única — la adaptación de ``BaseModel.id``.

    ≙ ``Id.__get__`` (``odoo19c: odoo/orm/fields_misc.py:103-114``): vacío
    devuelve ``False``, uno devuelve su id, y más de uno es un error de
    programación (*"Expected singleton"*). Se porta ese contrato tal cual.

    Admite además un id **suelto** —entero o :class:`~orm.identifiers.NewId`—
    y es una divergencia que hay que declarar, no un atajo. La fuente envuelve
    el id en un recordset (``comodel.browse(new_id)``) sólo para tener algo con
    ``.id``, y eso allá no consulta nada. Aquí :func:`~orm.utils.browse` **es
    una consulta**, y un ``NewId`` no tiene fila que traer: el envoltorio
    volvería vacío y el id se perdería en silencio. Por eso el id viaja crudo
    desde ``Cache.patch`` y se normaliza en este punto.
    """
    if isinstance(records, (int, NewId)):
        return records
    ids = record_ids(records)
    if not ids:
        return False
    if len(ids) == 1:
        return ids[0]
    raise ValueError("Expected singleton: %s" % (records,))


def _relational_update_inverse(self, records, value):
    """≙ ``_Relational._update_inverse`` (``:81``).

    Docstring de la fuente: *"Update the cached value of ``self`` for
    ``records`` with ``value``."* El genérico no sabe hacerlo — cada forma de
    relación guarda su caché distinta— así que declara el contrato y delega en
    la subclase. Se porta el ``raise`` verbatim: es lo que hace observable que
    a un tipo relacional nuevo le falta su implementación, en vez de que herede
    la del uno-a-muchos y corrompa la caché en silencio.
    """
    raise NotImplementedError


def _many2one_convert_to_cache(self, value, record, validate=True):
    """``Many2one.convert_to_cache`` — ≙ ``:328-351``. Formato: id o ``None``.

    Las cinco ramas de la fuente, con una divergencia de forma:

    - ``isinstance(value, BaseModel)`` se abre aquí a **instancia o
      ``QuerySet``**, que son las dos formas en que este árbol representa un
      conjunto de filas, y el modelo se compara con
      :func:`~orm.utils.model_of` en vez de con ``value._name``.
    - la rama de ``dict`` construye el registro virtual con
      ``comodel.new(value, origin=…)``, como la fuente. Levantaba
      ``NotImplementedError`` mientras ``BaseModel.new`` no existía (tarea
      **#327**, H-API-1135).

    La guarda final es la que da sentido a ``delegate``: si **todas** las filas
    son nuevas, el padre al que delegan también lo es, y su id se envuelve en
    un :class:`~orm.identifiers.NewId`.
    """
    if type(value) is int or type(value) is NewId:
        id_ = value
    elif isinstance(value, (models.Model, models.QuerySet)):
        ids = record_ids(value)
        if validate and (model_of(value) is not self.related_model or len(ids) > 1):
            raise ValueError("Wrong value for %s: %r" % (self, value))
        id_ = ids[0] if ids else None
    elif isinstance(value, tuple):
        # el valor es un par (id, nombre), o una tupla de ids
        id_ = value[0] if value else None
    elif isinstance(value, dict):
        # return a new record (with the given field 'id' as origin)
        comodel = self.related_model
        origin = comodel.browse(value.get('id'))
        id_ = comodel.new(value, origin=origin).id
    else:
        id_ = None

    if self.delegate and record and not any(record_ids(record)):
        # si todas las filas son nuevas, el padre tambien lo es
        id_ = id_ and NewId(id_)

    return id_


def _many2one_convert_to_display_name(self, value, record):
    """``Many2one.convert_to_display_name`` — ≙ ``:397-398``.

    La fuente escribe ``return value.display_name`` sin guarda, porque allá un
    ``Many2one`` vacío es un **conjunto vacío** y su ``display_name`` ya vale
    ``False``. Aquí una FK vacía es ``None``, que no tiene atributo alguno: la
    guarda ``if value else False`` es la traducción de esa semántica, no un
    añadido — devuelve el mismo ``False`` que la fuente para el campo vacío, y
    ``_compute_display_name`` lo distingue.

    ``Reference`` comparte cuerpo en la fuente (``:1101``); aquí lo hereda por
    la adjunción a ``models.ForeignKey``, de la que ``OneToOneField`` desciende.
    """
    return display_name_of(value) if value else False


def _relational_multi_convert_to_display_name(self, value, record):
    """``_RelationalMulti.convert_to_display_name`` — ≙ ``:714-715``.

    Verbatim de la fuente, ``raise NotImplementedError()``: un ``_rec_name``
    que nombre una colección no tiene etiqueta única, y devolver algo inventado
    escondería el error de declaración. El mensaje se añade porque el nuestro
    no tiene el ``repr`` del campo en el traceback de la fuente.
    """
    raise NotImplementedError(
        f'convert_to_display_name no aplica a {self!r}: una coleccion no '
        f'tiene etiqueta unica')


def _many2one_update_inverse(self, records, value):
    """``Many2one._update_inverse`` — ≙ ``:322-324``.

    El uno-a-uno del lado muchos: el valor se convierte al formato de caché
    **por fila**, porque :meth:`convert_to_cache` consulta la propia fila para
    decidir si el id del padre delegado es nuevo.
    """
    for record in records:
        self._update_cache(
            record, self.convert_to_cache(value, record, validate=False))


def _relational_multi_update_inverse(self, records, value):
    """``_RelationalMulti._update_inverse`` — ≙ ``:564-573``.

    Suma ``value`` al valor en caché de cada fila. Las dos aserciones de la
    fuente se portan verbatim porque son el contrato del método: sólo opera
    sobre **ids nuevos** sobre **filas nuevas** — un id real se escribe por la
    vía normal, no parcheando la caché.

    Cuando la fila todavía no tiene valor en caché, el id no se puede sumar a
    nada: se apunta en ``field_data_patches`` de la transacción y lo aplicará
    :func:`_relational_multi_update_cache` cuando el valor llegue.
    """
    new_id = single_record_id(value)
    assert not new_id, "Field._update_inverse solo admite un id nuevo"
    env = get_environment()
    field_cache = self._get_cache(env)
    for record_id in record_ids(records):
        assert not record_id, "Field._update_inverse solo admite filas nuevas"
        cache_value = field_cache.get(record_id, SENTINEL)
        if cache_value is SENTINEL:
            env.transaction.field_data_patches[self][record_id].append(new_id)
        else:
            field_cache[record_id] = tuple(unique(cache_value + (new_id,)))


def _relational_multi_update_cache(self, records, cache_value, dirty=False):
    """``_RelationalMulti._update_cache`` — ≙ ``:576-586``.

    Drena los parches que :func:`_relational_multi_update_inverse` dejó
    pendientes: los ids apuntados se suman al valor que se está escribiendo,
    en ese orden y sin repetir.

    ``models.Field._update_cache`` se resuelve **en tiempo de llamada**, no al
    importar: ``orm/fields.py`` instala el método base al final de su propio
    módulo y es él quien importa a éste (``orm/fields.py:84``), así que al
    ejecutarse estas líneas de módulo el atributo todavía no existe. Es el
    ``super()`` de la fuente escrito de la única forma que el orden de carga
    admite.
    """
    field_patches = get_environment().transaction.field_data_patches.get(self)
    if field_patches and records is not None:
        for record in records:
            ids = field_patches.pop(record.pk, ())
            if ids:
                value = tuple(unique(itertools.chain(cache_value, ids)))
            else:
                value = cache_value
            models.Field._update_cache(self, record, value, dirty)
        return
    models.Field._update_cache(self, records, cache_value, dirty)


#: ``delegate`` — ≙ ``Many2one.delegate`` (``:248``), *"whether self implements
#: delegation"*. Va sobre la clase por la misma razón que
#: ``bypass_search_access``: el atributo tiene que existir en las 759
#: declaraciones del árbol, pasen o no por la fábrica. Lo enciende
#: ``orm.inherits.apply_inherits`` sobre el campo concreto, que es el
#: equivalente del ``_setup_attrs__`` de la fuente (``:255-259``).
models.ForeignKey.delegate = False

RelatedField._update_inverse = _relational_update_inverse
models.ForeignKey.convert_to_cache = _many2one_convert_to_cache
models.ForeignKey.convert_to_display_name = _many2one_convert_to_display_name
models.ForeignKey._update_inverse = _many2one_update_inverse
models.ManyToManyField._update_inverse = _relational_multi_update_inverse


def _reverse_one2many_get_cache(self, env):
    """El caché del One2many inverso de un Many2one — ≙ ``Field._get_cache``.

    Aquí el One2many es el ``ManyToOneRel`` de Django y no un campo, así que
    no tenía caché propio. Lo necesita en un registro de ``new()``: sin fila
    que apunte a él, su conjunto de líneas sólo existe en caché. Sin cubos de
    contexto, como el ``One2many`` de la fuente.
    """
    return env.transaction.field_data[self]


def _reverse_one2many_cache_accessor(self):
    """``_get_cache`` sólo para el uno-a-muchos: el inverso de un
    ``OneToOneField`` es un registro, no una tupla de ids."""
    if isinstance(self, models.OneToOneRel):
        raise AttributeError('_get_cache')
    return functools.partial(_reverse_one2many_get_cache, self)


def _reverse_one2many_update_inverse_accessor(self):
    if isinstance(self, models.OneToOneRel):
        raise AttributeError('_update_inverse')
    return functools.partial(_relational_multi_update_inverse, self)


models.ManyToOneRel._get_cache = property(_reverse_one2many_cache_accessor)
models.ManyToOneRel._update_inverse = property(_reverse_one2many_update_inverse_accessor)


def _reverse_one2many_convert_to_cache(self, value, record, validate=True):
    """``_RelationalMulti.convert_to_cache`` — ≙ ``odoo19c: odoo/orm/
    fields_relational.py:589-641``. Formato: tupla de ids.

    Divergencia de forma: el comodelo es ``self.related_model`` (la clase) y
    el nombre del campo en el dueño es el accesor del inverso de Django.
    """
    # cache format: tuple(ids)
    if getattr(value, '_ids', None) is not None:
        if validate and model_of(value) is not self.related_model:
            raise ValueError("Wrong value for %s: %s" % (self, value))
        ids = value._ids
        if record and not record.id:
            # x2many field value of new record is new records
            ids = tuple(it and NewId(it) for it in ids)
        return ids

    elif isinstance(value, (list, tuple)):
        # value is a list/tuple of commands, dicts or record ids
        comodel = self.related_model
        # if record is new, the field's value is new records
        if record and not record.id:
            browse = lambda it: comodel.browse((it and NewId(it),))
        else:
            browse = comodel.browse
        # determine the value ids: in case of a real record or a new record
        # with origin, take its current value
        ids = OrderedSet(record[self.get_accessor_name()]._ids if record._origin else ())
        # modify ids with the commands
        for command in value:
            if isinstance(command, (tuple, list)):
                if command[0] == Command.CREATE:
                    ids.add(comodel.new(command[2], ref=command[1] or None).id)
                elif command[0] == Command.UPDATE:
                    line = browse(command[1])
                    if validate:
                        line.update(command[2])
                    else:
                        line._update_cache(command[2], validate=False)
                    ids.add(line.id)
                elif command[0] in (Command.DELETE, Command.UNLINK):
                    ids.discard(browse(command[1]).id)
                elif command[0] == Command.LINK:
                    ids.add(browse(command[1]).id)
                elif command[0] == Command.CLEAR:
                    ids.clear()
                elif command[0] == Command.SET:
                    ids = OrderedSet(browse(it).id for it in command[2])
            elif isinstance(command, dict):
                ids.add(comodel.new(command).id)
            else:
                ids.add(browse(command).id)
        # return result as a tuple
        return tuple(ids)

    elif not value:
        return ()

    raise ValueError("Wrong value for %s: %s" % (self, value))


def _reverse_one2many_convert_to_write(self, value, record):
    """``_RelationalMulti.convert_to_write`` — ≙ ``:671-711``."""
    if isinstance(value, tuple):
        # a tuple of ids, this is the cache format
        value = self.related_model.browse(value)

    if getattr(value, '_ids', None) is not None and model_of(value) is self.related_model:
        def get_origin(val):
            return val._origin if getattr(val, '_ids', None) is not None else val

        # make result with new and existing records
        inv_names = {field.name for field in field_inverses[self]}
        result = [Command.set([])]
        for record in value:
            origin = record._origin
            if not origin:
                values = record._convert_to_write({
                    name: record[name]
                    for name in record._cache
                    if name not in inv_names
                })
                result.append(Command.create(values))
            else:
                result[0][2].append(origin.id)
                if record != origin:
                    values = record._convert_to_write({
                        name: record[name]
                        for name in record._cache
                        if name not in inv_names and get_origin(record[name]) != origin[name]
                    })
                    if values:
                        result.append(Command.update(origin.id, values))
        return result

    if value is False or value is None:
        return [Command.clear()]

    if isinstance(value, list):
        return value

    raise ValueError("Wrong value for %s: %s" % (self, value))


def _reverse_one2many_only(function):
    """El método sólo para el uno-a-muchos (ver ``_get_cache``)."""
    def accessor(self):
        if isinstance(self, models.OneToOneRel):
            raise AttributeError(function.__name__)
        return functools.partial(function, self)
    return property(accessor)


models.ManyToOneRel.write_sequence = 0
models.ManyToOneRel.convert_to_cache = _reverse_one2many_only(_reverse_one2many_convert_to_cache)
models.ManyToOneRel.convert_to_write = _reverse_one2many_only(_reverse_one2many_convert_to_write)
models.ManyToOneRel._update_cache = _reverse_one2many_only(_relational_multi_update_cache)
models.ManyToManyField._update_cache = _relational_multi_update_cache
models.ManyToManyField.convert_to_display_name = (
    _relational_multi_convert_to_display_name)

#: ``One2many`` **no recibe estos métodos**, y es una ausencia declarada, no un
#: olvido: aquí es una clase plana (:class:`One2many`, arriba) que describe el
#: reverso de una FK, no un ``models.Field``, así que no participa de la caché
#: de campo ni tiene dónde colgarlos. En la fuente sí es un
#: ``_RelationalMulti`` y los hereda. Su desenlace va con el porte del lado
#: SQL del uno-a-muchos — tareas **#243** y **#244**.


class PrefetchMany2one(collections.abc.Reversible):
    """Los valores de un ``Many2one`` sobre el conjunto de prelectura.

    ≙ ``PrefetchMany2one`` (``odoo19c: odoo/orm/fields_relational.py:1734-1754``).
    Docstring de la fuente: *"Iterable for the values of a many2one field on
    the prefetch set of a given record."*

    Recorre los ids del conjunto de prelectura del registro, toma de la caché
    del campo el id relacionado de cada uno, **descarta** el que no tenga valor
    cacheado y **deduplica** conservando el orden — eso último lo aporta
    :func:`~tools.misc.unique`.

    **Divergencia de mecanismo:** la fuente pide la caché con
    ``self.field._get_cache(self.record.env)``, donde ``env`` es un
    ``__slots__`` del recordset; aquí una fila es una instancia de Django y el
    entorno es ambiente, así que se toma con
    :func:`~orm.environments.env`. Es la misma adaptación de
    :class:`~orm.models.RecordCache`.

    **Su consumidor real todavía no existe, y está medido.** ``_prefetch_ids``
    es el tercer ``__slots__`` del recordset de la fuente
    (``odoo19c: odoo/orm/models.py:362``), y este árbol no tiene recordset: 0
    apariciones del nombre en ``src/``. La clase se porta entera contra ese
    protocolo —lo único que consulta del registro es ese atributo— y el lote de
    prelectura que lo poblará es la tarea **#306**.
    """

    __slots__ = ('field', 'record')

    def __init__(self, record, field):
        self.record = record
        self.field = field

    def __iter__(self):
        field_cache = self.field._get_cache(get_environment())
        return unique(
            coid for id_ in self.record._prefetch_ids
            if (coid := field_cache.get(id_)) is not None
        )

    def __reversed__(self):
        field_cache = self.field._get_cache(get_environment())
        return unique(
            coid for id_ in reversed(self.record._prefetch_ids)
            if (coid := field_cache.get(id_)) is not None
        )


class PrefetchX2many(collections.abc.Reversible):
    """Los valores de un campo x2many sobre el conjunto de prelectura.

    ≙ ``PrefetchX2many`` (``odoo19c: odoo/orm/fields_relational.py:1757-1779``).
    Docstring de la fuente: *"Iterable for the values of an x2many field on the
    prefetch set of a given record."*

    Es la hermana de :class:`PrefetchMany2one` con una diferencia: la caché de
    un campo múltiple guarda una **colección** por id, así que el recorrido la
    aplana. El id que no está en caché no aporta nada —``field_cache.get(id_,
    ())``—, y :func:`~tools.misc.unique` deduplica **a través** de las
    colecciones, no dentro de cada una.

    Su divergencia de mecanismo y su bloqueo son los mismos que los de la
    hermana: entorno ambiente, y ``_prefetch_ids`` sin receptor hasta la tarea
    **#306**.
    """

    __slots__ = ('field', 'record')

    def __init__(self, record, field):
        self.record = record
        self.field = field

    def __iter__(self):
        field_cache = self.field._get_cache(get_environment())
        return unique(
            coid
            for id_ in self.record._prefetch_ids
            for coid in field_cache.get(id_, ())
        )

    def __reversed__(self):
        field_cache = self.field._get_cache(get_environment())
        return unique(
            coid
            for id_ in reversed(self.record._prefetch_ids)
            for coid in field_cache.get(id_, ())
        )


def _many2one_convert_to_column(self, value, record, values=None, validate=True):
    """``Many2one.convert_to_column`` — ≙ ``odoo19c: odoo/orm/fields_relational.py:326-327``.

    ``value or None``: el cero y la cadena vacía de una clave foránea son la
    ausencia de relación, no una fila con ese identificador. La base los
    conservaría —descarta por identidad— y la columna guardaría un ``0`` que no
    apunta a nada.
    """
    return value or None


models.ForeignKey.convert_to_column = _many2one_convert_to_column

_DJANGO_FOREIGN_KEY_GET_DB_PREP_SAVE = models.ForeignKey.get_db_prep_save


def _many2one_get_db_prep_save(self, value, connection):
    """El cableado de ``convert_to_column`` en la ruta de la clave foránea.

    ``ForeignKey.get_db_prep_save`` de Django (``related.py:1175``) no llama
    a la versión de ``models.Field`` que este árbol cablea: delega en el campo
    destino. Sin este paso, ``create({'company_id': False})`` llegaba al
    ``AutoField`` del destino como ``0`` y la columna guardaba una relación a
    una fila que no existe (``ForeignKeyViolation`` en PostgreSQL), donde la
    fuente escribe ``NULL`` (``odoo19c: odoo/orm/fields_relational.py:326-327``).
    """
    if not hasattr(value, 'as_sql'):
        value = self.convert_to_column(value, None, validate=False)
    return _DJANGO_FOREIGN_KEY_GET_DB_PREP_SAVE(self, value, connection)


models.ForeignKey.get_db_prep_save = _many2one_get_db_prep_save


def _many2one_convert_to_read(self, value, record, use_display_name=True):
    """``Many2one.convert_to_read`` — ≙ ``:366-378``.

    Con ``use_display_name`` y valor, el par ``(id, display_name)``; la
    etiqueta se evalúa en superusuario, porque su visibilidad depende del
    acceso al registro que lee, no al apuntado. Sin etiqueta, el id. Una FK
    vacía es aquí ``None`` y allá un conjunto vacío cuyo ``id`` vale
    ``False``: la guarda devuelve ese mismo ``False``. Un modelo de Django
    que no es ``BaseModel`` no tiene ``sudo``; su etiqueta se lee tal cual.
    """
    if use_display_name and value:
        target = value.sudo() if hasattr(value, 'sudo') else value
        try:
            return (value.id, display_name_of(target))
        except MissingError:
            # sólo si falta la fila apuntada
            return False
    return value.id if value else False


def _many2one_convert_to_write(self, value, record):
    """``Many2one.convert_to_write`` — ≙ ``:380-392``.

    Un id, o un ``NewId``, pasa tal cual; vacío es ``False``; un registro del
    comodelo da su id; un par ``(id, nombre)`` o una tupla de ids, su primer
    elemento; un diccionario, el id de un registro nuevo. La fuente reconoce el
    registro por ``_name``; aquí un comodelo puede ser un modelo de Django que
    no es ``BaseModel``, así que se reconoce por ``isinstance`` contra el
    modelo relacionado, que cubre a los dos.

    El cuerpo propio evita la cadena genérica de ``Field``
    (``convert_to_cache`` → ``convert_to_record`` → ``convert_to_read``):
    aquí ``convert_to_record`` de un ``Many2one`` devuelve el id crudo de la
    caché, y ``convert_to_read`` espera un registro.
    """
    if type(value) is int or type(value) is NewId:
        return value
    if not value:
        return False
    if isinstance(value, self.related_model):
        # un comodelo con clave propia no declara ``id``
        return value.id if hasattr(value, 'id') else value.pk
    if isinstance(value, tuple):
        # un par (id, nombre) o una tupla de ids
        return value[0] if value else False
    if isinstance(value, dict):
        return record.env[self.comodel_name].new(value).id
    raise ValueError(f'Wrong value for {self}: {value!r}')


models.ForeignKey.convert_to_read = _many2one_convert_to_read
models.ForeignKey.convert_to_write = _many2one_convert_to_write


def _reads_as_recordset(instance, comodel):
    """Si un ``One2many`` se lee como recordset: dueño y comodelo
    ``BaseModel`` y una fila guardada. Lo demás conserva el gestor de Django,
    que es la forma declarada para los modelos de ``TimeStampedModel``."""
    return (hasattr(instance, '_ids') and isinstance(comodel, type)
            and hasattr(comodel, '_from_ids')
            and isinstance(instance.pk, int))


def _read_one2many(field, instance, comodel):
    """Las líneas de ``instance`` en el ``One2many`` ``field``, como
    recordset del comodelo. — ≙ ``One2many.read`` (``odoo19c:
    odoo/orm/fields_relational.py:940-967``)
    seguido de ``_RelationalMulti.convert_to_record`` (``:643-653``).

    La búsqueda lleva ``active_test=False`` y el ``context`` del campo,
    sobre el ``domain`` del campo más el inverso; el orden es el
    ``_order`` del comodelo. Después, como ``convert_to_record``, se
    descartan las líneas archivadas salvo que el contexto del campo o el
    del entorno apaguen ``active_test``.

    Las dos mitades leen el entorno **del registro**, no el ambiental: la
    búsqueda corre sobre ``record.env`` con el contexto del campo encima
    (``records.env[comodel].with_context(**context)``, ``:942-944``), y las
    líneas se devuelven en ``record.env`` y se filtran con su contexto
    (``Comodel(record.env, value, ...)``, ``:645-650``). Así ``copy``, que
    lee las líneas bajo ``with_context(active_test=False)``, copia también
    las archivadas.

    **Divergencia de mecanismo:** sin caché por campo, se lee en cada
    acceso y para un solo registro; la fuente lee en lote y guarda los
    ids, incluidos los inactivos.
    """
    field_context = dict(field.context or {})
    reading = comodel._from_ids(instance.env, (), ()).with_context(
        **{'active_test': False, **field_context})
    with reading.env:
        domain = (field.get_comodel_domain(instance)
                  + [(field.inverse_name, 'in', [instance.id])])
        ids = reading.search(domain)._ids
    lines = comodel._from_ids(instance.env, ids, ids)
    active = comodel._active_field_name()
    if active and field_context.get(
            'active_test', instance.env.context.get('active_test', True)):
        lines = lines.filtered(active)
    return lines


#: ≙ ``_RelationalMulti.convert_to_write`` (``:671-711``) también para el
#: ``Many2many``: hasta ahora sólo el uno-a-muchos lo tenía, y el
#: ``Many2many`` caía en la cadena genérica, que deja pasar un texto donde la
#: fuente levanta ``ValueError``. ``_search_display_name`` descarta con ese
#: ``ValueError`` el valor que no es del tipo del campo.
models.ManyToManyField.convert_to_write = _reverse_one2many_convert_to_write

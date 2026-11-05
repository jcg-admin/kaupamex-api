"""Campos sin columna — ≙ el ``store=False`` de la referencia.

En Odoo un campo puede declararse **sin columna**: ``fields.Char(store=False,
default=_get_algo)`` o un ``compute`` sin ``store`` producen un campo que se
calcula al leerlo y nunca se escribe a la base (``odoo19c:
account/models/res_currency.py:17`` es el caso canónico). Allá ``store`` es un
atributo del campo y nunca un tipo distinto (``odoo19c:
odoo/orm/fields.py:455``).

Aquí tampoco lo es ya. Desde TASK-API-0417 las fachadas construyen siempre el
campo de Django y la costura lo contribuye con ``private_only=True``
(``orm/fields.py``, ``_field_contribute_to_class``): sin columna, sin
migración, en ``_meta.private_fields``. TASK-API-0418 retiró la clase
descriptora que antes cumplía ese papel.

Lo que vive en este módulo es lo que esa forma necesita alrededor:

- :func:`apply_source_defaults` y :func:`derive_source_attrs` — lo que
  ``compute=``/``related=`` implican sobre ``store``, ``readonly`` y demás,
  como en el ``_get_attrs`` de la fuente (``:443-465``);
- :func:`annotate_related` — el ``related`` y su búsqueda sobre el campo;
- :func:`non_stored_fields` — los campos sin columna de un modelo, que
  ``BaseModel._fields`` une a los de ``_meta`` para ser el registro de la
  fuente y no el de las columnas (:ref:`h-api-1025`).

Este archivo NO existe en la referencia, y ``src/orm`` es una raíz espejada
==========================================================================

Medido contra ``odoo19c: odoo/orm/`` — ``find`` por nombre y ``grep`` por
símbolo, los dos a **0**. La referencia no lo necesita: su
``fields.Char(store=False, ...)`` ya declara un campo sin columna. Este
mecanismo existe porque en Django todo ``models.Field`` **es** una columna.

Eso lo hace legítimo como **mecanismo construido**
(``porte-completo-no-parcial.md``: *si el stack no trae el mecanismo, se
construye*) y a la vez lo deja **fuera de sitio**: ``src/orm`` es la raíz
espejada de ``odoo/orm``, y ``atributos-de-clase-de-modelo.md`` §2 manda listar
la raíz de la referencia antes de crear un archivo ahí.

``check_porte_completo`` **no puede verlo**: compara símbolos dentro de un par
de archivos, y un archivo que la referencia no tiene no entra en ninguna
comparación. Cinco archivos de ``src/orm`` están en esta situación —
``checks``, ``fields_nonstored``, ``inherits``, ``method_chain``, ``routers``—
y hasta este pase sólo ``checks`` lo declaraba.

El veredicto por archivo —quedarse aquí con la divergencia declarada, o mudarse
a una raíz propia como ``src/core``— es la tarea **#121**.
"""

import types
import warnings

from django.db import models

__all__ = [
    'non_stored_fields',
    'apply_source_defaults',
    'annotate_related',
    'derive_source_attrs',
]


#: Centinela de «el declarante no dijo nada». Lo usan las fachadas en la firma
#: de su parámetro ``store=``: un ``store=None`` declarado y un ``store``
#: ausente tienen que distinguirse, y un default literal no los separa.
_UNSET = object()


#: Las claves del vocabulario de la fuente que un declarante puede pasar por
#: ``kwargs``. Se enumeran para saber CUÁLES declaró: la derivación añade
#: defaults, y sin la lista no habría cómo distinguir «el autor lo escribió»
#: de «el bloque lo dedujo» — que es lo que :func:`annotate_related` necesita
#: para no colgar un atributo de instancia por cada clave sobre un campo llano.
SOURCE_VOCABULARY_KEYS = frozenset(
    {
        'compute',
        'inverse',
        'recursive',
        'precompute',
        'compute_sudo',
        'related_sudo',
        'readonly',
        'store',
        'copy',
        'related',
    }
)


def derive_source_attrs(attrs, many_to_many=False, field_label=''):
    """
    Los tres bloques de derivación de la fuente, sobre ``attrs``, en su orden.

    ≙ ``odoo19c: odoo/orm/fields.py:443-465``. Es **una sola copia**, y ése es
    el punto: la tenían duplicada :func:`apply_source_defaults` —que deriva en
    el sitio de declaración— y ``_field_get_attrs`` de :mod:`orm.fields` —que
    deriva tras fusionar la cadena de la MRO—. Los dos momentos hacen falta:
    un campo suelto responde ``field.store`` antes de contribuir a ninguna
    clase, y una redeclaración sólo se puede corregir después de fusionar. Lo
    que no hacía falta eran dos cuerpos que se pudieran separar.

    Vive en este módulo, y no en :mod:`orm.fields` donde la fuente lo pone,
    porque la dirección de import ya está fijada: ``fields`` importa de aquí
    (``orm/fields.py:85``) y la vuelta sería un ciclo. Es la misma divergencia
    de sitio que este archivo entero declara (tarea **#291**).

    :param attrs: el diccionario con **lo que el declarante escribió**. Se
        muta en el sitio, igual que allá.
    :param many_to_many: el tercer caso de ``precompute``, que es nuestro y es
        de stack.
    :param field_label: qué campo nombra el aviso; vacío en el sitio de
        declaración, donde el campo aún no tiene nombre.
    """
    if attrs.get('compute'):
        # ``:443-451`` — un calculado no se almacena, se calcula elevado si
        # tiene columna, no se copia (salvo que tenga columna y sea escribible)
        # y es de sólo lectura (salvo que tenga inversa).
        attrs['store'] = store = attrs.get('store', False)
        attrs['compute_sudo'] = attrs.get('compute_sudo', store)
        if not (attrs['store'] and not attrs.get('readonly', True)):
            attrs['copy'] = attrs.get('copy', False)
        attrs['readonly'] = attrs.get('readonly', not attrs.get('inverse'))
    if attrs.get('related'):
        # ``:452-458`` — un related no se almacena, se calcula elevado, no se
        # copia y es de sólo lectura. Va DESPUÉS del bloque de ``compute`` y
        # lo pisa: un ``related=`` con ``compute=`` acaba con forma de related.
        attrs['store'] = store = attrs.get('store', False)
        attrs['compute_sudo'] = attrs.get(
            'compute_sudo', attrs.get('related_sudo', True)
        )
        attrs['copy'] = attrs.get('copy', False)
        attrs['readonly'] = attrs.get('readonly', True)
    if attrs.get('precompute'):
        # ``:459-465`` — avisa y apaga. ``precompute`` sólo tiene efecto sobre
        # un calculado (o un related, que es un calculado con otro nombre) y
        # con columna. Fuera de ahí la fuente lo dice en vez de tragárselo.
        suffix = f' {field_label}' if field_label else ''
        if not attrs.get('compute') and not attrs.get('related'):
            warnings.warn(
                "precompute attribute doesn't make any sense on non computed "
                f"field{suffix}",
                stacklevel=2,
            )
            attrs['precompute'] = False
        elif not attrs.get('store'):
            warnings.warn(
                "precompute attribute has no impact on non stored "
                f"field{suffix}",
                stacklevel=2,
            )
            attrs['precompute'] = False
        elif many_to_many:
            # El tercer caso es NUESTRO, y es de stack. Un muchos-a-muchos no
            # se puede adelantar al ``INSERT``: su valor no vive en una columna
            # de la fila sino en una tabla intermedia que necesita el ``pk``
            # para tener a quién apuntar. La fuente no lo tiene porque su ORM
            # asigna el id antes de ejecutar la cola de recálculo, y por eso
            # declara ``tag_ids`` con ``precompute=True``
            # (``odoo19c: account_account.py:107``).
            warnings.warn(
                "precompute attribute has no impact on a many2many field: "
                "its join table needs the pk of a row that does not exist "
                f"yet{suffix}",
                stacklevel=2,
            )
            attrs['precompute'] = False
    return attrs


def apply_source_defaults(
    related, kwargs, many_to_many=False, company_dependent=False
):
    """Lo que ``compute=`` y ``related=`` implican, resuelto al declarar.

    Deriva con :func:`derive_source_attrs` —la única copia de los tres bloques
    de la fuente— y añade las dos consecuencias que sólo se pueden resolver en
    el sitio de declaración, porque son argumentos del constructor de Django o
    contradicciones de la propia declaración.

    **Ya no retira nada de ``kwargs``.** Lo hacía porque el constructor de
    Django rechazaba las claves de la fuente; desde que
    ``_field_init_with_copy`` las recoge en ``_args__`` y las retira él mismo
    (``orm/fields.py``), retirarlas aquí sólo conseguía que la costura no las
    viera y tuviera que derivar de nuevo sobre un ``_args__`` mutilado. Medido
    en la sonda ``probe_vocabulary_reaches_args_by_type``: los **once** tipos
    de Django que las fachadas construyen —``CharField`` … ``ManyToManyField``,
    incluidos los dos relacionales, que tienen ``__init__`` propio— recogen
    ``store`` y ``related`` en ``_args__`` sin rechazarlos.

    **Se llamaba ``apply_related_defaults``.** El nombre describía la mitad que
    portaba; con las tres, mentiría.
    """
    declared_keys = SOURCE_VOCABULARY_KEYS & frozenset(kwargs)
    attrs = {key: kwargs[key] for key in declared_keys}
    if related:
        attrs['related'] = related
        #: Viaja también en ``kwargs`` para que ``_args__`` lo recoja: es lo
        #: que hace que la costura derive lo mismo tras fusionar la MRO, en vez
        #: de ver un campo sin ``related`` y dejar los defaults de clase.
        kwargs['related'] = related

    derive_source_attrs(attrs, many_to_many=many_to_many)
    attrs.setdefault('store', True)

    #: La exclusión vive en el sitio de declaración porque es una contradicción
    #: de lo declarado, no una decisión de rama: un campo sin columna no tiene
    #: ``jsonb`` donde repartir el valor por empresa. Resolverla más tarde la
    #: convertiría en un fallo de arranque en vez de un error donde se escribe.
    if company_dependent and not attrs['store']:
        raise ValueError(
            'store=False y company_dependent=True son excluyentes: un '
            'campo sin columna no tiene jsonb donde repartir el valor.'
        )

    #: ``editable=False`` es la forma NATIVA de Django de decir «esto no lo
    #: escribe el cliente», y es la que DRF ya consume: ``get_field_kwargs``
    #: (``rest_framework/utils/field_mapping.py:124-128``) hace
    #: ``if ... or not model_field.editable: kwargs['read_only'] = True``. Se
    #: pasa como argumento del constructor y no como atributo derivado porque
    #: Django lo lee al construir —``Field.__init__`` lo guarda y las
    #: migraciones lo deconstruyen—; la costura lo vuelve a derivar para el
    #: campo que llegue sin pasar por una fachada.
    if attrs.get('readonly') and attrs['store'] and 'editable' not in kwargs:
        kwargs['editable'] = False

    #: ``required`` vale ``False`` en la fuente (``odoo19c:
    #: odoo/orm/fields.py``, ``Field``) y un campo sin columna no tiene
    #: ``NOT NULL`` que cumplir. Django, en cambio, nace con ``blank=False``,
    #: y ``full_clean`` recorre ``_meta.fields``, que incluye los privados:
    #: sin esto un ``related`` sin columna se rechazaba como obligatorio. Un
    #: ``required=True`` declarado ya llegó como ``blank`` y ``setdefault`` no
    #: lo pisa.
    if not attrs['store']:
        kwargs.setdefault('blank', True)

    attrs['declared_keys'] = declared_keys
    return attrs


def annotate_related(field, related, attrs):
    """Deja en el campo lo que la declaración dijo, para que sea greppeable.

    Los cuatro atributos son del vocabulario de la fuente y Django no los
    conoce, así que no viajan en su constructor: se anotan aquí. Sin la
    anotación el árbol no tendría con qué medir cuántos campos son una
    proyección — el mismo criterio con que ``translate`` se anota en vez de
    tragarse (``orm/fields_textual.py``).
    """
    field.related = related
    #: ≙ ``odoo19c: odoo/orm/fields.py:500`` — ``self.__dict__.update(attrs)``,
    #: **incondicional**: la fuente no pregunta si el campo es ``related`` ni
    #: si es calculado, aplica todo lo que el autor declaró. Aquí vivía una
    #: salida temprana para la rama llana que la fuente no tiene, y con ella se
    #: perdían en silencio ``readonly`` (645 declaraciones en la referencia),
    #: ``inverse`` (35), ``recursive`` (3) y ``compute_sudo`` (1) — el default
    #: de clase (``orm/fields.py:1915-1945``) devolvía justo el valor que el
    #: autor quiso cambiar. Ver :ref:`h-api-1103`.
    #:
    #: Lo que SÍ se conserva de aquel razonamiento es su restricción, no su
    #: filtro: un campo que no declara nada no gana un atributo de instancia
    #: por cada clave del vocabulario. La fuente tampoco lo hace — su ``attrs``
    #: sale de ``_get_attrs`` (``:414-430``), que arranca con
    #: ``attrs.update(self._args__)``: **sólo lo que el autor pasó**, y los
    #: bloques de ``compute``/``related`` añaden defaults únicamente en esas
    #: dos ramas. ``declared_keys`` es el porte de esa asimetría.
    #:
    #: Un calculado entra entero: su vocabulario es lo que
    #: :class:`~orm.registry._DerivedCollector` lee para unir el campo con el
    #: ``_depends`` de su método. Sin la anotación, ``field.compute`` sería
    #: ``None`` y el mapa saldría vacío — que es lo que el censo midió antes de
    #: este porte (44 métodos, 0 campos, 0 aristas).
    declared_keys = attrs.get('declared_keys', frozenset())
    landing = (
        attrs
        if (related or attrs.get('compute'))
        else {
            key: value for key, value in attrs.items() if key in declared_keys
        }
    )
    for attribute, value in landing.items():
        #: Contabilidad del mecanismo, no vocabulario de la fuente: viaja en el
        #: diccionario para que esta función sepa qué declaró el autor, y no
        #: aterriza en el campo.
        if attribute == 'declared_keys':
            continue
        setattr(field, attribute, value)
    #: El campo queda buscable por su cadena, que es lo que navegar la FK a
    #: mano no da — la razón por la que este mecanismo se porta en vez de
    #: declinarse (:ref:`h-api-974`). ``_search_related`` lo instala
    #: :mod:`orm.domains`; aquí se liga a esta instancia. Con ``store`` la
    #: búsqueda va por la columna propia, así que no se cablea (``:635``).
    if related and not attrs['store']:
        field.search = _bind_search_related(field)
    return field


def _bind_search_related(field):
    """``_search_related`` ligado a ``field`` — el invocable que ``search``
    espera: ``(records, operator, value) -> Domain``."""

    def search(records, operator, value):
        return models.Field._search_related(field, records, operator, value)

    return search


class _RegistryCache:
    """Memoria del recorrido del MRO, por clase, con invalidación exacta.

    El recorrido cuesta lo suyo y :meth:`~orm.models.FieldSqlMixin._fields` lo
    hace en cada acceso, incluido el camino de composición de SQL. Medido sobre
    ``ResPartner`` —16 clases en el MRO, 17 campos sin columna— el recorrido
    son
    **20.9 us** contra **4.6 us** del mapa de ``_meta``: sin memoria, el
    registro del modelo pasa de 4.6 a 26.4 us por lectura.

    La invalidación es por **generación** y no por clase: un descriptor puede
    aterrizar en una clase base y cambiar el resultado de todas sus derivadas,
    así que la única invalidación correcta es tirar el mapa entero. Ocurre sólo
    mientras los addons instalan sus extensiones —``AppConfig.ready()``—, no en
    caliente.

    Con memoria el recorrido baja a **0.1 us** y el registro completo a
    **6.1 us**: lo que queda sobre los 4.6 del mapa de ``_meta`` es la unión de
    los 17, que es el precio de tener el registro de la fuente y no el de las
    columnas.

    *Métrica:* ``timeit`` con 2000 repeticiones sobre ``ResPartner``, con las
    apps ya cargadas.
    *Ciega a:* un descriptor que alguien cuelgue con ``setattr`` pelado, sin
    pasar por ``contribute_to_class`` ni por ``__set_name__``. Esa vía no
    invalida nada, y por eso la instalación de un campo sin columna se hace
    siempre por una de las dos.
    """

    def __init__(self):
        self._generation = 0
        self._by_class = {}

    def invalidate(self):
        self._generation += 1
        self._by_class.clear()

    def get(self, cls):
        cached = self._by_class.get(cls)
        if cached is not None and cached[0] == self._generation:
            return cached[1]
        return None

    def put(self, cls, mapping):
        self._by_class[cls] = (self._generation, mapping)


_REGISTRY_CACHE = _RegistryCache()


def _is_declared_one2many(held):
    """Si ``held`` es un ``fields.One2many(comodel, inverse)`` declarado.

    Ese campo no pasa por ``_meta`` (su ``contribute_to_class`` sólo hace
    ``setattr``), así que tampoco tiene columna ni lo ve ``get_fields``. Se
    reconoce por el atributo de la fuente, ``type == 'one2many'``
    (``odoo19c: odoo/orm/fields_relational.py:866``), y no por su clase:
    ``orm.fields_relational`` importa este módulo, y la importación inversa
    cerraría un ciclo. Un ``models.Field`` de Django con ese tipo ya está en
    ``_meta`` y no se recoge aquí.
    """
    return getattr(held, 'type', None) == 'one2many' and not isinstance(
        held, models.Field)


def non_stored_fields(cls):
    """Los campos sin columna que ``cls`` declara, por nombre.

    Es la mitad que le faltaba a ``BaseModel._fields`` para ser el registro de
    la fuente y no el de las columnas. Allá ``_fields`` es el mapa que el ORM
    construye al cargar la clase, y en él entra **todo** campo declarado, tenga
    columna o no: un ``related`` sin ``store`` está ahí igual que un ``Char``.
    Aquí las columnas las publica ``_meta.get_fields()`` y los campos sin
    columna viven en ``_meta.private_fields``. Sin este recorrido el registro
    del modelo queda estrictamente más estrecho que el de la fuente, y quien
    lo consulte por un nombre que sí existe recibe un fallo en vez del campo
    (:ref:`h-api-1025`).

    **Dos ramas.** La principal son los ``models.Field`` que la costura
    contribuyó con ``private_only=True`` —``_field_contribute_to_class``
    (``orm/fields.py``) lo refuerza con ``private_only or self.store is
    False``—; la otra, los ``One2many`` declarados, que no pasan por ``_meta``
    y se recogen del ``__dict__`` de cada clase del MRO, de la base a la
    derivada, así que la declaración más derivada gana. TASK-API-0418 retiró
    la tercera, la del descriptor sin columna, junto con la clase.

    El filtro sobre ``private_fields`` es ``store is False`` y no la mera
    pertenencia: Django también contribuye ahí ``GenericForeignKey`` y los
    campos de contenido genérico, que sí tienen columna asociada y no son
    campos sin almacenamiento de la fuente. Preguntar por la pertenencia
    mediría la tubería de Django y concluiría sobre el vocabulario de la
    referencia.
    """
    cached = _REGISTRY_CACHE.get(cls)
    if cached is not None:
        return cached
    found = {}
    for klass in reversed(getattr(cls, '__mro__', (cls,))):
        for name, held in vars(klass).items():
            if _is_declared_one2many(held):
                found[name] = held
    meta = getattr(cls, '_meta', None)
    for field in getattr(meta, 'private_fields', ()) or ():
        if getattr(field, 'store', True) is False:
            found[field.name] = field
    #: De sólo lectura a propósito: el mapa se comparte entre lecturas, y un
    #: consumidor que lo mutara corrompería el registro de todos los demás.
    mapping = types.MappingProxyType(found)
    _REGISTRY_CACHE.put(cls, mapping)
    return mapping

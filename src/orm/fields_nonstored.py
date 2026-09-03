"""Campo no persistido — ≙ el ``store=False`` de la referencia.

En Odoo un campo puede declararse **sin columna**: ``fields.Char(store=False,
default=_get_algo)`` produce un atributo que se calcula al leerlo y nunca se
escribe a la base (``odoo19c: account/models/res_currency.py:17`` es el caso
canónico). Django no lo tiene: todo ``models.Field`` es una columna.

Este módulo lo construye. No es una comodidad: sin él, portar
``fiscal_country_codes`` obligaba a inventar una forma distinta —una
``property`` colgada desde otro addon— y a repartir en el cableado lo que la
referencia declara **en la clase**. Es la diferencia entre adaptar la conducta
y copiar una restricción ajena.

Qué NO es
==========

- **No es un campo de Django.** No aparece en ``_meta.get_fields()``, no genera
  migración, no se puede filtrar con ``.filter(campo=…)``. Es exactamente lo
  que la referencia promete con ``store=False``: un valor que existe para
  leerse, no para consultarse.
- **No es una ``property``.** Admite asignación —``obj.campo = 'X'`` se guarda
  en la instancia y gana sobre el ``default``—, igual que en la referencia,
  donde un campo no almacenado sigue siendo escribible en memoria.

Cómo se declara
================

Con la misma firma que la fuente, en el cuerpo de la clase o colgado después::

    fiscal_country_codes = fields.Char(store=False,
                                       default=get_fiscal_country_codes)

El ``default`` puede ser un valor o un invocable. Si es invocable se llama con
la instancia cuando acepta un argumento, y sin argumentos cuando no — así
sirven tanto un cómputo que mira sólo la sesión (``env.companies`` en la
referencia) como uno que mira el registro (``record.company_id or …``).

Este archivo NO existe en la referencia, y ``src/orm`` es una raíz espejada
==========================================================================

Medido contra ``odoo19c: odoo/orm/`` — ``find`` por nombre y ``grep`` por
símbolo, los dos a **0**. La referencia no lo necesita: su ``fields.Char(store=False, ...)`` ya declara un campo sin columna. Este mecanismo existe porque en Django todo ``models.Field`` **es** una columna.

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
import inspect
import types
import warnings

from django.db import models

__all__ = ['NonStored', 'non_stored_fields', 'projection_or_none']


class NonStored:
    """Descriptor de un campo declarado ``store=False``.

    Sigue el protocolo de ``contribute_to_class`` de Django para que funcione
    en los dos caminos por los que un atributo llega a un modelo: el cuerpo de
    la clase (``ModelBase`` lo invoca) y ``Model.add_to_class`` (el que usan
    las extensiones ``_inherit`` de este puerto). Sin él, el segundo camino
    dejaría el descriptor sin saber su propio nombre.
    """

    def __init__(self, *args, default=None, help_text='', search=None,
                 related=None, verbose_name=None, compute=None, **_ignored):
        self.default = default
        self.help_text = help_text
        #: ≙ ``Field.string`` (``odoo19c: odoo/orm/fields.py:264``) — la
        #: etiqueta. Django la toma del primer posicional, y la fuente la
        #: declara con ``string=``; se conserva por las dos vías para que la
        #: declaración se lea contra la suya sin traducir nada. Un campo sin
        #: columna no la usa para pintar formulario, pero tirarla dejaría al
        #: árbol sin forma de medir cuántos la declaran.
        self.verbose_name = verbose_name if args[:1] == () else args[0]
        #: ≙ ``Field.related`` (``odoo19c: odoo/orm/fields.py:286``) — la ruta
        #: punteada cuyo extremo aporta el valor. Con ella el campo **no lee
        #: su default**: navega la cadena, que es el ``compute`` de la fuente
        #: (``:675`` ``_compute_related``). Es la forma de la gran mayoría de
        #: los ``related=`` que la referencia declara en los addons que este
        #: árbol porta — los que no llevan ``store`` y por tanto no tienen
        #: columna. El reparto lo publica
        #: ``python3 scripts/census_related_fields.py``, que no se transcribe
        #: aquí porque crece con la referencia.
        self.related = related
        #: ≙ ``Field.search`` (``odoo19c: odoo/orm/fields.py:289``): el nombre
        #: de un método o el invocable que sabe traducir una condición sobre
        #: este campo a un dominio sobre campos que sí tienen columna. Sin él
        #: el campo se puede leer y escribir, pero no se puede buscar — que es
        #: exactamente lo que la fuente promete con un campo sin ``search``.
        self.search = search
        #: ≙ ``Field.compute`` (``odoo19c: odoo/orm/fields.py:285``) — «el
        #: nombre de un método o el invocable que calcula el campo». Es la
        #: forma con que la fuente declara la inmensa mayoría de sus campos
        #: sin columna: medido sobre ``addons/*/models/*.py`` y
        #: ``odoo/addons/*/models/*.py`` de ``odoo19c``, **293** declaraciones
        #: de los siete tipos que enruta :func:`projection_or_none` llevan
        #: ``compute=`` y ningún ``store=True``.
        #:
        #: Se **conserva** y no se traga con el resto: sin él, el árbol no
        #: tiene con qué medir cuántos campos sin columna declaran de dónde
        #: sale su valor, y el motor de recálculo (tarea **#273**) no tendría
        #: dónde leerlo cuando llegue. Hoy nadie lo invoca — el valor sigue
        #: saliendo de ``related`` o de ``default``.
        self.compute = compute
        self.name = None

    # -- protocolo de nombre ------------------------------------------------

    def __set_name__(self, owner, name):
        """Camino del cuerpo de clase en una clase que NO es modelo Django."""
        self.name = name
        _REGISTRY_CACHE.invalidate()

    def contribute_to_class(self, cls, name, **_kwargs):
        """Camino de ``ModelBase`` y de ``add_to_class``.

        Django llama a este método en vez de ``setattr`` cuando el objeto lo
        declara. Aquí **no** se registra nada en ``_meta``: ese es justamente
        el punto — el campo no tiene columna.
        """
        self.name = name
        setattr(cls, name, self)
        _REGISTRY_CACHE.invalidate()

    # -- protocolo de descriptor -------------------------------------------

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        if self.name in instance.__dict__:
            return instance.__dict__[self.name]
        if self.related:
            return self.resolve_related(instance)
        return self.resolve_default(instance)

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value
        #: ``:632`` — la fuente cablea el inverso **sólo** si el campo no es de
        #: sólo lectura. Un ``related`` sin ``readonly=False`` declarado toma
        #: el defecto de ``:458`` y no propaga: escribirlo se queda en memoria.
        if self.related and not getattr(self, 'readonly', True):
            self.inverse_related(instance, value)

    def inverse_related(self, instance, value):
        """Escribe ``value`` en el extremo de la cadena — ≙
        ``Field._inverse_related`` (``odoo19c: fields.py:724``).

        Este árbol ya tenía ese método portado verbatim, **sobre
        ``models.Field``** (``orm/fields.py:1809``). Un :class:`NonStored` no
        desciende de ``models.Field``, así que nunca lo alcanzaba: un
        ``related`` con ``readonly=False`` aceptaba la escritura y la guardaba
        en sombra sobre el origen. Es la forma de :ref:`h-api-978` otra vez —
        acepta y no hace nada— en el otro sentido de la cadena.

        Dos cosas son verbatim de la fuente, y la segunda no es cosmética:

        - **La guarda de realidad** ``bool(target.id) == bool(record.id)``
          (``:731``), con su comentario: *«update 'target' only if 'record' and
          'target' are both real or both new»*. Un registro sin guardar no
          escribe en uno guardado.
        - **El eslabón vacío no revienta.** Sin destino no hay dónde escribir,
          y eso no es un error — igual que leerlo da vacío.

        Lo que **diverge, y es de mecanismo**: la fuente escribe con
        ``target[field.name] = value``, que en su ORM es un ``write()`` que se
        vacía solo. Aquí hay dos formas según lo que haya al final, porque
        Django las distingue:

        - un **valor**: ``setattr`` + ``save(update_fields=[...])``, la
          escritura mínima;
        - un **manager** del reverso de una FK: Django prohíbe la asignación
          directa y **nombra la salida en su propio error** — ``.set()``. Se
          usa ésa, que es la API que el stack declara para eso.
        """
        target, last_name = self.traverse_related(instance)
        if target is None:
            return
        #: ``:731`` verbatim — ambos reales o ambos nuevos.
        if bool(getattr(target, 'pk', None)) != bool(getattr(instance, 'pk',
                                                             None)):
            return
        held = getattr(type(target), last_name, None)
        if isinstance(held, NonStored):
            #: El extremo es otra proyección: su propio ``__set__`` decide si
            #: la cadena sigue. No se le puede pedir ``update_fields``, que es
            #: cosa de una columna.
            setattr(target, last_name, value)
            return
        current = getattr(target, last_name, None)
        if hasattr(current, 'set'):
            current.set(value)
            return
        setattr(target, last_name, value)
        target.save(update_fields=[last_name])

    def traverse_related(self, instance):
        """El registro anterior al último eslabón, y el nombre de ése — ≙
        ``Field.traverse_related`` (``odoo19c: fields.py:666``).

        Devuelve ``(None, nombre)`` cuando la cadena se corta antes de llegar,
        que es lo que deja al inverso sin destino donde escribir.
        """
        *path, last_name = self.related.split('.')
        target = instance
        for name in path:
            if target is None:
                return None, last_name
            target = getattr(target, name, None)
        return target, last_name

    def __delete__(self, instance):
        instance.__dict__.pop(self.name, None)

    # -- eje de esquema ----------------------------------------------------

    #: ≙ ``Field._column_type`` (``odoo19c: odoo/orm/fields.py:259``), que la
    #: fuente declara ``None`` y expone por la property ``column_type``
    #: (``:781``). Un campo sin columna **no tiene tipo de columna**: es lo
    #: mismo que dice el nombre de esta clase, escrito donde el eje de
    #: esquema lo lee.
    column_type = None

    def update_db(self, model, columns):
        """No hay columna que llevar a la tabla — ≙ el corte de
        ``Field.update_db`` (``odoo19c: odoo/orm/fields.py:1101``).

        La fuente abre con ``if not self.column_type: return False``, así que
        un campo sin columna sale por ahí y **nunca** alcanza los otros cuatro
        del eje (``update_db_column``, ``_convert_db_column``,
        ``update_db_notnull``, ``update_db_related``). Medido sobre todo
        ``odoo19c/odoo``: la única puerta a esa familia es ``update_db``
        (``models.py:3228``); los demás sólo se llaman desde su cuerpo o por
        ``super()`` en una subclase. Por eso aquí se porta **el corte**, no
        los cinco: declararlos sería inventar superficie que la fuente no
        expone por esta vía.

        Se declara en la clase por la misma razón que
        :meth:`inverse_related`: :class:`NonStored` **no desciende de
        ``models.Field``**, así que el enlace que ``orm.fields`` cuelga sobre
        él nunca lo alcanza. Sin este método un campo sin columna respondía
        ``AttributeError`` a una pregunta que la fuente contesta ``False``.
        """
        return False

    # -- protocolo de búsqueda ----------------------------------------------

    #: ``determine_domain`` lo instala :mod:`orm.fields` sobre esta clase, no
    #: se declara aquí: ``orm.fields`` importa a este módulo por la vía de
    #: ``fields_numeric``, así que el import inverso es un ciclo. Es la misma
    #: vía por la que ``type`` y ``relational`` llegan a ``models.Field``, y
    #: por la misma razón: el contrato de la fuente se comparte, la jerarquía
    #: del stack no.

    # -- resolución de la cadena related -----------------------------------

    def resolve_related(self, instance):
        """El valor del extremo de ``self.related``, navegando eslabón a
        eslabón — ≙ ``Field._compute_related`` (``odoo19c: :675``).

        **El eslabón vacío no revienta.** La fuente escribe
        ``next(iter(corecord), corecord)``: sobre un recordset vacío eso
        devuelve el propio vacío y la cadena sigue sin valor. Aquí el análogo
        es que un ``None`` corta el recorrido y el campo lee vacío, que es la
        misma conducta observable — una fila sin país no tiene código de país,
        y eso no es un error.
        """
        value = instance
        for name in self.related.split('.'):
            if value is None:
                return None
            value = getattr(value, name, None)
        return value

    # -- resolución del default --------------------------------------------

    def resolve_default(self, instance):
        """Llama al ``default`` con la instancia sólo si la acepta.

        La referencia pasa siempre ``self`` porque allá el ``default`` es un
        método del modelo. Aquí el mismo cómputo puede ser una función suelta
        que no necesita el registro —el caso de los que sólo miran la sesión—,
        y obligarla a aceptar un parámetro que ignora sería ruido en cada uno.
        Se inspecciona la firma una vez por lectura, que es barato frente a la
        consulta que el propio cómputo hace.
        """
        if not callable(self.default):
            return self.default
        try:
            firma = inspect.signature(self.default)
        except (TypeError, ValueError):
            # Invocable sin firma introspectable (builtin, C-extension): se
            # llama sin argumentos, que es la forma más común de ese caso.
            return self.default()
        if len(firma.parameters) >= 1:
            return self.default(instance)
        return self.default()


#: Centinela de «el declarante no dijo nada». Hace falta porque el defecto de
#: ``store`` **depende de si hay ``related``**: ``True`` en un campo normal y
#: ``False`` en una proyección (``odoo19c: odoo/orm/fields.py:455``). Un
#: default literal en la firma no puede expresar las dos cosas.
_UNSET = object()


def _declared_source_vocabulary(kwargs, related):
    """Saca de ``kwargs`` el vocabulario de la fuente, UNA vez.

    La fuente trabaja sobre **un** diccionario ``attrs`` que lee repetidas
    veces (``odoo19c: odoo/orm/fields.py:443-465``). Aquí el vocabulario llega
    en ``kwargs`` y hay que retirarlo antes de que lo vea el constructor de
    Django, así que se retira de golpe y los tres bloques leen del resultado.

    **Sacarlo bloque a bloque fue un defecto real**: el de ``compute`` corría
    primero y vaciaba ``copy``, ``readonly`` y ``compute_sudo``, así que el de
    ``related`` los leía siempre como no declarados y pisaba lo que el autor
    había escrito. Costó seis rojos en la suite —cuatro de escritura de
    related, uno de ``copy=False`` y uno de ``readonly=False``— y ninguno lo
    habría visto un subconjunto derivado por nombre de símbolo.

    ``copy`` es la excepción y por una razón medida: ``models.Field.__init__``
    **ya** lo acepta y lo anota (``orm/fields.py:900-910``), así que sobre un
    campo corriente tiene que seguir viajando en ``kwargs``. Sólo se retira
    cuando un bloque va a pisarlo.
    """
    declared = {
        'compute': kwargs.pop('compute', None),
        'inverse': kwargs.pop('inverse', None),
        'recursive': kwargs.pop('recursive', _UNSET),
        'precompute': kwargs.pop('precompute', _UNSET),
        'compute_sudo': kwargs.pop('compute_sudo', _UNSET),
        'related_sudo': kwargs.pop('related_sudo', _UNSET),
        'readonly': kwargs.pop('readonly', _UNSET),
        'store': kwargs.pop('store', _UNSET),
    }
    if declared['compute'] or related:
        declared['copy'] = kwargs.pop('copy', _UNSET)
    else:
        declared['copy'] = _UNSET
    return declared


def _apply_compute_block(declared, attrs):
    """El bloque ``compute`` de la fuente, verbatim.

    ≙ ``odoo19c: odoo/orm/fields.py:443-451``::

        if attrs.get('compute'):
            # by default, computed fields are not stored, computed in superuser
            # mode if stored, not copied (unless stored and explicitly not
            # readonly), and readonly (unless inversible)
            attrs['store'] = store = attrs.get('store', False)
            attrs['compute_sudo'] = attrs.get('compute_sudo', store)
            if not (attrs['store'] and not attrs.get('readonly', True)):
                attrs['copy'] = attrs.get('copy', False)
            attrs['readonly'] = attrs.get('readonly', not attrs.get('inverse'))

    La condición doblemente negada de ``copy`` tiene una sola rama que NO
    fuerza ``False``: con columna **y** ``readonly`` declarado falso. Sin un
    caso que la ejerza, esa rama no se distingue de las otras tres.
    """
    compute = declared['compute']
    attrs['compute'] = compute
    attrs['inverse'] = declared['inverse']
    if declared['recursive'] is not _UNSET:
        attrs['recursive'] = declared['recursive']
    if not compute:
        return attrs

    store = False if declared['store'] is _UNSET else declared['store']
    attrs['store'] = store
    attrs['compute_sudo'] = (store if declared['compute_sudo'] is _UNSET
                             else declared['compute_sudo'])
    readonly_default = True if declared['readonly'] is _UNSET else declared['readonly']
    if not (store and not readonly_default):
        attrs['copy'] = (False if declared['copy'] is _UNSET
                         else declared['copy'])
    elif declared['copy'] is not _UNSET:
        attrs['copy'] = declared['copy']
    attrs['readonly'] = (not declared['inverse']
                         if declared['readonly'] is _UNSET
                         else declared['readonly'])
    return attrs


def _apply_precompute_block(declared, attrs, many_to_many=False):
    """≙ ``odoo19c: odoo/orm/fields.py:459-465`` — avisa y desactiva.

    ``precompute`` sólo tiene efecto sobre un calculado (o un related, que es
    un calculado con otro nombre) **y** con columna. Fuera de ahí la fuente
    avisa y lo apaga; no lo acepta en silencio. El aviso no es decoración: sin
    él, un ``precompute=True`` sobre un campo sin cómputo se lee como que algo
    se adelanta, y no se adelanta nada.

    **El tercer caso es nuestro, y es de stack** (#313). Un muchos-a-muchos no
    se puede adelantar al ``INSERT`` porque su valor no vive en una columna de
    la fila: vive en una tabla intermedia que necesita el ``pk`` para tener a
    quién apuntar. La fuente no tiene el problema —su ORM asigna el id antes de
    ejecutar la cola de recálculo— y por eso declara ``tag_ids`` con
    ``precompute=True`` (``odoo19c: account_account.py:107``). Aquí se apaga
    con su aviso, que es la misma conducta que la fuente da a sus dos casos:
    decirlo, no tragárselo.
    """
    precompute = (False if declared['precompute'] is _UNSET
                  else declared['precompute'])
    if precompute:
        if not attrs.get('compute') and not attrs.get('related_declared'):
            warnings.warn(
                'precompute attribute does not make any sense on non computed '
                'field', stacklevel=4)
            precompute = False
        elif not attrs.get('store'):
            warnings.warn(
                'precompute attribute has no impact on non stored field',
                stacklevel=4)
            precompute = False
        elif many_to_many:
            warnings.warn(
                'precompute attribute has no impact on a many2many field: '
                'its join table needs the pk of a row that does not exist '
                'yet', stacklevel=4)
            precompute = False
    attrs['precompute'] = precompute
    return attrs


def apply_source_defaults(related, kwargs, many_to_many=False):
    """El bloque ``attrs`` de la fuente: lo que ``compute=`` y ``related=``
    implican sin declararse.

    ≙ ``odoo19c: odoo/orm/fields.py:443-465`` — tres bloques secuenciales sobre
    el mismo diccionario, en este orden: ``compute``, ``related``,
    ``precompute``. Se portan los tres.

    El de ``related``, verbatim::

        if attrs.get('related'):
            attrs['store'] = store = attrs.get('store', False)
            attrs['compute_sudo'] = attrs.get('compute_sudo',
                                              attrs.get('related_sudo', True))
            attrs['copy'] = attrs.get('copy', False)
            attrs['readonly'] = attrs.get('readonly', True)

    Los otros dos viven en :func:`_apply_compute_block` y
    :func:`_apply_precompute_block`, cada uno con su cita.

    ``store`` es el atributo que explica la forma del corpus: por defecto es
    ``True`` en un campo cualquiera y **``False``** tanto en un related como en
    un calculado. Medido sobre 3330 archivos ``models/*.py`` de ``odoo19c``: de
    las **3641** declaraciones con ``compute=``, **2368** no piden columna. El
    reparto de related lo publica ``scripts/census_related_fields.py``.

    **Se llamaba ``apply_related_defaults``.** El nombre describía la mitad que
    portaba; con las tres, mentiría.
    """
    declared = _declared_source_vocabulary(kwargs, related)
    attrs = {'related_declared': bool(related)}

    #: Orden de la fuente: ``compute``, luego ``related``, luego
    #: ``precompute``. Importa: los dos primeros escriben ``store`` y el
    #: segundo pisa al primero, que es lo que hace que un ``related=`` con
    #: ``compute=`` acabe con la forma del related.
    attrs = _apply_compute_block(declared, attrs)

    if related:
        related_sudo = (True if declared['related_sudo'] is _UNSET
                        else declared['related_sudo'])
        attrs.update({
            'store': (False if declared['store'] is _UNSET
                      else declared['store']),
            'compute_sudo': (related_sudo if declared['compute_sudo'] is _UNSET
                             else declared['compute_sudo']),
            'copy': False if declared['copy'] is _UNSET else declared['copy'],
            'readonly': (True if declared['readonly'] is _UNSET
                         else declared['readonly']),
        })
    elif not declared['compute']:
        attrs['store'] = (True if declared['store'] is _UNSET
                          else declared['store'])
        if declared['compute_sudo'] is not _UNSET:
            attrs['compute_sudo'] = declared['compute_sudo']
        if declared['readonly'] is not _UNSET:
            attrs['readonly'] = declared['readonly']

    attrs = _apply_precompute_block(declared, attrs, many_to_many)

    #: ``editable=False`` es la forma NATIVA de Django de decir «esto no lo
    #: escribe el cliente», y es la que DRF ya consume: ``get_field_kwargs``
    #: (``rest_framework/utils/field_mapping.py:124-128``) hace
    #: ``if ... or not model_field.editable: kwargs['read_only'] = True`` y
    #: retorna. Así el contrato del endpoint sale del riel del anfitrión, sin
    #: override en ningún serializer — el stack lo trae hecho.
    #:
    #: Aplica al calculado **y al related**, que es lo que la fuente declara
    #: para los dos (``:451`` y ``:458``, ambos ``readonly``). Una versión
    #: anterior lo restringía al calculado «para no cambiar el contrato de
    #: campos ya publicados»; la razón no se sostiene, pero **tampoco la
    #: medición con que se retiró**, y las dos quedan registradas porque el
    #: instrumento equivocado es el hallazgo:
    #:
    #: - se midió ``apps.get_models()`` y dio **0** campos con ``related``,
    #:   leído como «no hay contrato que proteger». Es un **falso negativo**:
    #:   un ``related`` sin ``store`` explícito sale ``NonStored``, que no
    #:   tiene columna y por tanto **no está en** ``_meta.get_fields()``. El
    #:   censo era ciego justo al objeto que buscaba;
    #:
    #: - por AST hay **12** declaraciones vivas —``res_bank`` ×4,
    #:   ``res_partner``, ``res_company``, ``res_config_settings`` ×5,
    #:   ``base_address_extended``—, no cero.
    #:
    #: Lo que hace correcta la propagación no es que no haya related vivos:
    #: es que la guarda exige ``store``, y **ninguna de las 12 declara
    #: ``store=True``**. La inyección no las alcanza hoy; alcanzará al primer
    #: related que pida columna, que es cuando la fuente dice que debe.
    if (attrs.get('readonly') and attrs.get('store')
            and 'editable' not in kwargs):
        kwargs['editable'] = False

    attrs.pop('related_declared', None)
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
    #: La salida temprana existe para NO tocar el campo corriente: sin
    #: ``related`` ni ``compute``, el diccionario trae sólo ``store`` y los
    #: defaults de clase (``orm/fields.py``) ya lo dicen. Anotar ahí pondría un
    #: atributo de instancia en cada uno de los miles de campos del árbol para
    #: repetir lo que la clase ya declara.
    #:
    #: Un calculado SÍ entra: su vocabulario es lo que
    #: :class:`~orm.registry._DerivedCollector` lee para unir el campo con el
    #: ``_depends`` de su método. Sin la anotación, ``field.compute`` sería
    #: ``None`` y el mapa saldría vacío — que es lo que el censo midió antes de
    #: este porte (44 métodos, 0 campos, 0 aristas).
    if not related and not attrs.get('compute'):
        return field
    for attribute, value in attrs.items():
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
    ``ResPartner`` —16 clases en el MRO, 17 campos sin columna— el recorrido son
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


def non_stored_fields(cls):
    """Los campos sin columna que ``cls`` declara, por nombre.

    Es la mitad que le faltaba a ``BaseModel._fields`` para ser el registro de
    la fuente y no el de las columnas. Allá ``_fields`` es el mapa que el ORM
    construye al cargar la clase, y en él entra **todo** campo declarado, tenga
    columna o no: un ``related`` sin ``store`` está ahí igual que un ``Char``.
    Aquí las columnas las publica ``_meta`` y los campos sin columna no — por
    diseño, porque un :class:`NonStored` no se registra en ``_meta``
    (:meth:`NonStored.contribute_to_class` lo dice explícitamente). Sin este
    recorrido el registro del modelo queda estrictamente más estrecho que el de
    la fuente, y quien lo consulte por un nombre que sí existe recibe un fallo
    en vez del campo (:ref:`h-api-1025`).

    Se recorre el **MRO entero** y no sólo el ``__dict__`` de ``cls``: un campo
    sin columna puede venir de una clase base o de la extensión que un addon
    cuelga con ``_inherit``, igual que allá. El recorrido va de la base a la
    derivada, así que la declaración más derivada gana — que es la resolución
    de atributo de Python, no un orden inventado aquí.

    Se lee ``vars(klass)`` y no ``getattr``: sobre la clase, un ``getattr``
    invoca ``NonStored.__get__``, que devuelve el descriptor sólo por
    convención del propio descriptor. El ``__dict__`` no depende de esa
    convención y ve también a un descriptor que no la siga.
    """
    cached = _REGISTRY_CACHE.get(cls)
    if cached is not None:
        return cached
    found = {}
    for klass in reversed(getattr(cls, '__mro__', (cls,))):
        for name, held in vars(klass).items():
            if isinstance(held, NonStored):
                found[name] = held
    #: De sólo lectura a propósito: el mapa se comparte entre lecturas, y un
    #: consumidor que lo mutara corrompería el registro de todos los demás.
    mapping = types.MappingProxyType(found)
    _REGISTRY_CACHE.put(cls, mapping)
    return mapping


def projection_or_none(related, kwargs, company_dependent=False, many_to_many=False):
    """El descriptor si la declaración es una proyección sin columna.

    Es el enrutador que comparten los constructores de campo. Devuelve la
    pareja ``(campo, atributos)``:

    - con ``related=`` y sin ``store`` —la forma de la inmensa mayoría de los
      que la referencia declara— devuelve el :class:`NonStored` **ya anotado**,
      y el constructor no llega a mirar sus propios argumentos;
    - en cualquier otro caso devuelve ``None`` y el constructor sigue su
      camino, anotando al final con :func:`annotate_related`.

    Por qué los argumentos del tipo se vuelven opcionales
    ======================================================

    Es lo que la referencia declara, no una comodidad de aquí::

        product_category = fields.Many2one(related='product_id.categ_id')
        tag_ids          = fields.Many2many(related='lead_id.tag_ids')
        subordinate_ids  = fields.One2many(related='employee_id.subordinate_ids')

    Ninguna nombra su comodelo: **el extremo de la cadena lo determina**. Y no
    hay dónde declararlo — un campo sin columna no tiene relación que definir;
    leerlo es navegar hasta lo que haya al final, sea un valor, un registro o
    un manager.

    Cuando la declaración **sí** pide columna, el comodelo vuelve a hacer
    falta y la referencia lo nombra::

        company_id = fields.Many2one(comodel_name='res.company',
                                     related='journal_id.company_id',
                                     store=True)

    Esa asimetría es el control que discrimina las dos ramas: si el enrutador
    devolviera siempre el descriptor, la rama con columna dejaría de existir
    sin que ningún caso lo notara.
    """
    related_attrs = apply_source_defaults(related, kwargs, many_to_many)
    if not related_attrs['store']:
        #: La exclusión vive AQUI y no en cada constructor porque es una
        #: contradicción de la declaración, no una decisión de rama: el
        #: enrutador es quien resuelve si hay columna, así que es el único
        #: sitio donde los dos hechos coinciden. Antes vivía después de la
        #: llamada, y con ``related=None`` nunca se alcanzaba — el enrutador
        #: devolvía el descriptor primero y la contradicción pasaba muda.
        if company_dependent:
            raise ValueError(
                'store=False y company_dependent=True son excluyentes: un '
                'campo sin columna no tiene jsonb donde repartir el valor.')
        return annotate_related(NonStored(**kwargs), related,
                                related_attrs), related_attrs
    return None, related_attrs

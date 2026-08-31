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

from django.db import models

__all__ = ['NonStored', 'projection_or_none']


class NonStored:
    """Descriptor de un campo declarado ``store=False``.

    Sigue el protocolo de ``contribute_to_class`` de Django para que funcione
    en los dos caminos por los que un atributo llega a un modelo: el cuerpo de
    la clase (``ModelBase`` lo invoca) y ``Model.add_to_class`` (el que usan
    las extensiones ``_inherit`` de este puerto). Sin él, el segundo camino
    dejaría el descriptor sin saber su propio nombre.
    """

    def __init__(self, *args, default=None, help_text='', search=None,
                 related=None, verbose_name=None, **_ignored):
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
        self.name = None

    # -- protocolo de nombre ------------------------------------------------

    def __set_name__(self, owner, name):
        """Camino del cuerpo de clase en una clase que NO es modelo Django."""
        self.name = name

    def contribute_to_class(self, cls, name, **_kwargs):
        """Camino de ``ModelBase`` y de ``add_to_class``.

        Django llama a este método en vez de ``setattr`` cuando el objeto lo
        declara. Aquí **no** se registra nada en ``_meta``: ese es justamente
        el punto — el campo no tiene columna.
        """
        self.name = name
        setattr(cls, name, self)

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


def apply_related_defaults(related, kwargs):
    """Los cuatro atributos que la fuente le da a un campo ``related=``.

    ≙ ``odoo19c: odoo/orm/fields.py:452-458``, verbatim::

        if attrs.get('related'):
            attrs['store'] = store = attrs.get('store', False)
            attrs['compute_sudo'] = attrs.get('compute_sudo',
                                              attrs.get('related_sudo', True))
            attrs['copy'] = attrs.get('copy', False)
            attrs['readonly'] = attrs.get('readonly', True)

    El primero es el que explica la forma del corpus: ``store`` por defecto es
    ``True`` en un campo cualquiera y **``False`` en un related**, así que de
    los que la referencia declara en los addons que este árbol porta, la gran
    mayoría **no lleva columna** (el reparto:
    ``python3 scripts/census_related_fields.py``). La prosa que los declinaba
    llamándolos
    «una copia que puede divergir» describía a los otros 45
    (:ref:`h-api-974`).

    **Los saca de ``kwargs``** y los devuelve en un diccionario. Los cuatro
    son del vocabulario de la fuente y el constructor de Django no los
    conoce: dejarlos dentro revienta con ``unexpected keyword argument``. Su
    hogar es el campo ya construido — lo hace :func:`annotate_related`.
    """
    declared_store = kwargs.pop('store', _UNSET)
    if not related:
        return {'store': True if declared_store is _UNSET else declared_store}
    declared_sudo = kwargs.pop('compute_sudo', _UNSET)
    if declared_sudo is _UNSET:
        declared_sudo = kwargs.pop('related_sudo', True)
    else:
        kwargs.pop('related_sudo', None)
    declared_copy = kwargs.pop('copy', _UNSET)
    declared_readonly = kwargs.pop('readonly', _UNSET)
    return {
        'store': False if declared_store is _UNSET else declared_store,
        'compute_sudo': declared_sudo,
        'copy': False if declared_copy is _UNSET else declared_copy,
        'readonly': True if declared_readonly is _UNSET else declared_readonly,
    }


def annotate_related(field, related, attrs):
    """Deja en el campo lo que la declaración dijo, para que sea greppeable.

    Los cuatro atributos son del vocabulario de la fuente y Django no los
    conoce, así que no viajan en su constructor: se anotan aquí. Sin la
    anotación el árbol no tendría con qué medir cuántos campos son una
    proyección — el mismo criterio con que ``translate`` se anota en vez de
    tragarse (``orm/fields_textual.py``).
    """
    field.related = related
    if not related:
        return field
    for attribute, value in attrs.items():
        setattr(field, attribute, value)
    #: El campo queda buscable por su cadena, que es lo que navegar la FK a
    #: mano no da — la razón por la que este mecanismo se porta en vez de
    #: declinarse (:ref:`h-api-974`). ``_search_related`` lo instala
    #: :mod:`orm.domains`; aquí se liga a esta instancia. Con ``store`` la
    #: búsqueda va por la columna propia, así que no se cablea (``:635``).
    if not attrs['store']:
        field.search = _bind_search_related(field)
    return field


def _bind_search_related(field):
    """``_search_related`` ligado a ``field`` — el invocable que ``search``
    espera: ``(records, operator, value) -> Domain``."""
    def search(records, operator, value):
        return models.Field._search_related(field, records, operator, value)
    return search


def projection_or_none(related, kwargs):
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
    related_attrs = apply_related_defaults(related, kwargs)
    if related and not related_attrs['store']:
        return annotate_related(NonStored(**kwargs), related,
                                related_attrs), related_attrs
    return None, related_attrs

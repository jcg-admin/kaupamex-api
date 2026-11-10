"""Campos textuales — fiel a ``odoo/orm/fields_textual.py`` (Odoo 19).

``Char``, ``Text`` y ``Html`` (Odoo ``Html``: ≈ ``TextField`` + saneo con
``dompurify`` en UI). Alias de nombre Odoo → clase Django (firma Django).

``store=False`` — el campo sin columna
=======================================

En la referencia un campo puede declararse sin persistencia:
``fields.Char(store=False, default=_get_algo)``
(``odoo19c: account/models/res_currency.py:17``). Django no lo tiene: todo
``models.Field`` es una columna.

Por eso ``Char`` no es un alias pelado sino un **despachador**: recibe el
vocabulario de la fuente, lo deriva y lo anota sobre el campo. El sitio de
declaración queda **idéntico al de la fuente**, que es el punto — la
alternativa era repartir en el cableado de cada addon lo que la referencia
declara en la clase.

Lo que el despachador **ya no hace es elegir clase** (TASK-API-0417): un
``Char`` sin columna sigue siendo un ``CharField``, porque ``store`` es un
atributo del campo y no un tipo (``odoo19c: odoo/orm/fields.py:455``). La
forma sin columna —sin columna en la tabla, sin accessor inverso, leída por
su ``compute`` o su ``default``— la resuelve la costura al contribuir a la
clase, no el constructor. Por la misma razón ``Text`` y ``Html`` reciben hoy
el vocabulario aunque la referencia no declare ninguno sin almacenar
(``grep -rn "Text(store=False"`` sobre ``odoo19c:`` da **0**): no es una rama
que haya que construirles, es la ausencia de rama.

``company_dependent`` — los tres lo llevan (tarea #129)
========================================================

Los tres tipos textuales están en ``COMPANY_DEPENDENT_FIELDS``, así que los
tres despachan: ``Char`` con su rama propia (tiene además ``store`` y
``translate``), ``Text`` con
:func:`~orm.fields_company_dependent.make_dispatcher`
y ``Html`` con un ``__new__`` — no puede ser una función porque
``tools/convert.py`` la usa en un ``isinstance`` (H-API-700).

``Html`` — identidad de clase sin cambiar la columna (H-API-700)
=================================================================

Hasta la tarea #554 ``Html`` era un alias pelado de ``TextField``: en runtime
un
campo HTML era indistinguible de un ``Text``, y ``Website._get_html_fields``
tenía que rodearlo parseando el fuente por AST. La referencia distingue el tipo
por catálogo — ``ttype = 'html'`` en ``ir.model.fields``
(``odoo19c: addons/website/models/website.py:1883-1908``) — y
:class:`Html` es aquí el equivalente mínimo que habilita ``isinstance``.

Dos invariantes deliberados:

- **La columna no cambia**: la clase no redefine ``db_type`` ni
  ``get_internal_type`` — sigue siendo ``TEXT``, como el alias.
- **La deconstrucción tampoco**: :meth:`Html.deconstruct` devuelve la ruta de
  ``django.db.models.TextField``, así que las migraciones ya generadas con el
  alias siguen siendo idénticas y ``makemigrations --check`` queda limpio.

El **saneo NO va en el campo** — sigue en la capa UI (``dompurify``), igual que
antes; la clase sólo aporta el tipo.
"""

import collections.abc
import json

from django.db import DEFAULT_DB_ALIAS, connections, models, router
from django.db.models.query_utils import DeferredAttribute

from orm.environments import env as current_env
from orm.fields_company_dependent import CompanyDependent, make_dispatcher
from orm.fields_nonstored import (
    _UNSET,
    annotate_related,
    apply_source_defaults,
)
from tools.misc import SENTINEL
from tools.sql import SQL, convert_column, convert_column_translatable

__all__ = ['Char', 'Text', 'Html', 'LangProxyDict', 'TranslatedChar',
           'TranslatedValue']

#: El idioma base de la fuente: el valor que todo campo traducible conserva
#: y al que cae la lectura sin traducción (``fields_textual.py:216-224``).
BASE_LANG = 'en_US'

Text = make_dispatcher('Text', 'text', models.TextField)


class Html(models.TextField):
    """``fields.Html`` — un ``TextField`` con identidad de tipo (H-API-700).

    ≙ ``odoo/orm/fields_textual.py`` clase ``Html`` de la referencia, reducida
    a lo que este árbol necesita: que ``isinstance(campo, Html)`` distinga un
    campo HTML de un ``Text`` en runtime. Sin saneo (capa UI) y sin columna
    propia (sigue ``TEXT``).
    """

    def __new__(cls, *args, company_dependent=False, related=None, **kwargs):
        """Despacha a ``CompanyDependent`` sin dejar de ser una clase.

        ``Html`` no puede ser una función como los otros ocho despachadores:
        ``tools/convert.py:969`` hace ``isinstance(campo, Html)`` para
        distinguir un campo HTML de un ``Text`` en runtime (H-API-700), y una
        función no es un tipo. La bifurcación va en ``__new__``, que sí la
        admite: cuando devuelve una instancia que **no** es de ``cls``, Python
        no llama a ``__init__`` — así el ``CompanyDependent`` queda construido
        por su propio constructor y no por el de ``TextField``.

        **La única rama que queda es ``company_dependent``.** ``store`` ya no
        elige clase: un ``Html`` sin columna sigue siendo un ``Html``
        (``odoo19c: odoo/orm/fields.py:455``). Por eso la derivación vive en
        :meth:`__init__`, que es el camino de la rama llana; aquí sólo se
        deriva la que no pasa por él, porque Python no llama a ``__init__``
        cuando ``__new__`` devuelve algo que no es de ``cls``.
        """
        if company_dependent:
            attrs = apply_source_defaults(
                related, kwargs, company_dependent=True
            )
            return annotate_related(
                CompanyDependent(*args, base_type='html', **kwargs),
                related,
                attrs,
            )
        return super().__new__(cls)

    def __init__(
        self,
        *args,
        company_dependent=False,
        related=None,
        store=_UNSET,
        **kwargs,
    ):
        """Deriva el vocabulario de la fuente y lo reenvía al constructor.

        **Reenvía en vez de tragar.** La versión anterior nombraba ``store`` y
        ``related`` sólo para que no llegaran al constructor de Django —y con
        eso nunca aterrizaban en ``_args__``, así que la costura veía un campo
        que no declaraba nada y le dejaba los defaults de clase. Hoy los
        reenvía: ``_field_init_with_copy`` los recoge y los retira él mismo
        (``orm/fields.py``), medido sobre los once tipos en la sonda
        ``probe_vocabulary_reaches_args_by_type``.
        """
        if store is not _UNSET:
            kwargs['store'] = store
        related_attrs = apply_source_defaults(related, kwargs)
        super().__init__(*args, **kwargs)
        annotate_related(self, related, related_attrs)

    def deconstruct(self):
        """Deconstruye como ``django.db.models.TextField``.

        Las migraciones existentes se generaron cuando ``Html`` era un alias de
        ``TextField``; conservar esa ruta evita que ``makemigrations`` proponga
        un ``AlterField`` por cada campo HTML del árbol (verificado con
        ``makemigrations --check --dry-run`` → *No changes detected*).
        """
        name, _path, args, kwargs = super().deconstruct()
        return name, 'django.db.models.TextField', args, kwargs


def Char(
    *args,
    store=_UNSET,
    required=None,
    translate=None,
    help=None,
    size=None,
    company_dependent=False,
    related=None,
    **kwargs,
):
    r"""``fields.Char`` — ≙ el de la referencia, con y sin columna.

    ``store=True`` (el defecto, y el de los 432 usos del árbol) devuelve un
    ``models.CharField`` con la firma de Django, exactamente como antes.

    ``store=False`` devuelve un campo **no persistido** cuyo valor sale de
    ``default`` al leerlo. No genera migración ni aparece en ``_meta``, que es
    lo que la referencia promete con esa bandera.

    Los tres alias de firma
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Añadidos 2026-08-14 para que el sitio de declaración se lea contra el de la
    fuente sin traducir nada (directiva del ejecutor sobre
    ``odoo19c: stock/models/product_strategy.py:12-13``)::

        name = fields.Char('Name', required=True, translate=True)

    ==============  =====================================================
    De la fuente    Aquí
    ==============  =====================================================
    ``required=``   ``blank=False``/``blank=True`` — el vacío de formulario
    ``help=``       ``help_text=``
    ``size=``       ``max_length=`` — la longitud de la columna ``varchar``
    ``translate=``  se **anota** en el campo; ver el aviso de abajo
    ==============  =====================================================

    ``size=`` es el cuarto alias, y no es cosmético: la referencia lo declara
    en **33** sitios (medido con ``grep -rhoP 'fields\.Char\([^)]*size\s*='``
    sobre ``odoo19c: addons`` y ``odoo``), y sin él cada uno de esos portes
    revienta con ``TypeError`` al construir el campo. Es el mismo nombre que
    ``_char_column_type`` ya traduce en el otro sentido
    (``orm/fields.py:1332``): allá ``('varchar', pg_varchar(self.size))``, aquí
    ``pg_varchar(self.max_length)``. Declararlo en la firma cierra el viaje de
    ida, que era el que faltaba.

    El primer argumento posicional ya coincidía: es ``verbose_name`` en Django
    y la etiqueta en la referencia.

    ``translate=True`` — una fila, un valor por idioma
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Cuarta rama del despachador (TASK-GEN-0060). Un traducible almacenado
    devuelve un :class:`TranslatedChar`: la columna es ``jsonb``
    ``{idioma: valor}``, como en la fuente
    (``odoo19c: odoo/orm/fields.py:783``),
    y leer el atributo da el valor del idioma activo con respaldo a ``en_US``.
    La bandera sigue en el campo (``field.translate``, ``:288``), así que el
    barrido de los campos traducibles sigue siendo un ``grep``.

    ``company_dependent=True`` — una fila, un valor por empresa
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tercera rama del despachador, con la firma de la fuente::

        barcode = fields.Char(company_dependent=True, max_length=64)

    Devuelve un :class:`~orm.fields_company_dependent.CompanyDependent`: la
    columna es ``jsonb`` con ``{empresa: valor}`` y leer el atributo da el
    valor de la empresa activa, o el default de ``ir.default``. Es lo que la
    referencia hace con el atributo homónimo de ``Field``
    (``odoo19c: odoo/orm/fields.py:291``, ``:783``).

    ``store=False`` y ``company_dependent=True`` son excluyentes, y la fuente
    también: un campo sin columna no tiene ``jsonb`` donde repartir el valor.
    """
    if required is not None:
        kwargs.setdefault('blank', not required)
    if help is not None:
        kwargs.setdefault('help_text', help)

    #: ``:452-458`` — un related NO se guarda por defecto, y un campo normal
    #: sí. El centinela distingue «no lo declaró» de «lo declaró ``True``»,
    #: que es lo que un default literal no puede: con ``store=True`` fijo,
    #: todo related habría salido con columna, y la forma de la gran mayoría
    #: se habría perdido: el reparto lo publica
    #: ``python3 scripts/census_related_fields.py``.
    if size is not None:
        kwargs['max_length'] = size
    if store is not _UNSET:
        kwargs['store'] = store
    related_attrs = apply_source_defaults(
        related, kwargs, company_dependent=company_dependent
    )
    store = related_attrs['store']

    if company_dependent:
        #: La exclusión ``store=False`` + ``company_dependent`` la levanta
        #: :func:`~orm.fields_nonstored.apply_source_defaults`, que es donde
        #: vive su única copia. Aquí quedan las dos que son de ``Char``.
        if translate:
            raise ValueError('company_dependent field cannot be translated')
        # La guarda de ``required`` va AQUI y no en ``CompanyDependent``: para
        # cuando el campo se construye, ``required`` ya se tradujo a ``blank``
        # arriba y el parametro no llega. Lo destapo su propio test —el
        # constructor tenia la comprobacion y nunca disparaba—.
        if required:
            raise ValueError('company_dependent field cannot be required')
        campo = CompanyDependent(*args, base_type='char', **kwargs)
    elif translate and store:
        #: ``fields.py:783`` — un traducible almacenado es una columna
        #: ``jsonb`` ``{idioma: valor}``. Ver :class:`TranslatedChar`.
        campo = TranslatedChar(*args, **kwargs)
    else:
        #: El ``CharField`` se construye con columna y sin ella. ``store`` es
        #: atributo del campo, no una clase distinta: la forma sin columna la
        #: resuelve la costura al contribuir a la clase (TASK-API-0417).
        campo = models.CharField(*args, **kwargs)
    campo.translate = bool(translate)
    return annotate_related(campo, related, related_attrs)


class LangProxyDict(collections.abc.MutableMapping):
    """Una vista de un idioma sobre la caché de un campo traducible.

    ≙ ``LangProxyDict`` (``odoo19c: odoo/orm/fields_textual.py:706-777``).
    Docstring de la fuente: *"A view on a dict[id, dict[lang, value]] that maps
    id to value given a fixed language."*

    El almacén real es ``{id: {idioma: valor}}``; esta clase lo presenta como
    ``{id: valor}`` para un idioma fijo, así que el resto del ORM lee y escribe
    la caché de un campo traducible sin saber que hay un nivel más.

    La regla de respaldo, que es su única lógica
    =============================================

    Cuando el valor **no está en base ni se calcula** —campo sin columna, o
    registro nuevo sin origen— el idioma pedido puede no existir en el mapa, y
    la fuente cae a ``en_US``. Cuando **sí** está en base, no cae: pedir un
    idioma ausente es un ``KeyError``, porque ahí el respaldo lo resuelve la
    consulta y no la caché.

    La fuente escribe esa condición **tres veces inline** —en :meth:`get`, en
    :meth:`__getitem__` y en :meth:`__setitem__`—; aquí sale una vez a
    :meth:`_falls_back`. Es la única diferencia de forma con la fuente, y la
    pide ``calibration-verified-numbers.md``: tres copias de la misma regla son
    tres fuentes de verdad que nadie sincroniza.

    ``key or key.origin`` distingue el registro guardado del recién creado: un
    id real es verdadero; un :class:`~orm.identifiers.NewId` sin origen es
    falso y no tiene fila que consultar.

    **Todavía no tiene consumidor en este árbol.** La columna ``jsonb`` por
    idioma ya existe (:class:`TranslatedChar`, TASK-GEN-0060), pero el idioma
    lo resuelve el descriptor sobre el mapa de la fila y no la caché del ORM:
    es la divergencia de mecanismo declarada en esa sección. El eje completo
    de traducción del ORM es TASK-GEN-0436. La clase se porta entera contra
    su contrato.
    """

    __slots__ = ('_cache', '_field', '_lang')

    def __init__(self, field, cache, lang):
        super().__init__()
        self._field = field
        self._cache = cache
        self._lang = lang

    def _falls_back(self, key):
        """¿Cae a ``en_US`` este id? — la condición que la fuente repite tres
        veces: el valor no se calcula y no está en base."""
        return not (
            self._field.compute or (self._field.store and (key or key.origin))
        )

    def get(self, key, default=None):
        # sólo por rendimiento, como la fuente
        vals = self._cache.get(key, SENTINEL)
        if vals is SENTINEL:
            return default
        if vals is None:
            return None
        if self._falls_back(key):
            return vals.get(self._lang, vals.get('en_US', default))
        return vals.get(self._lang, default)

    def __getitem__(self, key):
        vals = self._cache[key]
        if vals is None:
            return None
        if self._falls_back(key):
            return vals.get(self._lang, vals.get('en_US'))
        return vals[self._lang]

    def __setitem__(self, key, value):
        if value is None:
            self._cache[key] = None
            return
        vals = self._cache.get(key)
        if vals is None:
            # el id no está en caché, o lo está como ``{id: None}``
            self._cache[key] = vals = {self._lang: value}
        else:
            vals[self._lang] = value
        if self._falls_back(key):
            # sin fila que consultar, la caché tiene que llevar el valor de
            # respaldo para los demás idiomas
            vals.setdefault('en_US', value)

    def __delitem__(self, key):
        vals = self._cache.get(key)
        if vals:
            vals.pop(self._lang, None)

    def __iter__(self):
        for key, vals in self._cache.items():
            if vals is None or self._lang in vals:
                yield key

    def __len__(self):
        return sum(1 for _ in self)

    def clear(self):
        for vals in self._cache.values():
            if vals:
                vals.pop(self._lang, None)

    def __repr__(self):
        return (
            f"<LangProxyDict lang={self._lang!r} "
            f"size={len(self._cache)} at {hex(id(self))}>"
        )


def _textual_convert_to_column(
    self, value, record, values=None, validate=True
):
    """
    ``Char.convert_to_column`` — ≙ ``odoo19c:
    odoo/orm/fields_textual.py:84-85``.

    Delega en ``convert_to_cache``, que es donde la fuente pone el recorte a
    ``size`` y el descarte del valor vacío. Cubre también ``Selection``: la
    fuente las declara como dos clases (``:84`` y
    ``fields_selection.py:223-226``) y este stack lleva ambas al mismo
    ``models.CharField``, así que una sola sobrecarga porta las dos — sus
    cuerpos terminan en el mismo sitio, ``convert_to_cache`` y luego la base.
    """
    return self.convert_to_cache(value, record, validate)


def _textual_convert_to_cache(self, value, record, validate=True):
    """
    ``Char.convert_to_cache`` — ≙ ``odoo19c:
    odoo/orm/fields_textual.py:102-113``.

    Cuatro pasos, en el orden de la fuente: ``None`` y ``False`` se descartan
    **por identidad** —la cadena vacía sobrevive, y es un valor distinto de la
    ausencia—; ``bytes`` se decodifica; lo demás se lleva a texto; y el
    resultado se recorta al tamaño declarado.

    El tamaño lo declara ``max_length`` en este stack, que es donde la fuente
    pone ``self.size``. Un ``TextField`` no lo declara y entonces no recorta,
    igual que el ``Text`` de la fuente.
    """
    if value is None or value is False:
        return None
    text = value.decode() if isinstance(value, bytes) else str(value)
    size = getattr(self, 'max_length', None)
    return text[:size] if size else text


models.CharField.convert_to_cache = _textual_convert_to_cache
models.TextField.convert_to_cache = _textual_convert_to_cache


models.CharField.convert_to_column = _textual_convert_to_column
models.TextField.convert_to_column = _textual_convert_to_column


# ===========================================================================
# ``translate=True`` — una fila, un valor por idioma (TASK-GEN-0060)
# ===========================================================================
#
# ≙ la rama ``translate`` de ``BaseString`` (``odoo19c: odoo/orm/
# fields_textual.py``) y la columna ``jsonb`` de ``Field.column_type``
# (``odoo19c: odoo/orm/fields.py:783``). Es el mismo patrón que
# :class:`~orm.fields_company_dependent.CompanyDependent` con la clave del
# idioma en lugar de la empresa: el atributo interno guarda el mapa y el
# público entrega el valor del idioma activo.
#
# Divergencia de mecanismo, declarada: la fuente resuelve el idioma en su
# caché (``_get_cache_impl`` con :class:`LangProxyDict`, ``:226-231``); aquí el
# descriptor lo resuelve sobre el mapa de la fila, como hace el campo
# dependiente de empresa con la empresa. Los términos (``translate``
# invocable, ``:70-196``) no tienen consumidor: el despachador lleva
# ``translate`` a ``bool``, así que ningún campo del árbol los declara.


def _fallback_langs(lang):
    """≙ ``get_translation_fallback_langs`` (``:216-224``) sobre un código."""
    if lang == '_en_US':
        return ('_en_US', 'en_US')
    if lang == 'en_US':
        return ('en_US',)
    if lang.startswith('_'):
        return (lang, lang[1:], '_en_US', 'en_US')
    return (lang, 'en_US')


class TranslatedValue(models.Func):
    """El texto del idioma activo con respaldo — ≙ la rama de ``to_sql``
    (``fields_textual.py:394-402``) para una consulta de Django.

    ``COALESCE(col->>idioma, col->>'en_US')``. La usan los lookups de texto,
    ``order_to_django`` y el ``Meta.ordering`` de los modelos que ordenan por
    un campo traducible: sin ella, un filtro compararía la columna ``jsonb``
    con ``'"Kg"'`` (no da error y no casa nada) y un orden seguiría el
    ``jsonb`` crudo y no el texto.

    Recibe el nombre del campo o una expresión, y toma el campo del ``Col``
    ya resuelto: así es serializable en una migración
    (``TranslatedValue('name').asc()`` en ``Meta.ordering``).
    """

    output_field = models.TextField()

    def __init__(self, expression, **extra):
        if isinstance(expression, str):
            expression = models.F(expression)
        super().__init__(expression, **extra)

    def as_sql(self, compiler, connection, **extra_context):
        source = self.source_expressions[0]
        field = getattr(source, 'target', None) or source.output_field
        column, params = compiler.compile(source)
        langs = field.get_translation_fallback_langs(current_env())
        parts, all_params = [], []
        for lang in langs:
            parts.append(f'({column})->>%s')
            all_params.extend([*params, lang])
        if len(parts) == 1:
            return parts[0], all_params
        return f"COALESCE({', '.join(parts)})", all_params


#: Los lookups de texto que comparan el valor del idioma. ``isnull`` y los de
#: clave de ``JSONField`` (``has_key``…) siguen sobre la columna: preguntan
#: por el mapa, no por el texto.
_TEXT_LOOKUPS = frozenset({
    'exact', 'iexact', 'contains', 'icontains', 'in', 'gt', 'gte', 'lt',
    'lte', 'startswith', 'istartswith', 'endswith', 'iendswith', 'regex',
    'iregex', 'like', 'ilike',
})

_translated_lookups = {}


def _translated_lookup(base):
    """El lookup de texto ``base`` aplicado al valor del idioma activo."""
    if base in _translated_lookups:
        return _translated_lookups[base]

    class TranslatedLookup(base):
        def __init__(self, lhs, rhs):
            super().__init__(TranslatedValue(lhs), rhs)

    TranslatedLookup.__name__ = f'Translated{base.__name__}'
    TranslatedLookup.__qualname__ = TranslatedLookup.__name__
    _translated_lookups[base] = TranslatedLookup
    return TranslatedLookup


class _TranslatedMerge:
    """El lado derecho del ``SET`` de un ``UPDATE`` por idioma — ≙ la rama
    ``translate`` de ``_write_multi`` (``odoo19c: odoo/orm/models.py:
    4564-4576``)."""

    def __init__(self, field, value):
        self.field = field
        self.value = value

    def as_sql(self, compiler, connection):
        env = current_env()
        lang = self.field.translation_lang(env)
        new = {lang: self.value}
        if lang != 'en_US' and not env['res.lang']._get_data(code='en_US'):
            new[BASE_LANG] = self.value
        column = connection.ops.quote_name(self.field.column)
        return (f'COALESCE({column}, %s::jsonb) || %s::jsonb',
                [json.dumps({BASE_LANG: self.value}), json.dumps(new)])


class _TranslatedAttribute(DeferredAttribute):
    """La indirección por idioma — ≙ ``convert_to_record`` (``:117-123``) y
    ``write`` (``:288-325``) para ``translate=True``."""

    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        field = self.field
        if field.attname in instance.__dict__:
            stored = instance.__dict__[field.attname]
        else:
            stored = super().__get__(instance, cls)
        return field.translated_value(
            stored, field.translation_lang(current_env()))

    def __set__(self, instance, value):
        field = self.field
        # El mapa crudo —lo que Django asigna al hidratar la fila— y el vacío
        # pasan tal cual: ``False``/``None`` vacían la columna, como
        # ``super().write`` en la fuente (``:289-291``).
        if value is None or value is False or isinstance(value, dict):
            instance.__dict__[field.attname] = value or None
            return
        value = field.convert_to_cache(value, instance)
        env = current_env()
        lang = field.translation_lang(env)
        stored = instance.__dict__.get(field.attname)
        if not stored:
            # ``convert_to_column_insert`` (``:84-91``).
            instance.__dict__[field.attname] = {BASE_LANG: value, lang: value}
            return
        stored = {**stored, lang: value}
        # ``:322-324`` — sin ``en_US`` activo se escribe también, para que su
        # valor siga siendo significativo.
        if lang != 'en_US' and not env['res.lang']._get_data(code='en_US'):
            stored[BASE_LANG] = value
        instance.__dict__[field.attname] = stored


class TranslatedChar(models.JSONField):
    """``fields.Char(translate=True)`` — la columna ``jsonb`` por idioma."""

    #: ≙ ``Char.type`` — el tipo de la fuente, que ``type_for`` publica.
    type = 'char'
    #: ≙ ``BaseString.translate`` (``fields_textual.py:35``).
    translate = True

    #: Ver :meth:`CompanyDependent.get_attname`: la columna lleva el mapa y
    #: el atributo público el valor de un idioma; sin separarlos,
    #: ``refresh_from_db`` copiaría el escalar sobre el mapa.
    RAW_ATTNAME_SUFFIX = '_translations'

    def __init__(self, *args, **kwargs):
        kwargs.pop('translate', None)
        super().__init__(*args, **kwargs)

    def _check_default(self):
        """Un default escalar es válido: :meth:`get_default` lo entrega como
        mapa nuevo en cada llamada, así que no hay instancia compartida."""
        if self.has_default() and isinstance(self.default, str):
            return []
        return super()._check_default()

    def get_default(self):
        """El default de la fuente es el VALOR (``fields.Char(default='')``);
        la columna guarda el mapa, así que se entrega como lo haría un alta:
        ``{'en_US': valor, idioma: valor}`` (``convert_to_column_insert``,
        ``:84-91``)."""
        value = super().get_default()
        if value is None or isinstance(value, dict):
            return value
        value = self.convert_to_cache(value, None)
        if value is None:
            return None
        lang = self.translation_lang(current_env())
        return {BASE_LANG: value, lang: value}

    def get_attname(self):
        return f'{self.name}{self.RAW_ATTNAME_SUFFIX}'

    def set_attributes_from_name(self, name):
        super().set_attributes_from_name(name)
        self.column = self.db_column or self.name

    def contribute_to_class(self, cls, name, private_only=False):
        super().contribute_to_class(cls, name, private_only=private_only)
        setattr(cls, self.name, _TranslatedAttribute(self))

    def get_lookup(self, lookup_name):
        """Los lookups de texto comparan el valor del idioma activo."""
        if lookup_name in _TEXT_LOOKUPS:
            base = models.CharField.get_lookups().get(lookup_name)
            if base is not None:
                return _translated_lookup(base)
        return super().get_lookup(lookup_name)

    def translation_lang(self, env):
        """≙ ``translation_lang`` (``:213-214``)."""
        return env.lang or 'en_US'

    def get_translation_fallback_langs(self, env):
        """≙ ``get_translation_fallback_langs`` (``:216-224``)."""
        return _fallback_langs(self.translation_lang(env))

    def translated_value(self, stored, lang):
        """El valor de ``lang`` con su respaldo; ``None`` sin mapa."""
        if not stored:
            return None
        for candidate in _fallback_langs(lang):
            if candidate in stored:
                return stored[candidate]
        return None

    def raw_translations(self, record):
        """El mapa crudo ``{idioma: valor}`` de la fila."""
        return record.__dict__.get(self.attname) or {}

    def _get_stored_translations(self, record):
        """≙ ``_get_stored_translations`` (``:198-211``) — el mapa guardado,
        leído de la base y no de la fila en memoria."""
        query = SQL('SELECT %s FROM %s WHERE id = %s',
                    SQL.identifier(self.column),
                    SQL.identifier(type(record)._meta.db_table),
                    record.pk)
        with connections[router.db_for_read(type(record))].cursor() as cr:
            cr.execute(query.code, query.params)
            row = cr.fetchone()
        value = row[0] if row else None
        if isinstance(value, str):
            value = json.loads(value)
        return value

    def get_db_prep_save(self, value, connection):
        """Un texto en un ``UPDATE`` masivo escribe sólo su idioma.

        ``QuerySet.update(campo='x')`` no pasa por el descriptor; la fuente
        resuelve esa escritura en ``_write_multi`` con
        ``COALESCE(col, {'en_US': v}) || {idioma: v}`` (``odoo19c:
        odoo/orm/models.py:4564-4576``), que conserva los demás idiomas. El
        mapa (``dict``) y las expresiones siguen el camino de ``JSONField``.
        """
        if isinstance(value, (str, bytes)):
            return _TranslatedMerge(self, self.convert_to_cache(value, None))
        return super().get_db_prep_save(value, connection)

    def pre_save(self, model_instance, add):
        return model_instance.__dict__.get(self.attname)

    def value_from_object(self, obj):
        return self.raw_translations(obj)

    def get_prep_value(self, value):
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError(
                f'{self.name!r} guarda un mapa por idioma; recibió'
                f' {type(value).__name__}. Asigne por el atributo para'
                ' escribir el valor del idioma activo.')
        return value


TranslatedChar.convert_to_cache = _textual_convert_to_cache


def _string_convert_db_column(self, model, column, cr=None):
    """≙ ``BaseString._convert_db_column`` (``:64-68``).

    Hacia o desde una columna traducible pasa por
    :func:`~tools.sql.convert_column_translatable`, que deja el texto bajo
    ``en_US``; el resto, por :func:`~tools.sql.convert_column`.

    Divergencia declarada: el cursor opcional. Aquí el esquema lo evoluciona
    la migración sobre la conexión de su alias
    (:class:`~orm.migration_operations.ConvertColumnTranslatable`), y la base
    por empresa no es la ``default``.
    """
    table = model._meta.db_table
    column_type = self.column_type[1]

    def convert(cursor):
        if self.translate or column['udt_name'] == 'jsonb':
            convert_column_translatable(cursor, table, self.column,
                                        column_type)
        else:
            convert_column(cursor, table, self.column, column_type)

    if cr is not None:
        convert(cr)
        return
    with connections[DEFAULT_DB_ALIAS].cursor() as cursor:
        convert(cursor)


models.CharField._convert_db_column = _string_convert_db_column
models.TextField._convert_db_column = _string_convert_db_column
TranslatedChar._convert_db_column = _string_convert_db_column

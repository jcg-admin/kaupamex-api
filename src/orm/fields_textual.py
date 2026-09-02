"""Campos textuales — fiel a ``odoo/orm/fields_textual.py`` (Odoo 19).

``Char``, ``Text`` y ``Html`` (Odoo ``Html``: ≈ ``TextField`` + saneo con
``dompurify`` en UI). Alias de nombre Odoo → clase Django (firma Django).

``store=False`` — el campo sin columna
=======================================

En la referencia un campo puede declararse sin persistencia:
``fields.Char(store=False, default=_get_algo)``
(``odoo19c: account/models/res_currency.py:17``). Django no lo tiene: todo
``models.Field`` es una columna.

Por eso ``Char`` no es un alias pelado sino un **despachador**: con ``store``
por defecto devuelve el ``CharField`` de siempre, y con ``store=False``
devuelve un :class:`~orm.fields_nonstored.NonStored`. El sitio de declaración
queda **idéntico al de la fuente**, que es el punto — la alternativa era
repartir en el cableado de cada addon lo que la referencia declara en la clase.

``Text`` y ``Html`` **no** llevan el despachador de ``store``: ``grep -rn
"Text(store=False\\|Html(store=False)"`` sobre ``odoo19c:`` da **0** — la
referencia no declara ninguno sin almacenar, así que darles esa rama sería
construir para un caso que no existe.

``company_dependent`` — los tres lo llevan (tarea #129)
========================================================

Los tres tipos textuales están en ``COMPANY_DEPENDENT_FIELDS``, así que los
tres despachan: ``Char`` con su rama propia (tiene además ``store`` y
``translate``), ``Text`` con :func:`~orm.fields_company_dependent.make_dispatcher`
y ``Html`` con un ``__new__`` — no puede ser una función porque
``tools/convert.py`` la usa en un ``isinstance`` (H-API-700).

``Html`` — identidad de clase sin cambiar la columna (H-API-700)
=================================================================

Hasta la tarea #554 ``Html`` era un alias pelado de ``TextField``: en runtime un
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
from django.db import models

from orm.fields_company_dependent import CompanyDependent, make_dispatcher
from orm.fields_nonstored import (
    _UNSET,
    NonStored,
    annotate_related,
    apply_source_defaults,
    projection_or_none,
)

__all__ = ['Char', 'Text', 'Html']

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
        """
        projection, _attributes = projection_or_none(related, kwargs,
                                                     company_dependent)
        if projection is not None:
            return projection
        if company_dependent:
            return CompanyDependent(*args, base_type='html', **kwargs)
        instance = super().__new__(cls)
        instance.related = related
        return instance

    def __init__(self, *args, company_dependent=False, related=None,
                 store=None, **kwargs):
        """Traga las dos palabras clave — las ramas las resolvió
        :meth:`__new__`, y nombrarlas evita que caigan en ``**kwargs`` y
        lleguen al constructor de Django, que no las conoce."""
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        """Deconstruye como ``django.db.models.TextField``.

        Las migraciones existentes se generaron cuando ``Html`` era un alias de
        ``TextField``; conservar esa ruta evita que ``makemigrations`` proponga
        un ``AlterField`` por cada campo HTML del árbol (verificado con
        ``makemigrations --check --dry-run`` → *No changes detected*).
        """
        name, _path, args, kwargs = super().deconstruct()
        return name, 'django.db.models.TextField', args, kwargs


def Char(*args, store=_UNSET, required=None, translate=None, help=None,
         company_dependent=False, related=None, **kwargs):
    """``fields.Char`` — ≙ el de la referencia, con y sin columna.

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
    ``translate=``  se **anota** en el campo; ver el aviso de abajo
    ==============  =====================================================

    El primer argumento posicional ya coincidía: es ``verbose_name`` en Django
    y la etiqueta en la referencia.

    .. warning:: ``translate=True`` todavía no traduce nada.

       La referencia almacena el campo traducible como **columna ``jsonb``**
       ``{lang: valor}`` y resuelve el idioma en el ORM
       (``odoo19c: odoo/orm/fields_textual.py:53`` — ``if self.store and
       self.translate``; ``:66`` — ``column['udt_name'] == 'jsonb'``). Aquí la
       bandera **se conserva en el campo** (``field.odoo_translate``) para que
       la declaración sea fiel y greppeable, pero el almacenamiento por idioma
       no está construido: hoy la columna sigue siendo ``varchar`` y guarda un
       solo idioma.

       Anotarla en vez de aceptarla y tirarla es deliberado: un ``**kwargs``
       que se traga la bandera deja el árbol sin forma de medir cuántos campos
       esperan traducción. Con la anota, el barrido es un ``grep``.

       Almacenamiento ``jsonb`` + resolución por idioma: tarea **#333**.

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
    if store is not _UNSET:
        kwargs['store'] = store
    related_attrs = apply_source_defaults(related, kwargs)
    store = related_attrs['store']

    if company_dependent:
        if not store:
            raise ValueError(
                'store=False y company_dependent=True son excluyentes: un '
                'campo sin columna no tiene jsonb donde repartir el valor.')
        if translate:
            raise ValueError('company_dependent field cannot be translated')
        # La guarda de ``required`` va AQUI y no en ``CompanyDependent``: para
        # cuando el campo se construye, ``required`` ya se tradujo a ``blank``
        # arriba y el parametro no llega. Lo destapo su propio test —el
        # constructor tenia la comprobacion y nunca disparaba—.
        if required:
            raise ValueError('company_dependent field cannot be required')
        campo = CompanyDependent(*args, base_type='char', **kwargs)
    elif store:
        campo = models.CharField(*args, **kwargs)
    else:
        campo = NonStored(*args, **kwargs)
    campo.odoo_translate = bool(translate)
    return annotate_related(campo, related, related_attrs)

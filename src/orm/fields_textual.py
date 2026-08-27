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

``Text`` sigue siendo alias directo y ``Html`` es una **subclase** con identidad
propia (H-API-700); ninguno lleva el despachador de ``store``: ``grep -rn
"Text(store=False\\|Html(store=False)"`` sobre ``odoo19c:`` da **0** — la
referencia no declara ninguno sin almacenar, así que darles el despachador
sería construir para un caso que no existe.

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

from orm.fields_nonstored import NonStored

__all__ = ['Char', 'Text', 'Html']

Text = models.TextField


class Html(models.TextField):
    """``fields.Html`` — un ``TextField`` con identidad de tipo (H-API-700).

    ≙ ``odoo/orm/fields_textual.py`` clase ``Html`` de la referencia, reducida
    a lo que este árbol necesita: que ``isinstance(campo, Html)`` distinga un
    campo HTML de un ``Text`` en runtime. Sin saneo (capa UI) y sin columna
    propia (sigue ``TEXT``).
    """

    def deconstruct(self):
        """Deconstruye como ``django.db.models.TextField``.

        Las migraciones existentes se generaron cuando ``Html`` era un alias de
        ``TextField``; conservar esa ruta evita que ``makemigrations`` proponga
        un ``AlterField`` por cada campo HTML del árbol (verificado con
        ``makemigrations --check --dry-run`` → *No changes detected*).
        """
        name, _path, args, kwargs = super().deconstruct()
        return name, 'django.db.models.TextField', args, kwargs


def Char(*args, store=True, required=None, translate=None, help=None, **kwargs):
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
    """
    if required is not None:
        kwargs.setdefault('blank', not required)
    if help is not None:
        kwargs.setdefault('help_text', help)

    campo = models.CharField(*args, **kwargs) if store else NonStored(*args, **kwargs)
    campo.odoo_translate = bool(translate)
    return campo

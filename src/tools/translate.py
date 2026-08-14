"""i18n — fiel a ``odoo/tools/translate.py`` (Odoo 18/19).

Odoo expone ``_`` (y ``_lt``) desde ``odoo/tools/translate.py``. Aquí, con el
prefijo ``odoo.`` eliminado (convención del proyecto: ``tools`` ≙
``odoo/tools``), un addon escribe ``from tools.translate import _`` — leyendo
como su fuente Odoo (``from odoo.tools.translate import _``).

**La firma lleva argumentos de formato, y eso no es cosmético.** La referencia
declara ``__call__(self, source: str, *args, **kwargs)``
(``odoo19c: odoo/tools/translate.py:676``) y sustituye con ``translation %
args`` **después** de traducir (``:447``), para que el traductor pueda reordenar
los marcadores en su idioma. Django no trae esa forma: ``gettext_lazy`` sólo
acepta el mensaje, así que ``_('Delay on %s', rule.name)`` levantaba
``TypeError: gettext() takes 1 positional argument but 2 were given`` — un
fallo que sólo se ve al ejecutar la rama, no al importar el módulo.

Se construye el mecanismo sobre ``django.utils.functional.lazy`` en vez de
adaptar cada sitio a ``_('…') % args``:

- **Preserva la pereza.** ``gettext_lazy('…') % args`` evalúa de inmediato
  (medido: devuelve ``str``, no un proxy), así que un mensaje declarado a nivel
  de módulo o de clase se traduciría con el idioma del arranque, no con el de
  la petición. Con ``lazy()`` la traducción y la sustitución ocurren juntas, al
  convertir a texto.
- **Traduce antes de sustituir**, como la referencia: lo que se busca en el
  catálogo es la plantilla con sus marcadores, no el texto ya rellenado.

Lo que **no** se porta de la referencia, y por qué:

- ``LazyGettext`` como clase pública y su alias ``_lt`` (``:585``, ``:681``) —
  0 consumidores en este árbol (medido con ``grep -rn '_lt('``: la única
  aparición es una mención en un docstring de ``base_iban``). El ``_`` de aquí
  **ya es perezoso**, que es la propiedad por la que existe ``_lt``.
- El escape de ``Markup`` y el ``format_list`` de argumentos iterables
  (``:432``, ``:439``) — dependen de ``markupsafe`` y del vocabulario de QWeb,
  ninguno presente. El ``assert not (args and kwargs)`` de la fuente (``:610``)
  sí se conserva: es lo que impide mezclar las dos formas de sustitución.
"""
from django.utils.functional import lazy
from django.utils.translation import gettext

__all__ = ['_']


def _translate_and_format(source, args, kwargs):
    """Traduce ``source`` y sólo entonces sustituye — el orden de la fuente."""
    translation = gettext(source)
    if args:
        return translation % args
    if kwargs:
        return translation % kwargs
    return translation


_lazy_translate = lazy(_translate_and_format, str)


def _(source, *args, **kwargs):
    """≙ ``get_text_alias.__call__`` (``odoo19c: odoo/tools/translate.py:676``).

    :param source: el mensaje con sus marcadores, tal cual va al catálogo.
    :param args: argumentos posicionales de ``%``; excluyentes con ``kwargs``.
    :param kwargs: argumentos nombrados de ``%(nombre)s``.
    :return: un texto perezoso — se traduce y se formatea al convertirlo a
        ``str``, no al declararlo.
    """
    assert not (args and kwargs)
    return _lazy_translate(source, args, kwargs)

"""``ir.http`` extendido por ``html_editor`` — las tres banderas de edición.

Adaptación de ``odoo19c: addons/html_editor/models/ir_http.py``
(27 líneas, LGPL-3 — copia + adaptación con atribución, DEC-KX-03).

**4 símbolos en la fuente, 4 portados, 0 ausentes.** La constante
``CONTEXT_KEYS`` y los tres métodos de clase.

Qué hace
========

Tres banderas viajan en la *query string* y encienden el modo de edición:
``?editable``, ``?edit_translations`` y ``?translatable``. Este archivo las
lee del despacho y las deja donde el renderizado las pueda consultar; sin él,
pedir ``?editable`` no tendría efecto ninguno.

Y añade ``html_editor`` a la lista de módulos cuyas traducciones el cliente
descarga en el frontend: el editor tiene su propia interfaz y necesita sus
cadenas.

Qué pieza de este stack cubre cada delegación de la fuente
==========================================================

===============================  =====================================
Fuente delega en                 Aquí lo cubre
===============================  =====================================
``request.httprequest.args``     **django** — ``request.GET``
``request.update_context(...)``  **django** — atributos en el
                                 ``HttpRequest``, que es lo que este
                                 árbol usa como contexto de petición
                                 (mismo mecanismo que
                                 ``_frontend_pre_dispatch`` de
                                 ``http_routing``, que escribe
                                 ``request.LANGUAGE_CODE``)
el ``request`` global            ``get_current_request()`` de
                                 ``base.ir_http`` (``ContextVar``)
``_inherit = "ir.http"``         ``chain_method`` sobre
                                 ``base.IrHttp``
===============================  =====================================

Divergencias declaradas
=======================

- **``request.env.context`` → atributos del ``HttpRequest``.** Este ORM no
  tiene contexto de entorno; ``http_routing`` ya resolvió el mismo problema
  igual. La guarda ``key not in request.env.context`` de la fuente —*"no
  pises lo que ya venga puesto"*— se conserva como ``not hasattr(request,
  key)``.
- **El orden frente a ``super()``.** La fuente escribe
  ``super()._pre_dispatch(...)`` y **después** actualiza el contexto.
  ``chain_method`` invoca primero el eslabón nuevo, así que aquí el contexto
  se fija antes de que corra el eslabón previo. Se usa el ``combine``
  ``keep_previous`` para que la **respuesta** siga siendo la del eslabón
  previo (el redirect SEO 301 de ``http_routing``, si lo hay). Que las tres
  banderas queden puestas antes de un redirect no cambia nada: un redirect no
  renderiza.
- ``_get_translation_frontend_modules_name`` acumula, como la fuente, pero su
  orden es el **inverso** del de ``orm.method_chain.extend_list``: la fuente
  escribe ``["html_editor", *super()...]``, con lo propio **delante**. Por eso
  el ``combine`` es :func:`_prepend_previous` y no ``extend_list``.

Colisión medida con ``http_routing`` en ese mismo método
========================================================

**Medido tras instalar los dos addons:** el método devuelve ``['web']``, no
``['html_editor', 'web']``. La causa no está aquí:

- ``_local_apps()`` ordena por ``(depth, name)``; ``html_editor`` y
  ``http_routing`` quedan a la misma profundidad y ``html_editor`` va primero
  por orden alfabético. Su ``ready()`` corre antes.
- ``chain_method`` instala al recién llegado como eslabón **externo**, así que
  el de ``http_routing`` queda por fuera del de este addon.
- ``addons/http_routing/models/ir_http.py`` lo instala **sin ``combine``**, y
  el relevo por defecto sólo cae en el eslabón previo cuando el nuevo devuelve
  ``None``. El suyo devuelve ``['web']``, que no es ``None``: la contribución
  de este addon nunca se consulta.

Este addon no puede corregirlo desde sus propios archivos —quien decide es el
eslabón externo—, y ``http_routing`` está fuera de su alcance.

**Sucesor nombrado:** instalar
``_get_translation_frontend_modules_name`` de ``http_routing`` con
``combine=orm.method_chain.extend_list``, que es el ``combine`` de la familia
``super() + [lo propio]`` a la que ese método pertenece en la referencia. Con
él, los dos addons aportan y el orden lo fija la cadena de ``depends``. Se
reporta al orquestador.

*Métrica:* ``IrHttp._get_translation_frontend_modules_name()`` tras
``django.setup()`` con los dos addons instalados.
*Ciega a:* qué pasaría con un tercer addon que también extendiera el método —
el efecto depende del orden de ``ready()``, no de este archivo.
"""
from addons.base.models.ir_http import IrHttp, get_current_request
from orm.method_chain import chain_method, keep_previous

CONTEXT_KEYS = ['editable', 'edit_translations', 'translatable']


def _prepend_previous(new, previous):
    """``combine`` acumulativo con lo propio DELANTE — ≙ ``[propio, *super()]``.

    El hermano de ``orm.method_chain.extend_list`` para el orden contrario.
    Vive aquí y no allá porque hoy lo pide un solo consumidor; su hogar
    natural es ``src/orm/method_chain.py`` en cuanto haya un segundo.
    """
    return list(new or []) + list(previous or [])


def _get_editor_context(cls):
    """≙ ``_get_editor_context`` (``odoo19c: :9-15``).

    Comprueba ``?editable`` y compañía en la *query string*.
    """
    request = get_current_request()
    if request is None:
        return {}
    return {
        key: True
        for key in CONTEXT_KEYS
        if key in request.GET and not hasattr(request, key)
    }


def _pre_dispatch(cls, rule, args):
    """≙ ``_pre_dispatch`` (``odoo19c: :17-20``).

    Ver la divergencia del orden en el docstring del módulo: aquí el contexto
    se fija antes de delegar, y la respuesta que gana sigue siendo la previa.
    """
    request = get_current_request()
    ctx = cls._get_editor_context()
    if request is not None:
        for key, value in ctx.items():
            setattr(request, key, value)
    return None


def _get_translation_frontend_modules_name(cls):
    """≙ ``_get_translation_frontend_modules_name`` (``odoo19c: :22-27``)."""
    return ['html_editor']


def apply_html_editor_extensions():
    """Cuelga los tres métodos sobre ``base.IrHttp`` — ≙ ``_inherit``."""
    chain_method(IrHttp, '_get_editor_context',
                 classmethod(_get_editor_context))
    chain_method(IrHttp, '_pre_dispatch', classmethod(_pre_dispatch),
                 combine=keep_previous)
    chain_method(IrHttp, '_get_translation_frontend_modules_name',
                 classmethod(_get_translation_frontend_modules_name),
                 combine=_prepend_previous)

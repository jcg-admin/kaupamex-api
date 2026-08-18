"""Servicios del portal — verificación de acceso a documentos por token.

``document_check_access`` es la adaptación fiel de
``portal/controllers/portal.py:961-980`` (``_document_check_access``, leído
completo). Es el corazón de la compartición por link: si el usuario no puede
leer el documento por sus permisos normales, se acepta si presenta el
``access_token`` correcto — comparado en tiempo constante con ``consteq``
(el mismo ``odoo.tools.consteq`` de la referencia, ya portado en
``tools/misc``).

El contrato de acceso normal (``check_access('read')`` de Odoo) aquí es una
función ``can_read`` inyectable: cada documento decide su regla de lectura
(capacidad, fila-por-usuario L3). Sin token válido y sin permiso normal →
``AccessDenied``; documento inexistente → ``NotFound``.

``pager`` y ``get_records_pager`` (añadidos 2026-08-18, tarea **#535**) son las
otras dos funciones sueltas que la referencia declara en este mismo archivo,
bajo su encabezado ``Misc tools`` (``odoo19c: addons/portal/controllers/
portal.py:22`` y ``:96``). Se portan aquí y no en ``website`` porque ése es su
hogar en la fuente: ``website.py:25`` las importa con
``from odoo.addons.portal.controllers.portal import pager``, y ``Website.pager``
es una delegación de una línea.
"""
import math
from urllib.parse import urlencode

from exceptions import AccessDenied, MissingError
from tools.misc import consteq


def document_check_access(model, document_id, user, access_token=None,
                          can_read=None):
    """≙ ``_document_check_access`` (portal.py:961-980).

    :param model: la clase del modelo del documento (debe tener
        ``access_token``; ≙ heredar ``portal.mixin``).
    :param document_id: id del documento solicitado.
    :param user: el usuario que solicita (``request.user``).
    :param access_token: token presentado en el link, si lo hay.
    :param can_read: callable ``(document, user) -> bool`` con la regla de
        lectura normal del documento. Si se omite, sólo el token concede
        acceso (equivalente a un documento sin regla propia).
    :return: el documento (acceso concedido).
    :raise MissingError: el documento no existe (≙ ``MissingError`` de la
        referencia).
    :raise AccessDenied: ni permiso normal ni token válido (≙ ``AccessError``).
    """
    document = model.objects.filter(pk=document_id).first()
    if document is None:
        raise MissingError('This document does not exist.')

    if can_read is not None and can_read(document, user):
        return document

    # Sin permiso normal: sólo un token válido (comparación en tiempo
    # constante) concede el acceso — igual que la referencia.
    if (access_token and document.access_token
            and consteq(document.access_token, access_token)):
        return document

    raise AccessDenied(
        'You are not allowed to access this document.')


def pager(url, total, page=1, step=30, scope=5, url_args=None):
    """≙ ``pager`` (``odoo19c: addons/portal/controllers/portal.py:22-93``).

    Calcula todo lo que una barra de paginación necesita: cuántas páginas hay,
    el desplazamiento del primer registro, y la lista de números a mostrar con
    sus elipsis. La fuente lo describe como *"Enhanced pager logic for SEO
    optimization"* — de ahí que primera y última página siempre aparezcan: un
    rastreador que sólo ve «anterior/siguiente» no alcanza el fondo del
    catálogo.

    :param url: URL base del enlace de página.
    :param total: total de elementos a repartir en páginas.
    :param page: página actual.
    :param step: elementos por página.
    :param scope: cuántas páginas mostrar en la barra.
    :param url_args: parámetros extra que se añaden como query string.
    :returns: dict con ``page_count``, ``offset``, y los cinco descriptores de
        página (``page``, ``page_first``, ``page_previous``, ``page_next``,
        ``page_last``) más la lista ``pages``.

    **Divergencia declarada:** la fuente usa ``werkzeug.urls.url_encode``; aquí
    se usa ``urllib.parse.urlencode`` de la biblioteca estándar. Mismo
    resultado para un dict de parámetros, sin arrastrar werkzeug a un addon que
    no lo necesita para nada más.

    El parámetro ``scope`` se conserva en la firma **y no se usa**, igual que
    en la fuente: desde que la lógica pasó a la forma de elipsis, ninguna rama
    lo lee. Se porta tal cual porque es contrato público — cambiarlo aquí
    rompería a los llamadores que la referencia sí tiene.
    """
    page_count = int(math.ceil(float(total) / step))

    page = max(1, min(int(page if str(page).isdigit() else 1), page_count))

    page_previous = max(1, page - 1)
    page_next = min(page_count, page + 1)

    def get_url(page):
        result = "%s/page/%s" % (url, page) if page > 1 else url
        if url_args:
            result = "%s?%s" % (result, urlencode(url_args))
        return result

    if page_count <= 5:
        page_list = list(range(1, page_count + 1))
    elif page <= 3:
        page_list = [1, 2, 3, 4, "…", page_count]
    elif page >= page_count - 2:
        page_list = [1, "…"] + list(range(page_count - 3, page_count + 1))
    else:
        page_list = [1, "…", page - 1, page, page + 1, "…", page_count]

    pages = [
        {"num": p, "url": get_url(p) if p != "…" else None, "is_current": p == page}
        for p in page_list
    ]

    return {
        "page_count": page_count,
        "offset": (page - 1) * step,
        "page": {'url': get_url(page), 'num': page},
        "page_first": {'url': get_url(1), 'num': 1},
        "page_previous": {'url': get_url(page_previous), 'num': page_previous},
        "page_next": {'url': get_url(page_next), 'num': page_next},
        "page_last": {'url': get_url(page_count), 'num': page_count},
        "pages": pages,
    }


def get_records_pager(ids, current):
    """≙ ``get_records_pager`` (``odoo19c: …/portal.py:96-120``).

    Los enlaces «anterior / siguiente» **entre registros**, no entre páginas de
    una lista. Sirve para navegar un pedido tras otro desde el portal sin
    volver al índice.

    El atributo del que sale el enlace es ``access_url`` si el documento lo
    tiene (documento compartible por token → se le añade el token) y
    ``website_url`` si no. Ese orden es el de la fuente y no es indiferente:
    con ``access_url`` el vecino se abre con su propio token, así que el enlace
    funciona para un usuario que sólo tiene el link.

    **Divergencia declarada:** la fuente hace ``current.browse(ids[i])`` sobre
    el recordset; aquí se resuelve con el gestor por defecto del modelo del
    registro actual (``type(current).objects``), que es la forma del ORM de
    destino. La semántica es la misma — traer el registro vecino por su id.

    :param ids: los ids del listado, en el orden en que se muestra.
    :param current: el registro que se está viendo.
    :returns: dict con ``prev_record`` y ``next_record``, o ``None`` si el
        registro actual no está en el listado o el modelo no expone ninguna de
        las dos URL.
    """
    has_url = hasattr(current, 'access_url') or hasattr(current, 'website_url')
    if current.pk not in ids or not has_url:
        return None

    attr_name = 'access_url' if hasattr(current, 'access_url') else 'website_url'
    manager = type(current).objects
    index = ids.index(current.pk)
    prev_record = manager.filter(pk=ids[index - 1]).first() if index != 0 else None
    next_record = (manager.filter(pk=ids[index + 1]).first()
                   if index < len(ids) - 1 else None)

    def url_of(record):
        if record is None:
            return None
        value = getattr(record, attr_name, None)
        if value and attr_name == 'access_url':
            return '%s?access_token=%s' % (value, record._portal_ensure_token())
        return value or record

    return {
        'prev_record': url_of(prev_record),
        'next_record': url_of(next_record),
    }

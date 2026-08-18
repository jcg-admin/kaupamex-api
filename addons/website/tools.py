"""Utilidades del addon ``website`` — espejo de ``odoo19c: addons/website/tools.py``.

La raíz ``addons/website/`` está espejada, así que este archivo va aquí y no en
``src/tools/``: la referencia lo declara **dentro del addon**, no en el núcleo
(``atributos-de-clase-de-modelo.md``, segunda cláusula — el sitio del archivo
se lee contra la referencia antes de crearlo).

**Cobertura declarada.** La fuente declara **6** símbolos de primer nivel en
**164** líneas (medido por AST sobre ``odoo-tools@622ddc2a``); este archivo
porta **1**: ``get_base_domain``, el único que ``website.py`` necesita para el
bloque B2 (tarea #535). Los otros 5 quedan medidos y con dueño en la tarea
**#541**:

- ``distance`` y ``similarity_score`` — la métrica de parecido entre textos que
  alimenta la búsqueda del sitio. Su consumidor es el bloque **B3** (#536), que
  además está atado a ``pg_trgm``; portarlos antes sería código sin llamador.
- ``text_from_html`` y ``add_form_signature`` — operan sobre un árbol
  ``lxml.html`` de plantillas QWeb renderizadas, que este árbol todavía no
  produce.
- ``create_image_attachment`` — necesita ``ir.attachment`` resolviendo por
  external ID, que es la tarea #467.
"""
from urllib.parse import urlsplit


def get_base_domain(url, strip_www=False):
    """≙ ``get_base_domain`` (``odoo19c: addons/website/tools.py:96-112``).

    El dominio de una URL, sin esquema, sin barra final y —si se pide— sin el
    ``www.``.

    Lo consume ``Website._get_current_website_id`` para comparar el ``domain``
    configurado de cada sitio contra el ``Host`` de la petición. Por eso lo que
    devuelve es el ``netloc`` **con puerto**: el llamador decide si el puerto
    cuenta, y la fuente lo intenta primero con puerto y luego sin él.

    **Divergencia declarada:** la fuente usa ``werkzeug.urls.url_parse``; aquí
    ``urllib.parse.urlsplit`` de la biblioteca estándar. Sobre el ``netloc`` el
    resultado es el mismo, y evita atar el addon a werkzeug.

    Detalle que la fuente resuelve y no es obvio: una URL sin esquema
    (``midominio.com/x``) no tiene ``netloc`` para ningún parser — todo cae en
    ``path``. La fuente hereda ese comportamiento de ``url_parse`` y devuelve
    cadena vacía; se replica igual, porque el llamador ya trata la cadena vacía
    como «este sitio no declara dominio» y hace fallback.

    :param url: la URL de la que extraer el dominio.
    :param strip_www: si es cierto, quita el ``www.`` inicial.
    :returns: el dominio, o cadena vacía si la URL es falsy.
    """
    if not url:
        return ''

    url = urlsplit(url).netloc
    if strip_www and url.startswith('www.'):
        url = url[4:]
    return url

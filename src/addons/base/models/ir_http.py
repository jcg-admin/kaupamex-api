"""``ir.http`` — el enrutado HTTP y sus utilidades de URL.

Adaptación de ``odoo/addons/base/models/ir_http.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 456 líneas). En la referencia este
modelo **es** la capa HTTP: construye el mapa de rutas de Werkzeug, autentica
cada petición según el ``auth`` declarado por el endpoint, despacha, y
post-procesa la respuesta.

Aquí el enrutado y el despacho los hace Django (URLconf + middleware + DRF), y
la autenticación está decidida y documentada: **sesión de servidor**
(ADR-018) más **capacidad** por vista (``HasCapability``, DEC-11). Así que lo
que se porta es la parte que **no** es enrutado: las utilidades de URL, que
son puro algoritmo y valen en cualquier stack.

``slugify`` — la diferencia con el de Django, que sí importa
===========================================================

Es la pieza con más valor del archivo, y **no la duplica** nada del árbol:
``grep -rn "def slugify\\|from django.utils.text import" src/`` → **0**
[PROVEN].

Django trae ``django.utils.text.slugify``, pero por defecto
(``allow_unicode=False``) **descarta todo lo que no sea ASCII**: un título en
chino se convierte en cadena vacía y una URL entera desaparece. El de la
referencia conserva esos caracteres —su propio docstring lo ejemplifica:
``^h☺e$#!l(%l}o 你好&`` → ``h-e-l-l-o-你好``— y en cambio **sí** despoja los
acentos latinos por descomposición NFKD, para que ``é`` dé ``e`` y no ``e-``.

Esa combinación —quitar marcas combinantes pero conservar los caracteres de
otras escrituras— es una decisión deliberada, no un descuido, y es la razón
de portarlo en vez de usar el de Django. Un catálogo con productos en
japonés o árabe con el de Django pierde el slug entero.

Detalles del algoritmo que se conservan y son fáciles de perder:

- **``[\\W_]+``**: el guion bajo se reemplaza junto con los no-alfanuméricos.
  ``\\W`` por sí solo **no** incluye ``_``, así que sin el ``_`` explícito un
  ``hola_mundo`` quedaría con guion bajo en la URL.
- **``strip('-')`` antes de ``lower()``**: quita los guiones de los bordes que
  dejó el reemplazo, para que ``^hola$`` no dé ``-hola-``.
- **Re-normalizar a NFC al final**: tras descomponer con NFKD hay que
  recomponer, o el slug queda con caracteres combinantes sueltos que se ven
  igual y comparan distinto.
- **``max_length`` se aplica al final**, sobre el slug ya construido, no sobre
  la entrada.

Y en modo ``path`` (una ruta con ``/``): cada segmento se convierte por
separado, los vacíos se descartan, y **si la ruta acaba en una extensión
web conocida, se preserva la extensión** — sin eso, ``estilos.css`` daría
``estilos-css`` y la ruta dejaría de servir el archivo.

Rareza heredada del modo ``path``, conservada a propósito
---------------------------------------------------------

La rama de la extensión hace ``res[-1] = _slugify_one(path_no_ext) + ext``,
donde ``path_no_ext`` sale de ``os.path.splitext(value)`` sobre el
``value`` **completo** — la ruta entera, no el último segmento. Resultado
medido: ``"Mis Estilos/Tema Claro.css"`` da
``"mis-estilos/mis-estilos-tema-claro.css"``, con el primer segmento
repetido dentro del último. [PROVEN]

Casi seguro es un defecto de la referencia. **Se conserva igual**, por el
criterio ya fijado en H-API-168: "más correcto" no basta para divergir; el
criterio es la **comparabilidad**. Arreglarlo aquí haría que la misma ruta
diera distinto de un lado y del otro sin que nadie lo hubiera decidido.
Queda anotado para que la divergencia, si se toma, sea explícita.

Qué NO se porta, con su medición
================================

- **Todo el enrutado y el despacho**: ``routing_map``,
  ``_generate_routing_rules``, ``_match``, ``_pre_dispatch``, ``_dispatch``,
  ``_post_dispatch``, ``_handle_error``, ``_serve_fallback``, ``_redirect``.
  Y con ellos los convertidores de Werkzeug (``ModelConverter``,
  ``ModelsConverter``, ``SignedIntConverter``) y las clases de optimización
  del compilado de rutas (``LazyCompiledBuilder``, ``FasterRule``). En este
  árbol eso es la URLconf de Django más el router de DRF.
- **Los métodos de autenticación** (``_auth_method_user`` / ``_none`` /
  ``_public`` / ``_bearer``, ``_authenticate``, ``_authenticate_explicit``).
  Se conserva **el vocabulario** —los cuatro nombres, que es lo que un
  endpoint declara— pero no la implementación: la de este árbol es sesión de
  servidor (ADR-018) más capacidad (DEC-11), y montar un segundo camino de
  autenticación al lado del vigente es exactamente lo que no se debe hacer de
  rebote al portar un archivo.
- **``_geoip_resolve``**: delega en el resolutor de la petición de Odoo.
- **``_sanitize_cookies``**: en la referencia es un ``pass`` — un punto de
  extensión vacío para que otros módulos lo sobreescriban. Se porta como tal,
  con esa nota, en vez de omitirlo: su valor está en existir.
- **``RequestUID``**: marcador interno de su sistema de peticiones.
"""
import logging
import os
import re
import unicodedata

import models

_logger = logging.getLogger(__name__)

#: Extensiones cuyo tipo MIME sirve la web — verbatim de la fuente. En modo
#: ``path`` la extensión se preserva en vez de convertirse en parte del slug.
EXTENSION_TO_WEB_MIMETYPES = {
    '.css': 'text/css',
    '.less': 'text/less',
    '.scss': 'text/scss',
    '.js': 'text/javascript',
    '.xml': 'text/xml',
    '.csv': 'text/csv',
    '.html': 'text/html',
}

#: Los cuatro modos de autenticación que un endpoint puede declarar en la
#: referencia. Se conserva el **vocabulario**; la implementación de este árbol
#: es otra (ADR-018 + DEC-11). Ver el docstring del módulo.
AUTH_METHODS = ('user', 'public', 'none', 'bearer')

#: No-alfanuméricos **y** el guion bajo. Sin el ``_`` explícito, ``\W`` lo
#: dejaría pasar y el slug llevaría guion bajo.
_NON_WORD = re.compile(r'[\W_]+')


class IrHttp(models.Model):
    """``ir.http`` — utilidades de URL.

    Abstracto en la referencia y abstracto aquí. Del modelo original queda lo
    que no es enrutado; ver el docstring del módulo.
    """

    class Meta:
        abstract = True

    @classmethod
    def slugify_one(cls, value, max_length=None):
        """``_slugify_one`` — un texto a un segmento de URL.

        Conserva los caracteres de escrituras no latinas y despoja los
        acentos: ``^h☺e$#!l(%l}o 你好&`` → ``h-e-l-l-o-你好``, ``café`` →
        ``cafe``. Ver el docstring del módulo sobre por qué eso difiere del
        ``slugify`` de Django y por qué la diferencia importa.

        La referencia intenta primero ``python-slugify`` si está instalada;
        aquí no se intenta, porque no lo está y añadirla cambiaría el
        resultado según el entorno — que es peor que un resultado fijo.
        """
        decomposed = unicodedata.normalize('NFKD', value or '')
        # Quitar las marcas combinantes: 'é' pasa a 'e', no a 'e-'.
        cleaned = ''.join(
            char for char in decomposed
            if unicodedata.category(char) != 'Mn'
        )
        slug = _NON_WORD.sub('-', cleaned).strip('-').lower()
        slug = unicodedata.normalize('NFC', slug)
        return slug[:max_length] if max_length else slug

    @classmethod
    def slugify(cls, value, max_length=None, path=False):
        """``_slugify`` — un texto, o una ruta completa, a slug.

        En modo ``path`` cada segmento se convierte por separado, los vacíos
        se descartan, y si la ruta acaba en una extensión web conocida **la
        extensión se preserva**: sin eso ``estilos.css`` daría
        ``estilos-css`` y la ruta dejaría de servir el archivo.
        """
        if not path:
            return cls.slugify_one(value, max_length=max_length)

        segments = []
        for part in (value or '').split('/'):
            slug = cls.slugify_one(part, max_length=max_length)
            if slug:
                segments.append(slug)
        path_no_ext, ext = os.path.splitext(value or '')
        if ext in EXTENSION_TO_WEB_MIMETYPES and segments:
            segments[-1] = cls.slugify_one(path_no_ext) + ext
        return '/'.join(segments)

    @classmethod
    def slug(cls, value):
        """``_slug`` — el identificador de un registro para la URL.

        Acepta el registro o una tupla ``(id, nombre)``. En Odoo 19 devuelve
        **sólo el id**: el slug con nombre legible quedó en el módulo de sitio
        web, no en ``base``. Se porta lo que ``base`` hace.
        """
        if isinstance(value, tuple):
            return str(value[0])
        return str(getattr(value, 'pk', value))

    @classmethod
    def unslug(cls, value):
        """``_unslug`` — el inverso: ``(None, id)`` o ``(None, None)``.

        La forma del retorno se conserva aunque el primer elemento sea siempre
        ``None`` en ``base``: es el hueco del nombre del modelo, que el módulo
        de sitio web sí rellena. Devolver sólo el entero rompería a quien
        desempaqueta dos valores.
        """
        try:
            return None, int(value)
        except (TypeError, ValueError):
            return None, None

    @classmethod
    def sanitize_cookies(cls, cookies):
        """``_sanitize_cookies`` — punto de extensión, vacío por diseño.

        En la referencia es literalmente ``pass``. Se porta con esa nota
        porque su valor está en **existir**: es el sitio declarado donde otro
        módulo interviene las cookies salientes sin parchear el despacho.
        """
        return cookies

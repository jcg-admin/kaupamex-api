"""``assetsbundle`` — el empaquetador de assets de la referencia.

Adaptación de ``odoo/addons/base/models/assetsbundle.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 1087 líneas). Toma la lista de
archivos que ``ir.asset`` resuelve, los compila (SASS/SCSS/LESS → CSS),
minifica, genera *sourcemaps*, y guarda el resultado como adjunto con una URL
versionada.

Aquí el empaquetador es **Webpack**, en ``ui``. Este archivo porta la parte
que Webpack no cubre: el **contrato de la URL versionada** y su algoritmo de
versión.

Cierra ``base``: es el último archivo de ``odoo/addons/base/models/``
=====================================================================

``ir_asset.py`` ya lo anticipó al portarse — declaró que *"el resolutor de
rutas contra manifests no aplica: lo hace Webpack en ``ui``"*. Esa decisión se
extiende aquí al empaquetado en sí, con la misma medición y una razón añadida:
el compilador invoca ``sass``/``lessc``/``rtlcss`` **por subprocess** y guarda
el resultado en ``ir.attachment``. Montar eso al lado de Webpack daría dos
pipelines produciendo el mismo bundle, con dos versiones distintas del mismo
archivo servidas según quién lo pidiera.

Lo que sí falta en este árbol y este archivo aporta
==================================================

El **versionado del bundle**. Webpack pone un hash en el nombre del archivo,
pero el contrato de URL de la referencia —``<nombre>[.rtl][.autoprefixed].<ext>``
más un segmento ``unique`` de 7 caracteres— es de este lado: es lo que decide
cuándo un navegador puede cachear un bundle para siempre y cuándo debe pedirlo
de nuevo.

El algoritmo, portado y ejercitable:

1. cada asset aporta un **descriptor único** (ruta + fecha de modificación);
2. se concatenan con coma, en el orden del bundle — **el orden importa**:
   reordenar los mismos archivos debe dar otra versión, porque el CSS
   resultante es distinto;
3. se hace ``sha512`` del conjunto y se **trunca a 64 caracteres hex**;
4. la versión visible es la de **7 caracteres** del principio.

Precisión sobre el nombre del hash
----------------------------------

El comentario de la fuente dice *"We compute a SHA512/256"*, pero el código es
``hashlib.sha512(...).hexdigest()[:64]`` — SHA-512 **truncado** a 256 bits.
**No es lo mismo** que SHA-512/256, que es una variante distinta con otro
vector inicial y da otro resultado para la misma entrada. Se porta el código,
no el comentario; si alguien reimplementa esto en otro lenguaje leyendo el
comentario, obtendrá versiones que no casan.

Qué NO se porta, con su medición
================================

- **Todo el pipeline de compilación**: ``compile_css``, ``preprocess_css``,
  ``run_rtlcss``, ``autoprefix_css``, ``minify``, ``js_with_sourcemap``,
  ``css_with_sourcemap``, ``generate_xml_bundle``. Invocan ``sass``,
  ``lessc`` y ``rtlcss`` por subprocess. Medido:
  ``grep -rn "sass\|lessc\|rtlcss" pyproject.toml`` → **0**; y el pipeline
  vivo es ``ui``: Webpack 5 con ``sass-loader``, declarado en el ``CLAUDE.md``
  de ese submódulo. [PROVEN]
- **``WebAsset`` y su jerarquía** (``JavascriptAsset``, ``XMLAsset``,
  ``StylesheetAsset``, ``PreprocessedCSS``, ``SassStylesheetAsset``,
  ``ScssStylesheetAsset``, ``LessStylesheetAsset``): leen el archivo del
  disco, lo compilan y lo minifican. Se conserva de ellas **el descriptor
  único**, que es lo que alimenta la versión, como protocolo declarado en vez
  de como jerarquía de clases sin contenido.
- **El almacenamiento en ``ir.attachment``** (``get_attachments``,
  ``save_attachment``, ``_clean_attachments``, ``_unlink_attachments``): el
  bundle compilado se guarda como adjunto y se sirve desde ahí. Aquí lo sirve
  el servidor web sobre el ``dist`` de Webpack (Apache, ver ``server``).
- **``rx_css_import`` / ``rx_preprocess_imports`` / ``rx_css_split``**: las
  expresiones que reescriben los ``@import`` de CSS antes de compilar. Sin
  compilador no tienen entrada; se declara su ausencia en vez de dejar tres
  regex sin llamador.
"""
import hashlib
import logging

_logger = logging.getLogger(__name__)

#: Marcador de "cualquier versión" en una URL de bundle — siete guiones bajos,
#: la misma longitud que la versión real, para que la ruta encaje igual.
ANY_UNIQUE = '_' * 7

#: Extensiones que el empaquetador reconoce, verbatim de la fuente.
EXTENSIONS = ('.js', '.css', '.scss', '.sass', '.less', '.xml')

#: Extensiones que producen hoja de estilo — determinan si aplican los
#: sufijos ``.rtl`` y ``.autoprefixed`` en el nombre del bundle.
STYLE_EXTENSIONS = ('.css', '.scss', '.sass', '.less')

#: Longitud del hash truncado y de la versión visible.
CHECKSUM_LENGTH = 64
VERSION_LENGTH = 7


class AssetError(Exception):
    """Error de asset (``AssetError`` de la fuente)."""


class AssetNotFound(AssetError):
    """El asset referenciado no existe."""


class CompileError(RuntimeError):
    """Falló la compilación de un asset (``CompileError``)."""


class XMLAssetError(Exception):
    """Error en un asset XML (``XMLAssetError``)."""


def is_css(extension):
    """``is_css`` — ¿la extensión produce hoja de estilo?

    Acepta con o sin punto inicial, porque la fuente la llama de las dos
    formas (``'css'`` desde ``get_asset_url``, ``'.css'`` desde el nombre de
    archivo).
    """
    if not extension:
        return False
    normalized = extension if extension.startswith('.') else f'.{extension}'
    return normalized in STYLE_EXTENSIONS


def bundle_checksum(unique_descriptors):
    """El checksum de un bundle a partir de los descriptores de sus assets.

    Los descriptores se unen **con coma y en el orden del bundle**: reordenar
    los mismos archivos tiene que dar otro checksum, porque el CSS resultante
    es distinto.

    Sobre el algoritmo: la fuente lo comenta como *"SHA512/256"* pero lo
    implementa como ``sha512`` **truncado** a 64 caracteres hex. No son lo
    mismo — ver el docstring del módulo. Se porta el código.
    """
    joined = ','.join(unique_descriptors)
    return hashlib.sha512(joined.encode()).hexdigest()[:CHECKSUM_LENGTH]


def bundle_version(unique_descriptors):
    """``get_version`` — los primeros 7 caracteres del checksum."""
    return bundle_checksum(unique_descriptors)[:VERSION_LENGTH]


def asset_unique_descriptor(path, last_modified):
    """``unique_descriptor`` de un asset — lo que entra en el checksum.

    Ruta más fecha de modificación: la ruta distingue **qué** archivo es, y la
    fecha **qué versión** de él. Sólo con la ruta, editar un archivo no
    cambiaría la versión del bundle y el navegador seguiría sirviendo el
    anterior desde su caché.
    """
    return f'{path}:{last_modified}'


def bundle_name(name, extension, rtl=False, autoprefix=False):
    """``get_asset_url`` — el nombre del bundle con sus sufijos.

    Forma: ``<nombre>[.rtl][.autoprefixed].<extensión>``. Los dos sufijos
    aplican **sólo** a hojas de estilo: un bundle JS no tiene dirección de
    escritura ni prefijos de proveedor.

    El orden de los sufijos es el de la fuente (``.rtl`` antes de
    ``.autoprefixed``) y se conserva: es parte de la URL, y cambiarlo
    invalidaría las cachés de todo el mundo sin ganar nada.
    """
    styled = is_css(extension)
    direction = '.rtl' if styled and rtl else ''
    autoprefixed = '.autoprefixed' if styled and autoprefix else ''
    ext = extension.lstrip('.')
    return f'{name}{direction}{autoprefixed}.{ext}'

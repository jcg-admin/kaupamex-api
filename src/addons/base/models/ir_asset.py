"""``ir.asset`` — directivas declarativas sobre los bundles de assets.

Adaptación de ``odoo/addons/base/models/ir_asset.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 432 líneas). El propio docstring de
clase de la referencia dice que el archivo hace **dos** cosas:

    1. provee una función que devuelve la lista de rutas declaradas por un
       conjunto de addons (``_get_addon_paths``);
    2. permite crear registros ``ir.asset`` para añadir directivas a ciertos
       bundles.

Ese "dos cosas" es la línea de corte de esta portación, y no es una
clasificación inventada: la escribe la fuente.

Qué se porta — la capa declarativa completa
===========================================

- **El modelo** con sus siete campos: ``name``, ``bundle``, ``directive``
  (las **siete** directivas), ``path``, ``target``, ``active``, ``sequence``
  (default 16, el ``DEFAULT_SEQUENCE`` de la fuente), ordenado por
  ``sequence, id``.
- **``AssetPaths``** — la estructura que mantiene la lista ordenada de rutas
  con su memo de deduplicación, y sus cuatro operaciones (``index``,
  ``append``, ``insert``, ``remove``). Es álgebra pura sobre una lista: no
  toca disco, ni ORM, ni manifests. Se porta entera, incluido el detalle de
  que ``remove`` sobre rutas que **ninguna** está en el memo levanta
  "no encontrado" en vez de callar.
- **``apply_directive``** — la tabla de despacho de ``_process_path``: qué
  hace cada una de las siete directivas sobre la lista. Es la semántica del
  vocabulario, y sin ella los siete valores del ``Selection`` serían siete
  strings sin significado.
- **Los tres helpers puros**: ``fs2web`` (separador del SO → ``/``),
  ``can_aggregate`` (una URL con esquema o host, o bajo ``/web/content``, no
  se agrega) e ``is_wildcard_glob``.
- **Las extensiones de asset**, verbatim de ``odoo/tools/constants.py:3-6``:
  script ``js``; estilo ``css``, ``scss``, ``sass``, ``less``; plantilla
  ``xml``.
- **La invalidación de caché** en create/write/delete. La referencia llama
  ``registry.clear_cache('assets')``; aquí el equivalente es la caché de
  Django, con la misma disciplina: **toda** mutación invalida, incluido el
  borrado.

Qué NO se porta, con su medición
================================

**La resolución de rutas contra los manifests de addons** —
``_get_addon_paths``, ``_get_paths``, ``_get_active_addons_list``,
``_get_installed_addons_list``, ``_topological_sort``, ``_glob_static_file``,
``_parse_bundle_name``, ``_get_asset_bundle_url``.

Medido: ``find src -name '__manifest__.py'`` → **1** archivo
(``src/addons/sale/__manifest__.py``) sobre 78 addons. [PROVEN] La referencia
lee el ``assets`` de **cada** manifest para saber qué archivo va en qué
bundle; con un manifest de 78 ese recorrido no tiene sobre qué correr.

Y hay una segunda razón, independiente de la primera: **el bundler de este
producto es Webpack**, y vive en el repo `ui`, no aquí. La referencia resuelve
globs contra su carpeta ``static/`` y concatena; Webpack hace ese trabajo con
su propio grafo de dependencias. Portar el resolutor construiría un segundo
bundler que compite con el que ya empaqueta el SPA.

Lo que queda entonces es lo que sí tiene sentido aquí: **el registro
declarativo** de qué archivo se añade a qué bundle y en qué orden — que es
información que un addon del backend puede querer declarar y que el `ui`
puede consumir— más el álgebra que la ordena.
"""
import logging
import os
import re
from urllib.parse import urlparse

import fields
import models
from django.core.cache import cache

_logger = logging.getLogger(__name__)

#: ``DEFAULT_SEQUENCE`` de la referencia.
DEFAULT_SEQUENCE = 16

# Las directivas se guardan en variables para facilitar su uso y los chequeos
# de sintaxis — mismo comentario y mismos nombres que la fuente.
APPEND_DIRECTIVE = 'append'
PREPEND_DIRECTIVE = 'prepend'
AFTER_DIRECTIVE = 'after'
BEFORE_DIRECTIVE = 'before'
REMOVE_DIRECTIVE = 'remove'
REPLACE_DIRECTIVE = 'replace'
INCLUDE_DIRECTIVE = 'include'
#: Las que llevan argumento/campo ``target``.
DIRECTIVES_WITH_TARGET = [AFTER_DIRECTIVE, BEFORE_DIRECTIVE, REPLACE_DIRECTIVE]

# Extensiones de asset — verbatim de ``odoo/tools/constants.py:3-6``.
SCRIPT_EXTENSIONS = ('js',)
STYLE_EXTENSIONS = ('css', 'scss', 'sass', 'less')
TEMPLATE_EXTENSIONS = ('xml',)
ASSET_EXTENSIONS = SCRIPT_EXTENSIONS + STYLE_EXTENSIONS + TEMPLATE_EXTENSIONS

#: Centinela para una URL externa — ``EXTERNAL_ASSET`` de la referencia, que
#: allá es un ``object()`` sin más identidad que la suya.
EXTERNAL_ASSET = object()

#: Clave de la caché de bundles. La referencia usa ``clear_cache('assets')``.
ASSET_CACHE_KEY = 'ir_asset:bundles'


def fs2web(path):
    """Convierte una ruta del sistema de archivos a ruta web."""
    if os.path.sep == '/':
        return path
    return '/'.join(path.split(os.path.sep))


def can_aggregate(url):
    """¿La URL se puede agregar a un bundle?

    No, si trae esquema o host (es externa) o si va por ``/web/content``.
    """
    parsed = urlparse(url)
    return (
        not parsed.scheme
        and not parsed.netloc
        and not url.startswith('/web/content')
    )


def is_wildcard_glob(path):
    """¿Es un glob con comodines (``/web/file[14].*``) o un archivo único?"""
    return '*' in path or '[' in path or ']' in path or '?' in path


class AssetPaths:
    """Lista de rutas de asset ``(ruta, ruta_completa, bundle, modificado)``.

    Portación completa de la clase homónima de la referencia. El ``memo`` es
    lo que hace baratas las operaciones: una ruta ya presente no se vuelve a
    insertar, sin recorrer la lista para averiguarlo.
    """

    def __init__(self):
        self.list = []
        self.memo = set()

    def index(self, path, bundle):
        """Índice de ``path`` en la lista actual."""
        if path not in self.memo:
            self._raise_not_found(path, bundle)
        for index, asset in enumerate(self.list):
            if asset[0] == path:
                return index
        return None

    def append(self, paths, bundle):
        """Añade las rutas dadas al final de la lista."""
        for path, full_path, last_modified in paths:
            if path not in self.memo:
                self.list.append((path, full_path, bundle, last_modified))
                self.memo.add(path)

    def insert(self, paths, bundle, index):
        """Inserta las rutas dadas en la posición ``index``."""
        to_insert = []
        for path, full_path, last_modified in paths:
            if path not in self.memo:
                to_insert.append((path, full_path, bundle, last_modified))
                self.memo.add(path)
        self.list[index:index] = to_insert

    def remove(self, paths_to_remove, bundle):
        """Quita las rutas dadas de la lista.

        Si **ninguna** de las rutas pedidas está presente, levanta "no
        encontrado" en vez de callar — así un ``remove`` que apunta a un
        archivo inexistente se nota, que es el comportamiento de la fuente.
        """
        paths = {
            path for path, _full_path, _last_modified in paths_to_remove
            if path in self.memo
        }
        if paths:
            self.list[:] = [a for a in self.list if a[0] not in paths]
            self.memo.difference_update(paths)
            return
        if paths_to_remove:
            self._raise_not_found(
                [path for path, _fp, _lm in paths_to_remove], bundle)

    def _raise_not_found(self, path, bundle):
        raise ValueError(
            'Archivo(s) %s no encontrado(s) en el bundle %s' % (path, bundle))


def apply_directive(asset_paths, bundle, directive, paths, target_paths=None,
                    bundle_start_index=0):
    """Aplica una directiva sobre ``asset_paths`` — tabla de ``_process_path``.

    Es la semántica del vocabulario de siete directivas. ``include`` no se
    resuelve aquí: en la referencia recursa sobre el bundle incluido usando el
    resolutor de rutas, que es justo la mitad que no se porta.

    :raises ValueError: ante una directiva desconocida — *"esto nunca debería
        pasar"*, dice la fuente, y por eso revienta en vez de ignorar.
    """
    target_index = None
    if directive in DIRECTIVES_WITH_TARGET:
        if not target_paths:
            # Nada que hacer: el objetivo no resolvió a ninguna ruta.
            return
        target_index = asset_paths.index(target_paths[0][0], bundle)

    if directive == APPEND_DIRECTIVE:
        asset_paths.append(paths, bundle)
    elif directive == PREPEND_DIRECTIVE:
        asset_paths.insert(paths, bundle, bundle_start_index)
    elif directive == AFTER_DIRECTIVE:
        asset_paths.insert(paths, bundle, target_index + 1)
    elif directive == BEFORE_DIRECTIVE:
        asset_paths.insert(paths, bundle, target_index)
    elif directive == REMOVE_DIRECTIVE:
        asset_paths.remove(paths, bundle)
    elif directive == REPLACE_DIRECTIVE:
        asset_paths.insert(paths, bundle, target_index)
        asset_paths.remove(target_paths, bundle)
    elif directive == INCLUDE_DIRECTIVE:
        raise ValueError(
            'La directiva include exige el resolutor de rutas, que no está '
            'portado (ver el docstring del módulo)'
        )
    else:
        raise ValueError('Directiva inesperada: %r' % directive)


class IrAsset(models.Model):
    """Una directiva declarativa sobre un bundle (``ir.asset``).

    Los cuatro atributos de clase son los de la fuente
    (``odoo19c: ir_asset.py`` — ``atributos-de-clase-de-modelo.md``).
    """

    _name = 'ir.asset'
    _description = 'Asset'
    _order = 'sequence, id'
    _allow_sudo_commands = False

    DIRECTIVE_CHOICES = [
        (APPEND_DIRECTIVE, 'Añadir al final'),
        (PREPEND_DIRECTIVE, 'Añadir al inicio'),
        (AFTER_DIRECTIVE, 'Después de'),
        (BEFORE_DIRECTIVE, 'Antes de'),
        (REMOVE_DIRECTIVE, 'Quitar'),
        (REPLACE_DIRECTIVE, 'Reemplazar'),
        (INCLUDE_DIRECTIVE, 'Incluir'),
    ]

    name = fields.Char(max_length=255, verbose_name='Nombre')
    bundle = fields.Char(
        max_length=255, db_index=True, verbose_name='Nombre del bundle')
    directive = fields.Selection(
        max_length=16, choices=DIRECTIVE_CHOICES, default=APPEND_DIRECTIVE,
        verbose_name='Directiva',
    )
    path = fields.Char(
        max_length=512, verbose_name='Ruta (o patrón glob)')
    target = fields.Char(
        max_length=512, blank=True, default='', verbose_name='Objetivo',
        help_text='Odoo target; sólo lo usan after, before y replace.',
    )
    active = fields.Boolean(default=True, verbose_name='Activo')
    sequence = fields.Integer(
        default=DEFAULT_SEQUENCE, verbose_name='Secuencia')

    class Meta:
        db_table = 'ir_asset'
        ordering = ['sequence', 'id']
        verbose_name = 'Asset'
        verbose_name_plural = 'Assets'

    def __str__(self):
        return f'{self.bundle}: {self.directive} {self.path}'

    def save(self, *args, **kwargs):
        """Toda escritura invalida la caché de bundles, como allá."""
        super().save(*args, **kwargs)
        cache.delete(ASSET_CACHE_KEY)

    def delete(self, *args, **kwargs):
        """El borrado también invalida — la referencia lo hace en ``unlink``."""
        result = super().delete(*args, **kwargs)
        cache.delete(ASSET_CACHE_KEY)
        return result

    @staticmethod
    def matches_extension(path):
        """¿La ruta apunta a un asset de extensión conocida?"""
        return path.rsplit('.', 1)[-1] in ASSET_EXTENSIONS

    @classmethod
    def glob_to_regex(cls, pattern):
        """Traduce un glob de asset a expresión regular.

        La referencia delega en ``glob.glob`` sobre el disco; aquí no hay
        carpeta ``static/`` de addon que recorrer (ver el docstring del
        módulo), así que lo que se conserva es la **traducción del patrón**,
        que es lo que permite decidir si una ruta declarada casa con otra sin
        tocar el sistema de archivos.
        """
        out = []
        i = 0
        while i < len(pattern):
            char = pattern[i]
            if char == '*':
                if pattern[i:i + 2] == '**':
                    out.append('.*')
                    i += 2
                    continue
                out.append('[^/]*')
            elif char == '?':
                out.append('[^/]')
            elif char == '[':
                close = pattern.find(']', i)
                if close == -1:
                    out.append(re.escape(char))
                else:
                    out.append('[' + pattern[i + 1:close] + ']')
                    i = close + 1
                    continue
            else:
                out.append(re.escape(char))
            i += 1
        return re.compile('^' + ''.join(out) + '$')

"""``tools.which`` — localizar un ejecutable en el ``PATH``.

Fiel a ``odoo19c: odoo/tools/which.py`` (LGPL-3 — copia adaptada con
atribución preservada, DEC-KX-03). Aquella a su vez adapta el parche de Brian
Curtin para ``shutil.which`` (http://bugs.python.org/issue444582), y conserva
cuatro diferencias con el ``shutil.which`` de la stdlib que son las que
justifican que el módulo exista:

* usa ``PATHEXT`` en Windows;
* busca el directorio actual **antes** que el ``PATH`` en Windows, pero no
  antes de un ``path`` pasado explícitamente;
* acepta cadena o iterable para ``path`` y ``pathext``, y acepta el vacío
  (``''`` o ``[]``);
* no busca en el ``PATH`` un archivo cuyo nombre ya trae ruta.

Y cambia el contrato: ``which_files`` devuelve un generador y ``which``
devuelve la primera coincidencia, o levanta ``IOError(ENOENT)``.

``defpath`` y ``defpathext`` se inicializan a nivel de módulo, no en cada
llamada — es la fuente la que lo decide así.

**Divergencia de mecanismo declarada, la única.** La fuente prueba el módulo
con *doctests* en el cuerpo de ``which_files`` y un bloque
``if __name__ == '__main__': doctest.testmod()``. Aquí esos mismos casos viven
en ``tests/unit/tools/test_which.py``, que la suite sí corre; un doctest en el
docstring no lo ejecuta nadie en este árbol y sería un control que no puede
fallar (``metrica-decide-la-conclusion.md``, sub-patrón D).
"""
import sys
from os import F_OK, R_OK, W_OK, X_OK, access, defpath, environ, pathsep
from os.path import dirname, exists, join, split

__docformat__ = 'restructuredtext en'
__all__ = ['F_OK', 'R_OK', 'W_OK', 'X_OK', 'defpath', 'defpathext', 'dirname',
           'pathsep', 'which', 'which_files']

#: ``errno.ENOENT`` sin importar ``errno`` — verbatim de la fuente.
ENOENT = 2

windows = sys.platform.startswith('win')

defpath = environ.get('PATH', defpath).split(pathsep)

if windows:
    # Se puede insertar sin comprobar: los duplicados se quitan justo después.
    defpath.insert(0, '.')
    # Dado el desorden habitual del PATH en Windows, se eliminan duplicados.
    seen = set()
    defpath = [directory for directory in defpath
               if directory.lower() not in seen
               and not seen.add(directory.lower())]
    del seen

    defpathext = [''] + environ.get(
        'PATHEXT',
        '.COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC',
    ).lower().split(pathsep)
else:
    defpathext = ['']


def which_files(file, mode=F_OK | X_OK, path=None, pathext=None):
    """Localiza un archivo en la ruta que trae su propio nombre, en la del
    usuario, o en la que se pase.

    Genera rutas completas (no necesariamente absolutas) en las que el nombre
    dado casa con un archivo existente de un directorio de la ruta.

    :param file: nombre del archivo; si trae directorio, sólo se busca ahí.
    :param mode: modo de acceso que el archivo debe cumplir; por defecto la
        unión de ``os.F_OK`` y ``os.X_OK`` — un ejecutable que existe.
    :param path: la ruta donde buscar. Por defecto la variable ``PATH`` de la
        plataforma; admite cadena separada por ``os.pathsep`` o iterable.
    :param pathext: sólo se usa en Windows, para probar además el nombre con
        cada extensión. Por defecto ``PATHEXT``, o el valor por omisión de
        Windows XP/Vista si no está. El comando **siempre** se prueba primero
        sin extensión, incluso con un ``pathext`` explícito.
    """
    filepath, file = split(file)

    if filepath:
        path = (filepath,)
    elif path is None:
        path = defpath
    elif isinstance(path, str):
        path = path.split(pathsep)

    if pathext is None:
        pathext = defpathext
    elif isinstance(pathext, str):
        pathext = pathext.split(pathsep)

    if '' not in pathext:
        # Siempre se prueba el comando sin extensión, aun con pathext propio.
        pathext.insert(0, '')

    for directory in path:
        basepath = join(directory, file)
        for ext in pathext:
            fullpath = basepath + ext
            if exists(fullpath) and access(fullpath, mode):
                yield fullpath


def which(file, mode=F_OK | X_OK, path=None, pathext=None):
    """La primera coincidencia de :func:`which_files`, o ``IOError(ENOENT)``.

    Misma búsqueda que :func:`which_files`; devuelve la ruta completa (no
    necesariamente absoluta) del primer archivo que casa, y si no hay ninguno
    levanta ``IOError`` con ``errno`` ``ENOENT``.
    """
    path = next(which_files(file, mode, path, pathext), None)
    if path is None:
        raise IOError(ENOENT,
                      '%s not found' % (mode & X_OK and 'command' or 'file'),
                      file)
    return path

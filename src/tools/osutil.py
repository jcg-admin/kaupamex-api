"""``tools.osutil`` — utilidades sobre ``os`` y ``os.path``.

Fiel a ``odoo19c: odoo/tools/osutil.py`` (LGPL-3 — copia adaptada con
atribución preservada, DEC-KX-03).

Los cinco símbolos y sus consumidores medidos en la referencia:

* ``clean_filename`` — ``addons/web/controllers/export.py:554`` y
  ``pivot.py:17``: el nombre con que se descarga un export.
* ``zip_dir`` — ``odoo/service/db.py:279``, el volcado de una base con su
  ``filestore``.
* ``memory_info`` — los tres limitadores de ``service/server.py`` y el
  muestreador de ``tools/profiler.py``.
* ``system_name`` y ``WINDOWS_RESERVED`` no tienen llamador propio: los
  consumen ``memory_info`` y ``clean_filename`` desde este mismo archivo.
"""
import os
import platform
import re
import zipfile

system_name = platform.system()


#: Los nombres que Windows reserva. Un archivo llamado ``CON`` o ``LPT1`` no se
#: puede crear ahí ni siquiera con extensión, así que ``clean_filename`` los
#: sustituye enteros en vez de limpiarlos carácter a carácter.
WINDOWS_RESERVED = re.compile(r'''
    ^
    # raíces prohibidas: palabras reservadas
    (:?CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])
    # incluso con extensión está desaconsejado
    (:?\..*)?
    $
''', flags=re.IGNORECASE | re.VERBOSE)


def clean_filename(name, replacement=''):
    """Quita o sustituye los caracteres problemáticos del nombre dado, para que
    sea un nombre de archivo válido en la mayoría de sistemas operativos
    (incluidos los nombres que Windows reserva).

    Si el resultado queda vacío, devuelve ``"Untitled"``.

    Se admiten:

    * cualquier carácter alfanumérico (unicode);
    * guion bajo (``_``), que es inocuo;
    * punto (``.``) salvo en primera posición, para no crear un archivo oculto;
    * guion medio (``-``) salvo en primera posición, para no confundirlo con
      una opción de comando;
    * corchetes (``[`` y ``]``): aunque en shell son una *clase de caracteres*,
      son una forma común de etiquetar archivos, sobre todo en Windows;
    * paréntesis (``(`` y ``)``), la versión más natural aunque menos común de
      lo anterior;
    * el espacio.

    :param str name: nombre de archivo a limpiar.
    :param str replacement: cadena con la que sustituir cada secuencia
        problemática; por defecto la vacía, que las elimina. Cada secuencia
        contigua de problemas se sustituye por **una sola** ocurrencia.
    :rtype: str
    """
    if WINDOWS_RESERVED.match(name):
        return "Untitled"
    return re.sub(r'[^\w_.()\[\] -]+', replacement, name).lstrip('.-') or "Untitled"


def zip_dir(path, stream, include_dir=True, fnct_sort=None):
    """Comprime el directorio ``path`` en ``stream``.

    :param fnct_sort: función que se pasa al parámetro ``key`` del ``sorted()``
        de Python, para poder ordenar los archivos dentro del ZIP según lo que
        cada consumidor necesite.
    """
    path = os.path.normpath(path)
    len_prefix = len(os.path.dirname(path)) if include_dir else len(path)
    if len_prefix:
        len_prefix += 1

    dir_root_path = os.path.realpath(path)
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED,
                         allowZip64=True) as zipf:
        for dirpath, _dirnames, filenames in os.walk(path):
            filenames = sorted(filenames, key=fnct_sort)
            for fname in filenames:
                bname, ext = os.path.splitext(fname)
                ext = ext or bname
                if ext not in ['.pyc', '.pyo', '.swp', '.DS_Store']:
                    fpath = os.path.normpath(os.path.join(dirpath, fname))
                    real_fpath = os.path.realpath(fpath)
                    # El confinamiento: un enlace que apunte fuera del árbol no
                    # entra al ZIP. Sin este predicado un symlink a /etc se
                    # empaquetaría con el resto.
                    if (os.path.isfile(real_fpath)
                            and os.path.commonpath([dir_root_path, real_fpath])
                            == dir_root_path):
                        zipf.write(real_fpath, fpath[len_prefix:])


def memory_info(process):
    """:return: el uso de memoria que corresponde vigilar en este SO, en bytes.

    :param process: un ``psutil.Process``.
    """
    pmem = process.memory_info()
    # MacOSX asigna un vms enorme a todo proceso, así que ahí sólo se vigila
    # el rss.
    if system_name == 'Darwin':
        return pmem.rss
    return pmem.vms


if os.name != 'nt':
    is_running_as_nt_service = lambda: False  # noqa: E731
else:
    import win32service as ws
    import win32serviceutil as wsu

    from contextlib import contextmanager

    from release import nt_service_name

    def is_running_as_nt_service():
        """¿El proceso actual corre como servicio de Windows?"""
        @contextmanager
        def close_srv(srv):
            try:
                yield srv
            finally:
                ws.CloseServiceHandle(srv)

        try:
            with close_srv(ws.OpenSCManager(
                    None, None, ws.SC_MANAGER_ALL_ACCESS)) as hscm:
                with close_srv(wsu.SmartOpenService(
                        hscm, nt_service_name, ws.SERVICE_ALL_ACCESS)) as hs:
                    info = ws.QueryServiceStatusEx(hs)
                    return info['ProcessId'] == os.getppid()
        except Exception:
            return False

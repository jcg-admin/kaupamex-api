"""Contrato de ``tools.which`` — los casos POSIX de la fuente, ejecutables.

``odoo19c: odoo/tools/which.py:70-110`` prueba el módulo con *doctests* en el
cuerpo de ``which_files`` y un ``if __name__ == '__main__': doctest.testmod()``.
Aquí esos mismos casos viven como pruebas de la suite, que sí se corre — la
divergencia de mecanismo que el docstring del puerto declara.

**Un caso de la fuente NO se porta tal cual, y por medición.** Su control
negativo de modo es ``test_which([], 'sh', mode=W_OK)`` con el comentario
``# not running as root, are you?``. Aquí el proceso corre como ``uid 0``
(medido: ``os.access('/bin/sh', os.W_OK)`` → ``True``), así que ese caso
pasaría por la razón contraria a la que dice medir — el verde que no
discrimina de ``metrica-decide-la-conclusion.md``, sub-patrón D. Se sustituye
por un control de ``X_OK`` sobre un archivo **que existe** y no es ejecutable:
la raíz sí respeta el bit de ejecución (medido: ``0o644`` → ``X_OK`` falso),
así que el control puede fallar y falla por lo que dice medir.
"""
import os
import tempfile

import pytest

from tools import which as which_module
from tools.which import ENOENT, F_OK, which, which_files

#: El ejecutable que la fuente usa como sujeto en su rama POSIX.
SH = '/bin/sh'

posix_only = pytest.mark.skipif(
    which_module.windows, reason='los casos de la fuente son de la rama POSIX')


@posix_only
def test_the_subject_of_the_posix_cases_exists():
    # Premisa de todo lo que sigue: un control negativo apunta a un objeto que
    # existe, y uno positivo también. Si /bin/sh faltara, los casos de abajo
    # pasarían o fallarían por la ausencia y no por la búsqueda.
    assert os.path.exists(SH)
    assert os.access(SH, os.X_OK)


@posix_only
def test_a_bare_name_is_searched_on_the_path():
    assert SH in list(which_files('sh'))


@posix_only
def test_an_explicit_path_narrows_the_search():
    assert SH in list(which_files('sh', path=os.path.dirname(SH)))


@posix_only
def test_pathext_is_inert_outside_windows():
    # ``defpathext`` es [''] fuera de Windows, y el '' se inserta siempre —
    # incluso con un pathext explícito, según el contrato de la fuente.
    assert which_module.defpathext == ['']
    assert SH in list(which_files('sh', pathext='<inexistente>'))


@posix_only
def test_a_name_that_carries_its_own_directory_is_not_searched_on_the_path():
    # La cuarta diferencia declarada con ``shutil.which``: si el nombre trae
    # ruta, esa ruta manda y el PATH no se consulta.
    assert list(which_files(SH)) == [SH]
    assert list(which_files(SH, path='<inexistente>')) == [SH]
    assert list(which_files(SH, pathext='<inexistente>')) == [SH]


@posix_only
def test_an_empty_path_is_accepted_and_yields_nothing():
    # Tercera diferencia declarada: se acepta el vacío, como cadena o iterable.
    assert list(which_files('sh', path='')) == []
    assert list(which_files('sh', path=[])) == []


@posix_only
def test_a_path_given_as_an_iterable_is_accepted():
    assert SH in list(which_files('sh', path=[os.path.dirname(SH)]))


@posix_only
def test_a_nonexistent_directory_finds_nothing():
    assert list(which_files('sh', path='<inexistente>')) == []
    assert list(which_files('<inexistente>/sh')) == []


def test_the_mode_discriminates_over_a_file_that_exists():
    # El control que sustituye al ``mode=W_OK`` de la fuente: el archivo existe
    # y NO es ejecutable, así que el modo por defecto (F_OK | X_OK) no lo
    # encuentra y ``F_OK`` a secas sí. Si el modo se ignorara, las dos
    # aserciones darían el mismo resultado y el caso no diría nada.
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        path = handle.name
    try:
        os.chmod(path, 0o644)
        assert list(which_files(path)) == []
        assert list(which_files(path, mode=F_OK)) == [path]
    finally:
        os.unlink(path)


@posix_only
def test_which_returns_the_first_match():
    found = which('sh')
    assert os.path.basename(found) == 'sh'
    assert found == next(iter(which_files('sh')))


@posix_only
def test_which_raises_ioerror_with_enoent_when_nothing_matches():
    with pytest.raises(IOError) as excinfo:
        which('<inexistente>/sh')
    assert excinfo.value.errno == ENOENT
    # El mensaje distingue comando de archivo según el modo pedido.
    assert 'command' in str(excinfo.value)
    with pytest.raises(IOError) as excinfo:
        which('<inexistente>/sh', mode=F_OK)
    assert 'file' in str(excinfo.value)


def test_the_public_surface_is_the_one_the_source_declares():
    assert which_module.__all__ == [
        'F_OK', 'R_OK', 'W_OK', 'X_OK', 'defpath', 'defpathext', 'dirname',
        'pathsep', 'which', 'which_files']
    assert which_module.__docformat__ == 'restructuredtext en'
    assert ENOENT == 2

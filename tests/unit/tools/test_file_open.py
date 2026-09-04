"""``file_open_temporary_directory`` y el confinamiento de ``file_path`` (#131).

≙ ``odoo19c: odoo/tools/misc.py:196-313`` — las tres funciones son una sola
pieza: ``file_path`` decide qué rutas son legítimas, ``file_open`` sólo abre lo
que aquélla acepta, y ``file_open_temporary_directory`` **amplía** el conjunto
de raíces legítimas por transacción, para que la instalación de un módulo desde
un zip pueda leer lo que acaba de extraer sin abrir el árbol entero.

Qué haría fallar a estos casos
==============================

El confinamiento es una guarda de seguridad, así que su verde tiene que
discriminar (sub-patrón D de ``metrica-decide-la-conclusion.md``):

- El caso negativo apunta a ``/etc/passwd``, que **existe**. Pedir una ruta
  inexistente haría que el rechazo lo produjera ``os.path.exists`` y no la
  guarda: el caso pasaría con el confinamiento retirado.
- El temporal se prueba en los dos sentidos — dentro del contexto se acepta,
  al salir se rechaza — porque un registro que nunca se limpia deja la raíz
  abierta para el resto del proceso, que es el fallo silencioso que el
  ``finally`` de la fuente evita.
- El aislamiento se prueba contra **otra conexión**: si el registro viviera en
  un global, este caso pasaría a verde sin que existiera aislamiento alguno.
"""
import os
import pathlib
import threading

import pytest
from django.db import DEFAULT_DB_ALIAS, connections

import addons.base
from tools.misc import file_open, file_open_temporary_directory, file_path

#: Un archivo que existe bajo una raíz de addons — el control positivo.
INSIDE_ADDONS = 'base/__init__.py'


class TestThePathIsConfined:
    """Sólo se acepta lo que queda bajo una raíz conocida."""

    def test_a_relative_path_under_an_addons_root_resolves(self):
        resolved = file_path(INSIDE_ADDONS)

        assert os.path.isabs(resolved)
        assert os.path.exists(resolved)

    def test_a_traversal_to_an_existing_file_outside_is_refused(self):
        """``/etc/passwd`` EXISTE: lo que rechaza es la guarda, no la ausencia."""
        assert os.path.exists('/etc/passwd'), 'el caso negativo perdió su objeto'

        with pytest.raises(FileNotFoundError):
            file_path('../../../../etc/passwd')

    def test_an_absolute_path_outside_every_root_is_refused(self):
        with pytest.raises(FileNotFoundError):
            file_path('/etc/passwd')

    def test_an_unsupported_extension_is_refused_before_looking(self):
        with pytest.raises(ValueError):
            file_path(INSIDE_ADDONS, filter_ext=('.png',))


class TestTheTemporaryDirectoryWidensTheRoots:
    """≙ ``file_open_temporary_directory`` — la raíz extra, y sólo mientras dura."""

    def test_a_file_inside_the_temporary_directory_resolves_with_env(self):
        with file_open_temporary_directory(DEFAULT_DB_ALIAS) as module_dir:
            target = pathlib.Path(module_dir) / 'foo' / '__manifest__.py'
            target.parent.mkdir(parents=True)
            target.write_text("{'name': 'foo'}\n")

            assert file_path('foo/__manifest__.py',
                             env=DEFAULT_DB_ALIAS) == str(target)

    def test_without_env_the_temporary_root_is_not_consulted(self):
        """El parámetro es el que abre la raíz: sin él, la guarda sigue cerrada."""
        with file_open_temporary_directory(DEFAULT_DB_ALIAS) as module_dir:
            target = pathlib.Path(module_dir) / 'foo' / '__manifest__.py'
            target.parent.mkdir(parents=True)
            target.write_text("{'name': 'foo'}\n")

            with pytest.raises(FileNotFoundError):
                file_path('foo/__manifest__.py')

    def test_leaving_the_context_closes_the_root_again(self):
        with file_open_temporary_directory(DEFAULT_DB_ALIAS) as module_dir:
            target = pathlib.Path(module_dir) / 'foo' / '__manifest__.py'
            target.parent.mkdir(parents=True)
            target.write_text("{'name': 'foo'}\n")
            saved = str(target)

        with pytest.raises(FileNotFoundError):
            file_path('foo/__manifest__.py', env=DEFAULT_DB_ALIAS)
        assert not os.path.exists(saved), 'el temporal debe borrarse al salir'

    def test_the_registry_is_empty_again_after_the_context(self):
        before = list(getattr(connections[DEFAULT_DB_ALIAS],
                             '_file_open_tmp_paths', []))
        with file_open_temporary_directory(DEFAULT_DB_ALIAS):
            during = list(connections[DEFAULT_DB_ALIAS]._file_open_tmp_paths)
        after = list(connections[DEFAULT_DB_ALIAS]._file_open_tmp_paths)

        assert len(during) == len(before) + 1
        assert after == before

    def test_the_registry_is_cleaned_even_when_the_body_raises(self):
        """El ``finally`` de la fuente: una raíz que no se cierra queda abierta."""
        before = list(getattr(connections[DEFAULT_DB_ALIAS],
                             '_file_open_tmp_paths', []))
        with pytest.raises(RuntimeError):
            with file_open_temporary_directory(DEFAULT_DB_ALIAS):
                raise RuntimeError('el cuerpo revienta')

        assert list(connections[DEFAULT_DB_ALIAS]._file_open_tmp_paths) == before


class TestTheTemporaryRootIsPerTransaction:
    """Otra transacción no ve el temporal — el aislamiento que la fuente promete.

    ``connections[alias]`` es ``local`` al thread, así que otro thread recibe otro
    objeto de conexión —otra transacción— y su registro nace vacío. Si la lista
    viviera en un global del módulo, este caso pasaría a verde **sin** que
    existiera aislamiento alguno: por eso mide desde el otro thread y no desde
    éste.
    """

    def test_another_transaction_does_not_see_it(self):
        seen = {}

        def from_another_thread():
            seen['registry'] = list(
                getattr(connections[DEFAULT_DB_ALIAS],
                        '_file_open_tmp_paths', []))
            try:
                seen['path'] = file_path('foo/__manifest__.py',
                                          env=DEFAULT_DB_ALIAS)
            except FileNotFoundError as exc:
                seen['path'] = exc

        with file_open_temporary_directory(DEFAULT_DB_ALIAS) as module_dir:
            target = pathlib.Path(module_dir) / 'foo' / '__manifest__.py'
            target.parent.mkdir(parents=True)
            target.write_text("{'name': 'foo'}\n")

            assert file_path('foo/__manifest__.py', env=DEFAULT_DB_ALIAS)

            thread = threading.Thread(target=from_another_thread)
            thread.start()
            thread.join()

        assert seen['registry'] == [], 'el otro hilo hereda la raíz temporal'
        assert isinstance(seen['path'], FileNotFoundError)


class TestALoadedAddonPinsItsOwnRoot:
    """≙ el tramo ``sys.modules.get(f'odoo.addons.{...}')`` de la fuente.

    Si la primera componente de la ruta relativa nombra un addon **ya
    importado**, sólo se acepta su propio ``__path__``: dos raíces con un addon
    homónimo no se pisan, y el que gana es el que el proceso cargó.
    """

    def test_the_path_of_the_loaded_module_wins(self):
        resolved = file_path(INSIDE_ADDONS)

        expected = os.path.dirname(list(addons.base.__path__)[0])
        assert resolved.startswith(expected + os.sep)

    def test_a_temporary_root_cannot_impersonate_a_loaded_addon(self):
        """Lo que discrimina: sin el tramo del módulo cargado, esto resolvería.

        El temporal contiene ``base/nada_de_esto.py``; la raíz propia de
        ``addons.base`` no. Como la primera componente nombra un addon ya
        importado, la fuente **descarta** las demás raíces — incluida la
        temporal — y el archivo no aparece.
        """
        with file_open_temporary_directory(DEFAULT_DB_ALIAS) as module_dir:
            impostor = pathlib.Path(module_dir) / 'base' / 'nada_de_esto.py'
            impostor.parent.mkdir(parents=True)
            impostor.write_text('# no soy el base cargado\n')

            with pytest.raises(FileNotFoundError):
                file_path('base/nada_de_esto.py', env=DEFAULT_DB_ALIAS)


class TestFileOpenInheritsTheConfinement:
    """``file_open`` abre sólo lo que ``file_path`` acepta."""

    def test_it_opens_a_file_inside_a_temporary_directory(self):
        with file_open_temporary_directory(DEFAULT_DB_ALIAS) as module_dir:
            target = pathlib.Path(module_dir) / 'foo' / '__manifest__.py'
            target.parent.mkdir(parents=True)
            target.write_text("{'name': 'foo'}\n")

            with file_open('foo/__manifest__.py', env=DEFAULT_DB_ALIAS) as f:
                assert f.read() == "{'name': 'foo'}\n"

    def test_it_refuses_to_create_a_new_file(self):
        """*"Don't let create new files"* — verbatim de la fuente."""
        with file_open_temporary_directory(DEFAULT_DB_ALIAS) as module_dir:
            assert os.path.isdir(module_dir)

            with pytest.raises(FileNotFoundError):
                file_open('foo/nuevo.py', mode='w', env=DEFAULT_DB_ALIAS)

    def test_text_mode_forces_utf8(self):
        with file_open(INSIDE_ADDONS) as f:
            assert f.encoding.lower().replace('-', '') == 'utf8'

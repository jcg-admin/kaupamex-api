"""Contrato de ``tools.osutil`` — nombre de archivo, ZIP y memoria.

Fuente: ``odoo19c: odoo/tools/osutil.py``. La fuente no trae pruebas propias;
estos casos miden el contrato que sus consumidores medidos usan — el nombre con
que se descarga un export, el volcado de una base con su ``filestore``, y el
uso de memoria que vigilan los tres limitadores del servidor.

**El caso del enlace que apunta fuera del árbol es el control que discrimina.**
Apunta a un archivo que **existe** (``metrica-decide-la-conclusion.md``,
sub-patrón D): si apuntara a una ruta inexistente, el ``os.path.isfile`` del
propio ``zip_dir`` lo descartaría y el caso pasaría en verde aunque el
predicado de confinamiento no estuviera escrito.
"""
import io
import os
import platform
import zipfile

import pytest

from tools import osutil
from tools.osutil import (WINDOWS_RESERVED, clean_filename,
                          is_running_as_nt_service, memory_info, system_name,
                          zip_dir)


class TestCleanFilename:
    """El nombre con que ``export.py`` y ``pivot.py`` sirven una descarga."""

    @pytest.mark.parametrize('reserved', [
        'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM9', 'LPT1', 'LPT9',
        'con', 'Nul', 'CON.txt', 'lpt3.csv',
    ])
    def test_a_windows_reserved_name_is_replaced_whole(self, reserved):
        # Se sustituye entero, no carácter a carácter: en Windows no existe un
        # archivo llamado CON ni siquiera con extensión.
        assert WINDOWS_RESERVED.match(reserved)
        assert clean_filename(reserved) == 'Untitled'

    @pytest.mark.parametrize('allowed', [
        'informe 2026.csv', 'ventas_Q1.xlsx', 'lista [borrador].txt',
        'reporte (final).pdf', 'año-fiscal.csv', 'ñandú.txt',
    ])
    def test_the_allowed_characters_survive_untouched(self, allowed):
        assert clean_filename(allowed) == allowed

    def test_a_run_of_problem_characters_collapses_into_one_replacement(self):
        # «Cada secuencia contigua de problemas se sustituye por UNA sola
        # ocurrencia» — con el default vacío desaparece; con uno explícito, una.
        assert clean_filename('a///b') == 'ab'
        assert clean_filename('a///b', '_') == 'a_b'
        assert clean_filename('a/*?b', '-') == 'a-b'

    def test_a_leading_dot_or_dash_is_stripped(self):
        # Un punto delante crearía un archivo oculto; un guion delante se
        # confundiría con una opción de comando.
        assert clean_filename('.oculto') == 'oculto'
        assert clean_filename('-opcion') == 'opcion'
        assert clean_filename('..-.-nombre') == 'nombre'
        # En medio del nombre no se toca.
        assert clean_filename('a.b-c') == 'a.b-c'

    def test_an_empty_result_falls_back_to_untitled(self):
        assert clean_filename('') == 'Untitled'
        assert clean_filename('///') == 'Untitled'
        assert clean_filename('...') == 'Untitled'


class TestZipDir:
    """El volcado que ``service/db.py`` usa para empaquetar una base."""

    @staticmethod
    def _names(path, **kwargs):
        stream = io.BytesIO()
        zip_dir(path, stream, **kwargs)
        with zipfile.ZipFile(stream) as zipf:
            return zipf.namelist()

    def test_include_dir_decides_whether_the_root_name_is_kept(self, tmp_path):
        root = tmp_path / 'filestore'
        root.mkdir()
        (root / 'a.txt').write_text('uno')

        assert self._names(str(root)) == ['filestore/a.txt']
        assert self._names(str(root), include_dir=False) == ['a.txt']

    def test_the_ignored_extensions_never_enter_the_archive(self, tmp_path):
        root = tmp_path / 'modulo'
        root.mkdir()
        for name in ('a.txt', 'a.pyc', 'a.pyo', 'a.swp', '.DS_Store'):
            (root / name).write_text('x')
        # ``.DS_Store`` no tiene extensión para ``splitext``: el ``ext or bname``
        # de la fuente es lo que lo descarta igual.
        assert self._names(str(root), include_dir=False) == ['a.txt']

    def test_the_sort_key_orders_the_entries(self, tmp_path):
        root = tmp_path / 'orden'
        root.mkdir()
        for name in ('b.txt', 'a.txt', 'c.txt'):
            (root / name).write_text('x')

        assert self._names(str(root), include_dir=False) == [
            'a.txt', 'b.txt', 'c.txt']
        assert self._names(str(root), include_dir=False,
                           fnct_sort=lambda n: -ord(n[0])) == [
            'c.txt', 'b.txt', 'a.txt']

    def test_a_symlink_pointing_outside_the_tree_is_left_out(self, tmp_path):
        # El control que puede fallar. El destino EXISTE y es legible: si el
        # predicado de confinamiento desapareciera, el archivo de fuera
        # entraría al ZIP y este caso lo vería.
        outside = tmp_path / 'secreto.txt'
        outside.write_text('no debe viajar')
        root = tmp_path / 'filestore'
        root.mkdir()
        (root / 'propio.txt').write_text('si viaja')
        os.symlink(outside, root / 'fuga.txt')

        assert outside.is_file()
        assert (root / 'fuga.txt').is_file()   # el enlace resuelve
        assert self._names(str(root), include_dir=False) == ['propio.txt']

    def test_a_symlink_pointing_inside_the_tree_does_travel(self, tmp_path):
        # El control positivo del mismo predicado: sin él, el caso anterior no
        # distinguiría «confina» de «descarta todo enlace».
        root = tmp_path / 'filestore'
        (root / 'sub').mkdir(parents=True)
        (root / 'sub' / 'real.txt').write_text('dentro')
        os.symlink(root / 'sub' / 'real.txt', root / 'alias.txt')

        assert sorted(self._names(str(root), include_dir=False)) == [
            'alias.txt', 'sub/real.txt']


class _FakeMemoryInfo:
    """Lo mínimo del ``psutil.Process`` que ``memory_info`` consume."""

    def __init__(self, rss, vms):
        self.rss = rss
        self.vms = vms


class _FakeProcess:
    def __init__(self, rss, vms):
        self._info = _FakeMemoryInfo(rss, vms)

    def memory_info(self):
        return self._info


class TestMemoryInfo:
    """Lo que vigilan los tres limitadores de ``service/server.py``."""

    def test_darwin_watches_the_resident_size(self, monkeypatch):
        monkeypatch.setattr(osutil, 'system_name', 'Darwin')
        assert osutil.memory_info(_FakeProcess(rss=100, vms=900)) == 100

    @pytest.mark.parametrize('system', ['Linux', 'Windows', 'FreeBSD'])
    def test_the_rest_watch_the_virtual_size(self, monkeypatch, system):
        # MacOSX asigna un vms enorme a todo proceso; el resto sí lo vigila.
        monkeypatch.setattr(osutil, 'system_name', system)
        assert osutil.memory_info(_FakeProcess(rss=100, vms=900)) == 900

    def test_the_measured_system_is_the_one_platform_reports(self):
        assert system_name == platform.system()
        assert memory_info(_FakeProcess(rss=1, vms=2)) in (1, 2)


@pytest.mark.skipif(os.name == 'nt', reason='la rama NT necesita win32service')
def test_outside_windows_the_service_probe_is_always_false():
    # La rama ``os.name != 'nt'`` de la fuente: una lambda constante. Aquí es
    # el único camino ejecutable, y su contrato es devolver False sin tocar el
    # gestor de servicios.
    assert is_running_as_nt_service() is False

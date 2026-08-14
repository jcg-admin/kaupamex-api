"""El gate de raíz detecta un addon partido entre las dos raíces (H-API-572).

Estos tests son **puros**: no tocan Django ni la base. Miden el instrumento,
no el árbol — el árbol lo mide el gate cuando corre sin `roots`.

El control positivo NO es fabricado por quien escribió el patrón: reproduce la
forma exacta del episodio —un addon con `controllers/` nuevo bajo la raíz vieja
mientras su cuerpo ya vive en la nueva— que es lo que produjo el
``CONFLICT (file location)`` del merge de `develop`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))

from check_addon_root import addon_dirs, split_addons


def make_addon(root: Path, nombre: str, *, subpaquete: str | None = None) -> Path:
    """Crea un addon mínimo (paquete Python) bajo ``root``."""
    ruta = root / nombre
    ruta.mkdir(parents=True)
    (ruta / '__init__.py').write_text('')
    if subpaquete:
        sub = ruta / subpaquete
        sub.mkdir()
        (sub / '__init__.py').write_text('')
        (sub / 'urls.py').write_text('urlpatterns = []\n')
    return ruta


@pytest.fixture
def dos_raices(tmp_path):
    vieja = tmp_path / 'src' / 'addons'
    nueva = tmp_path / 'addons'
    vieja.mkdir(parents=True)
    nueva.mkdir(parents=True)
    return vieja, nueva


def test_arbol_sano_no_reporta_partidos(dos_raices):
    """El reparto correcto: cada addon en una sola raíz."""
    vieja, nueva = dos_raices
    make_addon(vieja, 'base')
    make_addon(nueva, 'account')
    make_addon(nueva, 'sale')

    partidos, total = split_addons(roots=(vieja, nueva))

    assert partidos == {}
    assert total == 3, 'el denominador cuenta nombres únicos, no directorios'


def test_addon_partido_por_subpaquete_nuevo_en_la_raiz_vieja(dos_raices):
    """La forma del episodio: el cuerpo migró, un ``controllers/`` nuevo no."""
    vieja, nueva = dos_raices
    make_addon(nueva, 'account_check_printing')          # el cuerpo, ya movido
    make_addon(vieja, 'account_check_printing',          # lo que trajo el merge
               subpaquete='controllers')

    partidos, total = split_addons(roots=(vieja, nueva))

    assert list(partidos) == ['account_check_printing']
    assert len(partidos['account_check_printing']) == 2
    assert total == 1, 'un nombre partido sigue siendo UN addon en el denominador'


def test_reporta_todos_los_partidos_no_solo_el_primero(dos_raices):
    """Un merge parte varios addons a la vez; el gate no puede quedarse en uno."""
    vieja, nueva = dos_raices
    for nombre in ('account_check_printing', 'account_debit_note',
                   'account_update_tax_tags'):
        make_addon(nueva, nombre)
        make_addon(vieja, nombre, subpaquete='controllers')
    make_addon(vieja, 'base')

    partidos, _ = split_addons(roots=(vieja, nueva))

    assert sorted(partidos) == ['account_check_printing', 'account_debit_note',
                                'account_update_tax_tags']


def test_ignora_directorios_que_no_son_paquete(dos_raices):
    """``__pycache__``, ``.git`` y un directorio de datos no son addons."""
    vieja, nueva = dos_raices
    make_addon(nueva, 'account')
    for ruido in ('__pycache__', '.mypy_cache', 'datos_sueltos'):
        (nueva / ruido).mkdir()

    assert addon_dirs(nueva) == {'account'}


def test_raiz_inexistente_no_revienta(tmp_path):
    """Un clon sin una de las raíces mide lo que hay, no falla."""
    nueva = tmp_path / 'addons'
    nueva.mkdir()
    make_addon(nueva, 'account')

    partidos, total = split_addons(roots=(tmp_path / 'no-existe', nueva))

    assert partidos == {}
    assert total == 1

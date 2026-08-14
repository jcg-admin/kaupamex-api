"""Regresiones de ``kaupamex-bin`` — el punto de entrada del producto L0.

Cubren el contrato que se adopta de ``odoo19c: odoo/cli/command.py:main``:
comando explícito, ayuda sin comando, y **default ``server``**. Ese último es el
que sostiene la partición por proceso de la referencia, así que se prueba en los
dos sentidos: que aplique cuando no hay comando y que **no** aplique cuando sí.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from addons.base.management.commands.server import Command as ServerCommand
from tests.subprocess_env import subprocess_env
from cli import command as cli_command

REPO_ROOT = Path(__file__).resolve().parents[3]
BIN = REPO_ROOT / 'kaupamex-bin'


@pytest.fixture
def capturado(monkeypatch):
    """Sustituye el dispatcher de Django y devuelve el argv que recibiría."""
    visto = {}

    def falso_execute(argv):
        visto['argv'] = list(argv)

    monkeypatch.setattr(cli_command, 'execute_from_command_line', falso_execute)
    return visto


def test_sin_comando_despacha_server(capturado):
    """Sin comando → ``server``. Es el default de la referencia."""
    cli_command.main(['kaupamex-bin'])
    assert capturado['argv'] == ['kaupamex-bin', 'server']


def test_sin_comando_conserva_las_banderas(capturado):
    """El default no se traga los argumentos que ya venían."""
    cli_command.main(['kaupamex-bin', '--config', '/tmp/x.py'])
    assert capturado['argv'] == ['kaupamex-bin', 'server', '--config', '/tmp/x.py']


def test_comando_explicito_no_se_toca(capturado):
    """Con comando nombrado, ``main`` no interfiere: pasa tal cual."""
    cli_command.main(['kaupamex-bin', 'company_create', '--name', 'acme'])
    assert capturado['argv'] == ['kaupamex-bin', 'company_create', '--name', 'acme']


@pytest.mark.parametrize('bandera', ['-h', '--help'])
def test_ayuda_sin_comando_despacha_help(capturado, bandera):
    """``-h``/``--help`` sin comando → ``help``, y la bandera no se reenvía."""
    cli_command.main(['kaupamex-bin', bandera])
    assert capturado['argv'] == ['kaupamex-bin', 'help']


def test_el_binario_existe_y_es_ejecutable():
    """El shim vive en la raíz y tiene bit de ejecución (== ``odoo-bin``)."""
    assert BIN.is_file(), f'falta el shim en {BIN}'
    assert BIN.stat().st_mode & 0o111, 'el shim no es ejecutable'


def test_el_binario_lista_el_comando_server():
    """Extremo a extremo: el shim arranca y ``server`` está registrado.

    No usa el dispatcher falso — corre el binario de verdad, que es lo único
    que prueba que el ``sys.path`` del shim resuelve.
    """
    salida = subprocess.run(
        [sys.executable, str(BIN), '--help'],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=120,
        env=subprocess_env(),
    )
    assert 'server' in salida.stdout, salida.stdout[-500:] + salida.stderr[-500:]


def test_server_sale_2_si_falta_la_configuracion():
    """Sin config, el comando **falla** en vez de arrancar con defaults.

    El bind, los workers y el timeout son decisiones del despliegue: arrancar
    con valores inventados sería peor que no arrancar.
    """
    cmd = ServerCommand()
    with pytest.raises(SystemExit) as exc:
        cmd.handle(config='/ruta/que/no/existe.py')
    assert exc.value.code == 2

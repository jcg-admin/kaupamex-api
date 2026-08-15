"""Regresiones de ``kaupamex-bin`` — el punto de entrada del producto L0.

Cubren el contrato que se adopta de ``odoo19c: odoo/cli/command.py:main``:
comando explícito, ayuda sin comando, y **default ``server``**. Ese último es el
que sostiene la partición por proceso de la referencia, así que se prueba en los
dos sentidos: que aplique cuando no hay comando y que **no** aplique cuando sí.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.db.utils import DatabaseError

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


# --- Perfil por defecto y preparación de la base (H-API-636) ----------------
#
# Los dos ejes que la referencia resuelve dentro de su comando por defecto:
# `odoo19c: odoo/tools/config.py:223` declara el perfil como opción con
# `env_name='ODOO_RC'` y cae en sus `my_default` abiertos cuando nadie lo
# declara; `odoo/cli/server.py:100-110` deja la base utilizable ANTES de servir.


def test_perfil_por_defecto_es_el_abierto(capturado, monkeypatch):
    """Sin declarar nada se cae en ``development``, como la referencia.

    Cablear ``production`` hacía que el camino sin declarar nada fuera el más
    endurecido: ``SECURE_SSL_REDIRECT = True`` devuelve 301 en todo, incluido
    ``/api/schema/``.
    """
    monkeypatch.delenv('DJANGO_SETTINGS_MODULE', raising=False)
    cli_command.main(['kaupamex-bin', 'server'])
    assert os.environ['DJANGO_SETTINGS_MODULE'] == 'config.settings.development'


def test_el_perfil_declarado_gana(capturado, monkeypatch):
    """Es ``setdefault``: quien declara producción la obtiene.

    Lo hacen ``setup/kaupamex.service`` y ``setup/kaupamex-cron.service``, así
    que invertir el default no relaja el despliegue.
    """
    monkeypatch.setenv('DJANGO_SETTINGS_MODULE', 'config.settings.production')
    cli_command.main(['kaupamex-bin', 'server'])
    assert os.environ['DJANGO_SETTINGS_MODULE'] == 'config.settings.production'


def test_stop_after_init_prepara_y_no_arranca(monkeypatch):
    """``--stop-after-init`` deja la base lista y vuelve, sin ``execvp``."""
    corridos = []
    monkeypatch.setattr(
        'addons.base.management.commands.server.call_command',
        lambda nombre, **kw: corridos.append(nombre),
    )
    monkeypatch.setattr(
        'os.execvp',
        lambda *a: pytest.fail('no debe arrancar con --stop-after-init'),
    )
    ServerCommand().handle(config=str(REPO_ROOT / 'setup' / 'gunicorn.conf.py'),
                           stop_after_init=True)
    assert corridos == ['migrate', 'createcachetable']


def test_no_init_salta_la_preparacion(monkeypatch):
    """``--no-init`` es el escape: no toca la base."""
    corridos = []
    monkeypatch.setattr(
        'addons.base.management.commands.server.call_command',
        lambda nombre, **kw: corridos.append(nombre),
    )
    monkeypatch.setattr('os.execvp', lambda *a: None)
    ServerCommand().handle(config=str(REPO_ROOT / 'setup' / 'gunicorn.conf.py'),
                           no_init=True, stop_after_init=True)
    assert corridos == []


def test_la_preparacion_no_aborta_por_error_de_base(monkeypatch):
    """Un fallo de base baja a INFO y **sigue** — como la referencia.

    ``odoo/cli/server.py:105-108`` usa INFO a propósito para no llenar de
    advertencias un entorno con acceso restringido, y continúa hasta
    ``server.start()``. ``setup/kaupamex.service`` declara la misma postura al
    usar ``Wants`` y no ``Requires`` para PostgreSQL.
    """
    def revienta(nombre, **kw):
        raise DatabaseError('permission denied for schema public')

    monkeypatch.setattr(
        'addons.base.management.commands.server.call_command', revienta,
    )
    arrancado = []
    monkeypatch.setattr('os.execvp', lambda *a: arrancado.append(a))
    ServerCommand().handle(config=str(REPO_ROOT / 'setup' / 'gunicorn.conf.py'))
    assert arrancado, 'el servidor debe arrancar aunque la base no responda'

"""Las opciones SMTP de producción que leen los lectores de ``tools.config``.

≙ ``--from-filter``, ``--smtp-ssl-certificate-filename`` y
``--smtp-ssl-private-key-filename`` (``odoo19c: odoo/tools/config.py:352,
364,366``). Producción las declara en el registro de opciones; sin ellas,
``tools.config.from_filter()`` y los certificados no se podrían fijar en un
despliegue. ``EMAIL_BACKEND`` deja de existir: ningún código envía por
``django.core.mail``.
"""
import subprocess
import sys
from pathlib import Path

from tests.subprocess_env import subprocess_env

SRC = Path(__file__).resolve().parents[3] / 'src'

PROBE = (
    'import config.settings.production as p; '
    'print(p.EMAIL_FROM_FILTER, p.EMAIL_SSL_CERTFILE, p.EMAIL_SSL_KEYFILE, '
    "hasattr(p, 'EMAIL_BACKEND'))"
)


def _production(**extra):
    env = subprocess_env(**extra)
    return subprocess.run(
        [sys.executable, '-c', PROBE], cwd=SRC, env=env,
        capture_output=True, text=True, check=True).stdout.split()


def test_production_reads_the_smtp_options_from_the_environment():
    assert _production(
        EMAIL_FROM_FILTER='kaupamex.mx', EMAIL_SSL_CERTFILE='/c.pem',
        EMAIL_SSL_KEYFILE='/k.pem',
    ) == ['kaupamex.mx', '/c.pem', '/k.pem', 'False']

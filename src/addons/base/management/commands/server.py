"""``server`` — levanta el servidor de aplicación del producto L0.

Equivalente de ``odoo19c: odoo/cli/server.py`` (``class Server(Command)``), que
es el comando por defecto del binario y cuyo trabajo real lo hace
``odoo/service/server.py``.

Aquí la partición es la misma con otros nombres: **este comando no implementa un
servidor**, delega en Gunicorn, que desde ADR-027 viaja dentro del producto como
dependencia de producción y trae su configuración en ``setup/gunicorn.conf.py``.
Es el mismo criterio con el que ``src/service/server.py`` quedó como stub
documentado: el runtime no se reimplementa.

Por qué ``execvp`` y no lanzar Gunicorn en proceso
---------------------------------------------------

``os.execvp`` **reemplaza** este proceso por Gunicorn en vez de envolverlo. Eso
deja el árbol de procesos igual al de invocarlo a mano — sin un padre Python
intermedio que reenvíe señales— así que ``SIGTERM`` de systemd llega al master
de Gunicorn directamente y el reciclado de workers funciona sin traducción.

Envolverlo habría exigido reimplementar el manejo de señales y el código de
salida: precisamente el trabajo que delegar en el runtime evita.
"""

import os
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

#: Config de Gunicorn, relativa a la raíz del repositorio (dos niveles sobre
#: ``src/``). Es la misma que documenta ``setup/gunicorn.conf.py`` para la
#: invocación a mano: ``gunicorn -c setup/gunicorn.conf.py``.
_CONF = Path(__file__).resolve().parents[5] / 'setup' / 'gunicorn.conf.py'


class Command(BaseCommand):
    help = (
        'Levanta el servidor de aplicacion (Gunicorn) con la configuracion de '
        'setup/gunicorn.conf.py. Es el comando por defecto de kaupamex-bin.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--config', default=str(_CONF),
            help='Ruta a la configuracion de Gunicorn (default: setup/gunicorn.conf.py).',
        )

    def handle(self, *args, **options):
        conf = Path(options['config'])
        if not conf.is_file():
            # Sin config no se arranca con defaults silenciosos: el bind, los
            # workers y el timeout son decisiones del despliegue, no del binario.
            self.stderr.write(f'configuracion de Gunicorn no encontrada: {conf}')
            sys.exit(2)
        argv = ['gunicorn', '-c', str(conf)]
        self.stdout.write(f'exec: {" ".join(argv)}')
        os.execvp('gunicorn', argv)

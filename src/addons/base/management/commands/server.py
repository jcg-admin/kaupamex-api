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

import logging
import os
import sys
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.utils import DatabaseError

_logger = logging.getLogger(__name__)

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
        parser.add_argument(
            '--no-init', action='store_true',
            help='No preparar la base antes de arrancar (equivale a saltar el bloque '
                 'de auto-creacion de la referencia).',
        )
        parser.add_argument(
            '--stop-after-init', action='store_true',
            help='Preparar la base y salir, sin levantar el servidor '
                 '(== stop_after_init de la referencia).',
        )

    def handle(self, *args, **options):
        conf = Path(options['config'])
        if not conf.is_file():
            # Sin config no se arranca con defaults silenciosos: el bind, los
            # workers y el timeout son decisiones del despliegue, no del binario.
            self.stderr.write(f'configuracion de Gunicorn no encontrada: {conf}')
            sys.exit(2)

        # `.get()` y no `[]`: el comando se instancia directo en los tests, sin
        # pasar por `add_arguments`, así que las banderas pueden no venir.
        if not options.get('no_init'):
            self._init_database()

        if options.get('stop_after_init'):
            return

        argv = ['gunicorn', '-c', str(conf)]
        self.stdout.write(f'exec: {" ".join(argv)}')
        os.execvp('gunicorn', argv)

    def _init_database(self):
        """Deja la base utilizable antes de servir la primera peticion.

        Adaptacion de ``odoo19c: odoo/cli/server.py:100-110``, el bloque que
        corre ANTES de ``server.start()``. Alli el trabajo es
        ``db._create_empty_database(db_name)`` seguido de
        ``config['init']['base'] = True``: crear la base **e instalar su nucleo**
        en el mismo arranque.

        Aqui la base la crea el aprovisionamiento (``db: provisioners/postgresql/
        db_setup.sh``), asi que lo que falta es su segunda mitad — el esquema y
        los datos de arranque: ``migrate`` (que aplica las migraciones de todos
        los addons instalados, el analogo de instalar ``base``) y
        ``createcachetable`` (que materializa ``cache_table``, sin la cual el
        backend ``DatabaseCache`` responde 500 en la primera peticion).

        Se portan las tres propiedades del bloque de la referencia, que valen por
        separado:

        1. **Idempotente.** Alla se traga ``db.DatabaseExists``; aqui los dos
           comandos son no-op cuando ya se aplicaron.
        2. **No aborta por falta de privilegio.** La referencia baja a ``INFO``
           con su razon escrita en el codigo —*"avoid reporting unnecessary
           warnings on build environment using restricted database access"*— y
           **sigue** hasta ``server.start()``. Igual aqui: el servidor arranca y
           los workers fallaran en la primera peticion si la base no responde,
           que es la conducta que ``setup/kaupamex.service`` ya declara al usar
           ``Wants`` y no ``Requires`` para PostgreSQL.
        3. **Corre antes de servir.** Por eso va antes del ``execvp``: despues no
           habria proceso donde correrlo.

        Lo que NO hace, y es deliberado: sembrar una empresa o un superusuario.
        La empresa inicial se declara en config (``BOOTSTRAP_COMPANY_CODE``, con
        ``default=''``) y la crea ``kaupamex-bin company_create``; con la clave
        vacia ``seed()`` es un no-op. La referencia tampoco nombra una empresa
        real al arrancar.
        """
        for comando in ('migrate', 'createcachetable'):
            try:
                call_command(comando, verbosity=0)
            except DatabaseError as err:
                # INFO a proposito, igual que la referencia: un entorno con
                # acceso restringido a la base no deberia llenar el arranque de
                # advertencias por algo que puede ser correcto en su despliegue.
                _logger.info(
                    'No se pudo preparar la base con %s, se omite: %s', comando, err,
                )
                self.stdout.write(f'{comando}: omitido ({err})')
            else:
                self.stdout.write(f'{comando}: ok')

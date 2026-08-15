"""``cli.command`` — el ``main()`` del binario, espejo de ``odoo19c:
odoo/cli/command.py:main`` (``odoo-tools@622ddc2a``).

Qué se adopta de la referencia
-------------------------------

Su ``main()`` hace cuatro cosas, y las cuatro se conservan:

1. resuelve el nombre del comando desde el primer argumento que no empieza
   con guion;
2. si se pide ayuda (``-h``/``--help``) sin comando, despacha ``help``;
3. **sin comando, el default es ``server``** — correr el binario a secas
   levanta el servidor;
4. comando desconocido → mensaje que apunta a ``--help`` y salida no-cero.

El punto 3 es el que importa para la arquitectura: en la referencia el servidor
web **es un comando entre dieciséis** (``odoo19c: odoo/cli/server.py:122``,
``class Server(Command)``), no el programa. Esa partición por subcomando es la
frontera de confianza que hace natural correr ``kaupamex-bin server`` y
``kaupamex-bin company_create`` como procesos —y credenciales— distintos.

Qué NO se adopta, y por qué
----------------------------

El **registro**. La referencia lo implementa a mano porque su framework no
trae uno; Django sí (``BaseCommand`` + descubrimiento por ``INSTALLED_APPS``).
Aquí ``main()`` delega en ``execute_from_command_line``, que ya resuelve
descubrimiento, parseo, ayuda y errores de comando.

Tampoco se adopta ``--addons-path=``: la referencia lo parsea antes que nada
para saber dónde buscar comandos de addons. Nuestras raíces son fijas —
``src/addons`` y ``addons/``, unidas en un solo namespace por
``modules.module.initialize_sys_path`` — y los addons se declaran en
``INSTALLED_APPS``, así que la ruta no es un parámetro de invocación.
"""

import os
import sys

from django.core.management import execute_from_command_line

#: Comando por defecto cuando no se nombra ninguno (== la referencia).
DEFAULT_COMMAND = 'server'

#: Nombre del programa en los mensajes de error.
PROG_NAME = os.path.basename(sys.argv[0]) or 'kaupamex-bin'


def main(argv=None):
    """Punto de entrada del binario. Devuelve None; sale por ``execute_*``."""
    argv = list(sys.argv if argv is None else argv)
    args = argv[1:]

    if args and not args[0].startswith('-'):
        # Comando explícito: Django lo resuelve y valida.
        pass
    elif '-h' in args or '--help' in args:
        # Ayuda sin comando: Django imprime el índice con `help`.
        args = ['help'] + [a for a in args if a not in ('-h', '--help')]
    else:
        # Sin comando → server (== la referencia).
        args = [DEFAULT_COMMAND] + args

    # Perfil por defecto: el ABIERTO, como la referencia. Sin `-c` ni `ODOO_RC`
    # el núcleo cae en sus `my_default` —`list_db` True, bind 0.0.0.0:8069— y
    # separa arrancar de endurecer: el endurecimiento vive fuera del binario
    # (`--proxy-mode`, `--x-sendfile`, el proxy delante).
    #
    # Esto no relaja producción: la declara quien la quiere, y ya lo hace —
    # `setup/kaupamex.service:67` y `setup/kaupamex-cron.service:42` fijan
    # `Environment=DJANGO_SETTINGS_MODULE=config.settings.production`. Como es
    # `setdefault`, esa declaración gana.
    #
    # Cablear `production` aquí hacía que el camino sin declarar nada fuera el
    # MÁS endurecido: la primera petición de un recién llegado recibía un 301 a
    # `https://` que nadie sirve (`SECURE_SSL_REDIRECT = True`), sin que el
    # mensaje de error nombrara la causa. Ver H-API-636.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    execute_from_command_line([argv[0]] + args)

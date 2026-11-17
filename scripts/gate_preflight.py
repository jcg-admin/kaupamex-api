"""Preflight de un gate de pytest: las bases que va a usar sirven.

Intervención 4.3.1 §3.5. Antes de lanzar miles de pruebas se comprueba,
sobre cada base que la ejecución va a usar —la de la suite y la de cada
worker de xdist (``<nombre>_gw<N>``)—, que:

1. acepta conexión;
2. no le falta ninguna migración del grafo vigente;
3. conserva los datos de referencia que la carga de datos necesita: el
   usuario ``id=1`` (``base.user_root``) con su socio y el
   ``commercial_partner_id`` de ese socio calculado;
4. ningún otro pytest compite por esas bases.

Por qué existe: el 2026-11-17 una base de worker sin el usuario ``id=1``
convirtió F2 en 1 857 errores derivados, y otra con
``commercial_partner_id`` vacío (un cálculo aplazado que se perdió al
cortarse la migración) hizo fallar la carga de ``account_security.xml``.
``pg_isready``, la existencia de tablas y las filas de
``django_migrations`` no ven ninguna de las dos.

Salida: ``0`` si todas las bases sirven; ``1`` con un renglón por problema;
``2`` si no pudo medir (configuración ausente). No escribe en ninguna base.
"""
import argparse
import os
import subprocess
import sys

import django
from django.conf import settings
from django.db import connections
from django.db.migrations.loader import MigrationLoader

# ``settings`` y ``connections`` son perezosos: importarlos no lee la
# configuración. ``setup()`` corre una sola vez, al cargar el módulo.
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))), 'src')
sys.path.insert(0, SRC)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

#: Datos de referencia que la carga de datos lee, con la consulta que los
#: comprueba y el problema que describe su ausencia.
REFERENCE_CHECKS = (
    ('SELECT 1 FROM res_users WHERE id = 1',
     'falta el usuario id=1 (base.user_root)'),
    ('SELECT 1 FROM res_users u JOIN res_partner p ON p.id = u.partner_id'
     ' WHERE u.id = 1 AND p.commercial_partner_id IS NOT NULL',
     'el socio del usuario id=1 no tiene commercial_partner_id calculado'),
)


def database_names(workers):
    """La base de la suite y la de cada worker de xdist."""
    default = settings.DATABASES['default']
    base = (default.get('TEST') or {}).get('NAME') or default['NAME']
    if not workers:
        return [base]
    return [f'{base}_gw{n}' for n in range(workers)]


def connection_for(name):
    """Una conexión de sólo lectura a la base ``name``, con la
    configuración de ``default``."""
    alias = f'preflight_{name}'
    if alias not in connections.settings:
        config = dict(settings.DATABASES['default'])
        config['NAME'] = name
        connections.settings[alias] = config
    return connections[alias]


def pending_migrations(connection):
    """Las hojas del grafo vigente que la base no tiene aplicadas."""
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    graph_nodes = set(loader.graph.nodes)
    return sorted(graph_nodes - set(loader.applied_migrations))


def reference_problems(cursor):
    """Los datos de referencia ausentes, en el orden de la tabla."""
    problems = []
    for query, message in REFERENCE_CHECKS:
        cursor.execute(query)
        if cursor.fetchone() is None:
            problems.append(message)
    return problems


def check_database(name):
    """Los problemas de la base ``name``; vacío si sirve."""
    connection = connection_for(name)
    try:
        connection.ensure_connection()
    except Exception as error:
        # Se informa como problema de la base, no se oculta.
        return [f'no acepta conexión: {error}']
    try:
        pending = pending_migrations(connection)
        if pending:
            return [f'{len(pending)} migraciones sin aplicar, p. ej. '
                    f'{pending[0][0]}.{pending[0][1]}']
        with connection.cursor() as cursor:
            return reference_problems(cursor)
    finally:
        connection.close()


def competing_pytest(own_pid):
    """Otros procesos pytest vivos, que competirían por las mismas bases."""
    result = subprocess.run(
        ['pgrep', '-f', '[p]ytest'], capture_output=True, text=True,
        check=False)
    pids = [int(pid) for pid in result.stdout.split()]
    excluded = ancestors(own_pid)
    return [pid for pid in pids if pid not in excluded]


def ancestors(pid):
    """``pid`` y sus ancestros: el shell que lanza el preflight puede llevar
    «pytest» en su línea de comando y no compite por las bases."""
    chain = set()
    while pid > 1 and pid not in chain:
        chain.add(pid)
        try:
            with open(f'/proc/{pid}/stat', encoding='utf-8') as stat:
                pid = int(stat.read().rsplit(')', 1)[1].split()[1])
        except OSError:
            break
    return chain


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--workers', type=int, default=0,
                        help='workers de xdist (-n); 0 = sin xdist')
    args = parser.parse_args(argv)
    problems = []
    others = competing_pytest(os.getpid())
    if others:
        problems.append(f'otros pytest vivos: {others}')
    for name in database_names(args.workers):
        problems.extend(f'{name}: {p}' for p in check_database(name))
    for problem in problems:
        print(f'PREFLIGHT {problem}')
    print(f'PREFLIGHT {"OK" if not problems else "FALLA"} '
          f'({len(database_names(args.workers))} bases medidas)')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())

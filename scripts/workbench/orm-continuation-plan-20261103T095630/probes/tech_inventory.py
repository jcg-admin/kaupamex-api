"""Inventario medido del stack instalado de Kaupamex API.

Por componente: distribución, versión, ubicación y los símbolos que las
unidades del ORM usan como primitivas (TRAE/CONSTRUYE). Un símbolo se marca
presente sólo si el import y el ``getattr`` funcionan en este intérprete.

Uso: ``DJANGO_SETTINGS_MODULE=config.settings.testing PYTHONPATH=src
python tech_inventory.py <salida.tsv>``
"""
import csv
import ctypes.util
import importlib
import importlib.metadata
import pathlib
import platform
import re
import shutil
import subprocess
import sys

import django

#: componente → (distribución, módulo, símbolos con los que se construye)
COMPONENTS = {
    'django': ('Django', 'django', [
        'db.migrations.executor.MigrationExecutor',
        'db.migrations.state.ProjectState',
        'db.migrations.operations.SeparateDatabaseAndState',
        'db.migrations.operations.RenameField',
        'db.backends.base.schema.BaseDatabaseSchemaEditor',
        'db.models.deletion.Collector',
        'db.models.GeneratedField',
        'db.models.CompositePrimaryKey',
        'core.management.commands.squashmigrations.Command',
    ]),
    'djangorestframework': ('djangorestframework', 'rest_framework', [
        'serializers.ModelSerializer', 'viewsets.ModelViewSet',
    ]),
    'psycopg': ('psycopg', 'psycopg', ['sql.SQL', 'types.json.Jsonb']),
    'lxml': ('lxml', 'lxml', ['etree.XMLParser', 'etree.RelaxNG']),
    'gunicorn': ('gunicorn', 'gunicorn', []),
    'pypdf': ('pypdf', 'pypdf', ['PdfReader', 'PdfWriter']),
}


def resolve(module, dotted):
    parts = dotted.split('.')
    for cut in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(
                '.'.join([module] + parts[:cut - 1]) if cut > 1 else module)
        except ImportError:
            continue
        for name in parts[cut - 1:]:
            obj = getattr(obj, name)
        return True
    return False


def symbol_state(module, dotted):
    try:
        return 'present' if resolve(module, dotted) else 'absent'
    except (AttributeError, ImportError):
        return 'absent'


VENDORED_HARU = pathlib.Path('src/tools/pdf/vendor/libharu')
HARU_HELPERS = ('pdf_receipt', 'pdf_report')


def vendored_libharu():
    """libharu va vendorizado (``src/tools/pdf/Makefile``): la versión se lee
    de su cabecera y los ayudantes compilados, del directorio de build."""
    header = VENDORED_HARU / 'include' / 'hpdf_version.h'
    if not header.exists():
        return ('libharu', 'vendored', 'absent', '', '')
    parts = dict(re.findall(
        r'#define HPDF_(MAJOR|MINOR|BUGFIX)_VERSION (\d+)',
        header.read_text()))
    version = '.'.join(parts.get(key, '?')
                       for key in ('MAJOR', 'MINOR', 'BUGFIX'))
    build_dir = header.parents[3]
    built = ';'.join(
        f'{name}={"built" if (build_dir / name).exists() else "not-built"}'
        for name in HARU_HELPERS)
    return ('libharu', 'vendored', version, str(VENDORED_HARU), built)


def main(out_path):
    django.setup()
    rows = [('cpython', platform.python_implementation(),
             platform.python_version(), sys.executable, '')]
    for component, (dist, module, symbols) in COMPONENTS.items():
        try:
            version = importlib.metadata.version(dist)
            location = importlib.import_module(module).__file__
        except (importlib.metadata.PackageNotFoundError, ImportError):
            rows.append((component, dist, 'absent', '', ''))
            continue
        states = ';'.join(f'{s}={symbol_state(module, s)}' for s in symbols)
        rows.append((component, dist, version, location, states))
    server = 'absent'
    if shutil.which('psql'):
        server = subprocess.run(
            ['psql', '--version'], capture_output=True, text=True,
            check=False).stdout.strip()
    rows.append(('postgresql', 'client', server, shutil.which('psql') or '',
                 ''))
    haru = ctypes.util.find_library('hpdf')
    rows.append(('libharu', 'system libhpdf', 'present' if haru else 'absent',
                 haru or '', ''))
    rows.append(vendored_libharu())
    with open(out_path, 'w', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t')
        writer.writerow(['component', 'distribution', 'version', 'location',
                         'symbols'])
        writer.writerows(rows)
    for row in rows:
        print('\t'.join(row[:3]))


if __name__ == '__main__':
    main(sys.argv[1])

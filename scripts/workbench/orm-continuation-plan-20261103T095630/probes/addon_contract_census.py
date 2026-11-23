"""Contrato por addon: lo que la fuente declara y lo que este árbol cubre.

Sonda de la unidad ``model-identity-contract-0397`` (diseño
``designs/model-identity-contract.md``). Complementa
``scripts/check_mirrored_roots.py``: aquél mide si cada **archivo** tiene
contraparte; éste mide, por addon aplicable (los que existen aquí y en
``odoo19c``), qué **identidades** y qué **datos** declara la fuente y cuáles
cubre el puerto:

- ``_name`` de la fuente por clase y tipo (``Model``, ``TransientModel``,
  ``AbstractModel``) y por carpeta (``models``, ``wizard``, ``report``…);
- cuántos de esos ``_name`` declara también algún modelo de aquí;
- la lista ``data`` del manifiesto de la fuente frente a la nuestra, y en
  particular sus archivos de ``security/``;
- si el addon tiene ``migrations/`` y ``tests`` propios aquí.

Uso (sin base de datos)::

    PYTHONPATH=src:scripts DJANGO_SETTINGS_MODULE=config.settings.testing \\
        .venv/bin/python <este archivo> > outputs/addon-contract-census.tsv

*Métrica:* clases con ``_name`` literal en los ``.py`` de cada addon de la
fuente (fuera de ``tests/``), su base declarada, y las claves ``data`` de los
dos manifiestos.
*Ciega a:* un ``_name`` cubierto con otro nombre aquí (lo recoge
``model_identity_census.py`` por tabla), un archivo de datos portado con otro
nombre, y las pruebas que viven fuera del directorio del addon
(``tests/unit/<addon>``, ``tests/integration/<addon>``: se cuentan aparte).
"""
import ast
import csv
import importlib
import os
import pathlib
import re
import sys

import django
from django.apps import apps

NAME_RE = re.compile(r"^\s+_name\s*=\s*['\"]([a-z0-9_.]+)['\"]", re.M)
KIND_RE = re.compile(r"(TransientModel|AbstractModel|Model)\b")


def source_identities(addon_dir):
    """``[(name, kind, folder)]`` de las clases de un addon de la fuente."""
    found = []
    for path in sorted(addon_dir.rglob('*.py')):
        rel = path.relative_to(addon_dir)
        if rel.parts[0] == 'tests':
            continue
        text = path.read_text(errors='ignore')
        for match in re.finditer(r"(?m)^class\s+\w+\(([^)]*)\):", text):
            body = text[match.end():].split('\nclass ', 1)[0]
            name = NAME_RE.search(body)
            if not name:
                continue
            kind = KIND_RE.search(match.group(1))
            found.append((name.group(1), kind.group(1) if kind else '?',
                          rel.parts[0] if len(rel.parts) > 1 else '-'))
    return found


def manifest_data(manifest_path):
    if not manifest_path.is_file():
        return None
    try:
        manifest = ast.literal_eval(manifest_path.read_text())
    except (SyntaxError, ValueError):
        return None
    return list(manifest.get('data', []))


def main():
    django.setup()
    roots = importlib.import_module('reference_roots')
    ref_addons = pathlib.Path(roots.tree('odoo19c')) / 'addons'
    ours = {}
    for base in (pathlib.Path('addons'), pathlib.Path('src/addons')):
        for path in sorted(base.iterdir()):
            if (path / '__manifest__.py').is_file():
                ours[path.name] = path
    our_names = {model.__dict__.get('_name')
                 for model in apps.get_models(include_auto_created=True)}
    writer = csv.writer(sys.stdout, delimiter='\t', lineterminator='\n')
    writer.writerow([
        'addon', 'source_names', 'covered', 'missing_model',
        'missing_transient', 'missing_abstract', 'missing_list',
        'source_data', 'our_data', 'source_security', 'our_security',
        'missing_data', 'migrations', 'tests'])
    base_dir = pathlib.Path(roots.tree('odoo19c')) / 'odoo' / 'addons'
    for addon, path in ours.items():
        ref_dir = ref_addons / addon
        if not ref_dir.is_dir():
            ref_dir = base_dir / addon
        if not ref_dir.is_dir():
            continue
        identities = source_identities(ref_dir)
        names = {name for name, _k, _f in identities}
        missing = sorted({(n, k) for n, k, _f in identities
                          if n not in our_names})
        by_kind = {kind: sum(1 for _n, k in missing if k == kind)
                   for kind in ('Model', 'TransientModel', 'AbstractModel')}
        source_data = manifest_data(ref_dir / '__manifest__.py') or []
        our_data = manifest_data(path / '__manifest__.py') or []
        missing_data = [d for d in source_data if d not in our_data]
        test_dirs = [pathlib.Path('tests') / kind / addon
                     for kind in ('unit', 'integration')]
        writer.writerow([
            addon, len(names), len(names) - len({n for n, _k in missing}),
            by_kind['Model'], by_kind['TransientModel'],
            by_kind['AbstractModel'],
            ' '.join(n for n, _k in missing) or '-',
            len(source_data), len(our_data),
            sum(1 for d in source_data if d.startswith('security/')),
            sum(1 for d in our_data if d.startswith('security/')),
            len(missing_data),
            'yes' if (path / 'migrations').is_dir() else 'no',
            sum(1 for d in test_dirs if d.is_dir())])


if __name__ == '__main__':
    sys.path[:0] = [str(pathlib.Path('scripts').resolve()),
                    str(pathlib.Path('src').resolve())]
    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'config.settings.testing')
    main()

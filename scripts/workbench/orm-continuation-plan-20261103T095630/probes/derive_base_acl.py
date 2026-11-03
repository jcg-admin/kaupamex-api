#!/usr/bin/env python3
"""Deriva la ACL de ``base`` desde el CSV de la referencia.

Lee ``odoo19c: odoo/addons/base/security/ir.model.access.csv`` y conserva las
filas cuyo ``model_id:id`` es el identificador externo de un modelo cargado:
``model_`` más su ``_name`` con los puntos como guion bajo, que es como la
fuente nombra los registros de ``ir.model``. No adivina: una fila sin modelo
se descarta y una ambigua aborta.

Imprime el literal ``_ACCESS`` que ``addons/base/security/ir_model_access.py``
declara, y en stderr el reparto (sin modelo, nombres repetidos). Necesita el
árbol de ``odoo-tools`` y la configuración de Django; sólo lee.

Uso, desde ``src/``, con ``BENCH`` en la ruta del banco::

    eval "$(python3 ../scripts/reference_roots.py --env)"
    PYTHONPATH=. DJANGO_SETTINGS_MODULE=config.settings.testing \\
        uv run python "$BENCH/probes/derive_base_acl.py" \\
        "$ODOO19C/odoo/addons/base/security/ir.model.access.csv"
"""
import csv
import sys

import django
from django.apps import apps


def derive(csv_path):
    by_xmlid = {}
    for model in apps.get_models():
        name = getattr(model, '_name', None)
        if isinstance(name, str) and '.' in name:
            xmlid = 'model_' + name.replace('.', '_')
            by_xmlid.setdefault(xmlid, set()).add(
                f'{model._meta.app_label}.{model.__name__}')
    derived, missing = [], 0
    with open(csv_path, newline='') as handle:
        for row in csv.DictReader(handle):
            labels = by_xmlid.get(row['model_id:id'])
            if not labels:
                missing += 1
                continue
            if len(labels) > 1:
                raise SystemExit(f'ambiguo: {row["model_id:id"]} -> {labels}')
            group = row['group_id:id'].removeprefix('base.') or None
            perms = tuple(int(row[key]) for key in (
                'perm_read', 'perm_write', 'perm_create', 'perm_unlink'))
            derived.append((row['name'], next(iter(labels)), group, perms))
    return derived, missing


def main():
    django.setup()
    derived, missing = derive(sys.argv[1])
    print('_ACCESS = (')
    for name, label, group, perms in derived:
        print(f'    ({name!r}, {label!r}, {group!r}, {perms!r}),')
    print(')')
    names = [row[0] for row in derived]
    print(f'derivadas {len(derived)} · sin modelo {missing} · '
          f'nombres repetidos {len(names) - len(set(names))}',
          file=sys.stderr)


if __name__ == '__main__':
    main()

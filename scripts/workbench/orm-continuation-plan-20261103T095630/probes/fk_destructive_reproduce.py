"""EXPERIMENTAL: ¿borra el Collector un hijo que la fuente conservaría?

Medición exploratoria escrita antes de cerrar Search Existing: no es
autoridad, ni producto, ni evidencia de aceptación por sí sola. Sobre las
divergencias de política de ``outputs/fk_reference_ondelete.tsv``, toma una
fila hija real de la base de pruebas y pide al Collector qué haría al borrar
su padre. No borra nada: ``collect`` sólo planifica, y todo ocurre en una
transacción que se revierte.

Uso: python fk_destructive_reproduce.py <tsv de referencia> <salida.tsv>
"""
import collections
import csv
import importlib
import sys

import django


class Rollback(Exception):
    """Revierte la transacción de la medición."""


def classify(apps, deletion, db, label, field_name, expected):
    model = apps.get_model(label)
    field = model._meta.get_field(field_name)
    child = (model._base_manager.using(db.DEFAULT_DB_ALIAS)
             .exclude(**{f'{field.attname}__isnull': True}).first())
    if child is None:
        return 'no verificable: sin fila hija en la base', '-'
    parent = getattr(child, field.name)
    collector = deletion.Collector(using=db.DEFAULT_DB_ALIAS)
    try:
        collector.collect([parent])
    except (deletion.ProtectedError, deletion.RestrictedError):
        observed = 'rehúsa'
    else:
        doomed = {obj.pk for obj in collector.data.get(model, ())}
        nulled = any(
            fld.name == field.name and child.pk in {o.pk for o in objs}
            for (fld, _value), objs in collector.field_updates.items())
        observed = ('borra el hijo' if child.pk in doomed
                    else 'vacía la referencia' if nulled else 'conserva')
    expectation = {'set null': 'vacía la referencia',
                   'restrict': 'rehúsa', 'cascade': 'borra el hijo'}
    if observed == expectation[expected]:
        return 'sin diferencia observable', observed
    if observed == 'borra el hijo':
        return 'pérdida reproducida', observed
    return 'diferencia semántica sin pérdida', observed


def main(reference, out):
    django.setup()
    apps = importlib.import_module('django.apps').apps
    db = importlib.import_module('django.db')
    deletion = importlib.import_module('django.db.models.deletion')
    rows = []
    with open(reference, encoding='utf-8') as handle:
        for row in csv.DictReader(handle, delimiter='\t'):
            if 'política' in row['verdict']:
                rows.append(row)
    summary = collections.Counter()
    results = []
    try:
        with db.transaction.atomic():
            for row in rows:
                expected = row['reference_ondelete'].replace(
                    ' (defecto)', '')
                verdict, observed = classify(
                    apps, deletion, db, row['django_field'], row['field'],
                    expected)
                key = (f"{expected} -> {row['django_policy']}", verdict)
                summary[key] += 1
                results.append([row['django_field'], row['field'],
                                row['reference_field'], expected,
                                row['django_policy'], observed, verdict])
            raise Rollback
    except Rollback:
        pass
    with open(out, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle, delimiter='\t', lineterminator='\n')
        writer.writerow(['django_field', 'field', 'reference_field',
                         'reference_ondelete', 'django_policy', 'observed',
                         'verdict'])
        writer.writerows(results)
    print('divergencias de política medidas:', len(results))
    for (pair, verdict), count in sorted(summary.items()):
        print(f'  {pair}: {verdict}: {count}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])

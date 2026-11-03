"""El censo de nulabilidad de los ``Many2one`` — H-API-1122.

La fuente resuelve ``required`` como ``False`` salvo declaración
(``odoo19c: odoo/orm/fields_relational.py:282``). Ninguna columna de este
árbol puede ser ``NOT NULL`` donde la fuente declara el campo opcional.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / 'scripts'))
import census_many2one_nullability as census  # noqa: E402
import reference_roots  # noqa: E402


@pytest.mark.parametrize(('values', 'null', 'expected'), [
    ({True}, False, 'aligned_required'),
    ({False}, True, 'aligned_optional'),
    ({False}, False, 'required_by_omission'),
    ({True}, True, 'relaxed'),
    ({'expr'}, False, 'required_expr'),
    (set(), False, 'unmatched'),
    ({False, True}, False, 'aligned_required'),
])
def test_the_bucket_of_a_column(values, null, expected):
    assert census.bucket(values, null) == expected


@pytest.mark.skipif(not reference_roots.tree('odoo19c').is_dir(),
                    reason='odoo19c no está montado')
def test_no_column_is_required_only_by_omission():
    declared, tables = census.reference_index()
    offenders = []
    for model, field in census.consumer_columns():
        _, _, result = census.column_bucket(model, field, declared, tables)
        if result == 'required_by_omission':
            offenders.append(f'{model._meta.label}.{field.name}')
    assert offenders == []

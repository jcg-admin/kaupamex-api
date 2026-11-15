"""Las cabeceras de los modelos de ``account`` frente a la fuente.

Cada clase portada lleva, sobre sus atributos de clase, un comentario
de dos líneas: ``#: Atributos de clase de ``<name>``, verbatim`` y
``#: (``odoo19c: <ruta>:<a>-<b>``).``
Esta suite no repite los valores: los lee del tramo citado de la referencia
y exige que el puerto declare cada atributo con el mismo valor. Quedan fuera
``_check_company_auto`` y ``_inherits``, que son tramos propios (cambian la
conducta del ORM al asignar y al guardar).

Con ``_name`` declarado, ``load_modules`` escribe el xmlid del modelo
(``account.model_<tabla>``), que es lo que la seguridad de la referencia
cita en su ``ir.model.access.csv``.
"""

import ast
import pathlib
import re

import pytest
from django.db import DEFAULT_DB_ALIAS

from modules.loading import load_modules
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.unit

API = pathlib.Path(__file__).resolve().parents[3]
REFERENCE = (pathlib.Path('/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/'
                          'odoo-19.0/addons'))
HEADER = re.compile(r"#: Atributos de clase de ``([a-z_.]+)``, verbatim\n"
                    r"\s*#: \(``odoo19c: (account/models/[a-z_]+\.py):"
                    r"(\d+)-(\d+)``\)")
OWN_SLICES = {'_check_company_auto', '_inherits'}


def _cited_headers():
    found = []
    for path in sorted((API / 'addons/account/models').glob('*.py')):
        text = path.read_text()
        for match in HEADER.finditer(text):
            found.append(match.groups())
    return found


CITED = _cited_headers()


def _source_attributes(rel_path, first, last):
    lines = (REFERENCE / rel_path).read_text().splitlines()
    chunk = '\n'.join(line.strip() for line in lines[int(first) - 1:int(last)])
    values = {}
    for node in ast.parse(chunk).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = ast.literal_eval(node.value)
    return values


def test_the_slice_covers_the_twenty_seven_models():
    assert len(CITED) == 27
    assert len({name for name, *_ in CITED}) == 27


@pytest.mark.skipif(not REFERENCE.is_dir(), reason='odoo-tools no montado')
@pytest.mark.parametrize('name,rel_path,first,last', CITED,
                         ids=[c[0] for c in CITED])
def test_the_port_declares_what_the_source_declares(name, rel_path, first,
                                                    last):
    expected = _source_attributes(rel_path, first, last)
    assert expected.get('_name') == name
    model = MODELS_BY_NAME[name]
    for attribute, value in expected.items():
        if attribute in OWN_SLICES:
            continue
        declared = getattr(model, attribute)
        if isinstance(value, list) and isinstance(declared, str):
            declared = [declared]
        assert declared == value, attribute


@pytest.mark.django_db
def test_loading_writes_the_model_xmlid_of_each_header():
    load_modules(DEFAULT_DB_ALIAS)
    imd = MODELS_BY_NAME['ir.model.data']
    stored = set(imd.objects.filter(module='account',
                                    name__startswith='model_')
                 .values_list('name', flat=True))
    missing = sorted('model_' + name.replace('.', '_') for name, *_ in CITED
                     if 'model_' + name.replace('.', '_') not in stored)
    assert missing == []

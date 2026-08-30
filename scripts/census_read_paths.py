#!/usr/bin/env python3
"""Censo de las cinco rutas de lectura de un campo — cierra el DESCONOCIDO #216.

La fuente aloja el protocolo de descriptor en ``Field.__get__``
(``odoo19c: odoo/orm/fields.py:1642``). Django lo aloja en ``DeferredAttribute``
(``django/db/models/query_utils.py:243``), **otra clase**, y lo instala por
campo en ``Field.contribute_to_class`` (``fields/__init__.py:955``).

Portar ``__get__`` sobre ``models.Field`` no es una decision de fidelidad sino
de mecanismo, y el riesgo no es un test rojo: ``contribute_to_class`` pone el
descriptor en el ATRIBUTO del modelo, no en el campo. Si ademas el campo fuera
descriptor, `Model._meta` —que guarda campos como atributos— empezaria a
invocarlo al leerlos.

Este censo NO decide: mide. Recorre las cinco rutas de lectura y publica, por
cada una, quien contesta hoy y que hace la fuente ahi que Django no.

Uso::

    uv run python scripts/census_read_paths.py
"""
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')

import django  # noqa: E402

#: Lo que la fuente hace en ``Field.__get__``, leido del cuerpo (``:1642-1700``).
#: Cada entrada es un paso suyo y la pregunta que este censo le hace al arbol.
REFERENCE_STEPS = (
    ('control de acceso al campo',
     '_has_field_access / _check_field_access antes de devolver nada'),
    ('registro nulo o multiple',
     'ensure_one, o el valor nulo convertido si el recordset esta vacio'),
    ('computo pendiente',
     'recompute(record) si el campo es compute y store'),
    ('cache por transaccion',
     '_get_cache(env)[record_id], y si falla la cascada de respaldos'),
    ('lectura desde la base',
     '_to_prefetch(record)._fetch_field(self) — la prelectura por lote'),
)


def descriptor_of(model, name):
    """El descriptor que gobierna la lectura de ``name``, o ``None``."""
    for klass in model.__mro__:
        if name in vars(klass):
            return vars(klass)[name]
    return None


def main():
    django.setup()
    from django.apps import apps
    from django.db.models.query_utils import DeferredAttribute

    from orm.fields_company_dependent import _CompanyDependentAttribute
    from orm.fields_nonstored import NonStored

    partner = apps.get_model('base', 'ResPartner')

    print('=== Quien contesta hoy cada ruta de lectura ===\n')

    rows = []
    plain = descriptor_of(partner, 'name')
    rows.append(('1. campo con columna, instancia cargada', 'name',
                 type(plain).__name__))
    rows.append(('2. campo con columna, valor diferido', 'name',
                 type(plain).__name__ + ' (la misma clase: decide al leer)'))
    rows.append(('3. campo con columna, instancia sin guardar', 'name',
                 type(plain).__name__ + ' (misma; levanta AttributeError)'))

    dependents = [f.name for f in partner._meta.get_fields()
                  if getattr(f, 'company_dependent', False)]
    if dependents:
        name = dependents[0]
        rows.append(('4. campo dependiente de empresa', name,
                     type(descriptor_of(partner, name)).__name__))
    else:
        rows.append(('4. campo dependiente de empresa', '(ninguno en el modelo)',
                     'NO MEDIDO en este modelo'))

    non_stored = [n for n, v in vars(partner).items()
                  if isinstance(v, NonStored)]
    if non_stored:
        rows.append(('5. campo no persistido (store=False)', non_stored[0],
                     type(descriptor_of(partner, non_stored[0])).__name__))
    else:
        rows.append(('5. campo no persistido (store=False)',
                     '(ninguno en el modelo)', 'NO MEDIDO en este modelo'))

    width = max(len(r[0]) for r in rows)
    for path, field, who in rows:
        print(f'  {path:<{width}}  {field:<24}  {who}')

    print('\n=== Que instala Django, y donde ===\n')
    print('  descriptor_class de Field          ', DeferredAttribute.__name__)
    print('  se instala en                      el ATRIBUTO del modelo')
    print('                                     (contribute_to_class, si hay columna)')
    print('  el campo mismo es descriptor?      ', hasattr(
        apps.get_model('base', 'ResPartner')._meta.get_field('name'), '__get__'))

    print('\n=== Los cinco pasos de Field.__get__ de la fuente ===\n')
    for paso, que in REFERENCE_STEPS:
        print(f'  {paso:<28}  {que}')

    print('\n=== Los dos precedentes del arbol ===\n')
    print('  Dos rutas YA tienen descriptor propio, y NINGUNA lo puso en el')
    print('  campo: las dos lo pusieron en el atributo, como Django.')
    print(f'    - {_CompanyDependentAttribute.__name__:<28} orm/fields_company_dependent.py')
    print(f'    - {NonStored.__name__:<28} orm/fields_nonstored.py')


if __name__ == '__main__':
    main()

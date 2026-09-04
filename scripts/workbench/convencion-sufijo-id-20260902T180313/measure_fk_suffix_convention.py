"""Que convencion de sufijo declara cada FK portada, y contra que la lee su consumidor.

Pregunta del ejecutor 2026-09-02: *"Nosotros usamos _id_id por alguna razon, que
construida con ORM"*. El instrumento mide DOS ejes que no son el mismo:

- **Declaracion**: como se llama el campo en la clase (``partner_id`` vs
  ``parent``). De ahi Django deriva el ``attname`` (``partner_id_id`` vs
  ``parent_id``), que es donde vive la clave foranea cruda.
- **Lectura**: con que nombre lo lee quien lo consume desde otro archivo.

Un archivo escrito con una convencion que lee a un modelo escrito con la otra
produce un ``AttributeError`` en tiempo de EJECUCION. Este guion los reparte
para poder decidir cual es la convencion y cual es la deriva, en vez de
suponerlo.
"""
import ast
import collections
import json
import pathlib
import sys

import django

django.setup()
from django.apps import apps  # noqa: E402
from django.db.models import ForeignKey, OneToOneField  # noqa: E402


def census_of_declarations():
    """Cada FK del arbol, con su nombre declarado y su ``attname``."""
    con_sufijo, sin_sufijo = [], []
    for model in apps.get_models():
        etiqueta = model._meta.app_label
        for field in model._meta.get_fields():
            if not isinstance(field, (ForeignKey, OneToOneField)):
                continue
            if getattr(field, 'auto_created', False):
                continue
            fila = (etiqueta, model.__name__, field.name, field.attname)
            (con_sufijo if field.name.endswith('_id') else sin_sufijo).append(fila)
    return con_sufijo, sin_sufijo


def main():
    con, sin = census_of_declarations()
    por_app = collections.Counter()
    for etiqueta, _m, nombre, _a in con + sin:
        por_app[(etiqueta, nombre.endswith('_id'))] += 1

    apps_mezcladas = sorted({
        etiqueta for etiqueta, _ in por_app
        if por_app.get((etiqueta, True), 0) and por_app.get((etiqueta, False), 0)
    })

    salida = {
        'total_fk': len(con) + len(sin),
        'con_sufijo_id': len(con),
        'sin_sufijo_id': len(sin),
        'apps_que_mezclan_las_dos': apps_mezcladas,
        'reparto_por_app': {
            etiqueta: {
                'con_sufijo': por_app.get((etiqueta, True), 0),
                'sin_sufijo': por_app.get((etiqueta, False), 0),
            }
            for etiqueta in sorted({e for e, _ in por_app})
        },
    }
    print(json.dumps(salida, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())

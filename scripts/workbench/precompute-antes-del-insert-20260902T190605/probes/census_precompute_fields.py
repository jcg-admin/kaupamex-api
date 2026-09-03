"""Censo de los campos ``precompute`` vivos y de su cadena de dependencia.

Mide, sobre el registro ya poblado por Django:

- que campos declaran ``precompute=True``, con su ``readonly``;
- que metodo de computo escribe cada uno;
- que campos del MISMO modelo nombra el ``@api.depends`` de ese metodo.

La tercera columna es la que decide el orden del pase: un campo cuyo computo
lee otro precompute del mismo modelo tiene que correr despues.
"""
import django

django.setup()

from django.apps import apps  # noqa: E402

from orm import registry  # noqa: E402
from orm.utils import model_field_registry  # noqa: E402

total = 0
for model in apps.get_models():
    fields_of = model_field_registry(model)
    rows = [(name, field) for name, field in fields_of.items()
            if getattr(field, 'precompute', False)]
    if not rows:
        continue
    print(f'{model._meta.label}')
    for name, field in rows:
        total += 1
        depends = sorted({
            dotted.split('.')[0]
            for dotted in registry.field_depends[field]
        } & set(fields_of))
        print(f'  {name:24} readonly={getattr(field, "readonly", False)!s:5}'
              f' compute={field.compute:32} depends={depends}')
print(f'total {total}')

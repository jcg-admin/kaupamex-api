"""Sonda — ¿qué ``type`` publica hoy cada familia de campo del árbol?

El registro de optimizadores despacha por ``field.type`` (``domains.py:919``),
así que un ``''`` universal deja muerta la familia de optimizadores por tipo.
"""
import django

django.setup()

from django.db import models  # noqa: E402

from orm.fields import type_for  # noqa: E402

CLASSES = [
    models.BooleanField, models.CharField, models.TextField,
    models.IntegerField, models.FloatField, models.DecimalField,
    models.DateField, models.DateTimeField, models.JSONField,
    models.BinaryField, models.EmailField, models.URLField,
]


def main():
    vivos = 0
    for cls in CLASSES:
        instance = cls()
        declared = getattr(instance, 'type', None)
        derived = type_for(instance)
        if declared:
            vivos += 1
        print(f'{cls.__name__:20} declara={declared!r:14} type_for={derived!r}')
    print(f'\ncon type declarado: {vivos} de {len(CLASSES)}')

    selection = models.CharField(choices=[('a', 'A')])
    print(f"CharField(choices=...) declara={getattr(selection, 'type', None)!r} "
          f"type_for={type_for(selection)!r}")


if __name__ == '__main__':
    main()

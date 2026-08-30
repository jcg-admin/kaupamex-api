"""Sonda: se dispara __set_name__ en el cuerpo de un modelo de Django?

La pregunta importa porque el mecanismo de nombrado de la fuente
(odoo19c: odoo/orm/table_objects.py:39-50) cuelga entero de ese protocolo:
el objeto de tabla toma su nombre del atributo de clase que lo aloja.

Django no usa type.__new__ con el namespace completo — ModelBase separa los
atributos con contribute_to_class y los añade despues con add_to_class. Si
__set_name__ no se dispara, el nombrado hay que construirlo de otra forma.
"""
import django
from django.conf import settings

settings.configure(
    INSTALLED_APPS=['django.contrib.contenttypes', 'django.contrib.auth'],
    DATABASES={},
    USE_TZ=True,
)
django.setup()

from django.db import models  # noqa: E402


class Sensor:
    """Registra si el protocolo lo nombro, y con que nombre."""

    def __init__(self):
        self.name = ''
        self.owner = None
        self.fired = False

    def __set_name__(self, owner, name):
        self.fired = True
        self.owner = owner.__name__
        self.name = name


class _Plain:
    _probe = Sensor()


class _DjangoModel(models.Model):
    _probe = Sensor()
    label = models.CharField(max_length=8)

    class Meta:
        app_label = 'contenttypes'


print('clase Python normal:')
print(f'  fired={_Plain._probe.fired} name={_Plain._probe.name!r} '
      f'owner={_Plain._probe.owner!r}')
print('modelo de Django:')
print(f'  fired={_DjangoModel._probe.fired} name={_DjangoModel._probe.name!r} '
      f'owner={_DjangoModel._probe.owner!r}')
print(f'  el atributo sobrevive en la clase: '
      f'{isinstance(getattr(_DjangoModel, "_probe", None), Sensor)}')
print(f'  Meta.constraints por defecto: {_DjangoModel._meta.constraints!r}')

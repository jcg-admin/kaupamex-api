"""Sonda 2: que hay disponible en el owner cuando corre __set_name__?

La fuente, en __set_name__, consulta getattr(owner, 'pool', None) para
distinguir la clase de definicion de la de registro, y apila el objeto en
owner._table_object_definitions. Aqui el equivalente seria tocar _meta.
Si _meta aun no existe en ese instante, el registro tiene que ir a otro sitio.
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

observed = {}


class Sensor:
    def __set_name__(self, owner, name):
        observed[name] = {
            'tiene__meta': hasattr(owner, '_meta'),
            'tiene_pool': hasattr(owner, 'pool'),
            'bases': [b.__name__ for b in owner.__mro__[1:3]],
        }


class _DjangoModel(models.Model):
    _probe = Sensor()

    class Meta:
        app_label = 'contenttypes'


for name, data in observed.items():
    print(f'{name}: {data}')
print(f'tras construir la clase, _meta existe: {hasattr(_DjangoModel, "_meta")}')

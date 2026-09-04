"""Mide la especie —abstracto, transitorio, regular— de cada modelo registrado
y de sus padres, para saber si el arbol viola alguna de las tres reglas de
herencia que la referencia declara.

La pregunta que responde: ¿tiene el arbol vivo algun modelo abstracto que
herede de uno concreto, o algun transitorio que cruce la frontera con uno
regular? De la respuesta depende si el check de #332 se instala sobre un
baseline limpio o si destapa deuda que hay que pagar antes.

Se corre asi::

    PYTHONPATH=src DJANGO_SETTINGS_MODULE=config.settings.testing \
        uv run python scripts/workbench/especie-de-modelo-heredada-*/measure_inherited_model_kind.py

Los dos lectores de abajo son los mismos que orm/model_classes.py porta:
_abstract y _transient no cuelgan de models.Model en este arbol
—seria la colision de la tarea #98—, asi que la especie se lee de donde el
stack si la guarda.
"""
import django
django.setup()
from orm import registry
from orm.models import AbstractModel
from orm.models_transient import TransientModel

def es_abstracto(c):
    m = getattr(c, '_meta', None)
    return bool((m is not None and m.abstract) or getattr(c, '_abstract', False))

def es_transitorio(c):
    return bool(getattr(c, '_transient', False))

viola = {'abstracto-de-concreto': [], 'transitorio-de-no': [], 'no-de-transitorio': []}
for name, cls in registry.MODELS_BY_NAME.items():
    for parent in cls.__mro__[1:]:
        if parent is cls or not getattr(parent, '_name', None):
            continue
        if es_abstracto(cls) and not es_abstracto(parent):
            viola['abstracto-de-concreto'].append((name, parent._name))
        if es_transitorio(cls) and not es_transitorio(parent) and parent is not object:
            viola['transitorio-de-no'].append((name, parent._name))
        if not es_transitorio(cls) and es_transitorio(parent):
            viola['no-de-transitorio'].append((name, parent._name))

print('modelos registrados:', len(registry.MODELS_BY_NAME))
print('abstractos:', sum(1 for c in registry.MODELS_BY_NAME.values() if es_abstracto(c)))
print('transitorios:', sum(1 for c in registry.MODELS_BY_NAME.values() if es_transitorio(c)))
for k, v in viola.items():
    print(f'{k}: {len(v)}', v[:4])

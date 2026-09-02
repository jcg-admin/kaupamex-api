"""Mide si ``pre_init`` entrega los nombres que quien llama dio, y si
``pre_save`` corre antes del INSERT con ``_state.adding`` aun en True.

Es la premisa del mecanismo de #312: la fuente decide por ``fname not in
vals``, y aqui no hay ``vals`` — hay una instancia de Django cuyos campos
estan todos poblados, los dados y los que tomaron su default. Sin un canal que
distinga los dos, el precompute no puede respetar el valor explicito.

Se ejecuta con:

    DJANGO_SETTINGS_MODULE=config.settings.testing PYTHONPATH=src \
        uv run python scripts/workbench/precompute-.../probes/probe_init_signals.py
"""
import django

django.setup()

from django.db.models.signals import post_init, pre_init, pre_save  # noqa: E402

from django.apps import apps  # noqa: E402

visto = []


def en_pre_init(sender, args, kwargs, **_):
    visto.append(('pre_init', sender.__name__, sorted(kwargs), len(args)))


def en_post_init(sender, instance, **_):
    visto.append(('post_init', sender.__name__, instance._state.adding))


def en_pre_save(sender, instance, **_):
    visto.append(('pre_save', sender.__name__, instance._state.adding,
                  instance.pk))


pre_init.connect(en_pre_init, dispatch_uid='probe')
post_init.connect(en_post_init, dispatch_uid='probe')
pre_save.connect(en_pre_save, dispatch_uid='probe')

ResCurrency = apps.get_model('base', 'ResCurrency')

# 1. Construccion con kwargs explicitos — lo que la fuente llama ``vals``.
c = ResCurrency(name='ZZZ', symbol='Z')
for fila in visto:
    print(fila)
visto.clear()

# 2. Carga desde la base: ``from_db`` construye por posicion, no por kwargs.
print('--- from_db')
list(ResCurrency.objects.all()[:1])
for fila in visto[:2]:
    print(fila)

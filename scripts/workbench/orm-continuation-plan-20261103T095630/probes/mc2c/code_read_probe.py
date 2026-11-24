"""EXPERIMENTAL — medición exploratoria escrita antes de cerrar Search
Existing: no es autoridad, ni producto, ni evidencia de aceptación por sí sola.

Plugin de pytest que registra cada lectura de ``account.account.code`` hecha
sin empresa activa (``env().company is None``), con la prueba y el primer
marco de ``addons/`` o ``src/`` que la pide. No cambia el valor leído.

Los módulos de Django se importan con ``importlib`` dentro del gancho: el
plugin se carga antes de que pytest-django configure Django.
"""
import importlib
import json
import os
import traceback

OUT = os.environ['MC2C_PROBE_OUT']


def _short(frame):
    path = frame.filename.split('kaupamex-api')[-1]
    return f'{path}:{frame.lineno}:{frame.name}'


def _record(frames):
    caller = next((frame for frame in reversed(frames)
                   if '/addons/' in frame.filename
                   or '/src/' in frame.filename), None)
    test = os.environ.get('PYTEST_CURRENT_TEST', '').split(' ')[0]
    with open(OUT, 'a') as handle:
        handle.write(json.dumps({
            'test': test,
            'caller': _short(caller) if caller else None,
        }) + '\n')


def pytest_configure(config):
    models = importlib.import_module('addons.account.models')
    environments = importlib.import_module('orm.environments')
    descriptor = models.AccountAccount.__dict__['code']
    original_get = type(descriptor).__get__

    class Probe(type(descriptor)):
        def __get__(self, instance, owner=None):
            value = original_get(self, instance, owner)
            if (instance is not None
                    and environments.env().company is None):
                frames = [frame for frame in traceback.extract_stack()[:-1]
                          if '/site-packages/' not in frame.filename
                          and 'code_read_probe' not in frame.filename]
                _record(frames)
            return value

    descriptor.__class__ = Probe

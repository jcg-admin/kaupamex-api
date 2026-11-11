"""Un transitorio exige sus fechas de acceso — ``odoo19c:
odoo/orm/model_classes.py:216-220``.

Oráculo literal: *"TransientModels must have log_access turned on, in order
to implement their vacuum policy"*, como ``TypeError``, antes de inscribir el
modelo. Aquí ``_log_access`` son las columnas ``create_date`` y ``write_date``
(``LOG_ACCESS_COLUMNS``), que ``TransientModel`` declara: la limpieza barre por
``write_date``.

Mutaciones que lo hacen caer: no conectar la comprobación a la construcción
de la clase (cae la del modelo construido); aceptar un transitorio sin
columnas (caen las dos del rechazo); exigirlas a un modelo normal (cae la del
modelo corriente).
"""
import itertools

import pytest
from django.db import models
from django.test.utils import isolate_apps

from orm.model_classes import check_transient_log_access

pytestmark = pytest.mark.integration

_HOLDERS = itertools.count()
MESSAGE = 'TransientModels must have log_access turned on'


def _build(attrs):
    with isolate_apps():
        meta = type('Meta', (), {'app_label': 'base'})
        body = {'__module__': __name__, 'Meta': meta, **attrs}
        return type(f'TransientHolder{next(_HOLDERS)}', (models.Model,), body)


def _dates():
    """Las cuatro columnas de ``LOG_ACCESS_COLUMNS``: las fechas y la
    autoría, como enteros porque ``isolate_apps`` no trae ``res.users``."""
    return {'create_uid': models.IntegerField(null=True),
            'create_date': models.DateTimeField(null=True),
            'write_uid': models.IntegerField(null=True),
            'write_date': models.DateTimeField(null=True)}


class TestTheCheck:

    def test_a_transient_with_its_dates_passes(self):
        model = _build({'_transient': True, **_dates()})
        assert check_transient_log_access(model) is None

    def test_a_transient_without_dates_is_refused(self):
        with pytest.raises(TypeError, match=MESSAGE):
            _build({'_transient': True})

    def test_log_access_turned_off_is_refused(self):
        with pytest.raises(TypeError, match=MESSAGE):
            _build({'_transient': True, '_log_access': False, **_dates()})

    def test_an_ordinary_model_needs_no_dates(self):
        model = _build({})
        assert check_transient_log_access(model) is None

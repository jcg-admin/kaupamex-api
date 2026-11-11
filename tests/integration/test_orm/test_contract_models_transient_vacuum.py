"""Limpieza de transitorios por antigüedad — ``odoo19c:
odoo/orm/models_transient.py:48-83``.

La referencia exige ``_log_access`` a todo transitorio
(``odoo/orm/model_classes.py:217-220``), así que todo transitorio tiene la
fecha de escritura por la que ``_transient_clean_rows_older_than`` barre
(``:75-83``): borra lo escrito antes de ``now - seconds``, con un piso de
cinco minutos, y ``_transient_vacuum`` devuelve ``(_name, quedan_más)``.

Mutaciones que lo hacen caer: retirar las columnas de fecha (cae todo lo que
barre); quitar el piso de cinco minutos (cae la de lo reciente); no borrar
(cae la de lo antiguo).
"""
import datetime

import pytest
from django.apps import apps
from django.db import transaction
from django.utils import timezone

from addons.base.models.ir_profile import BaseEnableProfilingWizard
from addons.base.models.timestamped_mixin import transaction_now
from orm.models_transient import TransientModel

pytestmark = pytest.mark.integration


def _row_written(ago):
    row = BaseEnableProfilingWizard.objects.create()
    BaseEnableProfilingWizard.objects.filter(pk=row.pk).update(
        write_date=timezone.now() - ago)
    return row


class TestEveryTransientHasAWriteDate:

    def test_each_concrete_transient_declares_updated_at(self):
        concrete = [model for model in apps.get_models()
                    if issubclass(model, TransientModel)]
        assert concrete
        missing = [model._meta.label for model in concrete
                   if not any(f.name == 'write_date'
                              for f in model._meta.get_fields())]
        assert missing == []


class TestTheAgeCleanup:

    def test_a_row_older_than_the_limit_is_removed(self, db):
        old = _row_written(datetime.timedelta(hours=2))
        BaseEnableProfilingWizard._transient_clean_rows_older_than(3600)
        assert not BaseEnableProfilingWizard.objects.filter(
            pk=old.pk).exists()

    def test_a_row_written_in_the_last_five_minutes_is_kept(self, db):
        recent = _row_written(datetime.timedelta(minutes=2))
        BaseEnableProfilingWizard._transient_clean_rows_older_than(0)
        assert BaseEnableProfilingWizard.objects.filter(
            pk=recent.pk).exists()

    def test_the_vacuum_reports_the_model_and_whether_rows_remain(self, db):
        _row_written(datetime.timedelta(hours=2))
        name, has_remaining = BaseEnableProfilingWizard._transient_vacuum()
        assert name == BaseEnableProfilingWizard._name
        assert has_remaining is False


class TestTheTransactionClock:
    """Las fechas y el corte salen de ``cr.now()``, no del reloj de pared.

    ``odoo19c: odoo/orm/models.py:4801-4805`` fija las columnas de acceso
    con ``cr.now()``, y ``models_transient.py:78`` corta con
    ``self.env.cr.now()``.
    """

    def test_the_dates_of_a_new_row_are_the_transaction_time(self, db):
        # El reloj es el de UNA transacción: fuera de un bloque atómico cada
        # lectura sería la suya propia.
        with transaction.atomic():
            row = BaseEnableProfilingWizard.objects.create()
            now = transaction_now(row._state.db)
        assert row.create_date == now
        assert row.write_date == now

    def test_a_wall_clock_ahead_does_not_age_a_fresh_row(
            self, db, monkeypatch):
        row = BaseEnableProfilingWizard.objects.create()
        ahead = timezone.now() + datetime.timedelta(days=1)
        monkeypatch.setattr(timezone, 'now', lambda: ahead)

        BaseEnableProfilingWizard._transient_clean_rows_older_than(3600)

        assert BaseEnableProfilingWizard.objects.filter(pk=row.pk).exists()

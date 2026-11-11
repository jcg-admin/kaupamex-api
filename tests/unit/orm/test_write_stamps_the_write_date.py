"""``write`` fecha la escritura — ≙ ``odoo19c: odoo/orm/models.py:4394-4396``.

Con ``_log_access`` la fuente hace ``vals.setdefault('write_date', ...)`` en
cada ``write``. Aquí la fecha es ``TimeStampedModel.write_date``, ``auto_now``,
y la pone ``pre_save``; el ``write`` de la mezcla guarda con ``update_fields``,
así que tiene que nombrar la columna para que la fecha llegue a la tabla.
"""

import datetime

import pytest
from django.utils import timezone

from addons.base.models.res_partner import ResPartner

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def test_a_write_stamps_updated_at(db):
    partner = ResPartner.objects.create(name='fecha', email='')
    long_ago = timezone.now() - datetime.timedelta(days=30)
    ResPartner.objects.filter(pk=partner.pk).update(write_date=long_ago)
    partner.refresh_from_db()

    partner.write({'comment': 'otro'})

    partner.refresh_from_db()
    assert partner.comment == 'otro'
    assert partner.write_date > long_ago

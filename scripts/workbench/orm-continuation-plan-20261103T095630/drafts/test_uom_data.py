"""Los datos maestros de ``uom`` entran por su manifiesto.

≙ ``odoo19c: addons/uom/__manifest__.py:13-14`` (``data/uom_data.xml`` en
la clave ``data``) y ``addons/uom/data/uom_data.xml``: 31 registros con xml
id, entre ellos la jornada (``product_uom_day``, 8 horas) que
``sale_timesheet`` compara con ``timesheet_encode_uom_id`` para convertir el
costo por hora en costo por día. Los lee ``modules.loading.load_modules``,
como los de ``hr`` (``test_hr_security_data``).
"""
import pytest

from addons.base.models import IrModelData
import modules.loading as loading

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _installed(db):
    loading.load_modules('default')


def _ref(xmlid):
    return IrModelData.ref(xmlid)


def test_the_working_day_is_eight_hours():
    day = _ref('uom.product_uom_day')
    assert day.name == 'Days'
    assert day.relative_factor == pytest.approx(8.0)
    assert day.relative_uom_id == _ref('uom.product_uom_hour')


def test_every_record_of_the_source_has_its_xml_id():
    names = set(IrModelData.objects.filter(module='uom').values_list(
        'name', flat=True))
    assert {'product_uom_unit', 'product_uom_hour', 'product_uom_day',
            'product_uom_minute', 'decimal_product_uom'} <= names
    assert IrModelData.objects.filter(module='uom', model='uom.uom').count() \
        == 30


def test_an_inactive_unit_of_the_source_stays_inactive():
    assert _ref('uom.product_uom_dozen').active is False

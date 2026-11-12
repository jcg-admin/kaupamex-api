"""Los datos de ``uom`` entran por su manifiesto.

≙ ``odoo19c: addons/uom/__manifest__.py:13-16``: ``data/uom_data.xml``,
``security/uom_security.xml`` e ``ir.model.access.csv`` en la clave
``data``, que ``load_data`` lee al instalar. ``uom_data.xml`` trae 31
registros con xml id —30 unidades y la precisión ``decimal_product_uom``—,
entre ellos la jornada (``product_uom_day``, 8 horas) con que
``sale_timesheet`` convierte el costo por hora en costo por día. Aquí los lee
el mismo ciclo de instalación (``modules.loading.load_modules``), como los de
``hr`` (``test_hr_security_data``).
"""
import pytest

from addons.base.models import IrModelData
from addons.base.models.ir_model import IrModelAccess
from addons.uom.models import Uom
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
    assert day.factor == pytest.approx(8.0)


def test_every_unit_of_the_source_has_its_xml_id():
    rows = IrModelData.objects.filter(module='uom')
    units = [row for row in rows if isinstance(_ref(f'uom.{row.name}'), Uom)]
    assert len(units) == 30
    assert {'product_uom_unit', 'product_uom_hour', 'product_uom_day',
            'product_uom_minute', 'product_uom_dozen'} <= {
        row.name for row in units}
    assert _ref('uom.decimal_product_uom').name == 'Product Unit'


def test_an_inactive_unit_of_the_source_stays_inactive():
    assert _ref('uom.product_uom_dozen').active is False


def test_the_group_and_the_access_rows_of_the_source_are_loaded():
    assert _ref('uom.group_uom').name == 'Manage Multiple Units of Measure'
    manager = _ref('uom.access_uom_uom_manager')
    user = _ref('uom.access_uom_uom_user')
    assert isinstance(manager, IrModelAccess)
    assert manager.group_id == _ref('base.group_system')
    assert (manager.perm_read, manager.perm_write, manager.perm_create,
            manager.perm_unlink) == (True, True, True, True)
    assert user.group_id == _ref('base.group_user')
    assert (user.perm_read, user.perm_write, user.perm_create,
            user.perm_unlink) == (True, False, False, False)

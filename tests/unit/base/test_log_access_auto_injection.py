"""DEC-09: el log-access en los modelos que no heredan la base común.

≙ el ``add_default`` de las cuatro columnas en el metaclase de la fuente
(``odoo19c: odoo/orm/models.py:274-292``) y ``_log_access = _auto``
(``odoo/orm/model_classes.py:267``). Diseño en
``designs/log-access-auto-injection.md`` del Workbench.

*Métrica:* columnas de ``LOG_ACCESS_COLUMNS`` en el ``_meta`` de cada
modelo, y su valor tras un alta y una escritura por la ruta del ORM.
*Ciega a:* la columna física de una base que no haya migrado; eso lo mide
``makemigrations --check`` y el ci-multidb, no esta prueba.
"""
import pytest
from django.db import models
from django.test.utils import isolate_apps

from addons.account.models import AccountAccount
from addons.base.models import IrAttachment, ResUsers
from addons.base.models.ir_model import IrModelInherit
from addons.base.models.res_country import ResCountry
from addons.hr.models.hr_employee_public import HrEmployeePublic
from orm.environments import user_scope
from orm.model_classes import LOG_ACCESS_COLUMNS, adopt_log_access

pytestmark = pytest.mark.django_db


def _columns(model):
    return {field.name for field in model._meta.local_fields}


@pytest.mark.parametrize('model', [ResCountry, IrAttachment, AccountAccount])
def test_reference_models_without_the_base_get_the_four_columns(model):
    assert set(LOG_ACCESS_COLUMNS) <= _columns(model)


def test_a_model_that_turns_log_access_off_gets_none():
    assert IrModelInherit._log_access is False
    assert not set(LOG_ACCESS_COLUMNS) & _columns(IrModelInherit)


def test_adoption_is_idempotent():
    assert adopt_log_access(ResCountry) == 0


def test_injected_columns_are_stamped_on_save(user):
    """``res.country`` es un modelo de Django sin la base del ORM: no tiene
    ``write()``, así que su ruta es ``save()``, donde los sellan los
    ``pre_save`` de las columnas inyectadas."""
    with user_scope(user.pk):
        # QZ es de uso privado en ISO 3166-1: no lo siembra la base.
        country = ResCountry.objects.create(name='Tierra Media', code='QZ')
    other = ResUsers.objects.create_user(login=f'{user.login}-other',
                                         password='OtherPass123!',
                                         name='Other User')
    with user_scope(other.pk):
        country.name = 'Tierra Media 2'
        country.save()
    country.refresh_from_db()
    assert country.create_uid_id == user.pk
    assert country.write_uid_id == other.pk
    assert country.created_at is not None
    assert country.updated_at >= country.created_at


def test_a_model_prepared_later_receives_them_by_the_signal():
    with isolate_apps('addons.base'):
        meta = type('Meta', (), {'app_label': 'base'})
        probe = type('LogAccessProbe', (models.Model,), {
            '__module__': __name__, 'Meta': meta,
            '_name': 'test.log.access.probe',
            'label': models.CharField(max_length=10)})
    assert set(LOG_ACCESS_COLUMNS) <= _columns(probe)


def test_the_public_employee_view_exposes_the_four_magic_columns():
    """``hr.employee.public`` es ``_auto = False`` con ``_log_access =
    True``: su vista selecciona las cuatro de ``hr_employee`` (``odoo19c:
    addons/hr/models/hr_employee_public.py:14-15,185-193``)."""
    names = {field.name for field in HrEmployeePublic._meta.local_fields}
    assert {'create_date', 'create_uid', 'write_date', 'write_uid'} <= names
    select = HrEmployeePublic._get_fields()
    for column in ('create_uid_id', 'write_date', 'write_uid_id'):
        assert f' AS {column}' in select


def _probe(name, **attrs):
    with isolate_apps('addons.base'):
        meta = type('Meta', (), {'app_label': 'base'})
        return type(name, (models.Model,), {
            '__module__': __name__, 'Meta': meta,
            'label': models.CharField(max_length=10), **attrs})


def test_a_probe_with_log_access_off_receives_nothing():
    """``_log_access = False`` excluye el modelo (``odoo19c:
    odoo/orm/models.py:283``)."""
    probe = _probe('LogAccessOffProbe', _name='test.log.access.off',
                   _log_access=False)
    assert not set(LOG_ACCESS_COLUMNS) & _columns(probe)


def test_a_declared_column_is_not_overwritten():
    """``add_default`` no pisa un campo declarado (``odoo19c:
    odoo/orm/models.py:274-281``)."""
    date_name = LOG_ACCESS_COLUMNS[1]
    own = models.DateTimeField(null=True, help_text='propia')
    probe = _probe('LogAccessOwnProbe', _name='test.log.access.own',
                   **{date_name: own})
    assert probe._meta.get_field(date_name).help_text == 'propia'
    # ``get_field`` devuelve el primero: un duplicado sólo se ve contando.
    names = [field.name for field in probe._meta.local_fields]
    assert names.count(date_name) == 1
    assert set(LOG_ACCESS_COLUMNS) <= _columns(probe)

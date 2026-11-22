"""El x2many vive en el entorno del registro, y un borrado de Django invalida
la caché.

≙ ``odoo19c: odoo/orm/fields.py:1642-1650`` (``Field.__get__`` toma
``record.env``) y ``odoo19c: odoo/orm/models.py`` ``unlink`` →
``self.env.invalidate_all(flush=False)``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
orm-record-env-x2many-and-django-delete-cache.md``.

*Métrica:* el ``su`` del entorno de los registros que devuelve un One2many
leído desde un registro elevado, y el valor de un Many2one tras borrar con
Django el registro al que apuntaba (``SET NULL``).
*Ciega a:* cambios hechos por SQL crudo fuera de un borrado.
"""
import pytest

from addons.base.models.res_partner import ResPartner
from exceptions import AccessError
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


def _multi_with_lines():
    multi = env()['test_orm.multi'].create({})
    env()['test_orm.multi.line'].create([
        {'multi': multi.id, 'name': 'a'},
        {'multi': multi.id, 'name': 'b'},
    ])
    return multi


def test_the_lines_of_an_elevated_order_live_in_its_environment():
    with sudo():
        created = _multi_with_lines()
    # El registro se lee en el entorno ambiente, sin elevar; sólo
    # ``sudo()`` sobre él lo eleva.
    multi = env()['test_orm.multi'].browse(created.id)
    assert multi.env.su is False
    lines = multi.sudo().lines
    assert len(lines) == 2
    assert lines.env.su is True


def test_a_django_delete_invalidates_the_cached_set_null():
    partner = ResPartner.objects.create(name='U3b socio borrable')
    with sudo():
        multi = env()['test_orm.multi'].create({'partner': partner.pk})
        assert multi.partner_id == partner.pk
        partner.delete()
        multi.refresh_from_db()
        assert multi.partner_id is None


def test_unlink_checks_access_in_the_environment_of_the_records():
    """≙ ``self.check_access('unlink')``
    (``odoo19c: odoo/orm/models.py:4203``):
    el ACL se lee del entorno del recordset; un ``sudo()`` sobre él basta."""
    with sudo():
        created = _multi_with_lines()
    multi = env()['test_orm.multi'].browse(created.id)
    with pytest.raises(AccessError):
        multi.lines.unlink()
    multi.sudo().lines.unlink()
    with sudo():
        assert not env()['test_orm.multi'].browse(created.id).lines

"""Un adjunto hereda el acceso del registro al que apunta.

≙ ``odoo19c: odoo/addons/base/models/ir_attachment.py:504-708`` y
``:710-795``: sobre lo que la ACL de modelo deja pasar, ``public`` siempre se
lee; con ``res_model``/``res_id`` manda el acceso al registro; sin registro,
sólo el creador y el sistema (``designs/attachment-record-access.md``).

El registro adjuntado es ``res.company``: el usuario tiene ACL de lectura
sobre el modelo y una regla que sólo le deja ver una de dos empresas.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import ResCompany
from addons.base.models.ir_attachment import condition_values
from addons.base.models.ir_model import IrModel, IrModelAccess, IrModelData
from addons.base.models.ir_rule import IrRule
from addons.base.models.res_groups import ResGroups
from exceptions import AccessError
from orm.domains import Domain
from orm.environments import env as current_env, sudo, user_scope

pytestmark = pytest.mark.django_db


@pytest.fixture
def companies():
    seen = ResCompany.objects.create(code='att-seen', name='Visible')
    hidden = ResCompany.objects.create(code='att-hidden', name='Oculta')
    row, _ = IrModel.objects.get_or_create(
        model='res.company', defaults={'name': 'Compañía'})
    IrModelAccess.objects.create(name='att company read', model_id=row,
                                 perm_read=True, perm_write=True)
    IrRule.objects.create(name='att sólo la visible',
                          model_name='res.company',
                          domain_force="[('code', '=', 'att-seen')]")
    return seen, hidden


@pytest.fixture
def employee():
    """Un interno: ``base.group_user`` le da la ACL de ``ir.attachment``."""
    user = get_user_model().objects.create_user(
        login='att.employee@kaupamex.mx', group_ids=[])
    ResGroups.objects.get(pk=IrModelData._xmlid_to_res_id(
        'base.group_user', raise_if_not_found=True)).user_ids.add(user)
    return user


def attach(name, **values):
    with sudo():
        return current_env()['ir.attachment'].create(
            {'name': name, 'type': 'url', 'url': 'https://example.com',
             **values})


def as_user(user, attachment, method, *args):
    """Llama ``method`` sobre el adjunto DENTRO del alcance del usuario: el
    entorno que evalúa la ACL y las reglas es el ambiental."""
    with user_scope(user.pk):
        records = current_env()['ir.attachment'].browse(attachment.ids)
        return getattr(records, method)(*args)


def test_the_attachment_of_a_hidden_record_is_refused(companies, employee):
    _seen, hidden = companies
    attachment = attach('hidden', res_model='res.company', res_id=hidden.pk)
    with pytest.raises(AccessError):
        as_user(employee, attachment, 'check_access', 'read')


def test_the_attachment_of_a_visible_record_is_read(companies, employee):
    seen, _hidden = companies
    attachment = attach('seen', res_model='res.company', res_id=seen.pk)
    as_user(employee, attachment, 'check_access', 'read')


def test_a_public_attachment_is_read_anyway(companies, employee):
    _seen, hidden = companies
    attachment = attach('public', res_model='res.company', res_id=hidden.pk,
                        public=True)
    as_user(employee, attachment, 'check_access', 'read')


def test_without_a_record_only_its_creator_reads_it(companies, employee):
    attachment = attach('orphan')
    with pytest.raises(AccessError):
        as_user(employee, attachment, 'check_access', 'read')


def test_search_leaves_out_hidden_records(companies, employee):
    seen, hidden = companies
    visible = attach('s-seen', res_model='res.company', res_id=seen.pk)
    attach('s-hidden', res_model='res.company', res_id=hidden.pk)
    with user_scope(employee.pk):
        found = current_env()['ir.attachment'].search(
            [('res_model', '=', 'res.company'),
             ('res_id', 'in', [seen.pk, hidden.pk])])
    assert list(found.ids) == visible.ids


def test_moving_an_attachment_to_a_hidden_record_is_refused(
        companies, employee):
    seen, hidden = companies
    attachment = attach('mv', res_model='res.company', res_id=seen.pk)
    with pytest.raises(AccessError):
        as_user(employee, attachment, 'write', {'res_id': hidden.pk})


def test_condition_values_reads_the_in_values():
    model = current_env()['ir.attachment']
    assert set(condition_values(model, 'res_id',
                                Domain('res_id', 'in', [3, 5]))) == {3, 5}
    assert condition_values(model, 'res_id', Domain('name', '=', 'x')) is None

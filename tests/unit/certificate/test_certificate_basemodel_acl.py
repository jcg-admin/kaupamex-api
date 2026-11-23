"""``certificate`` sobre ``BaseModel`` y con la ACL de la referencia.

≙ ``odoo19c: addons/certificate/models/certificate.py:20-24`` y
``odoo19c: addons/certificate/models/key.py:35-37`` (los dos son
``BaseModel``; la llave declara ``_name`` y ``_description``), y
``odoo19c: addons/certificate/security/ir.model.access.csv`` (dos filas:
todo para ``base.group_system``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-certificate.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelAccess, IrModelData
from addons.certificate.models.certificate import CertificateCertificate
from addons.certificate.models.key import CertificateKey
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


def _user(login, *groups):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    for name in groups:
        user.group_ids.add(MODELS_BY_NAME['res.groups'].objects.get(
            pk=IrModelData.objects.get(module='base', name=name).res_id))
    return user


@pytest.mark.parametrize('model', [CertificateCertificate, CertificateKey])
def test_both_models_are_base_models(model):
    assert issubclass(model, BaseModel)


def test_the_key_declares_its_source_header():
    assert CertificateKey._name == 'certificate.key'
    assert CertificateKey._description == 'Cryptographic Keys'


def test_the_acl_is_the_reference_csv_with_its_external_ids():
    loaded = IrModelData.objects.filter(module='certificate',
                                        model='ir.model.access')
    assert sorted(loaded.values_list('name', flat=True)) == [
        'access_certificate_admin', 'access_key_admin']
    for name in ('access_certificate_admin', 'access_key_admin'):
        row = IrModelAccess.objects.get(pk=loaded.get(name=name).res_id)
        assert (row.perm_read, row.perm_write, row.perm_create,
                row.perm_unlink) == (True, True, True, True)


def test_only_a_system_user_reads_certificates():
    internal = _user('certificate-acl-internal', 'group_user')
    with user_scope(internal.pk), pytest.raises(AccessError):
        Environment(uid=internal.pk)['certificate.certificate'].search([])
    admin = _user('certificate-acl-system', 'group_user', 'group_system')
    with user_scope(admin.pk):
        found = Environment(uid=admin.pk)['certificate.certificate'].search(
            [])
    assert not found

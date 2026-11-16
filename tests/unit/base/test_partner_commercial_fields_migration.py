"""Los contactos que siembra una migración reciben su entidad comercial.

``base.partner_root`` y ``base.public_partner`` se crean en las migraciones
``0106`` y ``0113`` con el modelo histórico, que no ejecuta cómputos: en una
base construida sólo por migraciones su ``commercial_partner_id`` quedaba
nulo, y la regla ``account.account_invoice_rule_portal`` (``[user.
commercial_partner_id.id]``) no se podía evaluar al aprovisionar una base de
empresa. En la fuente esos contactos se crean por el ORM, que los calcula
(``odoo19c: odoo/addons/base/models/res_partner.py:515-528``).
"""
import importlib

import pytest
from django.apps import apps
from django.db import connection

from addons.base.data.res_users_data import seed_root_user
from addons.base.models import ResPartner
from orm.environments import get_transaction, sudo
from orm.migration_operations import ComputeStoredFields
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db
MIGRATION = 'addons.base.migrations.0116_partner_commercial_fields'


def _operation():
    migration = importlib.import_module(MIGRATION).Migration
    [operation] = migration.operations
    return operation


def _columns(pk):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT commercial_partner_id, commercial_company_name '
            'FROM res_partner WHERE id = %s', [pk])
        return cursor.fetchone()


def test_the_migration_computes_both_stored_fields_of_the_partner():
    operation = _operation()
    assert isinstance(operation, ComputeStoredFields)
    assert (operation.app_label, operation.model_name) == (
        'base', 'respartner')
    assert sorted(operation.field_names) == [
        'commercial_company_name', 'commercial_partner_id']


def test_it_runs_after_every_migration_that_seeds_partners():
    migration = importlib.import_module(MIGRATION).Migration
    assert ('base', '0115_rescompany_purchase_fields') in (
        migration.dependencies)


def test_a_partner_seeded_without_computes_points_at_itself():
    with sudo():
        partner = ResPartner.objects.create(name='Sembrado sin cómputo')
        get_transaction().flush()
        ResPartner.objects.filter(pk=partner.pk).update(
            commercial_partner_id=None)
        assert _columns(partner.pk)[0] is None
        with connection.schema_editor() as editor:
            _operation().code(apps, editor)
    assert _columns(partner.pk)[0] == partner.pk


def test_a_contact_reaches_its_company():
    with sudo():
        company = ResPartner.objects.create(name='Empresa S', is_company=True)
        contact = ResPartner.objects.create(name='Contacto S', parent=company)
        get_transaction().flush()
        ResPartner.objects.filter(pk__in=[company.pk, contact.pk]).update(
            commercial_partner_id=None)
        with connection.schema_editor() as editor:
            _operation().code(apps, editor)
    assert _columns(contact.pk)[0] == company.pk


def test_the_root_partner_resolves_for_the_portal_rule():
    """El contrato que fallaba: ``user.commercial_partner_id.id``."""
    with sudo():
        user = seed_root_user(apps, connection.alias)
        get_transaction().flush()
        ResPartner.objects.filter(pk=user.partner_id).update(
            commercial_partner_id=None)
        with connection.schema_editor() as editor:
            _operation().code(apps, editor)
        user = apps.get_model('base', 'ResUsers').objects.get(
            pk=SUPERUSER_ID)
        assert user.commercial_partner_id.id == user.partner_id

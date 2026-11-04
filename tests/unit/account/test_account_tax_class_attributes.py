"""La cabecera de ``account.tax``: los siete atributos de clase de la fuente.

≙ ``AccountTax`` (``odoo19c: addons/account/models/account_tax.py:71-78``).
Sin ``_name`` el modelo no entra en ``orm.registry.MODELS_BY_NAME`` y
``env['account.tax']`` no resuelve, que es justo lo que la envoltura de
base-lines necesita para su respaldo vacío (``load('tax_ids',
self.env['account.tax'])``).
"""

import pytest

from addons.account.models import AccountTax
from orm import models
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.unit


def test_the_seven_class_attributes_the_source_declares():
    assert AccountTax._name == 'account.tax'
    assert AccountTax._inherit == ['mail.thread']
    assert AccountTax._description == 'Tax'
    assert AccountTax._order == 'sequence,id'
    assert AccountTax._check_company_auto is True
    assert AccountTax._rec_names_search == [
        'name', 'description', 'invoice_label']
    assert (AccountTax._check_company_domain.__func__
            is models.check_company_domain_parent_of)


def test_the_order_and_the_table_match_the_django_meta():
    assert AccountTax._meta.ordering == ['sequence', 'id']
    assert AccountTax._meta.db_table == AccountTax._name.replace('.', '_')


@pytest.mark.django_db
def test_the_environment_resolves_the_model_by_its_name():
    with Environment(None, SUPERUSER_ID, {}) as env:
        assert env['account.tax'] is AccountTax


def test_the_fields_the_name_search_names_exist():
    """``_rec_names_search`` nombra ``description`` e ``invoice_label``
    (``odoo19c: :134-135``); sin ellos el gate de rutas no compila."""
    fields = {field.name: field for field in AccountTax._meta.get_fields()}
    assert {'name', 'description', 'invoice_label'} <= set(fields)
    assert fields['invoice_label'].translate is True

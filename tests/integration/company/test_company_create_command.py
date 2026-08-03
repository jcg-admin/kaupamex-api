"""Integración — management command ``company_create`` (SOL-091, T-091-07).

Verifica la orquestación del adapter contra la ``Company`` **real** (get_or_create
idempotente) mockeando sólo el primitivo de provisioning ``provision_company_database``
(que requiere DDL global — fuera del alcance de este test de alta unitaria). Cubre:

1. Alta de la fila L0 + provisioning de ``company_<id>_db`` con el alias derivado.
2. Idempotencia: re-ejecutar con el mismo código NO duplica la fila.
"""
from io import StringIO
from unittest import mock

import pytest

from django.core.management import call_command

from addons.platform.models import Company

pytestmark = pytest.mark.integration


@mock.patch('addons.platform.management.commands.company_create.provision_company_database')
def test_creates_row_and_provisions_db(mock_provision, db):
    mock_provision.return_value = ('company_stub_db', True)
    out = StringIO()
    call_command('company_create', 'acme', '--name', 'ACME S.A.', stdout=out)

    company = Company.objects.get(code='acme')
    assert company.name == 'ACME S.A.'
    mock_provision.assert_called_once_with('company_%s_db' % company.id)
    assert 'row_created=True' in out.getvalue()


@mock.patch('addons.platform.management.commands.company_create.provision_company_database')
def test_second_run_is_idempotent(mock_provision, db):
    mock_provision.return_value = ('company_stub_db', False)
    call_command('company_create', 'globex', stdout=StringIO())
    first_id = Company.objects.get(code='globex').id

    out = StringIO()
    call_command('company_create', 'globex', stdout=out)

    assert Company.objects.filter(code='globex').count() == 1
    assert Company.objects.get(code='globex').id == first_id  # misma fila
    assert 'row_created=False' in out.getvalue()
    # default de nombre = código cuando no se pasa --name
    assert Company.objects.get(code='globex').name == 'globex'

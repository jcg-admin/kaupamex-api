"""Descubrimiento de bases via information_schema (SOL-091, T-091-04).

Verifica contra MariaDB real (no SQLite) que ``list_all_schema_names`` lee el
catálogo del motor — el equivalente de ``list_dbs`` de Odoo sobre
``pg_database`` — y que ``list_company_db_names`` aplica el filtro
``company_<N>_db`` (== ``db_filter``). Sin este descubrimiento por catálogo,
``orm`` necesitaría un modelo/tabla de registro, lo que lo volvería una app de
dominio (infiel a ``odoo/orm/``, que no tiene modelos de negocio).
"""
import pytest
from django.db import connection

from service.db import list_all_schema_names, list_company_db_names

pytestmark = pytest.mark.django_db


def test_list_all_schema_names_includes_test_schema():
    # El schema de la conexión 'default' de test debe aparecer en el catálogo.
    names = list_all_schema_names('default')
    assert connection.settings_dict['NAME'] in names
    # information_schema siempre existe en MariaDB.
    assert 'information_schema' in names


def test_list_company_db_names_filters_to_company_shape():
    # Sin bases company_<N>_db provisionadas, el descubrimiento devuelve [].
    # (El schema de test es kaupamex_qa, que no matchea company_<N>_db.)
    names = list_company_db_names('default')
    assert all(n.startswith('company_') and n.endswith('_db') for n in names)

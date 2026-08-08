"""Descubrimiento de bases via catálogo del motor (SOL-091, T-091-04).

Verifica contra PostgreSQL real (no SQLite) que ``list_all_schema_names`` lee
``pg_database`` —el mismo catálogo que ``list_dbs`` de Odoo— y que ``list_company_db_names`` aplica el filtro
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
    # ``postgres`` siempre existe: es la base de mantenimiento del cluster, la
    # que ``service.db`` usa para el DDL de bases.
    assert 'postgres' in names
    # ``information_schema`` NO aparece: en PostgreSQL es un *schema* dentro de
    # cada base, no una base. Que en MariaDB saliera aquí era consecuencia de
    # que allá "schema" y "base" son la misma cosa.
    assert 'information_schema' not in names
    # Las plantillas quedan fuera por el ``NOT datistemplate`` de la consulta:
    # no son bases de trabajo y ofrecerlas invitaría a escribir en ellas.
    assert 'template0' not in names and 'template1' not in names


def test_list_company_db_names_filters_to_company_shape():
    # Sin bases company_<N>_db provisionadas, el descubrimiento devuelve [].
    # (El schema de test es kaupamex_qa, que no matchea company_<N>_db.)
    names = list_company_db_names('default')
    assert all(n.startswith('company_') and n.endswith('_db') for n in names)

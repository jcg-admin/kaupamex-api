"""Los Many2many de entrevistadores con el nombre y la tabla de la fuente.

≙ ``odoo19c: addons/hr_recruitment/models/hr_job.py:64-70`` (``hr.job.
interviewer_ids``, sin ``relation``: la tabla la deriva
``odoo/orm/fields_relational.py:1291-1295``) y ``hr_applicant.py:125-127``
(``hr.applicant.interviewer_ids`` sobre
``hr_applicant_res_users_interviewers_rel``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
recruitment-interviewer-fields.md``.
"""
import pytest
from django.db import connection

from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

#: modelo → (tabla intermedia, columna del modelo, columna de ``res.users``)
SOURCE_TABLES = {
    'hr.job': ('hr_job_res_users_rel', 'hr_job_id', 'res_users_id'),
    'hr.applicant': ('hr_applicant_res_users_interviewers_rel',
                     'hr_applicant_id', 'res_users_id'),
}


@pytest.mark.parametrize('model_name', sorted(SOURCE_TABLES))
def test_the_field_carries_the_source_name(model_name):
    field = MODELS_BY_NAME[model_name]._meta.get_field('interviewer_ids')
    assert field.many_to_many
    assert field.related_model is MODELS_BY_NAME['res.users']


@pytest.mark.parametrize('model_name', sorted(SOURCE_TABLES))
def test_the_django_name_is_gone(model_name):
    names = {f.name for f in MODELS_BY_NAME[model_name]._meta.get_fields()}
    assert 'interviewers' not in names


@pytest.mark.parametrize('model_name', sorted(SOURCE_TABLES))
def test_the_relation_table_and_columns_are_the_source_ones(model_name):
    table, column1, column2 = SOURCE_TABLES[model_name]
    through = MODELS_BY_NAME[model_name]._meta.get_field(
        'interviewer_ids').remote_field.through
    assert through._meta.db_table == table
    with connection.cursor() as cr:
        columns = {c.name for c in connection.introspection
                   .get_table_description(cr, table)}
    assert {column1, column2} <= columns

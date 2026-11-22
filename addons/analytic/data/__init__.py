"""Datos semilla del addon ``analytic``.

≙ ``odoo19c: addons/analytic/data/analytic_data.xml:13-17``: el plan «Project»
y el parámetro ``analytic.project_plan`` que lo nombra. La siembra vive aquí y
no en la migración porque tiene dos llamadores: ``migrations/0017`` y el
catálogo de semillas de ``tests/conftest.py``, que la repone después de que un
test transaccional vacíe las tablas (H-API-22). Con una copia en cada sitio,
una divergiría.
"""
from django.db import connections

XML_MODULE = 'analytic'
XML_NAME = 'analytic_plan_projects'


def _main_company_id(apps, alias):
    """La empresa ``base.main_company``, o la de menor id."""
    IrModelData = apps.get_model('base', 'IrModelData')
    row = IrModelData.objects.using(alias).filter(
        module='base', name='main_company').first()
    if row is not None:
        return row.res_id
    Company = apps.get_model('base', 'ResCompany')
    company = Company.objects.using(alias).order_by('id').first()
    return company.pk if company is not None else None


def seed_project_plan(apps, alias):
    """Crea el plan «Project» y ``analytic.project_plan`` si el parámetro no
    existe. Como la fuente (``noupdate``), no toca uno ya fijado."""
    SystemParameter = apps.get_model('base', 'SystemParameter')
    Plan = apps.get_model('analytic', 'AccountAnalyticPlan')
    IrModelData = apps.get_model('base', 'IrModelData')
    if SystemParameter.objects.using(alias).filter(
            key='analytic.project_plan').exists():
        return
    plan = Plan.objects.using(alias).create(name='Project')
    # ``<field name="default_applicability">optional</field>`` de la fuente
    # escribe el valor de la empresa con que se cargan los datos, la
    # principal; la columna es ``jsonb`` ``{empresa: valor}``.
    company_id = _main_company_id(apps, alias)
    if company_id is not None:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                'UPDATE account_analytic_plan SET default_applicability = '
                'jsonb_build_object(%s::text, %s) WHERE id = %s',
                [company_id, 'optional', plan.pk])
    plan.parent_path = f'{plan.pk}/'
    plan.complete_name = plan.name
    plan.save(update_fields=['parent_path', 'complete_name'])
    SystemParameter.objects.using(alias).create(
        key='analytic.project_plan', value=str(plan.pk))
    IrModelData.objects.using(alias).update_or_create(
        module=XML_MODULE, name=XML_NAME,
        defaults={'model': 'analytic.AccountAnalyticPlan',
                  'res_id': plan.pk, 'noupdate': True})

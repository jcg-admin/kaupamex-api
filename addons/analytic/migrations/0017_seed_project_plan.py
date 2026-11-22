"""Siembra el plan «Project» y ``analytic.project_plan``.

≙ ``odoo19c: addons/analytic/data/analytic_data.xml:13-17``: el parámetro
nombra el plan cuyas cuentas viven en ``account_id``; ``_get_all_plans``
levanta sin él (``designs/analytic-plan-methods.md``). Como la fuente
(``noupdate``), no se toca un parámetro ya fijado.
"""
from django.db import migrations

XML_MODULE = 'analytic'
XML_NAME = 'analytic_plan_projects'


def seed(apps, schema_editor):
    alias = schema_editor.connection.alias
    SystemParameter = apps.get_model('base', 'SystemParameter')
    Plan = apps.get_model('analytic', 'AccountAnalyticPlan')
    IrModelData = apps.get_model('base', 'IrModelData')
    if SystemParameter.objects.using(alias).filter(
            key='analytic.project_plan').exists():
        return
    # ``default_applicability`` depende de la empresa: sin valor propio la
    # responde ``ir.default`` con ``optional``, el valor que la fuente fija.
    plan = Plan.objects.using(alias).create(name='Project')
    plan.parent_path = f'{plan.pk}/'
    plan.complete_name = plan.name
    plan.save(update_fields=['parent_path', 'complete_name'])
    SystemParameter.objects.using(alias).create(
        key='analytic.project_plan', value=str(plan.pk))
    IrModelData.objects.using(alias).get_or_create(
        module=XML_MODULE, name=XML_NAME,
        defaults={'model': 'analytic.AccountAnalyticPlan',
                  'res_id': plan.pk, 'noupdate': True})


class Migration(migrations.Migration):

    dependencies = [
        ('analytic', '0016_plan_parent_id_complete_name'),
        ('base', '0126_fill_cron_action_code'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]

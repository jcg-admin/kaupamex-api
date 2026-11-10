"""Calcula sobre las filas existentes los calculados almacenados que una
migración anterior de esta app añadió sin calcular.

≙ ``odoo19c: odoo/orm/models.py:3220-3238``. Las dependencias son las hojas
vigentes de las apps cuyos campos lee el cómputo, medidas con
``registry.field_depends`` (TASK-API-0516).
"""
from django.db import migrations

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0004_alter_crmlead_date_last_stage_update_and_more'),
        ('base', '0102_company_dependent_not_null_index'),
        ('sales_team',
         '0007_crmteam_assignment_domain_crmteam_assignment_optout_and_more'),
    ]

    operations = [
        ComputeStoredFields('crm', 'crmlead', [
            'company_id',
            'date_last_stage_update',
            'date_open',
            'day_close',
            'day_open',
            'email_domain_criterion',
            'email_state',
            'function',
            'lang_id',
            'partner_name',
            'phone_state',
            'prorated_revenue',
            'recurring_revenue_monthly',
            'recurring_revenue_monthly_prorated',
            'recurring_revenue_prorated',
            'website',
            'won_status',
        ]),
    ]

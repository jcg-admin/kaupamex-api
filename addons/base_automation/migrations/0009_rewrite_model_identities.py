"""Lleva a la identidad contractual las dos columnas de modelo de la regla.

``model_name`` es la copia de ``model_id.model`` (``odoo19c:
addons/base_automation/models/base_automation.py:134``) y
``trg_field_ref_model_name`` la de ``ir_model_fields.relation`` (``:376``);
con ``base.0128`` ya aplicada, estas dos siguen.
"""
from django.db import migrations

from orm.migration_operations import RewriteModelIdentities


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0128_rewrite_model_identities'),
        ('base_automation', '0008_seed_cron_check'),
    ]

    operations = [
        RewriteModelIdentities('base_automation', 'model_name'),
        RewriteModelIdentities('base_automation', 'trg_field_ref_model_name'),
    ]

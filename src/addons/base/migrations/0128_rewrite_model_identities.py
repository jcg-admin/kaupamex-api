"""Lleva a la identidad contractual las columnas que nombran modelos.

La fuente guarda ``model._name`` en ``ir_model.model`` (``odoo19c:
odoo/addons/base/models/ir_model.py:428``) y, por la misma llave, en
``ir_model_fields.model``/``relation``, ``ir_model_data.model``,
``ir_rule.model_name``, ``ir_act_server.model_name`` e
``ir_act_report_xml.model``. Este árbol guardaba la etiqueta de Django; el
corte C3 de ``designs/model-identity-contract.md`` cambia los escritores y
esta migración reescribe las filas existentes.
"""
from django.db import migrations, models

from orm.migration_operations import RewriteModelIdentities


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0127_cron_xml_ids'),
    ]

    operations = [
        RewriteModelIdentities('ir_model', 'model', unique_with=['model']),
        RewriteModelIdentities('ir_model_fields', 'model',
                               unique_with=['model', 'name']),
        RewriteModelIdentities('ir_model_fields', 'relation'),
        RewriteModelIdentities('ir_model_data', 'model'),
        RewriteModelIdentities('ir_rule', 'model_name'),
        RewriteModelIdentities('ir_act_server', 'model_name'),
        RewriteModelIdentities('ir_act_report_xml', 'model'),
        migrations.AlterField(
            model_name='irrule',
            name='model_name',
            field=models.CharField(
                db_index=True, max_length=120, verbose_name='Modelo',
                help_text=("Odoo model_id. Identidad del modelo, "
                           "p.ej. 'sale.order'.")),
        ),
    ]

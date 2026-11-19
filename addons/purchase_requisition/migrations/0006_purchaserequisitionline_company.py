"""``company_id`` de ``purchase.requisition.line``, related almacenado.

≙ ``odoo19c: addons/purchase_requisition/models/purchase_requisition.py:181``
(``related='requisition_id.company_id', store=True``). La columna nace con el
valor de su acuerdo en las filas que ya existen, como la que la fuente
calcula al crear el campo.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0125_irattachment_res_id_help_text"),
        ("purchase_requisition", "0005_restrict_ondelete_block_f"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaserequisitionline",
            name="company",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="base.rescompany",
                verbose_name="Empresa",
            ),
        ),
        migrations.RunSQL(
            sql=(
                'UPDATE purchase_requisition_line AS line '
                'SET company_id = agreement.company_id '
                'FROM purchase_requisition AS agreement '
                'WHERE agreement.id = line.requisition_id'
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

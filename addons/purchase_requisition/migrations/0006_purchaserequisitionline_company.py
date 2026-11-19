"""``company_id`` de ``purchase.requisition.line``, related almacenado.

≙ ``odoo19c: addons/purchase_requisition/models/purchase_requisition.py:181``
(``related='requisition_id.company_id', store=True``). La columna nace vacía
y ``ComputeStoredFields`` la calcula sobre las filas existentes
(``odoo19c: odoo/orm/models.py:3220-3238``).
"""

import django.db.models.deletion
from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


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
        ComputeStoredFields('purchase_requisition', 'purchaserequisitionline',
                            ['company']),
    ]

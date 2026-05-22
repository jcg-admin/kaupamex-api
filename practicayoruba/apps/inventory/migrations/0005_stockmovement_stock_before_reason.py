"""
Migration 0005 — T-111: add stock_before + reason to StockMovement.

stock_before (nullable): stock level before the movement, required by
RNF-PROC-002 §3 for full audit trail.

reason (blank-able CharField): structured reason code for TYPE_ADJUSTMENT
movements (UC-INV-04). Previously concatenated in notes; now a queryable
column ("how many MERMA this month?").
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_adjustmentmovement_cancellationmovement_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockmovement',
            name='stock_before',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='stockmovement',
            name='reason',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]

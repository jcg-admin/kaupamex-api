from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logistics', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipmentguide',
            name='estimated_delivery',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

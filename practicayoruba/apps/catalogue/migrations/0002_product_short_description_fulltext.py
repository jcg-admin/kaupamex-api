# Generated migration — Sprint 5 — UC-SRCH-01
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='category',
            options={'ordering': ['name'], 'verbose_name_plural': 'categories'},
        ),
        migrations.AddField(
            model_name='product',
            name='short_description',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE catalogue_product "
                "ADD FULLTEXT INDEX ft_product_name_desc "
                "(name, description, short_description)"
            ),
            reverse_sql=(
                "ALTER TABLE catalogue_product "
                "DROP INDEX ft_product_name_desc"
            ),
        ),
    ]

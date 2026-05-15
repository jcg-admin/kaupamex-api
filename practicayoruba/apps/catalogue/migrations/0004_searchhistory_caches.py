"""
Migration Sprint 6:
- Agrega modelo SearchHistory (UC-SRCH-03).
- Crea la tabla de cache (UC-SRCH-02 / UC-CAT-08).
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('catalogue', '0003_product_is_featured'),
    ]

    operations = [
        # Tabla de cache para DatabaseCache (UC-SRCH-02)
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS `cache_table` (
                `cache_key`  varchar(255) NOT NULL PRIMARY KEY,
                `value`      longtext     NOT NULL,
                `expires`    datetime(6)  NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            reverse_sql="DROP TABLE IF EXISTS `cache_table`;",
            hints={'target_db': 'default'},
        ),
        # Modelo SearchHistory (UC-SRCH-03)
        migrations.CreateModel(
            name='SearchHistory',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True)),
                ('term',        models.CharField(db_index=True, max_length=100)),
                ('searched_at', models.DateTimeField(auto_now=True)),
                ('user',        models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='search_history',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Historial de búsqueda',
                'db_table': 'catalogue_search_history',
                'ordering': ['-searched_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='searchhistory',
            constraint=models.UniqueConstraint(
                fields=['user', 'term'],
                name='unique_user_term',
            ),
        ),
    ]

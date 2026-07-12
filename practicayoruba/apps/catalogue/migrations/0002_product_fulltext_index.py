# FULLTEXT index para búsqueda de productos (UC-SRCH-01).
#
# Se recrea tras la regeneración from-scratch de migraciones de la
# iniciativa party (T-201): al squashear a 0001_initial se perdió el
# ``RunSQL`` que crea el índice FULLTEXT (makemigrations no regenera
# operaciones RunSQL manuales), por lo que ``_fulltext_search``
# (catalogue/views.py) fallaba con "Can't find FULLTEXT index matching
# the column list". Ver catalogue/models.py y ``_fulltext_search``.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
    ]

    operations = [
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

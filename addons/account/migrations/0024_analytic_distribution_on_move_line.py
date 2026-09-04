"""``account.move.line`` hereda ``analytic.mixin`` — tarea #526.

La columna ``analytic_distribution`` y su indice GIN. El indice es el
equivalente de ``init()`` del mixin (``odoo19c: analytic/models/
analytic_mixin.py:32-40``): la fuente lo emite en el gancho que su ORM invoca
al instalar el modulo, y el hogar de un DDL en este arbol es una migracion.

El indice cubre el mismo predicado que ``_search_analytic_distribution``
consulta —el arreglo de IDs que ``regexp_split_to_array`` extrae de las claves
del JSON— asi que el operador ``&&`` de solapamiento lo usa. PostgreSQL admite
el indice funcional sobre esa expresion sin rodeo; era el unico de los cuatro
constructos de la referencia que MariaDB no tenia, y ese motor quedo atras en
ADR-028.
"""

import django.db.models.deletion
from django.db import migrations, models

from addons.account.models.account_move_line import AccountMoveLine


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0023_alter_accountmove_commercial_partner_and_more"),
        ("uom", "0005_alter_uom_options_alter_uom_relative_uom_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountmoveline",
            name="analytic_distribution",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Odoo analytic_distribution: {"id1,id2,...": porcentaje}.',
                null=True,
                verbose_name="Distribución analítica",
            ),
        ),
        migrations.AlterField(
            model_name="accountmoveline",
            name="product_uom_id",
            field=models.ForeignKey(
                blank=True,
                db_column="product_uom_id",
                help_text='Odoo product_uom_id ("Unit", account_move_line.py:372). La calcula compute_product_uom_id(), que save() invoca. El domain= de la fuente no tiene analogo declarativo en Django y se acota al elegir filtered_sellers.',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="move_lines",
                to="uom.uom",
                verbose_name="Unidad",
            ),
        ),
        migrations.RunSQL(
            sql=AccountMoveLine.analytic_distribution_gin_index_sql(
                'account_move_line'),
            reverse_sql=(
                'DROP INDEX IF EXISTS '
                'account_move_line_analytic_distribution_accounts_gin_index'
            ),
        ),
    ]

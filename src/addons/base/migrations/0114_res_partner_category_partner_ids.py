"""``res.partner.category.partners`` → ``partner_ids``, con la tabla y las
columnas de la fuente (``odoo19c: odoo/addons/base/models/res_partner.py:
154``), y el color al azar como ``default`` del campo (``:145-149``). El
renombre conserva las filas: Django renombra la tabla intermedia y sus
columnas en lugar de recrearlas."""
from django.db import migrations, models

import addons.base.models.res_partner
import orm.fields_relational


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0113_seed_public_user"),
    ]

    operations = [
        migrations.RenameField(
            model_name="respartnercategory",
            old_name="partners",
            new_name="partner_ids",
        ),
        migrations.AlterField(
            model_name="respartnercategory",
            name="partner_ids",
            field=orm.fields_relational.Many2manyField(
                blank=True,
                column1="category_id",
                column2="partner_id",
                db_table="res_partner_res_partner_category_rel",
                help_text="Odoo partner_ids, con column1=category_id.",
                related_name="category_ids",
                to="base.respartner",
                verbose_name="Contactos",
            ),
        ),
        migrations.AlterField(
            model_name="respartnercategory",
            name="color",
            field=models.IntegerField(
                default=addons.base.models.res_partner._get_default_color,
                help_text=(
                    "Odoo color. Un entero de 1 a 11 repartido al azar al "
                    "crear."
                ),
                verbose_name="Color",
            ),
        ),
    ]

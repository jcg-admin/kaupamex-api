"""``attribute_id`` y ``value_ids`` con los nombres de la fuente.

≙ ``product.attribute.value.attribute_id`` y
``product.template.attribute.line.attribute_id``/``value_ids``
(``odoo19c: addons/product/models/product_attribute_value.py`` y
``product_template_attribute_line.py``): sus cabeceras los nombran en
``_order``, ``_rec_name`` y ``_rec_names_search``. Las FK conservan su columna
(``no-op``); la tabla del Many2many cambia de nombre con su campo y conserva
las filas; las dos restricciones únicas se rehacen sobre las mismas columnas.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0025_source_fk_names"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="productattributevalue",
            name="unique_attribute_value_name",
        ),
        migrations.RemoveConstraint(
            model_name="producttemplateattributeline",
            name="unique_template_attribute",
        ),
        migrations.AlterField(
            model_name="productattributevalue",
            name="attribute",
            field=models.ForeignKey(
                db_column="attribute_id",
                help_text="Atributo (Odoo attribute_id).",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="values",
                to="product.productattribute",
            ),
        ),
        migrations.RenameField(
            model_name="productattributevalue",
            old_name="attribute",
            new_name="attribute_id",
        ),
        migrations.AlterField(
            model_name="producttemplateattributeline",
            name="attribute",
            field=models.ForeignKey(
                db_column="attribute_id",
                help_text="Atributo (Odoo attribute_id).",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="template_lines",
                to="product.productattribute",
            ),
        ),
        migrations.RenameField(
            model_name="producttemplateattributeline",
            old_name="attribute",
            new_name="attribute_id",
        ),
        migrations.RenameField(
            model_name="producttemplateattributeline",
            old_name="values",
            new_name="value_ids",
        ),
        migrations.AddConstraint(
            model_name="productattributevalue",
            constraint=models.UniqueConstraint(
                fields=("attribute_id", "name"),
                name="unique_attribute_value_name"
            ),
        ),
        migrations.AddConstraint(
            model_name="producttemplateattributeline",
            constraint=models.UniqueConstraint(
                fields=("product_tmpl", "attribute_id"),
                name="unique_template_attribute",
            ),
        ),
    ]

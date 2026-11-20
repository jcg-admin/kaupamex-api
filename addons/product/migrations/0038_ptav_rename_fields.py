"""Renombra los enlaces de ``product.template.attribute.value``.

Nombres de la fuente (``odoo19c: addons/product/models/
product_template_attribute_value.py:27-33``). ``RenameField`` y no
``RemoveField``/``AddField``, que borraría las filas; la restricción única
se retira antes y la vuelve a crear ``0039`` sobre los nombres nuevos.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0037_document_ir_attachment_id"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="producttemplateattributevalue",
            name="unique_template_attribute_value",
        ),
        migrations.RenameField(
            model_name="producttemplateattributevalue",
            old_name="line",
            new_name="attribute_line_id",
        ),
        migrations.RenameField(
            model_name="producttemplateattributevalue",
            old_name="attribute_value",
            new_name="product_attribute_value_id",
        ),
    ]

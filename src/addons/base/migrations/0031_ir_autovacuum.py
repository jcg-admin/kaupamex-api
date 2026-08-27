"""Registra ``ir.autovacuum`` como modelo sin tabla (H-API-752).

La referencia lo declara ``AbstractModel`` — sin tabla, pero **registrado por
nombre**, que es lo que permite a su cron apuntarlo con
``model_id ref="model_ir_autovacuum"``
(``odoo19c: odoo/addons/base/data/ir_cron_data.xml:5``).

Aquí el equivalente declarado es ``Meta.managed = False``
(``atributos-de-clase-de-modelo.md``, fila de ``_auto``): Django lo registra
—``apps.get_model('base.IrAutovacuum')`` resuelve— y no emite DDL. Por eso
esta migración es de **estado**, no de esquema: no crea ``ir_autovacuum``.

Antes de esto la clase era plana, y el runner del cron —que resuelve su
objetivo con ``apps.get_model``— no podía alcanzarla: sembrar el job habría
fallado con ``LookupError`` en la corrida, no al desplegar.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0030_rescompany_account_peppol_contact_email_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="IrAutovacuum",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
            ],
            options={
                "verbose_name": "Barrido automático",
                "verbose_name_plural": "Barridos automáticos",
                "db_table": "ir_autovacuum",
                "managed": False,
            },
        ),
    ]

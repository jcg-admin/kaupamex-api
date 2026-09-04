"""El ``so_line`` que ``sale`` cuelga sobre la linea analitica (tarea #976).

La referencia lo declara en ``odoo19c: sale/models/analytic.py:6-9`` como una
extension de ``account.analytic.line``. Aqui la columna vive en la tabla de
``analytic`` —el autodetector atribuye la migracion al ``app_label`` del
**modelo**, no al del addon que cuelga el campo— igual que las cuatro que
``sale_timesheet`` aporto en ``0004``.

Tres operaciones, y cada una es un atributo del campo con forma de DDL:

- ``AddField so_line`` ≙ ``comodel_name='sale.order.line'`` +
  ``string='Sales Order Item'``.
- ``AddIndex analytic_line_so_line_nn`` ≙ ``index='btree_not_null'``
  (``:9``), que en 19 pide un btree **parcial**: la mayoria de los apuntes
  analiticos no nace de una venta, y un indice completo pagaria por todas esas
  filas nulas. ``db_index=True`` daria el btree entero, que es otro indice.
  Mismo precedente que ``website_sale/migrations/0003`` con
  ``website_sale_salesteam_nn``.
- ``AlterField business_domain`` ≙ ``selection_add=[('sale_order', 'Sale
  Order')]`` (``:12-20``). No es columna nueva: la columna ya existe y lo que
  cambia es su vocabulario, que Django materializa como ``AlterField``.

Lo que ``AddField`` cierra es un bloqueo raiz declarado: ``0004`` dice verbatim
*"so_line no existe en este arbol"* al portar el ``order`` de
``sale_timesheet``, que la fuente define como ``related=so_line.order_id``.
Ese ``related`` se puede reconectar ahora; lo lleva la tarea #977.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analytic", "0005_alter_accountanalyticplan_default_applicability"),
        ("sale", "0007_seed_sale_security"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountanalyticline",
            name="so_line",
            field=models.ForeignKey(
                blank=True,
                help_text='Odoo so_line ("Sales Order Item"). Acotado a las líneas con qty_delivered_method=analytic; ver SO_LINE_DOMAIN. El índice parcial que la fuente pide con index=btree_not_null lo declara la migración de analytic.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="analytic_lines",
                to="sale.saleorderline",
                verbose_name="Línea de pedido de venta",
            ),
        ),
        migrations.AddIndex(
            model_name="accountanalyticline",
            index=models.Index(
                condition=models.Q(("so_line__isnull", False)),
                fields=["so_line"],
                name="analytic_line_so_line_nn",
            ),
        ),
        migrations.AlterField(
            model_name="accountanalyticapplicability",
            name="business_domain",
            field=models.CharField(
                choices=[
                    ("general", "Miscelánea"),
                    ("invoice", "Factura de cliente"),
                    ("bill", "Factura de proveedor"),
                    ("timesheet", "Hoja de horas"),
                    ("sale_order", "Pedido de venta"),
                ],
                help_text="Odoo business_domain; único valor que declara la raíz analytic. Otros addons amplían el vocabulario con extend_model(selection_add=…) ≙ selection_add: account suma invoice y bill, sale suma sale_order.",
                max_length=32,
                verbose_name="Dominio de negocio",
            ),
        ),
    ]

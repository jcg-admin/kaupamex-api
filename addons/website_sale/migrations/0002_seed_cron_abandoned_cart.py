"""Siembra el cron de recuperación de carrito — equivalente de ``ir_cron_data.xml``.

La referencia declara ``ir_cron_send_availability_email`` en el ``data/`` del
addon (``odoo19c: website_sale/data/ir_cron_data.xml:3-9``,
``odoo-tools@622ddc2a``): cada hora, ``model._send_abandoned_cart_email()``
sobre ``model_website``. Aquí ese XML es esta data-migration, igual que
``mail/migrations/0004_seed_cron_email_queue.py``.

Depende de ``base`` porque las dos filas que crea —``ir.actions.server`` e
``ir.cron``— viven ahí, y de ``0001`` porque el ``model_name`` que la acción
guarda apunta a ``WebsiteSaleSettings``, que ``0001`` crea.

El nombre del cron de la fuente dice *availability* y su cuerpo envía el correo
de carrito abandonado: el identificador quedó de un uso anterior. Aquí el
nombre describe lo que hace, y la divergencia se declara para que nadie la lea
como un porte incompleto.

Idempotente: un segundo pase no duplica ni pisa el intervalo que el operador
haya ajustado, que es lo que ``noupdate="1"`` garantiza en el XML original.
"""
from django.db import migrations

from addons.base.data import sembrar_cron
from addons.website_sale.models.website import CRON_SEND_ABANDONED_CART_EMAIL


def sembrar(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias,
                 CRON_SEND_ABANDONED_CART_EMAIL)


class Migration(migrations.Migration):

    dependencies = [
        ('website_sale', '0001_initial'),
        ('base', '0008_alter_iractionsactions_path_and_more'),
    ]

    operations = [
        migrations.RunPython(sembrar, migrations.RunPython.noop),
    ]

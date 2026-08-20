"""Retira el cron propio de la purga: ahora lo recoge ``ir.autovacuum``.

``0002`` sembró un job dedicado porque el método de purga era público y no
tenía otro llamador. Con H-API-747 cerrado, ``IrLogging._purge_expired`` lleva
``@api.autovacuum`` y el colector lo invoca desde el único cron del barrido
(``base.0032``), que es la forma de la referencia: un método de recolección se
marca y no se le da job propio
(``odoo19c: odoo/addons/base/data/ir_cron_data.xml:3``).

Dejar los dos vivos no sería redundancia inocua: el job viejo apunta a
``purge_expired``, nombre que dejó de existir al portarse el guion bajo
(``porte-completo-no-parcial.md``, H-API-581). Una fila que nombra un método
inexistente es un job que parece configurado y falla **en la corrida**, no al
desplegar — exactamente lo que ``test_ir_cron_seed`` existe para atrapar.

**Idempotente y reversible.** Sin la fila no hace nada; al revertir la vuelve a
sembrar con el spec congelado de ``0002``.
"""
from django.db import migrations

from addons.base.data import sembrar_cron

MODELO = 'base.IrLogging'
METODO = 'purge_expired'

# El spec de la reversa, congelado igual que en ``0002``. Se repite en vez de
# importarse porque un módulo de migración cuyo nombre empieza con dígito no es
# un identificador de Python: importarlo exigiría ``importlib``, y la copia
# literal es más barata y más fiel a lo que una data-migration debe ser — un
# hecho fechado, no una lectura de código vivo.
CRON_PURGE_LOGS = {
    'name': 'Observability: purgar logs por retencion',
    'model_name': MODELO,
    'method_name': METODO,
    'interval_number': 1,
    'interval_type': 'days',
    'priority': 8,
}


def retirar(apps, schema_editor):
    """Borra el par acción + cron. El cron primero: su FK apunta a la acción."""
    alias = schema_editor.connection.alias
    IrActionsServer = apps.get_model('base', 'IrActionsServer')
    IrCron = apps.get_model('base', 'IrCron')

    accion = IrActionsServer.objects.using(alias).filter(
        model_name=MODELO, method_name=METODO).first()
    if accion is None:
        return
    IrCron.objects.using(alias).filter(ir_actions_server=accion).delete()
    accion.delete()


def resembrar(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias, CRON_PURGE_LOGS)


class Migration(migrations.Migration):

    dependencies = [
        ('observability', '0003_dissolve_request_log'),
        ('base', '0032_seed_cron_autovacuum'),
    ]

    operations = [
        migrations.RunPython(retirar, resembrar),
    ]

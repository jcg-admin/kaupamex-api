"""Retira ``RequestLog`` y repunta el cron de retención (DEC-AF-11).

El ejecutor partió el modelo en sus dos mitades: la de **error**
(``correlation_id``, ``path``, ``exception_class``, ``error_detail``) se funde
en ``ir.logging``, y la de **acceso** (``method``, ``status_code``,
``duration_ms``, ``ip``, ``user_agent``) es trabajo del ``access_log`` del
proxy inverso, que ya la escribe. Una fila por petición en la base de la
aplicación duplicaba lo que Apache guarda por diseño.

Dos operaciones, en este orden:

1. **Repuntar el cron.** ``0002`` sembró la acción con
   ``model_name='observability.RequestLog'`` porque el método de purga vivía
   ahí y cubría **los dos** modelos. Hoy ``purge_expired`` es de
   ``base.IrLogging`` — el único sujeto que queda. Sin este repunte el runner
   resolvería ``getattr(apps.get_model('observability', 'RequestLog'), ...)``
   sobre un modelo que la operación 2 acaba de borrar.
2. **Borrar la tabla.** ``observability_requestlog`` no tiene ninguna FK
   entrante (medido: 0 referencias al modelo fuera de sus propios archivos),
   así que el ``DROP`` no arrastra nada.

**Idempotente en las dos direcciones que importan.** Una base que ya corrió
``0002`` tiene la fila vieja y se repunta; una base **nueva** la crea ya
apuntando a ``base.IrLogging`` —``data/__init__.py`` lleva el valor nuevo— y
el paso 1 no encuentra nada que hacer. Si por un pase mixto existieran las
dos, se conserva la nueva y se retira el par viejo (acción + cron), que es lo
que ``get_or_create`` habría producido con la clave natural
``(model_name, method_name)``.
"""
from django.db import migrations

VIEJO = 'observability.RequestLog'
NUEVO = 'base.IrLogging'
METODO = 'purge_expired'


def _repuntar(apps, alias, desde, hacia):
    """Mueve la acción de purga de ``desde`` a ``hacia``. Devuelve qué hizo."""
    IrActionsServer = apps.get_model('base', 'IrActionsServer')
    IrCron = apps.get_model('base', 'IrCron')

    acciones = IrActionsServer.objects.using(alias)
    vieja = acciones.filter(model_name=desde, method_name=METODO).first()
    if vieja is None:
        return 'sin fila que repuntar'

    if acciones.filter(model_name=hacia, method_name=METODO).exists():
        # Pase mixto: la nueva ya existe. Se retira el par viejo entero — el
        # cron primero, porque la FK apunta a la accion.
        IrCron.objects.using(alias).filter(ir_actions_server=vieja).delete()
        vieja.delete()
        return 'par viejo retirado (la fila nueva ya existia)'

    vieja.model_name = hacia
    vieja.save(using=alias)
    return 'repuntada'


def repuntar_a_ir_logging(apps, schema_editor):
    _repuntar(apps, schema_editor.connection.alias, VIEJO, NUEVO)


def repuntar_a_request_log(apps, schema_editor):
    _repuntar(apps, schema_editor.connection.alias, NUEVO, VIEJO)


class Migration(migrations.Migration):

    dependencies = [
        ('observability', '0002_seed_cron_purge_logs'),
    ]

    operations = [
        migrations.RunPython(repuntar_a_ir_logging, repuntar_a_request_log),
        migrations.DeleteModel(name='RequestLog'),
    ]

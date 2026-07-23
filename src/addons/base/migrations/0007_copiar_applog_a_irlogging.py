# Migración de datos manual (DEC-08 slice 2, adoptar-arquitectura-server-service-odoo).
#
# Copia NO destructiva de core.AppLog -> base.IrLogging (ver mapeo de campos
# en addons/base/models/ir_logging_log.py). No borra AppLog ni su tabla; eso
# lo hace la migración de esquema separada core/migrations/0002_eliminar_applog.py,
# que depende de ESTA migración para garantizar que los datos ya están
# copiados antes de eliminar el modelo origen.
#
# PK preservada (IrLogging.id = AppLog.id) a propósito: permite que el
# `reverse_code` (best-effort, ver docstring de la función) identifique
# exactamente qué filas copió esta migración.
from django.db import migrations


def _desactivar_auto_now(model):
    """Evita que created_at/updated_at se sobreescriban con timezone.now()
    durante bulk_create (Field.pre_save aplica auto_now/auto_now_add incluso
    en bulk_create). Solo afecta esta clase histórica dinámica de la
    migración, no el modelo real de la app."""
    for field in model._meta.local_fields:
        if field.name == 'created_at':
            field.auto_now_add = False
        elif field.name == 'updated_at':
            field.auto_now = False


def copiar_applog_a_irlogging(apps, schema_editor):
    AppLog = apps.get_model('core', 'AppLog')
    IrLogging = apps.get_model('base', 'IrLogging')
    if not AppLog.objects.exists():
        return
    _desactivar_auto_now(IrLogging)

    filas = [
        IrLogging(
            id=row.id,
            name=row.logger_name,
            type=IrLogging._meta.get_field('type').default,  # 'server'
            dbname='',
            level=row.level,
            message=row.msg,
            # path/func/line: AppLog no capturaba call-site; queda vacío para
            # filas históricas (documentado en ir_logging_log.py). Las filas
            # nuevas, escritas por el DatabaseLogHandler actualizado, sí lo
            # populan.
            path='',
            func='',
            line='',
            correlation_id=row.correlation_id,
            trace=row.trace,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in AppLog.objects.all().iterator()
    ]
    IrLogging.objects.bulk_create(filas, batch_size=500)


def revertir_copia(apps, schema_editor):
    """Best-effort: borra de IrLogging las filas cuyo id todavía exista en
    AppLog en el momento de revertir. No es una reversión perfecta — si ya
    se revirtió la migración de esquema que elimina AppLog (core 0002), la
    tabla AppLog ya fue recreada vacía por esa reversión y esta función no
    tiene con qué comparar (ver discusión en el docstring del módulo)."""
    AppLog = apps.get_model('core', 'AppLog')
    IrLogging = apps.get_model('base', 'IrLogging')
    ids = list(AppLog.objects.values_list('id', flat=True))
    if ids:
        IrLogging.objects.filter(pk__in=ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0006_irlogging'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(copiar_applog_a_irlogging, revertir_copia),
    ]

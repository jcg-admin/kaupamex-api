# Migración de datos manual (DEC-08/DEC-12 slice 3, adoptar-arquitectura-server-service-odoo).
#
# Copia NO destructiva de core.RequestLog -> observability.RequestLog (mismos
# campos; RequestLog no cambia de forma, solo de addon/app_label). No borra
# RequestLog de core ni su tabla; eso lo hace la migración de esquema separada
# core/migrations/0003_eliminar_requestlog.py, que depende de ESTA migración
# para garantizar que los datos ya están copiados antes de eliminar el modelo
# origen.
#
# PK preservada (observability.RequestLog.id = core.RequestLog.id) a propósito:
# permite que el `reverse_code` (best-effort, ver docstring de la función)
# identifique exactamente qué filas copió esta migración. La FK `user_id` se
# copia tal cual (best-effort, ver instrucción del slice): no se valida contra
# el modelo de usuario en la migración de datos.
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


def copiar_requestlog_a_observability(apps, schema_editor):
    CoreRequestLog = apps.get_model('core', 'RequestLog')
    ObsRequestLog = apps.get_model('observability', 'RequestLog')
    if not CoreRequestLog.objects.exists():
        return
    _desactivar_auto_now(ObsRequestLog)

    filas = [
        ObsRequestLog(
            id=row.id,
            correlation_id=row.correlation_id,
            method=row.method,
            path=row.path,
            view_name=row.view_name,
            user_id=row.user_id,
            status_code=row.status_code,
            duration_ms=row.duration_ms,
            ip=row.ip,
            user_agent=row.user_agent,
            exception_class=row.exception_class,
            error_detail=row.error_detail,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in CoreRequestLog.objects.all().iterator()
    ]
    ObsRequestLog.objects.bulk_create(filas, batch_size=500)


def revertir_copia(apps, schema_editor):
    """Best-effort: borra de observability.RequestLog las filas cuyo id
    todavía exista en core.RequestLog en el momento de revertir. No es una
    reversión perfecta — si ya se revirtió la migración de esquema que
    elimina core.RequestLog (core 0003), esa tabla ya fue recreada vacía por
    esa reversión y esta función no tiene con qué comparar (mismo caso ya
    documentado en base/0007_copiar_applog_a_irlogging.py)."""
    CoreRequestLog = apps.get_model('core', 'RequestLog')
    ObsRequestLog = apps.get_model('observability', 'RequestLog')
    ids = list(CoreRequestLog.objects.values_list('id', flat=True))
    if ids:
        ObsRequestLog.objects.filter(pk__in=ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('observability', '0001_initial'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(copiar_requestlog_a_observability, revertir_copia),
    ]

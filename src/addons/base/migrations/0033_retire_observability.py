"""Retira la tabla de ``BusinessEvent`` y el rastro del addon ``observability``.

El addon se retiró entero (decisión del ejecutor 2026-08-20, tarea #621). Su
último modelo vivo, ``BusinessEvent``, tenía **un** emisor
(``ORDER_CANCELLED``) y **cero** lectores, y ese único hecho ya lo registra el
chatter por duplicado: ``sale/services.py`` (``track_sale_state``) y
``sale/models/sale_order.py`` (``action_cancel`` → ``_track_state``) escriben
el cambio de estado y el motivo en ``mail.message`` / ``mail.tracking.value``.
Ver :ref:`h-api-754`.

**Por qué esta migración vive en ``base`` y no en ``observability``.** El
precedente de la casa —``observability.0003``, que disolvió ``RequestLog``—
pudo usar ``DeleteModel`` dentro del propio addon porque el addon seguía vivo.
Aquí el addon **desaparece**: retirado de ``addons/``, sus migraciones ya no se
cargan nunca y un ``DeleteModel`` ahí dentro no se ejecutaría jamás. La
limpieza tiene que emitirla un addon **superviviente**, y ``base`` es el que
todos declaran.

**Irreversible por construcción.** La tabla es append-only y la referencia no
tiene contraparte que reconstruir: el rastro de negocio vive en el chatter. El
reverso es un no-op declarado, no un olvido.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0032_seed_cron_autovacuum"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS observability_business_event CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Sin esto, ``django_migrations`` conserva cuatro filas de un app_label
        # que ya no existe: ruido permanente en `showmigrations` y en cualquier
        # auditoría del estado de esquema.
        migrations.RunSQL(
            sql="DELETE FROM django_migrations WHERE app = 'observability';",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

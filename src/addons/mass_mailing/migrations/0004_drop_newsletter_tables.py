"""Retiro del addon ``newsletter`` (paso 3 de la disolución).

Los datos ya se copiaron a ``mass_mailing`` (``0003``) y el addon salió de
``INSTALLED_APPS``; sus tablas quedan huérfanas. Esta migración las elimina de
forma idempotente (``DROP TABLE IF EXISTS``). En instalaciones nuevas —donde el
addon nunca existió— es un no-op. Reversible como no-op (no se recrean tablas de
un addon retirado; el estado fiel vive en ``mailing_contact``/``mailing_mailing``).
"""
from django.db import migrations

_DROP = (
    'DROP TABLE IF EXISTS newsletter_subscriber;\n'
    'DROP TABLE IF EXISTS newsletter_campaign;'
)


class Migration(migrations.Migration):

    dependencies = [
        ('mass_mailing', '0003_migrate_newsletter_data'),
    ]

    operations = [
        migrations.RunSQL(_DROP, reverse_sql=migrations.RunSQL.noop),
    ]

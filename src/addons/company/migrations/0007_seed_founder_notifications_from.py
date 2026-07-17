"""Siembra el remitente transaccional L1 de PracticaYoruba (founder tenant)
como su propio ``CompanySetting`` — SOL-090 follow-up #199.

Cierra el barrido L0/L1 (DEC-KX-05): ``DEFAULT_FROM_EMAIL =
'noreply@practicayoruba.com'`` en ``config.settings.base`` era la config
**L1 correcta del tenant founder** (el remitente no-reply de sus correos
transaccionales: auth, órdenes, envíos, devoluciones, soporte), NO un default
stale ni un valor de plataforma. Migrarla es **sembrarla como fila de
PracticaYoruba** (este archivo), igual que ``0006`` hizo con contacto/
newsletter — no reemplazarla por un valor de Kaupamex.

El ``DEFAULT_FROM_EMAIL`` que queda en ``base.py`` pasa a ser el fallback
**neutral de plataforma** (``noreply@kaupamex.com``, env-overridable): lo usa
Django implícitamente y el alertamiento de backups (infra L0, sin dimensión de
empresa). Los consumidores transaccionales per-tenant
(``addons.notifications.emails``, ``addons.users.tokens_email``) leen
``CompanySetting.get_setting('notifications.from_email', <fallback neutral>)``
bajo la empresa resuelta (ambiente para notificaciones autenticadas;
``company=user.company_id`` explícito para los correos de auth pre-login).

Mismo gotcha de router que ``0006`` (H-API-091-07): ``company_id=founder.pk``
escalar, NO ``company=founder`` instancia.
"""
from django.db import migrations

from addons.company.models import FOUNDER_COMPANY_CODE

NOTIFICATIONS_FROM_KEY = 'notifications.from_email'
FOUNDER_NOTIFICATIONS_FROM = 'noreply@practicayoruba.com'


def seed_founder_notifications_from(apps, schema_editor):
    Company = apps.get_model('company', 'Company')
    CompanySetting = apps.get_model('company', 'CompanySetting')
    db = schema_editor.connection.alias
    founder, _ = Company.objects.using(db).get_or_create(
        code=FOUNDER_COMPANY_CODE,
        defaults={'name': 'PracticaYoruba', 'status': 'active'},
    )
    CompanySetting.objects.using(db).get_or_create(
        company_id=founder.pk, key=NOTIFICATIONS_FROM_KEY,
        defaults={'value': FOUNDER_NOTIFICATIONS_FROM},
    )


def unseed_founder_notifications_from(apps, schema_editor):
    Company = apps.get_model('company', 'Company')
    CompanySetting = apps.get_model('company', 'CompanySetting')
    db = schema_editor.connection.alias
    if not Company.objects.using(db).filter(code=FOUNDER_COMPANY_CODE).exists():
        return
    founder = Company.objects.using(db).get(code=FOUNDER_COMPANY_CODE)
    CompanySetting.objects.using(db).filter(
        company=founder, key=NOTIFICATIONS_FROM_KEY,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0006_seed_founder_settings'),
    ]

    operations = [
        migrations.RunPython(
            seed_founder_notifications_from, unseed_founder_notifications_from,
        ),
    ]

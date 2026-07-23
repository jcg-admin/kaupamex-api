"""Siembra los valores L1 originales de PracticaYoruba (founder tenant) como
sus propios ``CompanySetting`` — SOL-090 slice 3.

Corrección de diseño mid-flight (clarificación del ejecutor, mismo turno):
PracticaYoruba es un **tenant L1** (la founder company,
``FOUNDER_COMPANY_CODE``), NO L0 — Kaupamex es L0 (operador de plataforma).
``hola@practicayoruba.com`` / ``newsletter@practicayoruba.com`` NO eran un
default stale a eliminar — eran la config **L1 correcta de ese tenant**,
mal ubicada como ``default=`` global en ``config.settings.base``. Migrarlas
es **sembrarlas como filas de PracticaYoruba** (este archivo), no
reemplazarlas por un valor de Kaupamex.

Contraste con L2 (slice 2, ``addons.base`` migración ``0003``):
``backup.alert_email`` → ``admin@kaupamex.com`` sigue siendo correcto ahí
porque el alertamiento de backups es infra **L0** (plataforma, sin
dimensión de empresa). Contacto/newsletter SÍ son **per-tenant (L1)** — se
quedan con PracticaYoruba; el fallback del consumidor cuando no hay empresa
activa o no hay fila (``addons.contact.views``, ``addons.newsletter.views``)
es **neutral** (nivel Kaupamex, ``*@kaupamex.com``), NO específico de
PracticaYoruba — PracticaYoruba es solo un tenant entre potencialmente
varios.
"""
from django.db import migrations

from addons.company.models import FOUNDER_COMPANY_CODE, FOUNDER_L1_SETTINGS


def seed_founder_settings(apps, schema_editor):
    Company = apps.get_model('company', 'Company')
    CompanySetting = apps.get_model('company', 'CompanySetting')
    db = schema_editor.connection.alias
    # get_or_create idéntico al de Company.get_founder() (no se puede llamar
    # el classmethod real sobre el modelo histórico de la migración).
    founder, _ = Company.objects.using(db).get_or_create(
        code=FOUNDER_COMPANY_CODE,
        defaults={'name': 'PracticaYoruba', 'status': 'active'},
    )
    for key, value in FOUNDER_L1_SETTINGS.items():
        # ``company_id=founder.pk`` (escalar), NO ``company=founder``
        # (instancia): asignar una instancia a un campo FK al construir el
        # modelo dispara el ``ForwardManyToOneDescriptor.__set__`` de
        # Django, que fija ``instance._state.db`` llamando al
        # ``CompanyDatabaseRouter`` — ANTES de que ``.using(db)`` aplique, y
        # sin ``company_scope`` activo revienta con ``CompanyContextRequired``
        # bajo N>1 (mismo gotcha documentado como H-API-091-07 en
        # ``tests/integration/platform/test_multidb_isolation.py``, ahí para
        # ``orders/migrations/0002_seed_shipping_zones.py``). Un campo
        # escalar (``company_id``) no pasa por ese descriptor.
        CompanySetting.objects.using(db).get_or_create(
            company_id=founder.pk, key=key, defaults={'value': value},
        )


def unseed_founder_settings(apps, schema_editor):
    Company = apps.get_model('company', 'Company')
    CompanySetting = apps.get_model('company', 'CompanySetting')
    db = schema_editor.connection.alias
    if not Company.objects.using(db).filter(code=FOUNDER_COMPANY_CODE).exists():
        # Nunca se sembró (la founder company no existía en esta BD) — nada
        # que revertir.
        return
    founder = Company.objects.using(db).get(code=FOUNDER_COMPANY_CODE)
    CompanySetting.objects.using(db).filter(
        company=founder, key__in=list(FOUNDER_L1_SETTINGS),
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0005_companysetting'),
    ]

    operations = [
        migrations.RunPython(seed_founder_settings, unseed_founder_settings),
    ]

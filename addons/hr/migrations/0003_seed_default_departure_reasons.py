"""Siembra los tres motivos de baja maestros — ≙ ``hr/data/hr_departure_reason_data.xml``.

Sin ellos ``HrDepartureReason._get_default_departure_reasons()`` no resuelve
nada y su guarda de borrado (``delete()``) queda sin efecto — mismo patrón
que ``account/migrations/0012_seed_account_tags.py`` resuelve para las tres
etiquetas maestras de ``account.account.tag`` en este mismo árbol.

``base`` entra en las dependencias porque la fila del identificador externo
vive en ``ir.model.data``, que es de ese addon.
"""
from django.db import migrations

#: ``(xmlid sin módulo, nombre)`` — ≙ los tres ``self.env.ref(...)`` de
#: ``_get_default_departure_reasons`` (``odoo19c: hr_departure_reason.py:19-22``).
DEFAULT_DEPARTURE_REASONS = (
    ('departure_fired', 'Despedido'),
    ('departure_resigned', 'Renunció'),
    ('departure_retired', 'Jubilado'),
)


def seed(apps, schema_editor):
    """Crea (o respeta) los tres motivos y sus identificadores externos.

    Escribe sobre los modelos **históricos** (``apps.get_model``) porque
    corre dentro de una migración. Idempotente por ``(module, name)`` de
    ``ir.model.data`` — un segundo pase repunta la fila en vez de duplicarla.
    """
    alias = schema_editor.connection.alias
    HrDepartureReason = apps.get_model('hr', 'HrDepartureReason')
    IrModelData = apps.get_model('base', 'IrModelData')
    label = HrDepartureReason._meta.label

    for sequence, (name, reason_label) in enumerate(DEFAULT_DEPARTURE_REASONS, start=1):
        row = IrModelData.objects.using(alias).filter(
            module='hr', name=name).first()
        existing = None
        if row is not None:
            existing = HrDepartureReason.objects.using(alias).filter(
                pk=row.res_id).first()
        if existing is None:
            existing = HrDepartureReason.objects.using(alias).filter(
                name=reason_label).first()
        if existing is None:
            existing = HrDepartureReason.objects.using(alias).create(
                name=reason_label, sequence=sequence * 10)
        IrModelData.objects.using(alias).update_or_create(
            module='hr', name=name,
            defaults={'model': label, 'res_id': existing.pk, 'noupdate': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0002_hrcontracttype_hrdeparturereason_hremployeecategory_and_more'),
        ('base', '0024_respartner_check_name'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]

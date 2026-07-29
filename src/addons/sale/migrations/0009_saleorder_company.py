"""Añade FK ``company`` a ``SaleOrder`` + backfill L3 (SOL-085 S3).

Rollout de scoping por empresa (L3): la columna nace nullable y las filas
heredadas se asignan a la founder company (PracticaYoruba, el L1 de ejemplo)
en el mismo pase. Espeja el patrón multi-DB seguro de
``company/0006_seed_founder_settings``: se usa ``company_id=founder.pk``
(escalar) y ``.using(db)``, NUNCA ``company=founder`` (instancia) — asignar
una instancia a un FK dispara el ``ForwardManyToOneDescriptor`` de Django, que
fija ``_state.db`` vía el ``CompanyDatabaseRouter`` antes de que ``.using(db)``
aplique y revienta con ``CompanyContextRequired`` bajo N>1 (H-API-091-07).
"""
import django.db.models.deletion
from django.db import migrations, models

from addons.company.models import FOUNDER_COMPANY_CODE


def backfill_company(apps, schema_editor):
    Company = apps.get_model("company", "Company")
    SaleOrder = apps.get_model("sale", "SaleOrder")
    db = schema_editor.connection.alias
    # get_or_create idéntico a Company.get_founder() (no se puede llamar el
    # classmethod real sobre el modelo histórico de la migración).
    founder, _ = Company.objects.using(db).get_or_create(
        code=FOUNDER_COMPANY_CODE,
        defaults={"name": "PracticaYoruba", "status": "active"},
    )
    SaleOrder.objects.using(db).filter(company__isnull=True).update(
        company_id=founder.pk,
    )


def unbackfill_company(apps, schema_editor):
    # No-op: al revertir se elimina la columna (operación siguiente en reverse),
    # el dato del backfill desaparece con ella. Nada que deshacer por separado.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("company", "0009_subscriptionbillingrun_subscriptioninvoice"),
        ("sale", "0008_port_draft_orders_to_sale"),
    ]

    operations = [
        migrations.AddField(
            model_name="saleorder",
            name="company",
            field=models.ForeignKey(
                blank=True,
                help_text="Empresa dueña de la orden (Odoo company_id). NULL pre-backfill.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sale_orders",
                to="company.company",
            ),
        ),
        migrations.RunPython(backfill_company, unbackfill_company),
    ]

"""El equipo de venta del sitio — ≙ ``website.salesteam_id`` (tarea #568).

La referencia declara el campo en
``odoo19c: website_sale/models/website.py:63-69`` como columna de ``website``.
Aquí vive en ``website_sale_settings`` por la restricción de plataforma que
``models/website.py`` declara como su D-1: el autodetector atribuye la
migración al ``app_label`` del **modelo**, así que una columna sobre ``website``
obligaría a escribir en ``addons/website/migrations/``, que es de otro addon.

Dos operaciones, que son los dos atributos del campo con forma de DDL:

- ``AddField salesteam`` ≙ ``comodel_name='crm.team'`` + ``ondelete='set
  null'`` + ``default=_default_salesteam_id``.
- ``AddIndex website_sale_salesteam_nn`` ≙ ``index='btree_not_null'``
  (``:66``), que en 19 pide un btree **parcial**: la mayoría de los sitios no
  fija equipo, y un índice completo pagaría por todas esas filas nulas.

``crm_team.py`` de este addon **no** aporta ninguna operación aquí: sus dos
campos son ``compute`` sin ``store`` en la fuente (``odoo19c:
website_sale/models/crm_team.py:12-17``) y aquí ``fields.NonStored``, que por
construcción no genera columna.

Nota sobre las dependencias
============================

El autodetector propuso además ``("website", "0009_websiteviewinfo")`` — una
migración **sin publicar**, de trabajo en vuelo en otro addon. Se repinta a lo
que esta migración de verdad necesita, por el mismo criterio que ``0001``
dejó escrito: *"se ancla a la última publicada … depender de una migración sin
publicar ataría este addon a un nombre que todavía puede cambiar"*.

Lo que necesita son dos cosas: la tabla que altera (``website_sale.0002``) y el
modelo al que apunta la FK (``sales_team.0001``). La cadena hacia ``website`` y
``mail`` ya la garantiza ``0001``, que depende de las dos.
"""
import addons.website_sale.models.website
import django.db.models.deletion
from django.db import migrations, models


def _sales_team_field(default):
    return models.ForeignKey(
        blank=True,
        default=default,
        help_text="Equipo de venta al que se atribuyen los pedidos de este sitio (Odoo website.salesteam_id).",
        null=True,
        on_delete=django.db.models.deletion.SET_NULL,
        related_name="websites",
        to="sales_team.crmteam",
        verbose_name="Equipo de venta",
    )


def _backfill_local_sales_team(apps, schema_editor):
    """Resolve only historical models and metadata in the migrated database."""
    using = schema_editor.connection.alias
    metadata = apps.get_model('base', 'IrModelData')
    teams = apps.get_model('sales_team', 'CrmTeam')
    sites = apps.get_model('website_sale', 'WebsiteSaleSettings')
    reference = metadata.objects.using(using).filter(
        module='sales_team', name='salesteam_website_sales').first()
    if reference is None or not reference.res_id:
        return
    if reference.model.casefold() != teams._meta.label.casefold():
        raise ValueError('Sales-team XMLID points to a different historical model')
    team = teams.objects.using(using).filter(pk=reference.res_id, active=True).first()
    if team is not None:
        sites.objects.using(using).filter(salesteam__isnull=True).update(salesteam=team.pk)


class Migration(migrations.Migration):

    dependencies = [
        ("sales_team", "0001_initial"),
        ("website_sale", "0002_seed_cron_abandoned_cart"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.AddField(
                model_name="websitesalesettings", name="salesteam",
                field=_sales_team_field(None),
            )],
            state_operations=[migrations.AddField(
                model_name="websitesalesettings", name="salesteam",
                field=_sales_team_field(addons.website_sale.models.website._default_salesteam_id),
            )],
        ),
        migrations.RunPython(_backfill_local_sales_team, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="websitesalesettings",
            index=models.Index(
                condition=models.Q(("salesteam__isnull", False)),
                fields=["salesteam"],
                name="website_sale_salesteam_nn",
            ),
        ),
    ]

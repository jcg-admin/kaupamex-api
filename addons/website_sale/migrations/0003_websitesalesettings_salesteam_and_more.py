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


class Migration(migrations.Migration):

    dependencies = [
        ("sales_team", "0001_initial"),
        ("website_sale", "0002_seed_cron_abandoned_cart"),
    ]

    operations = [
        migrations.AddField(
            model_name="websitesalesettings",
            name="salesteam",
            field=models.ForeignKey(
                blank=True,
                default=addons.website_sale.models.website._default_salesteam_id,
                help_text="Equipo de venta al que se atribuyen los pedidos de este sitio (Odoo website.salesteam_id).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="websites",
                to="sales_team.crmteam",
                verbose_name="Equipo de venta",
            ),
        ),
        migrations.AddIndex(
            model_name="websitesalesettings",
            index=models.Index(
                condition=models.Q(("salesteam__isnull", False)),
                fields=["salesteam"],
                name="website_sale_salesteam_nn",
            ),
        ),
    ]

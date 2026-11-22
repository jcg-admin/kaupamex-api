from django.db import migrations, models


class Migration(migrations.Migration):
    """``edi_format_ids`` se declara en el diario, sobre la tabla de siempre.

    ≙ ``odoo19c: addons/account_edi/models/account_journal.py:11-16``. El
    campo lo cuelga ``account_edi`` con ``extend_model``; su migración vive en
    la app dueña del modelo, como ``stock/0018`` para ``purchase_ids``. La
    tabla ``account_edi_format_journals`` ya existe con las mismas columnas
    (``accountjournal_id``, ``accountediformat_id``): sólo cambia el estado y
    las filas se conservan.
    """

    dependencies = [
        ("account", "0051_journal_portal_access_token"),
        ("account_edi", "0006_journal_edi_format_ids_state"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="accountjournal",
                    name="edi_format_ids",
                    field=models.ManyToManyField(
                        blank=True,
                        db_table="account_edi_format_journals",
                        help_text="Send XML/EDI invoices",
                        related_name="+",
                        to="account_edi.accountediformat",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]

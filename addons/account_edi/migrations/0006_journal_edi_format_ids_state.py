from django.db import migrations


class Migration(migrations.Migration):
    """El M2M de formatos y diarios deja de declararse en el formato.

    ≙ ``edi_format_ids`` de ``account.journal`` (``odoo19c: addons/account_edi/
    models/account_journal.py:11-16``): la fuente lo declara en el diario y el
    formato no lleva inverso. Sólo cambia el estado; la tabla
    ``account_edi_format_journals`` y sus filas se conservan, y la declaración
    nueva vive en ``account`` (``0052_accountjournal_edi_format_ids``).
    """

    dependencies = [
        ("account_edi", "0005_log_access_user_column_names"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="accountediformat",
                    name="journals",
                ),
            ],
            database_operations=[],
        ),
    ]

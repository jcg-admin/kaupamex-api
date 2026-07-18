# Mueve MenuItem a la app addons.authz_menu (SOL-094 frente B, DEC-01).
# SeparateDatabaseAndState: solo cambia el *state* (quita el modelo del app label
# authz); la tabla física ``authz_menu_item`` NO se toca (la re-declara en state
# la migración authz_menu.0001). Sin database_operations => sin DROP TABLE.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("authz", "0011_delete_reauthsession"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name="menuitem",
                    name="authz_menu__parent__8f655c_idx",
                ),
                migrations.DeleteModel(
                    name="MenuItem",
                ),
            ],
            database_operations=[],
        ),
    ]

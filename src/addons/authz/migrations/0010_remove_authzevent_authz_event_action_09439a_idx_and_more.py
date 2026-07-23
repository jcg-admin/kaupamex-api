# Mueve AuthzEvent a la app addons.authz_audit (SOL-094 frente B, DEC-01).
# SeparateDatabaseAndState: solo cambia el *state* (quita el modelo del app
# label authz); la tabla física ``authz_event`` NO se toca (la re-crea en state
# la migración authz_audit.0001). Sin database_operations => sin DROP TABLE.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("authz", "0009_accessrule_perm_create_accessrule_perm_read_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name="authzevent",
                    name="authz_event_action_09439a_idx",
                ),
                migrations.RemoveIndex(
                    model_name="authzevent",
                    name="authz_event_actor_i_bb271b_idx",
                ),
                migrations.DeleteModel(
                    name="AuthzEvent",
                ),
            ],
            database_operations=[],
        ),
    ]

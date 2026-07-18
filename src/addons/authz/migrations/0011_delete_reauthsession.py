# Mueve ReauthSession a la app addons.authz_reauth (SOL-094 frente B, DEC-01).
# SeparateDatabaseAndState: solo cambia el *state* (quita el modelo del app label
# authz); la tabla física ``authz_reauth_session`` NO se toca (la re-declara en
# state la migración authz_reauth.0001). Sin database_operations => sin DROP TABLE.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("authz", "0010_remove_authzevent_authz_event_action_09439a_idx_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="reauthsession",
                    name="uq_authz_reauth_session",
                ),
                migrations.RemoveIndex(
                    model_name="reauthsession",
                    name="authz_reaut_user_id_256fb4_idx",
                ),
                migrations.DeleteModel(
                    name="ReauthSession",
                ),
            ],
            database_operations=[],
        ),
    ]

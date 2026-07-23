# Mueve ReauthSession a la app addons.authz_reauth (SOL-094 frente B, DEC-01).
# SeparateDatabaseAndState: la tabla ``authz_reauth_session`` ya existe (creada
# por authz.0005); aqui solo se registra el modelo en el *state* de esta app. Sin
# database_operations => sin CREATE TABLE. El index (authz_reaut_user_id_256fb4_idx)
# y la constraint (uq_authz_reauth_session) conservan sus nombres fisicos.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authz", "0011_delete_reauthsession"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="ReauthSession",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "session_key",
                            models.CharField(
                                blank=True,
                                db_index=True,
                                default="",
                                help_text="Sesión Django a la que se ata la reautenticación.",
                                max_length=40,
                                verbose_name="Clave de sesión",
                            ),
                        ),
                        ("started_at", models.DateTimeField(verbose_name="Iniciada")),
                        (
                            "expires_at",
                            models.DateTimeField(db_index=True, verbose_name="Expira"),
                        ),
                        (
                            "ip_addr",
                            models.GenericIPAddressField(
                                blank=True, null=True, verbose_name="IP"
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="reauth_sessions",
                                to=settings.AUTH_USER_MODEL,
                                verbose_name="Usuario",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Sesión reautenticada",
                        "verbose_name_plural": "Sesiones reautenticadas",
                        "db_table": "authz_reauth_session",
                        "ordering": ["-started_at"],
                        "indexes": [
                            models.Index(
                                fields=["user", "session_key", "expires_at"],
                                name="authz_reaut_user_id_256fb4_idx",
                            )
                        ],
                        "constraints": [
                            models.UniqueConstraint(
                                fields=("user", "session_key"),
                                name="uq_authz_reauth_session",
                            )
                        ],
                    },
                ),
            ],
        ),
    ]

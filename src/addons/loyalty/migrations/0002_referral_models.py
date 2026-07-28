"""Adopta los modelos del programa de referidos en ``loyalty``.

State-only (``SeparateDatabaseAndState``): las tablas ``referral_referral`` y
``referral_code`` ya existen (creadas por la ex-migracion ``referral.0001``); el
programa de referidos se re-aloja en ``loyalty`` porque es la capa de referral
del framework de fidelidad de Odoo. Solo cambia el ``app_label`` de los modelos.

**H-API-21 (2026-07-28):** nació ``state-only`` porque la tabla ya existía,
creada por la ex-migración del app donante. Al plegarse ese app su migración
se eliminó del árbol y nadie quedó creando la tabla. El defecto era
**silencioso** (``migrate`` termina OK; sólo falla el ORM en runtime) y
quedaba oculto bajo ``--reuse-db``. Se restituye la creación real.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loyalty", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    state_operations = [
        migrations.CreateModel(
            name="Referral",
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
                ("code", models.CharField(db_index=True, max_length=50)),
                (
                    "status",
                    models.CharField(
                        choices=[("PENDING", "Pendiente"), ("COMPLETED", "Completado")],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "referee",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referral_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "referrer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referrals_made",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reward_voucher",
                    models.ForeignKey(
                        blank=True,
                        help_text="Voucher de recompensa emitido al referidor (Subflujo C).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="referral_rewards",
                        to="loyalty.voucher",
                    ),
                ),
            ],
            options={
                "verbose_name": "Referido",
                "db_table": "referral_referral",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ReferralCode",
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
                    "code",
                    models.CharField(
                        help_text="Formato REF-{user.id}-{6 chars}. Siempre en mayusculas.",
                        max_length=50,
                        unique=True,
                        verbose_name="Codigo referral",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referral_code",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Codigo referral",
                "db_table": "referral_code",
            },
        ),
    ]

    # H-API-21: las operaciones se aplican a la BD, no sólo al estado.
    operations = state_operations

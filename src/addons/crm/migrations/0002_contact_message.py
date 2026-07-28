"""Adopta ``ContactMessage`` en ``crm`` (state-only).

La tabla ``contact_message`` ya existe (creada por la ex-migración
``contact.0001``); el mensaje del formulario de contacto se re-aloja en ``crm``
—hogar fiel de las capturas del formulario de contacto (Odoo ``website_crm`` →
``crm.lead``)—. Solo cambia el ``app_label``.

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
        ("crm", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    state_operations = [
        migrations.CreateModel(
            name="ContactMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False, help_text="True si la fila fue borrada via soft delete.", verbose_name="Eliminado (logico)")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Fecha de borrado logico")),
                ("name", models.CharField(max_length=120)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, default="", max_length=40)),
                ("subject", models.CharField(max_length=200)),
                ("body", models.TextField()),
                ("read", models.BooleanField(default=False)),
                ("replied", models.BooleanField(default=False)),
                ("reply_body", models.TextField(blank=True, default="")),
                ("reply_sent_at", models.DateTimeField(blank=True, null=True)),
                ("reply_sent_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="contact_replies_sent", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Mensaje de contacto",
                "verbose_name_plural": "Mensajes de contacto",
                "db_table": "contact_message",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["read"], name="contact_mes_read_d4ce31_idx"),
                    models.Index(fields=["-created_at"], name="contact_mes_created_54923f_idx"),
                ],
            },
        ),
    ]

    # H-API-21: las operaciones se aplican a la BD, no sólo al estado.
    operations = state_operations

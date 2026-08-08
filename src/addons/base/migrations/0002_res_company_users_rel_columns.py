"""Renombra las columnas de ``res_company_users_rel`` a las de la referencia.

Django autogeneraba ``rescompany_id``/``resusers_id``; la referencia declara
``cid``/``user_id`` desde ambos lados del M2M (``odoo-tools@622ddc2a``:
``odoo19c: res_company.py:68`` y ``res_users.py:247``; ``odoo18c: :54`` y
``:403``). El modelo ``through`` explícito existe sólo para fijar esos
nombres.

Se recrea la tabla en vez de renombrar columnas porque el M2M automático no
tiene modelo en el estado de migraciones: sale del árbol con ``RemoveField``
y vuelve como ``CreateModel``. Medido antes de aplicar: la tabla tenía
**0 filas** (``SELECT COUNT(*)`` sobre ``kaupamex_qa``), así que no hay
membresías que preservar — hoy nadie las escribe todavía.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="rescompany",
            name="user_ids",
        ),
        migrations.CreateModel(
            name="ResCompanyUsersRel",
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
                (
                    "cid",
                    models.ForeignKey(
                        db_column="cid",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="base.rescompany",
                        verbose_name="Compañía",
                    ),
                ),
                (
                    "user_id",
                    models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Usuario",
                    ),
                ),
            ],
            options={
                "verbose_name": "Usuario aceptado de la compañía",
                "verbose_name_plural": "Usuarios aceptados de la compañía",
                "db_table": "res_company_users_rel",
            },
        ),
        migrations.AddField(
            model_name="rescompany",
            name="user_ids",
            field=models.ManyToManyField(
                blank=True,
                related_name="company_ids",
                through="base.ResCompanyUsersRel",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Usuarios aceptados",
            ),
        ),
        migrations.AddConstraint(
            model_name="rescompanyusersrel",
            constraint=models.UniqueConstraint(
                fields=("cid", "user_id"), name="res_company_users_rel_uniq"
            ),
        ),
    ]

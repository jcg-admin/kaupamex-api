"""Admite las dos acciones de administración de la concesión.

Se emitían contra ``BusinessEvent`` con cadenas libres que no estaban en su
``ACTION_CHOICES``; su eje declarado es el de autorización. Los códigos se
acortaron para caber en ``max_length=20`` — ``ADMIN_ROLE_PERMISSIONS_CHANGED``
medía 29. Ver :ref:`h-api-753`.

``choices`` no toca el esquema en PostgreSQL: la columna sigue siendo el mismo
``varchar(20)``. La migración existe para que el estado declarado y el del
modelo no divergan (lo que ``makemigrations --check`` vigila).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authz_audit", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="authzevent",
            name="action",
            field=models.CharField(
                choices=[
                    ("DENY", "Denegación (403)"),
                    ("SENSITIVE_USE", "Uso de capacidad sensible"),
                    ("ROLE_PERMS_CHANGED", "Permisos de un rol modificados"),
                    ("USER_ROLES_SET", "Roles de un usuario reasignados"),
                ],
                db_index=True,
                max_length=20,
                verbose_name="Acción",
            ),
        ),
    ]

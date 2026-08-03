from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="HrDepartment",
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
                ("name", models.CharField(max_length=150, verbose_name="Nombre")),
                (
                    "parent_path",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=255
                    ),
                ),
                ("active", models.BooleanField(default=True, verbose_name="Activo")),
                ("note", models.TextField(blank=True, default="", verbose_name="Nota")),
                (
                    "color",
                    models.IntegerField(default=0, verbose_name="Índice de color"),
                ),
            ],
            options={
                "verbose_name": "Departamento",
                "verbose_name_plural": "Departamentos",
                "db_table": "hr_department",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="HrJob",
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
                ("name", models.CharField(max_length=150, verbose_name="Puesto")),
                (
                    "no_of_recruitment",
                    models.IntegerField(
                        default=1,
                        help_text="Número de nuevos empleados que se espera reclutar.",
                        verbose_name="Objetivo",
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", verbose_name="Descripción"
                    ),
                ),
                (
                    "requirements",
                    models.TextField(blank=True, default="", verbose_name="Requisitos"),
                ),
                ("active", models.BooleanField(default=True, verbose_name="Activo")),
            ],
            options={
                "verbose_name": "Puesto",
                "verbose_name_plural": "Puestos",
                "db_table": "hr_job",
                "ordering": ["name"],
            },
        ),
    ]

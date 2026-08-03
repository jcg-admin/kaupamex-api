import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("hr", "0001_initial"),
        ("platform", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="hrdepartment",
            name="company",
            field=models.ForeignKey(
                blank=True,
                help_text="Empresa dueña del departamento (Odoo company_id).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="hr_departments",
                to="platform.company",
                verbose_name="Empresa (tenant)",
            ),
        ),
        migrations.AddField(
            model_name="hrdepartment",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="children",
                to="hr.hrdepartment",
                verbose_name="Departamento padre",
            ),
        ),
        migrations.AddField(
            model_name="hrdepartment",
            name="subsidiary",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="departments",
                to="platform.subsidiary",
                verbose_name="Subsidiaria",
            ),
        ),
        migrations.AddField(
            model_name="hrjob",
            name="company",
            field=models.ForeignKey(
                blank=True,
                help_text="Empresa dueña del puesto (Odoo company_id).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="hr_jobs",
                to="platform.company",
                verbose_name="Empresa (tenant)",
            ),
        ),
        migrations.AddField(
            model_name="hrjob",
            name="department",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="jobs",
                to="hr.hrdepartment",
                verbose_name="Departamento",
            ),
        ),
        migrations.AddField(
            model_name="hrjob",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="recruiter_jobs",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Reclutador",
            ),
        ),
    ]

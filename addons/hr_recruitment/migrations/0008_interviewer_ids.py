"""``hr.applicant.interviewers`` → ``interviewer_ids``, con la tabla y las
columnas de la fuente (``odoo19c: hr_recruitment/models/hr_applicant.py:
125-127``). El renombre conserva las filas: Django renombra la tabla
intermedia y sus columnas en lugar de recrearlas."""
from django.conf import settings
from django.db import migrations

import orm.fields_relational


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("hr_recruitment", "0007_log_access_user_column_names"),
    ]

    operations = [
        migrations.RenameField(
            model_name="hrapplicant",
            old_name="interviewers",
            new_name="interviewer_ids",
        ),
        migrations.AlterField(
            model_name="hrapplicant",
            name="interviewer_ids",
            field=orm.fields_relational.Many2manyField(
                blank=True,
                column1='hr_applicant_id',
                column2='res_users_id',
                db_index=True,
                db_table='hr_applicant_res_users_interviewers_rel',
                related_name='interviewing_applicants',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Entrevistadores',
            ),
        ),
    ]

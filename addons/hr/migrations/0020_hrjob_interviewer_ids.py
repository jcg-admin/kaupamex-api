"""``hr.job.interviewers`` → ``interviewer_ids`` (campo que cuelga
``hr_recruitment``), con la tabla que la fuente deriva
(``odoo19c: odoo/orm/fields_relational.py:1291-1295``):
``hr_job_res_users_rel``. El renombre conserva las filas."""
from django.conf import settings
from django.db import migrations

import orm.fields_relational


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("hr", "0019_log_access_user_column_names"),
    ]

    operations = [
        migrations.RenameField(
            model_name="hrjob",
            old_name="interviewers",
            new_name="interviewer_ids",
        ),
        migrations.AlterField(
            model_name="hrjob",
            name="interviewer_ids",
            field=orm.fields_relational.Many2manyField(
                blank=True,
                column1='hr_job_id',
                column2='res_users_id',
                db_table='hr_job_res_users_rel',
                help_text=(
                    'Ven todos los candidatos del puesto y pueden '
                    'rechazarlos, sin necesitar permisos de reclutamiento.'
                ),
                related_name='interviewer_jobs',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Entrevistadores',
            ),
        ),
    ]

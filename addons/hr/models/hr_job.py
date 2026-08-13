"""``hr.job`` — catálogo de puestos (Odoo ``hr``).

Adaptación fiel de Odoo hr/models/hr_job.py (odoo-tools@622ddc2a, odoo19c:,
LGPL-3). Re-hogar de ``platform.Job`` a su familia fiel ``hr``. Ver
``analisis-porte-familia-hr`` (D-2 company_id, D-3 name/active).

Campos fieles-mínimos: sin ``hr.employee``. ``employee_ids`` /
``expected_employees`` / ``no_of_employee`` (cuelgan de ``hr.employee``) y
``contract_type_id`` (``hr.contract.type``) quedan **deferidos**. NO se porta
``allowed_user_ids`` — la propia referencia lo marca ``TODO (master): remove``.
"""
import fields
import models

from addons.base.models import TimeStampedModel
from addons.mail.models import MailThread


class HrJob(MailThread, TimeStampedModel):
    """``hr.job`` — catálogo de puestos. El departamento es opcional."""

    name = fields.Char(max_length=150, verbose_name='Puesto')  # D-3: ex title
    department = fields.Many2one(
        'hr.HrDepartment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='jobs', verbose_name='Departamento',
    )
    # D-2: FK directa a base.ResCompany (Odoo company_id), igual que HrDepartment.
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_jobs', verbose_name='Empresa (tenant)',
        help_text='Empresa dueña del puesto (Odoo company_id).',
    )
    no_of_recruitment = fields.Integer(
        default=1, verbose_name='Objetivo',
        help_text='Número de nuevos empleados que se espera reclutar.',
    )
    description = fields.Html(blank=True, default='', verbose_name='Descripción')
    requirements = fields.Text(blank=True, default='', verbose_name='Requisitos')
    user = fields.Many2one(
        'base.ResUsers', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='recruiter_jobs', verbose_name='Reclutador',
    )
    active = fields.Boolean(default=True, verbose_name='Activo')  # D-3: ex is_active

    # DEFERIDO (no stub): employee_ids, expected_employees, no_of_employee —
    # requieren hr.employee (GAP). DEFERIDO: contract_type_id — requiere
    # hr.contract.type (GAP). NO se porta allowed_user_ids (TODO-remove upstream).

    class Meta:
        db_table = 'hr_job'
        verbose_name = 'Puesto'
        verbose_name_plural = 'Puestos'
        ordering = ['name']

    def __str__(self):
        return self.name

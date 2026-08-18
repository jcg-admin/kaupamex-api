"""``hr.department`` — unidad organizativa (Odoo ``hr``).

Adaptación fiel de Odoo hr/models/hr_department.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3). Re-hogar de ``platform.Department`` (antes ``company``,
DIS-01..DIS-04) a su familia fiel ``hr``. Ver
``analisis-porte-familia-hr`` (D-2 company_id, D-3 active, D-4 helper).

Campos fieles-mínimos: sin ``hr.employee`` (GAP grande, otro NÚCLEO). Los
campos que cuelgan de ``hr.employee`` (``manager_id``, ``member_ids``,
``total_employee``) y de ``mail.activity.plan`` (``plan_ids``) quedan
**deferidos** —ausentes, no stubs— y se agregan en migración aditiva cuando
esas tablas aterricen.
"""
import fields
import models

from addons.base.models import TimeStampedModel, _reject_hierarchy_cycle
from addons.mail.models import MailThread


class HrDepartment(MailThread, TimeStampedModel):
    """``hr.department`` — unidad organizativa con sub-departamentos.

    Hereda ``MailThread`` igual que ``hr.department`` hereda ``mail.thread``
    en la referencia (``odoo19c: hr/models/hr_department.py:14``); el mixin es
    abstracto y no agrega columnas.
    """

    name = fields.Char(max_length=150, verbose_name='Nombre')
    # D-2: FK directa a base.ResCompany (Odoo company_id, res.company). El eje
    # de aislamiento por Company que usa el árbol (record rules ``ir_rule``,
    # DEC-KX-05). Opcional + SET_NULL como el resto de FKs de company del
    # proyecto (sale.order).
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_departments', verbose_name='Empresa',
        help_text='Empresa dueña del departamento (Odoo company_id).',
    )
    # ``subsidiary`` se disolvió (D-1 cerrada contra la referencia): la
    # jerarquía multi-entidad-legal es ``res.company.parent_id``/``child_ids``
    # ('Branches', ``odoo19c: res_company.py:51-52``), que ``base.ResCompany``
    # ya porta. ``hr.department`` en la referencia solo lleva ``company_id``.
    parent = fields.Many2one(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children', verbose_name='Departamento padre',
    )
    parent_path = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
    )
    active = fields.Boolean(default=True, verbose_name='Activo')  # D-3: ex is_active
    note = fields.Text(blank=True, default='', verbose_name='Nota')
    color = fields.Integer(default=0, verbose_name='Índice de color')

    # DEFERIDO (no stub): manager / member_ids — requieren hr.employee (GAP).
    # DEFERIDO: plan_ids / plans_count — requieren mail.activity.plan (GAP).
    # Se agregan en migración aditiva cuando esas tablas aterricen.

    class Meta:
        db_table = 'hr_department'
        verbose_name = 'Departamento'
        verbose_name_plural = 'Departamentos'
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        _reject_hierarchy_cycle(self, 'parent', 'DEPARTMENT_CYCLE')

    def _compute_parent_path(self):
        """Ruta materializada del ancestro, terminada en ``/``.

        Espeja el patrón a mano de ``base.ResCompany`` (no el flag
        ``_parent_store`` que la referencia da vía ORM).
        """
        if self.parent_id is None:
            return f'{self.pk}/'
        return f'{self.parent.parent_path}{self.pk}/'

    def save(self, *args, **kwargs):
        """Mantiene la ruta materializada, que en la referencia mantiene el ORM."""
        super().save(*args, **kwargs)
        path = self._compute_parent_path()
        if path != self.parent_path:
            self.parent_path = path
            super().save(update_fields=['parent_path'])

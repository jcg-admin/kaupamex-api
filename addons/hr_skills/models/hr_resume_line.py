"""``hr.resume.line`` — una línea del currículum de un empleado.

Adaptación fiel de Odoo hr_skills/models/hr_resume_line.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 15 campos + 1 constraint + 3 métodos
==================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``employee_id`` / ``name`` / ``date_start`` / ``date_end`` /
       ``duration`` / ``description`` / ``line_type_id`` / ``course_type`` /
       ``certificate_filename`` / ``certificate_file`` (``:13-33``)
     - portados verbatim
   * - ``resume_line_properties`` (``:34-37``)
     - portado (DIVERGENCIA de firma) — ``fields.Properties`` en este
       árbol es ``JSONField`` (``src/orm/fields_properties.py``) y no
       acepta el kwarg ``definition=``; el esquema
       (``line_type_id.resume_line_type_properties_definition``) queda
       documentado en ``help_text``, sin validación automática contra él
   * - ``avatar_128`` (related, ``:14``)
     - propiedad — delega en ``employee_id``
   * - ``company_id`` / ``department_id`` (related, ``:15-16``)
     - propiedades — delegan en ``employee_id``
   * - ``is_course`` (related, ``:23``)
     - propiedad — delega en ``line_type_id``
   * - ``color`` (compute, ``:30``)
     - portado — columna con default ``'#000000'``; recómputo
       ``_compute_color()`` disponible (sin motor de ``@api.depends``, ver
       divergencia de ``hr_skill_type.py``)
   * - ``external_url`` (compute, store=True, readonly=False, ``:31``)
     - portado — columna real (es ``store=True``); recómputo
       ``_compute_external_url()`` disponible
   * - ``_date_check`` (``models.Constraint``, ``:39-42``)
     - portado — ``Meta.constraints`` (``CheckConstraint``)
   * - ``_onchange_external_url`` (``:44-49``)
     - portado (divergencia) — sin motor de ``@api.onchange``; queda como
       método explícito, no auto-wireado (mismo criterio que
       ``hr_individual_skill_mixin.py``)
   * - ``_compute_external_url`` (``:51-55``)
     - portado
   * - ``_compute_color`` (``:57-61``)
     - portado
"""
import re
from datetime import date

import fields
import models

from addons.base.models import TimeStampedModel


class HrResumeLine(TimeStampedModel):
    """``hr.resume.line`` — una línea del CV de un empleado."""

    _name = 'hr.resume.line'
    _description = 'Resume line of an employee'
    _order = 'line_type_id, date_end desc, date_start desc'

    employee = fields.Many2one(
        'hr.HrEmployee', on_delete=models.CASCADE,
        db_index=True, related_name='resume_line_ids',
        verbose_name='Empleado',
    )
    name = fields.Char(
        required=True, translate=True, verbose_name='Nombre',
    )
    date_start = fields.Date(
        default=date.today, verbose_name='Fecha de inicio',
    )
    date_end = fields.Date(null=True, blank=True, verbose_name='Fecha de fin')
    duration = fields.Integer(
        default=0, verbose_name='Duración',
        help_text='Odoo duration.',
    )
    description = fields.Html(
        null=True, blank=True, verbose_name='Descripción',
        help_text='Odoo description (translate=True en la fuente — sin '
                  'dispatcher de traducción en fields.Html, ver '
                  'fields.Char.translate en la fachada).',
    )
    line_type = fields.Many2one(
        'hr_skills.HrResumeLineType', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resume_line_ids',
        verbose_name='Tipo',
    )
    course_type = fields.Selection(
        choices=[('external', 'Externo')],
        default='external', verbose_name='Tipo de curso',
    )
    color = fields.Char(
        default='#000000', verbose_name='Color',
        help_text='Odoo color (compute) — recómputo: _compute_color().',
    )
    external_url = fields.Char(
        blank=True, default='', verbose_name='URL externa',
        help_text='Odoo external_url (compute, store=True) — recómputo: '
                  '_compute_external_url().',
    )
    certificate_filename = fields.Char(
        blank=True, default='',
        verbose_name='Nombre de archivo del certificado',
    )
    certificate_file = fields.Binary(
        null=True, blank=True, verbose_name='Certificado',
    )
    resume_line_properties = fields.Properties(
        null=True, blank=True, verbose_name='Propiedades',
        definition='line_type.resume_line_type_properties_definition',
        help_text='Odoo resume_line_properties — esquema definido por '
                  'line_type_id.resume_line_type_properties_definition '
                  '(JSON en este árbol).',
    )

    class Meta:
        db_table = 'hr_resume_line'
        ordering = ['line_type', '-date_end', '-date_start']
        verbose_name = 'Línea de CV'
        verbose_name_plural = 'Líneas de CV'
        constraints = [
            # ≙ ``_date_check`` (``:35-38``).
            models.CheckConstraint(
                condition=models.Q(date_end__isnull=True)
                | models.Q(date_start__lte=models.F('date_end')),
                name='hr_resume_line_date_chk',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def avatar_128(self):
        """≙ ``avatar_128`` (``related='employee_id.avatar_128'``)."""
        return self.employee.avatar_128 if self.employee_id else None

    @property
    def company(self):
        """≙ ``company_id`` (``related='employee_id.company_id'``)."""
        return self.employee.company if self.employee_id else None

    @property
    def department(self):
        """≙ ``department_id`` (``related='employee_id.department_id'``)."""
        return self.employee.department if self.employee_id else None

    @property
    def is_course(self):
        """≙ ``is_course`` (``related='line_type_id.is_course'``)."""
        return bool(self.line_type_id and self.line_type.is_course)

    def _onchange_external_url(self):
        """≙ ``_onchange_external_url`` (``:40-45``) — DIVERGENCIA: sin
        motor de ``@api.onchange``, disponible como método explícito."""
        if not self.name and self.external_url:
            match = re.search(
                r'((https|http):\/\/)?(www\.)?(.*)\.', self.external_url,
            )
            if match:
                self.name = match.group(4).capitalize()

    def _compute_external_url(self):
        """≙ ``_compute_external_url`` (``:47-51``)."""
        if self.course_type != 'external':
            self.external_url = ''
        return self.external_url

    def _compute_color(self):
        """≙ ``_compute_color`` (``:53-57``)."""
        if self.course_type == 'external':
            self.color = '#a2a2a2'
        return self.color

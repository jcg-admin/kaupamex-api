"""``hr.resume.line.type`` — categoría de una línea de CV (curso, experiencia…).

Adaptación fiel de Odoo hr_skills/models/hr_resume_line_type.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03). Porte completo — 4 de 4 campos, sin métodos.
"""
import fields

from addons.base.models import TimeStampedModel


class HrResumeLineType(TimeStampedModel):
    """``hr.resume.line.type`` — el tipo de una línea del currículum."""

    _name = 'hr.resume.line.type'
    _description = 'Type of a resume line'
    _order = 'sequence'

    name = fields.Char(
        max_length=255, required=True, translate=True, verbose_name='Nombre',
    )
    sequence = fields.Integer(default=10, verbose_name='Secuencia')
    is_course = fields.Boolean(default=False, verbose_name='Curso')
    resume_line_type_properties_definition = fields.PropertiesDefinition(
        null=True, blank=True, verbose_name='Propiedades de sección',
        help_text='Odoo resume_line_type_properties_definition — esquema de '
                  'propiedades dinámicas para las líneas de este tipo '
                  '(JSON en este árbol; src/orm/fields_properties.py).',
    )

    class Meta:
        db_table = 'hr_resume_line_type'
        ordering = ['sequence']
        verbose_name = 'Tipo de línea de CV'
        verbose_name_plural = 'Tipos de línea de CV'

    def __str__(self):
        return self.name

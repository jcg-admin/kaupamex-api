"""``hr.recruitment.degree`` — el nivel académico de un candidato (Odoo
``hr_recruitment``).

Adaptación fiel de Odoo ``hr_recruitment/models/hr_recruitment_degree.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 17 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03). Porte completo — 5 de 5 símbolos.
"""
import fields
import models
from addons.base.models import TimeStampedModel


class HrRecruitmentDegree(TimeStampedModel):
    """``hr.recruitment.degree`` — catálogo de grados académicos."""

    _name = 'hr.recruitment.degree'
    _description = 'Applicant Degree'

    name = fields.Char(
        max_length=255, verbose_name='Nombre del grado', help_text='Odoo "Degree Name".',
    )
    score = fields.Float(default=0, verbose_name='Puntaje')
    sequence = fields.Integer(default=1, verbose_name='Secuencia')

    class Meta:
        db_table = 'hr_recruitment_degree'
        verbose_name = 'Grado académico'
        verbose_name_plural = 'Grados académicos'
        constraints = [
            # ≙ ``_name_uniq`` (``:19-22``).
            models.UniqueConstraint(
                fields=['name'], name='hr_recruitment_degree_name_uniq',
                violation_error_message='The name of the Degree of '
                                        'Recruitment must be unique!',
            ),
            # ≙ ``_score_range`` (``:23-26``).
            models.CheckConstraint(
                condition=models.Q(score__gte=0) & models.Q(score__lte=1),
                name='hr_recruitment_degree_score_range',
                violation_error_message='Score should be between 0 and 100%',
            ),
        ]

    def __str__(self) -> str:
        return self.name

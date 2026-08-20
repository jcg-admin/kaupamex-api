"""``hr.applicant.category`` — etiqueta libre de un candidato (Odoo
``hr_recruitment``).

Adaptación fiel de Odoo ``hr_recruitment/models/hr_applicant_category.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 22 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03). Mismo patrón que
``addons.utm.models.utm_tag.UtmTag``: nombre + color aleatorio + unicidad.

Porte símbolo por símbolo — 4 de 4
====================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_get_default_color`` (``:12-13``)
     - portado como función de módulo (el ``default=`` de Django exige un
       invocable sin argumentos; mismo criterio que ``utm.tag._default_color``)
   * - ``name`` (``:15``)
     - portado
   * - ``color`` (``:16``)
     - portado
   * - ``_name_uniq`` (``:18-21``)
     - portado — ``Meta.constraints`` con ``UniqueConstraint``
"""
from random import randint

import fields
import models
from addons.base.models import TimeStampedModel


def _get_default_color():
    """≙ ``_get_default_color`` (``odoo19c: hr_applicant_category.py:12-13``)."""
    return randint(1, 11)


class HrApplicantCategory(TimeStampedModel):
    """``hr.applicant.category`` — una etiqueta de candidato."""

    _name = 'hr.applicant.category'
    _description = 'Category of applicant'

    name = fields.Char(
        verbose_name='Nombre de la etiqueta',
        help_text='Odoo "Tag Name".',
    )
    color = fields.Integer(
        default=_get_default_color, verbose_name='Índice de color',
    )

    class Meta:
        db_table = 'hr_applicant_category'
        verbose_name = 'Etiqueta de candidato'
        verbose_name_plural = 'Etiquetas de candidato'
        constraints = [
            models.UniqueConstraint(
                fields=['name'], name='hr_applicant_category_name_uniq',
                violation_error_message='Tag name already exists!',
            ),
        ]

    def __str__(self) -> str:
        return self.name

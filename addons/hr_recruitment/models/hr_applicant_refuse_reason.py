"""``hr.applicant.refuse.reason`` — el motivo de rechazo de un candidato
(Odoo ``hr_recruitment``).

Adaptación fiel de Odoo ``hr_recruitment/models/hr_applicant_refuse_reason.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 15 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 4 de 4 campos
============================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``sequence`` (``:12``)
     - portado
   * - ``name`` (``:13``)
     - portado
   * - ``template_id`` (``:14``)
     - portado — FK a ``MailTemplate`` (``addons.mail``); el ``domain=`` de
       la referencia (sólo plantillas de ``hr.applicant``) es filtrado de
       formulario/DRF, no del modelo — se documenta, no se aplica aquí
   * - ``active`` (``:15``)
     - portado
"""
import fields
import models
from addons.base.models import TimeStampedModel
from addons.mail.models import MailTemplate


class HrApplicantRefuseReason(TimeStampedModel):
    """``hr.applicant.refuse.reason`` — catálogo de motivos de rechazo."""

    _name = 'hr.applicant.refuse.reason'
    _description = 'Refuse Reason of Applicant'
    _order = 'sequence'

    sequence = fields.Integer(default=10)
    name = fields.Char(max_length=255, verbose_name='Descripción')
    template = fields.Many2one(
        'mail.MailTemplate', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_applicant_refuse_reasons',
        verbose_name='Plantilla de correo',
        help_text='Odoo template_id: plantilla usada al notificar el rechazo '
                  '(domain hr.applicant filtrado en la capa de formulario, '
                  'no aquí).',
    )
    active = fields.Boolean(default=True, verbose_name='Activo')

    class Meta:
        db_table = 'hr_applicant_refuse_reason'
        # ≙ ``_order = 'sequence'`` (``odoo19c: :12``).
        ordering = ['sequence']
        verbose_name = 'Motivo de rechazo'
        verbose_name_plural = 'Motivos de rechazo'

    def __str__(self) -> str:
        return self.name

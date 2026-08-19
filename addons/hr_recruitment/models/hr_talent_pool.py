"""``hr.talent.pool`` — una reserva de candidatos para reutilizar entre
puestos (Odoo ``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/hr_talent_pool.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 65 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 9 de 10
======================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_inherit = ["mail.thread"]`` (``:9``)
     - portado — ``MailThread`` (``addons.mail``)
   * - ``_get_default_color``…``categ_ids`` (9 campos, ``:12-42``)
     - portados — ``tracking=True`` de la referencia es ACL/chatter de vista,
       no del modelo; no se aplica aquí
   * - ``_compute_talent_count`` (``:45-50``)
     - portado
   * - ``action_talent_pool_add_talents`` (``:52-61``)
     - BLOQUEADO — familia (b): ``ir.actions.act_window`` (framework de
       acciones cliente Odoo, sin equivalente en este stack DRF+React)
"""
from random import randint

import fields
import models
from addons.base.models import TimeStampedModel
from addons.mail.models import MailThread
from orm.environments import get_current_company, get_current_user


def _get_default_color():
    """≙ ``_get_default_color`` (``odoo19c: hr_talent_pool.py:11-12``)."""
    return randint(1, 11)


class HrTalentPool(MailThread, TimeStampedModel):
    """``hr.talent.pool`` — bolsa de candidatos reutilizables."""

    _name = 'hr.talent.pool'
    _description = 'Talent Pool'

    active = fields.Boolean(default=True, verbose_name='Activo')
    name = fields.Char(
        max_length=255, verbose_name='Título', help_text='Odoo "Title".',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_talent_pools', default=get_current_company,
        verbose_name='Empresa',
    )
    # Odoo pool_manager: domain "[('share', '=', False), ('company_ids', 'in',
    # company_id)]" — filtrado de formulario/DRF, no del modelo (mismo
    # criterio que hr_applicant_refuse_reason.template).
    pool_manager = fields.Many2one(
        'base.ResUsers', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_talent_pools', default=get_current_user,
        verbose_name='Responsable de la bolsa',
    )
    # ≙ ``talent_ids`` (Many2many hacia ``hr.applicant``). La referencia
    # también declara ``hr.applicant.talent_pool_ids`` como M2M sin
    # ``relation=`` explícita hacia ``hr.talent.pool`` — sin nombre de tabla
    # propio, Odoo resuelve ambos lados a la MISMA tabla junction (par de
    # modelos ordenado): son dos caras de una única arista, no dos M2M
    # distintos. Aquí se declara UNA vez, con el reverso nombrado
    # ``talent_pools`` — el accesor que ``HrApplicant.talent_pools`` expone.
    talents = fields.Many2many(
        'hr_recruitment.HrApplicant', related_name='talent_pools',
        blank=True, verbose_name='Talentos',
        help_text='Odoo talent_ids: los candidatos de esta bolsa.',
    )
    description = fields.Html(blank=True, default='', verbose_name='Descripción')
    color = fields.Integer(default=_get_default_color, verbose_name='Color')
    categs = fields.Many2many(
        'hr_recruitment.HrApplicantCategory', related_name='talent_pools',
        blank=True, verbose_name='Etiquetas',
    )

    class Meta:
        db_table = 'hr_talent_pool'
        verbose_name = 'Bolsa de talento'
        verbose_name_plural = 'Bolsas de talento'

    def __str__(self) -> str:
        return self.name

    def talent_count(self):
        """≙ ``_compute_talent_count`` (``odoo19c: :45-50``) — el número de
        candidatos en esta bolsa. La referencia agrupa por
        ``talent_pool_ids`` (el lado del campo en ``hr.applicant``); aquí es
        el mismo dato, leído por el lado directo del M2M."""
        return self.talents.count()

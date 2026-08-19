"""``hr.recruitment.source`` — el canal por el que llega un candidato (Odoo
``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/hr_recruitment_source.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 59 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 6 de 10, 4 BLOQUEADOS
====================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_inherit = ['utm.source.mixin']`` (``:11``)
     - portado — ``UtmSourceMixin`` (``addons.utm``, mixin abstracto de Django)
   * - ``email``…``campaign_id`` (5 campos, ``:13-17``)
     - portados
   * - ``_compute_has_domain`` (``:19-25``)
     - portado (una rama BLOQUEADA — ver divergencia 1)
   * - ``create_alias`` (``:27-43``)
     - BLOQUEADO
   * - ``create_and_get_alias`` (``:45-48``)
     - BLOQUEADO — llama enteramente a ``create_alias``
   * - ``unlink`` (``:50-54``)
     - portado — ``delete()``

Divergencias y bloqueos declarados
=====================================

1. **``job_id.company_id.alias_domain_id`` / ``self.env.company.alias_domain_id``
   no existen.** Medido: ``grep -rn "alias_domain" src/addons/base/models/
   res_company.py`` → 0 hits — ``base.ResCompany`` no tiene la columna que la
   referencia agrega vía ``mail: models/res_company.py`` (``_inherit =
   'res.company'``), y ese archivo no está portado en ``addons/mail``. La
   rama ``source.alias_id`` de ``_compute_has_domain`` sí se porta (lee
   ``MailAlias.alias_domain_id``, que existe).
2. **``create_alias``/``create_and_get_alias`` BLOQUEADOS por tres piezas
   ausentes a la vez:** (a) la divergencia 1 (``alias_domain_id`` de
   empresa); (b) ``self.env.ref('hr_recruitment.utm_campaign_job')`` — dato
   XML no sembrado, y este addon no crea data/migraciones (fuera de
   write-set del pase); (c) ``self.env['ir.model']._get_id('hr.applicant')``
   — ``IrModel`` (``src/addons/base/models/ir_model.py``) no declara
   ``_get_id``/``_get`` (medido: 0 hits). Sucesor: cuando ``mail``
   porte ``res_company.py`` (alias_domain_id) y ``base`` complete
   ``IrModel``, este archivo se completa con las tres piezas.
"""
import fields
import models
from addons.base.models import TimeStampedModel
from addons.mail.models import MailAlias
from addons.utm.models.utm_medium import UtmMedium
from addons.utm.models.utm_source import UtmSourceMixin


def _default_medium():
    """≙ ``default=lambda self: self.env['utm.medium']._fetch_or_create_utm_medium('website')``
    (``odoo19c: hr_recruitment_source.py:15``). ``default=`` no acepta lambda."""
    return UtmMedium._fetch_or_create_utm_medium('website').pk


class HrRecruitmentSource(UtmSourceMixin, TimeStampedModel):
    """``hr.recruitment.source`` — un canal (bolsa de trabajo, referido…) por
    puesto."""

    _name = 'hr.recruitment.source'
    _description = 'Source of Applicants'

    job = fields.Many2one(
        'hr.HrJob', on_delete=models.CASCADE, null=True, blank=True,
        db_index=True, related_name='recruitment_sources',
        verbose_name='Puesto',
    )
    alias = fields.Many2one(
        'mail.MailAlias', on_delete=models.PROTECT, null=True, blank=True,
        related_name='recruitment_sources', verbose_name='Alias de correo',
    )
    medium = fields.Many2one(
        'utm.UtmMedium', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', default=_default_medium, verbose_name='Medio',
    )
    campaign = fields.Many2one(
        'utm.UtmCampaign', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Campaña',
    )

    class Meta:
        db_table = 'hr_recruitment_source'
        verbose_name = 'Origen de reclutamiento'
        verbose_name_plural = 'Orígenes de reclutamiento'

    @property
    def email(self):
        """≙ ``email`` (``related='alias_id.display_name'``, ``:13``)."""
        return self.alias.display_name if self.alias_id else None

    def has_domain(self):
        """≙ ``_compute_has_domain`` (``odoo19c: :19-25``).

        Rama ``alias_id`` portada; la rama sin alias (empresa del puesto o
        empresa activa) queda ``False`` — ``base.ResCompany.alias_domain_id``
        no existe (divergencia 1 del docstring del módulo).
        """
        if self.alias_id:
            return bool(self.alias.alias_domain_id)
        return False

    def delete(self, *args, **kwargs):
        """≙ ``unlink`` (``odoo19c: :50-54``) — arrastra el alias consigo."""
        alias = self.alias if self.alias_id else None
        result = super().delete(*args, **kwargs)
        if alias is not None:
            alias.delete()
        return result

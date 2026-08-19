"""``talent.pool.add.applicants`` — mover/copiar candidatos a una bolsa de
talento (Odoo ``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/wizard/talent_pool_add_applicants.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 72 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

``TransientModel`` → clase con classmethods, sin tabla.

Porte símbolo por símbolo — 2 de 2 (forma)
==============================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_add_applicants_to_pool`` (``:22-49``)
     - portado
   * - ``action_add_applicants_to_pool`` (``:51-72``)
     - resuelto con otra forma — devuelve los talentos resultantes; sin
       acción de cliente (familia b)

Divergencia declarada
========================

``Command.link``/``self.env['hr.applicant'].copy()`` → manager M2M
Django (``.add()``) y ``HrApplicant.objects.create()`` reconstruyendo los
``vals`` (mismo criterio que ``job_add_applicants.py`` de este addon —
sin recordset ``copy()`` en este ORM).
"""
from orm.models_transient import TransientModel


class TalentPoolAddApplicants(TransientModel):
    """Enlaza candidatos existentes —o crea su copia como talento— en una
    o más bolsas de talento."""

    class Meta:
        abstract = True
        managed = False

    _name = 'talent.pool.add.applicants'
    _description = 'Add applicants to talent pool'

    @classmethod
    def add_applicants_to_pool(cls, applicants, talent_pools, categories):
        """≙ ``_add_applicants_to_pool`` (``odoo19c: :22-49``)."""
        talents = []
        for applicant in applicants:
            if applicant.talent_pools.exists():
                for pool in talent_pools:
                    pool.talents.add(applicant)
                for categ in categories:
                    applicant.categs.add(categ)
                talents.append(applicant)
            else:
                HrApplicant = type(applicant)
                talent = HrApplicant.objects.create(
                    partner_name=applicant.partner_name,
                    partner=applicant.partner,
                    email_from=applicant.email_from,
                    partner_phone=applicant.partner_phone,
                    linkedin_profile=applicant.linkedin_profile,
                    type=applicant.type,
                    job=None,
                )
                for pool in talent_pools:
                    pool.talents.add(talent)
                for categ in list(applicant.categs.all()) + list(categories):
                    talent.categs.add(categ)
                talent.pool_applicant = talent
                talent.save(update_fields=['pool_applicant'])
                applicant.pool_applicant = talent
                applicant.save(update_fields=['pool_applicant'])
                talents.append(talent)
        return talents

    @classmethod
    def action_add_applicants_to_pool(cls, applicants, talent_pools, categories):
        """≙ ``action_add_applicants_to_pool`` (``odoo19c: :51-72``) —
        devuelve los talentos; sin acción de cliente (familia b)."""
        return cls.add_applicants_to_pool(applicants, talent_pools, categories)

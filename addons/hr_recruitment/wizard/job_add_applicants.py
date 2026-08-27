"""``job.add.applicants`` — copiar candidatos hacia otros puestos (Odoo
``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/wizard/job_add_applicants.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 58 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

``TransientModel`` → clase con classmethods, sin tabla — mismo patrón que
``hr.HrDepartureWizard``. El estado del wizard (candidatos, puestos) lo
pasa el llamador como argumentos.

Porte símbolo por símbolo — 2 de 2 (forma), con divergencia declarada
==========================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_add_applicants_to_job`` (``:11-29``)
     - portado
   * - ``action_add_applicants_to_job`` (``:31-58``)
     - resuelto con otra forma — la rama ``ir.actions.act_window``/
       ``ir.actions.client`` (familia b) no tiene análogo; el classmethod
       devuelve los candidatos creados y el mensaje de resumen, para que
       la capa DRF que lo cablee componga su propia respuesta

Divergencia declarada
========================

``applicant.copy_data()`` (recordset de Odoo) no tiene análogo directo:
se reconstruyen los ``vals`` campo por campo desde cada
``hr.applicant`` de origen — mismo criterio que ``account_debit_note``
al copiar líneas.
"""
from orm.models_transient import TransientModel
from tools.translate import _


class JobAddApplicants(TransientModel):
    """Copia candidatos existentes hacia uno o más puestos nuevos."""

    class Meta:
        abstract = True
        managed = False

    _name = 'job.add.applicants'
    _description = 'Add applicants to a job'

    @classmethod
    def _copy_applicant_vals(cls, applicant):
        """≙ la parte de ``applicant_data`` que ``copy_data()`` construía
        (``odoo19c: :12``) — los campos que viajan a la nueva aplicación."""
        return {
            'partner_name': applicant.partner_name,
            'partner': applicant.partner,
            'email_from': applicant.email_from,
            'partner_phone': applicant.partner_phone,
            'linkedin_profile': applicant.linkedin_profile,
            'type': applicant.type,
            'priority': applicant.priority,
        }

    @classmethod
    def add_applicants_to_job(cls, applicants, jobs):
        """≙ ``_add_applicants_to_job`` (``odoo19c: :11-29``) — crea una
        aplicación nueva por cada par (candidato, puesto), en la primera
        etapa elegible de ese puesto."""
        HrApplicant = type(next(iter(applicants), None)) if applicants else None
        if HrApplicant is None:
            return []
        new_applicants = []
        for applicant in applicants:
            base_vals = cls._copy_applicant_vals(applicant)
            for job in jobs:
                stage = job._get_first_stage() if hasattr(job, '_get_first_stage') else None
                vals = dict(base_vals)
                vals.update(job=job, stage=stage)
                new_applicants.append(HrApplicant.objects.create(**vals))
        return new_applicants

    @classmethod
    def action_add_applicants_to_job(cls, applicants, jobs):
        """≙ ``action_add_applicants_to_job`` (``odoo19c: :31-58``) —
        devuelve los nuevos candidatos y un mensaje de resumen; sin acción
        de cliente (familia b, ver docstring del módulo)."""
        new_applicants = cls.add_applicants_to_job(applicants, jobs)
        if len(new_applicants) == 1:
            message = None
        else:
            names = ', '.join({a.partner_name or '' for a in new_applicants})
            message = _(
                'Se crearon %(amount)s postulaciones nuevas para: %(names)s',
                amount=len(new_applicants), names=names,
            )
        return {'applicants': new_applicants, 'message': message}

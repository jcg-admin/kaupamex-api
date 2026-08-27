"""``hr.job`` — puntuación de matching de un candidato contra el puesto.

Adaptación de Odoo hr_recruitment_skills/models/hr_job.py
(odoo-tools, odoo19c:, LGPL-3, 66 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 campo + 2 métodos (medido por AST)
=================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Dónde queda aquí
   * - ``applicant_matching_score`` (Float compute sin store, ``:11-13``)
     - resuelto con otra forma — el compute depende del contexto
       ``active_applicant_id``, así que no cabe ni columna ni propiedad:
       queda el método ``_compute_applicant_matching_score(applicant)``
       que devuelve el porcentaje (DIVERGENCIA 1). Su ``groups=`` no se
       porta (DIVERGENCIA 2)
   * - ``_compute_applicant_matching_score`` (``:15-44``)
     - portado — ``active_applicant_id`` del contexto → argumento
       ``applicant``
   * - ``action_search_matching_applicants`` (``:46-66``)
     - BLOQUEADO — ``ir.actions.actions._for_xml_id`` + vistas XML +
       ``Markup`` de ayuda: acción de cliente Odoo (familia (b), mismo
       criterio que ``hr_fleet/models/employee.py``). El dato de negocio
       que la acción listaba está disponible con el ORM::

           HrApplicant.objects.exclude(job=job).filter(
               skill_ids__in=job.job_skill_ids.values('skill_id'))

Divergencias declaradas
========================

1. **``@api.depends_context('active_applicant_id')`` → argumento.** Sin
   contexto de request en la capa de modelo, el candidato a puntuar llega
   como argumento; la rama "sin candidato activo → score falso" de la
   referencia (``:17-20``) es el llamador no invocando el método.
2. **``groups=`` no se porta** — el gate de autorización (DEC-11,
   ``HasCapability``) es de la vista DRF.
3. **``markupsafe.Markup`` no se importa** — sólo lo usaba la acción
   bloqueada; además no es dependencia del árbol (medido en ``uv.lock``
   por la tanda anterior — preámbulo, regla 1).
"""
from orm.model_classes import extend_model


def _compute_applicant_matching_score(self, applicant):
    """≙ ``_compute_applicant_matching_score`` (``:15-44``) — porcentaje de
    coincidencia de ``applicant`` contra las habilidades y el grado
    esperado de este puesto. DIVERGENCIA 1: candidato como argumento.

    Devuelve ``0`` cuando el puesto no declara habilidades (la rama
    ``job.applicant_matching_score = False`` de la referencia).
    """
    if not self.job_skill_ids.exists():
        return 0
    job_skills = list(self.job_skill_ids.all())
    job_degree = (self.expected_degree.score * 100
                  if self.expected_degree_id else 0)
    job_total = sum(j_s.level_progress for j_s in job_skills) + job_degree
    job_skill_map = {j_s.skill_id: j_s.level_progress for j_s in job_skills}

    matching_applicant_skills = [
        a_s for a_s in applicant._compute_current_applicant_skill_ids()
        if a_s.skill_id in job_skill_map
    ]
    applicant_degree = (applicant.type.score * 100
                        if job_degree > 1 and applicant.type_id else 0)
    applicant_total = sum(
        min(a_s.level_progress, job_skill_map[a_s.skill_id] * 2)
        for a_s in matching_applicant_skills
    ) + applicant_degree

    return applicant_total / job_total * 100 if job_total else 0


def apply_hr_recruitment_skills_hr_job_extensions():
    """Cuelga sobre ``hr.job`` lo que ``hr_recruitment_skills`` le añade —
    ≙ ``_inherit``. Se invoca desde ``HrRecruitmentSkillsConfig.ready()``."""
    extend_model(
        'hr', 'HrJob',
        metodos={
            '_compute_applicant_matching_score':
                _compute_applicant_matching_score,
        },
    )

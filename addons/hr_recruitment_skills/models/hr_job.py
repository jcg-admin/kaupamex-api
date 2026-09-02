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
     - DIVERGENCIA 4 declarada (tarea #62,
       ``scripts/divergencias_declaradas.txt``): el dato de negocio —
       real, portado — es ``_search_matching_applicants``; el envoltorio
       ``ir.actions.act_window`` + vista XML + ``Markup`` de ayuda no
       tiene mecanismo en este backend DRF (familia (b), mismo criterio
       que ``hr_fleet/models/employee.py``)
   * - ``_search_matching_applicants`` — NO es símbolo de la referencia;
       es la porción de datos de ``action_search_matching_applicants``,
       nombrada aparte para que el gate de porte pueda verla
     - portado — ``HrApplicant.objects.exclude(job=self).filter(
       skill_ids__in=self.job_skill_ids.values_list('skill_id',
       flat=True)).distinct()``

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
4. **``action_search_matching_applicants`` — envoltorio de acción de
   cliente, sin mecanismo en este stack (tarea #62).** Este backend no
   tiene ``ir.actions.act_window``, ni registro de vistas XML, ni motor
   de navegación de cliente — es un DRF puro; ninguno de los tres existe
   para NINGÚN addon del árbol, no sólo aquí (mismo criterio que
   ``hr_fleet``, ``authz_passkey``, etc., ya declarados en
   ``scripts/divergencias_declaradas.txt``). Lo que la acción listaba —el
   queryset de candidatos que comparten habilidad con el puesto y los dos
   mensajes de ayuda— SÍ se construyó: vive en
   ``_search_matching_applicants(self)``, real y con test. Declarado en
   el registro como
   ``hr_recruitment_skills/models/hr_job.py::HrJob::
   action_search_matching_applicants``.
"""
from django.apps import apps as django_apps

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


def _search_matching_applicants(self):
    """La porción de datos de ``action_search_matching_applicants``
    (``:46-66``) — DIVERGENCIA 4 declarada
    (``scripts/divergencias_declaradas.txt``): el envoltorio de acción de
    cliente no tiene mecanismo aquí; esto es la consulta que esa acción
    listaba.

    Devuelve el queryset de ``hr.applicant`` que NO están en este puesto
    y comparten al menos una habilidad con las que el puesto requiere.
    Vacío si el puesto no declara habilidades (misma guarda que
    ``_compute_applicant_matching_score``).
    """
    HrApplicant = django_apps.get_model('hr_recruitment', 'HrApplicant')
    if not self.job_skill_ids.exists():
        return HrApplicant.objects.none()
    skill_pks = self.job_skill_ids.values_list('skill_id', flat=True)
    return (HrApplicant.objects.exclude(job_id=self.pk)
            .filter(skill_ids__in=skill_pks).distinct())


def apply_hr_recruitment_skills_hr_job_extensions():
    """Cuelga sobre ``hr.job`` lo que ``hr_recruitment_skills`` le añade —
    ≙ ``_inherit``. Se invoca desde ``HrRecruitmentSkillsConfig.ready()``."""
    extend_model(
        'hr', 'HrJob',
        metodos={
            '_compute_applicant_matching_score':
                _compute_applicant_matching_score,
            '_search_matching_applicants': _search_matching_applicants,
        },
    )

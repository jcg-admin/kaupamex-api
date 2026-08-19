"""``hr.applicant`` — habilidades del candidato y matching contra el puesto.

Adaptación de Odoo hr_recruitment_skills/models/hr_applicant.py
(odoo-tools, odoo19c:, LGPL-3, 166 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 6 campos + 8 métodos (medido por AST)
==================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Dónde queda aquí
   * - ``applicant_skill_ids`` (One2many, ``:11-13``)
     - sin código — reverso automático de
       ``hr_recruitment_skills.HrApplicantSkill.applicant``
       (``related_name='applicant_skill_ids'``)
   * - ``current_applicant_skill_ids`` (compute, readonly=False, ``:14-19``)
     - propiedad de sólo lectura (la mitad ``compute``); la mitad de
       escritura era transporte del protocolo de comandos (ver ``write``)
   * - ``skill_ids`` (Many2many compute+store, ``:20``)
     - portado — columna real; recómputo ``_compute_skill_ids()``
       disponible (mismo criterio que ``hr_skills/models/hr_job.py``)
   * - ``matching_skill_ids`` / ``missing_skill_ids`` / ``matching_score``
       (compute sin store, ``:21-31``)
     - propiedades — delegan en ``_compute_matching_skill_ids()``
   * - ``_compute_current_applicant_skill_ids`` (``:34-37``)
     - portado — por instancia (sin recordset)
   * - ``_compute_skill_ids`` (``:40-42``)
     - portado
   * - ``_compute_matching_skill_ids`` (``:46-76``)
     - portado — DIVERGENCIA 1: ``matching_job_id`` era contexto de
       request; aquí es el argumento ``matching_job``
   * - ``_get_employee_create_vals`` (``:78-92``)
     - portado — encadenado sobre el nombre PÚBLICO local
       ``get_employee_create_vals`` (DIVERGENCIA 2)
   * - ``_map_applicant_skill_ids_to_talent_skill_ids`` (``:94-133``)
     - BLOQUEADO — protocolo de comandos x2many (DIVERGENCIA 3 de
       ``hr_skills/models/hr_individual_skill_mixin.py``): existe
       únicamente para re-mapear tuplas ``(comando, id, vals)`` de un
       candidato a su talento; sin ese transporte no hay nada que traducir
   * - ``action_add_to_job`` (``:135-144``)
     - portado — DIVERGENCIA 3 (contexto → argumento; ``env.ref`` de la
       etapa → primera etapa por secuencia; sin acción de ventana)
   * - ``create`` (``:147-153``) / ``write`` (``:155-166``)
     - BLOQUEADOS — ambos existen sólo para fusionar/transformar listas de
       comandos x2many en ``vals`` (``current_applicant_skill_ids`` +
       ``applicant_skill_ids``) y sincronizar la copia del talento vía
       ``_map_applicant_skill_ids_to_talent_skill_ids``; misma DIVERGENCIA
       3 del mixin — aquí un one2many se escribe con llamadas directas al
       manager (``HrApplicantSkill.objects.create(...)``), no con comandos

Divergencias declaradas
========================

1. **``@api.depends_context('matching_job_id')`` → argumento.** Sin
   contexto de request en la capa de modelo, ``_compute_matching_skill_ids
   (matching_job=None)`` recibe el puesto contra el que se compara; sin
   argumento usa ``self.job`` (el mismo fallback de la referencia).
2. **La base local ya publica ``get_employee_create_vals`` sin guion.**
   ``hr_recruitment/models/hr_applicant.py:511`` portó
   ``_get_employee_create_vals`` como público; el encadenado va sobre el
   nombre que existe (encadenar ``_get_employee_create_vals`` instalaría
   un método nuevo que nadie llama). El valor añadido es
   ``vals['employee_skill_ids']``: una lista de **dicts planos** de vals —
   no tuplas ``(0, 0, vals)`` — que el llamador materializa con
   ``HrEmployeeSkill.objects.create(employee=…, **vals)`` tras crear el
   empleado (doctrina del mixin: one2many por manager, no por comandos).
3. **``action_add_to_job``**: ``matching_job_id`` del contexto → argumento
   ``job``; ``env.ref('hr_recruitment.stage_job0')`` → primera etapa por
   secuencia (los data XML de etapas no se portan; mismo cálculo que
   ``reset_applicant`` en la base local); ``with_context(just_moved=True)``
   cae (0 consumidores locales de esa clave, medido); el ``ir.actions``
   de retorno es navegación de cliente — el método devuelve ``self``.
4. **``groups=`` no se porta** — el gate de autorización (DEC-11,
   ``HasCapability``) es de la vista DRF.
5. **``.sudo()`` → acceso directo** — sin usuario ambiente no hay
   elevación (``job.expected_degree.sudo().score`` → ``score``).
"""
import fields
from django.apps import apps as django_apps

from addons.hr_recruitment_skills.models.hr_applicant_skill import HrApplicantSkill
from addons.hr_skills.models.hr_skill import HrSkill
from orm.method_chain import chain_method
from orm.model_classes import extend_model
from orm.models import Q


def _compute_current_applicant_skill_ids(self):
    """≙ ``_compute_current_applicant_skill_ids`` (``:34-37``) — las
    habilidades vigentes del candidato (certificación más reciente si no
    hay vigentes), por instancia."""
    by_applicant = HrApplicantSkill._get_current_skills_by_applicant(
        self.applicant_skill_ids.all(),
    )
    return by_applicant[self.pk]


def current_applicant_skill_ids(self):
    """≙ ``current_applicant_skill_ids`` (``:14-19``, compute sin store)."""
    return self._compute_current_applicant_skill_ids()


def _compute_skill_ids(self):
    """≙ ``_compute_skill_ids`` (``:40-42``) — sincroniza la columna M2M
    con las habilidades declaradas (mismo criterio que
    ``hr_skills/models/hr_job.py::_compute_skill_ids``)."""
    skill_ids = list(
        self.applicant_skill_ids.values_list('skill_id', flat=True).distinct(),
    )
    self.skill_ids.set(skill_ids)
    return self.skill_ids


def _compute_matching_skill_ids(self, matching_job=None):
    """≙ ``_compute_matching_skill_ids`` (``:46-76``) — DIVERGENCIA 1: el
    puesto de comparación llega como argumento, no por contexto.

    Devuelve ``(matching_skills, missing_skills, matching_score)`` donde
    los dos primeros son querysets de ``hr.skill`` y el tercero el entero
    redondeado 0-100 (la referencia escribía los tres campos compute).
    """
    job = matching_job if matching_job is not None else self.job
    empty = HrSkill.objects.none()
    if job is None or not (job.job_skill_ids.exists() or job.expected_degree_id):
        return (empty, empty, 0)
    job_skills = list(job.job_skill_ids.all())
    job_degree = (job.expected_degree.score * 100) if job.expected_degree_id else 0
    job_total = sum(j_s.level_progress for j_s in job_skills) + job_degree
    job_skill_map = {j_s.skill_id: j_s.level_progress for j_s in job_skills}

    matching_applicant_skills = [
        a_s for a_s in self._compute_current_applicant_skill_ids()
        if a_s.skill_id in job_skill_map
    ]
    applicant_degree = (self.type.score * 100
                        if job_degree > 1 and self.type_id else 0)
    applicant_total = sum(
        min(a_s.level_progress, job_skill_map[a_s.skill_id] * 2)
        for a_s in matching_applicant_skills
    ) + applicant_degree

    matching_pks = {a_s.skill_id for a_s in matching_applicant_skills}
    matching_skills = HrSkill.objects.filter(pk__in=matching_pks)
    missing_skills = HrSkill.objects.filter(
        pk__in=set(job_skill_map) - matching_pks,
    )
    matching_score = (round(applicant_total / job_total * 100)
                      if job_total else 0)
    return (matching_skills, missing_skills, matching_score)


def matching_skill_ids(self):
    """≙ ``matching_skill_ids`` (``:21-25``, compute sin store)."""
    return self._compute_matching_skill_ids()[0]


def missing_skill_ids(self):
    """≙ ``missing_skill_ids`` (``:26-30``, compute sin store)."""
    return self._compute_matching_skill_ids()[1]


def matching_score(self):
    """≙ ``matching_score`` (``:31``, compute sin store)."""
    return self._compute_matching_skill_ids()[2]


def _employee_create_vals_skills(self):
    """La porción de ``vals`` que este addon aporta — ≙ el override de
    ``_get_employee_create_vals`` (``:78-92``). Ver DIVERGENCIA 2: dicts
    planos, no comandos ``(0, 0, vals)``."""
    return {
        'employee_skill_ids': [
            {
                'skill': applicant_skill.skill,
                'skill_level': applicant_skill.skill_level,
                'skill_type': applicant_skill.skill_type,
            }
            for applicant_skill in self.applicant_skill_ids.all()
        ],
    }


def _merge_vals(new_vals, previous_vals):
    """``combine`` del encadenado: funde la porción nueva sobre los vals de
    la implementación previa (el ``vals.update`` que la referencia hace vía
    ``super()``)."""
    previous_vals.update(new_vals)
    return previous_vals


def action_add_to_job(self, job):
    """≙ ``action_add_to_job`` (``:135-144``) — mueve al candidato al
    puesto y lo reingresa en la primera etapa. DIVERGENCIA 3 del docstring
    del módulo (argumento, etapa por secuencia, sin acción de ventana)."""
    HrRecruitmentStage = django_apps.get_model(
        'hr_recruitment', 'HrRecruitmentStage',
    )
    self.job = job
    self.stage = (HrRecruitmentStage.objects
                  .filter(Q(jobs__isnull=True) | Q(jobs=job))
                  .exclude(fold=True).order_by('sequence').first())
    self.save(update_fields=['job', 'stage'])
    return self


def apply_hr_recruitment_skills_hr_applicant_extensions():
    """Cuelga sobre ``hr.applicant`` lo que ``hr_recruitment_skills`` le
    añade — ≙ ``_inherit``. Se invoca desde
    ``HrRecruitmentSkillsConfig.ready()``."""
    extend_model(
        'hr_recruitment', 'HrApplicant',
        campos={
            'skill_ids': fields.Many2many(
                'hr_skills.HrSkill', blank=True,
                related_name='applicants_with_skill',
                help_text='Odoo skill_ids (compute+store) — sincronizar '
                          'con _compute_skill_ids().',
            ),
        },
        metodos={
            '_compute_current_applicant_skill_ids':
                _compute_current_applicant_skill_ids,
            '_compute_skill_ids': _compute_skill_ids,
            '_compute_matching_skill_ids': _compute_matching_skill_ids,
            'action_add_to_job': action_add_to_job,
        },
        propiedades={
            'current_applicant_skill_ids': current_applicant_skill_ids,
            'matching_skill_ids': matching_skill_ids,
            'missing_skill_ids': missing_skill_ids,
            'matching_score': matching_score,
        },
        luego=lambda model: chain_method(
            model, 'get_employee_create_vals',
            _employee_create_vals_skills, combine=_merge_vals,
        ),
    )

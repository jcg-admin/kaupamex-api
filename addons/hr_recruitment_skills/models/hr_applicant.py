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
     - portado — por instancia (sin recordset). Bug de forma C corregido
       en ``hr_applicant_skill.py`` (tarea #62, ver su docstring): devolvía
       ``[]`` siempre desde ``api@a8949680``
   * - ``_compute_skill_ids`` (``:40-42``)
     - portado
   * - ``_compute_matching_skill_ids`` (``:46-76``)
     - portado — DIVERGENCIA 1: ``matching_job_id`` era contexto de
       request; aquí es el argumento ``matching_job``
   * - ``_get_employee_create_vals`` (``:78-92``)
     - portado — encadenado sobre el nombre PÚBLICO local
       ``get_employee_create_vals`` (DIVERGENCIA 2)
   * - ``_map_applicant_skill_ids_to_talent_skill_ids`` (``:94-133``)
     - portado (DIVERGENCIA 6) — CERRADO tarea #62: aplanado del protocolo
       de comandos x2many a una reconciliación directa por ``skill`` contra
       ``self.pool_applicant``, vía el manager (doctrina del mixin)
   * - ``action_add_to_job`` (``:135-144``)
     - portado — DIVERGENCIA 3 (contexto → argumento; ``env.ref`` de la
       etapa → primera etapa por secuencia; sin acción de ventana)
   * - ``create`` (``:147-153``)
     - portado (DIVERGENCIA 7) — CERRADO tarea #62: classmethod real,
       instalado sobre ``HrApplicant`` (no había ``create`` previo que
       relevar)
   * - ``write`` (``:155-166``)
     - portado (DIVERGENCIA 8) — CERRADO tarea #62: método público nuevo
       (no pisa el ``save()`` que ``hr_recruitment`` ya declara — ver
       DIVERGENCIA 8)

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
6. **``_map_applicant_skill_ids_to_talent_skill_ids`` — de comandos a
   reconciliación (tarea #62).** La fuente recibe ``vals`` (una lista de
   comandos ``(comando, id, valores)``) y traduce cada uno contra las
   pks del talento. Sin ese transporte (DIVERGENCIA 3 de
   ``hr_skills/models/hr_individual_skill_mixin.py``, que sigue vigente
   para el propio mixin), la traducción se aplana a ``_reconcile_
   applicant_skills(target, specs)``: compara ``self.applicant_skill_ids``
   contra ``self.pool_applicant.applicant_skill_ids`` **por** ``skill``
   —no por posición ni por id de fila, que no tienen sentido cruzando dos
   candidatos— y crea/actualiza/borra lo que corresponda. Es la MISMA
   invariante de negocio (el talento refleja las habilidades del
   candidato) resuelta sin protocolo de comandos, con el mismo criterio
   que ``_check_not_overlapping_regular_skill`` en el mixin (DIVERGENCIA 2
   ahí: de lote a instancia). Firma sin ``vals``: no hace falta transportar
   nada, ``self.applicant_skill_ids`` YA está actualizado cuando se llama.
7. **``create`` — mismo aplanamiento que #6, aplicado a la creación.**
   ``vals`` es un dict con las columnas escalares del padre más,
   opcionalmente, ``'applicant_skill_ids'``/``'current_applicant_skill_ids'``
   — listas de dicts ``{'skill', 'skill_level', 'skill_type'}`` (el
   ``skill_type`` es opcional; el ``default=`` del mixin lo resuelve si se
   omite). Se instala como ``classmethod`` con ``metodos=`` (no
   ``overrides=``): ``HrApplicant`` no declara ningún ``create`` previo
   que relevar (verificado: ``grep -n "def create" addons/hr_recruitment/
   models/hr_applicant.py`` → 0 hits), así que no hay ``super()`` que
   invocar — a diferencia de ``sale/models/ir_config_parameter.py``, cuyo
   ``create`` SÍ tiene previa y por eso usa ``wrap_method``.
8. **``write`` — mismo aplanamiento, sin colisionar con** ``save()``.
   ``hr_recruitment/models/hr_applicant.py:446`` YA overridea ``save()``
   para su propio ``create``/``write`` (fuente ``:615-693`` — otro rango,
   la sincronía de entrevistadores). Instalar aquí un método con OTRO
   nombre (``write``, el símbolo literal de la referencia) evita competir
   con esa cadena: ``write(vals)`` reconcilia habilidades cuando ``vals``
   trae ``'applicant_skill_ids'``/``'current_applicant_skill_ids'``
   (mismo guard que la fuente, ``:156``, para no borrar habilidades en un
   ``write`` que no las toca), aplica el resto de ``vals`` con
   ``setattr`` + ``self.save()`` (que SÍ dispara la cadena de
   ``hr_recruitment``), y sólo entonces propaga a
   ``pool_applicant`` — igual orden que la fuente (``:163-165``, dentro
   del mismo ``if``).
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


def _fk_pk(value):
    """Normaliza un valor de FK —instancia o pk— a su pk, o ``None``."""
    if value is None:
        return None
    return value.pk if hasattr(value, 'pk') else value


def _reconcile_applicant_skills(applicant, skill_specs):
    """Reconcilia ``applicant.applicant_skill_ids`` contra ``skill_specs`` —
    iterable de dicts ``{'skill', 'skill_level', 'skill_type'}`` (las dos
    primeras claves obligatorias; instancias o pks) — creando, actualizando
    y borrando filas de ``hr.applicant.skill`` por manager directo.

    Es el aplanamiento común a ``create``/``write``/``_map_applicant_
    skill_ids_to_talent_skill_ids`` (DIVERGENCIAS 6-8 del docstring del
    módulo): el protocolo de comandos x2many de la fuente no existe en
    este ORM, y las tres funciones de la referencia que lo consumían
    resuelven la MISMA operación — dejar el conjunto de habilidades de un
    candidato igual a una lista dada.

    Devuelve el queryset resultante de ``applicant.applicant_skill_ids``.
    """
    existing_by_skill = {a_s.skill_id: a_s
                          for a_s in applicant.applicant_skill_ids.all()}
    seen = set()
    for spec in skill_specs:
        skill_pk = _fk_pk(spec['skill'])
        skill_level_pk = _fk_pk(spec['skill_level'])
        skill_type_pk = _fk_pk(spec.get('skill_type'))
        seen.add(skill_pk)
        existing = existing_by_skill.get(skill_pk)
        if existing is not None:
            existing.skill_level_id = skill_level_pk
            if skill_type_pk is not None:
                existing.skill_type_id = skill_type_pk
            existing.save(update_fields=['skill_level', 'skill_type'])
        else:
            create_kwargs = {
                'applicant_id': applicant, 'skill_id': skill_pk,
                'skill_level_id': skill_level_pk,
            }
            # ``skill_type`` tiene ``default=`` en el mixin: se OMITE, no se
            # manda en None, para que Django lo aplique (un `None` explícito
            # lo pisaría y violaría el NOT NULL de la columna).
            if skill_type_pk is not None:
                create_kwargs['skill_type_id'] = skill_type_pk
            HrApplicantSkill.objects.create(**create_kwargs)
    for skill_pk, orphan in existing_by_skill.items():
        if skill_pk not in seen:
            orphan.delete()
    return applicant.applicant_skill_ids.all()


def _map_applicant_skill_ids_to_talent_skill_ids(self):
    """≙ ``_map_applicant_skill_ids_to_talent_skill_ids`` (``:94-133``) —
    DIVERGENCIA 6 del docstring del módulo.

    Refleja ``self.applicant_skill_ids`` sobre
    ``self.pool_applicant.applicant_skill_ids``. No hace nada si ``self``
    no tiene talento, si ``self`` ES su propio talento, o si ``self`` es
    ya un talento (``is_pool_applicant()``) — las mismas guardas que el
    llamador de la fuente aplicaba antes de invocar (``write``, ``:163``).

    Devuelve el queryset resultante de las habilidades del talento.
    """
    talent = self.pool_applicant
    if talent is None or talent.pk == self.pk or self.is_pool_applicant():
        return HrApplicantSkill.objects.none()
    specs = [
        {
            'skill': applicant_skill.skill_id,
            'skill_level': applicant_skill.skill_level_id,
            'skill_type': applicant_skill.skill_type_id,
        }
        for applicant_skill in self.applicant_skill_ids.all()
    ]
    return _reconcile_applicant_skills(talent, specs)


def create(cls, vals_list):
    """≙ ``create`` (``:147-153``) — DIVERGENCIA 7 del docstring del
    módulo.

    ``vals`` puede traer ``'applicant_skill_ids'``/``'current_applicant_
    skill_ids'`` (listas de specs — ver ``_reconcile_applicant_skills``);
    las funde igual que la fuente ("la duplicación del talento no
    funciona sin esto", comentario ``:149-150``) y materializa las
    habilidades del candidato recién creado por manager directo.

    Devuelve la lista de ``HrApplicant`` creados.
    """
    created = []
    for vals in vals_list:
        vals = dict(vals)
        skills = vals.pop('current_applicant_skill_ids', []) \
            + vals.pop('applicant_skill_ids', [])
        applicant = cls.objects.create(**vals)
        if skills:
            _reconcile_applicant_skills(applicant, skills)
        created.append(applicant)
    return created


def write(self, vals):
    """≙ ``write`` (``:155-166``) — DIVERGENCIA 8 del docstring del
    módulo.

    Si ``vals`` trae ``'applicant_skill_ids'``/``'current_applicant_
    skill_ids'`` (mismo guard que la fuente, ``:156``), reconcilia
    ``self.applicant_skill_ids`` contra la lista fusionada y propaga a
    ``self.pool_applicant`` — ≙ ``_map_applicant_skill_ids_to_talent_
    skill_ids`` (``:163-165``), mismo ``if``. Las demás claves de
    ``vals`` se aplican por ``setattr`` + ``self.save()`` — el
    ``super().write(vals)`` de la fuente (``:166``), que en este árbol
    es la cadena que ``hr_recruitment/models/hr_applicant.py:446`` ya
    instaló sobre ``save()``.

    Devuelve ``self``.
    """
    vals = dict(vals)
    touched_skills = ('current_applicant_skill_ids' in vals
                       or 'applicant_skill_ids' in vals)
    if touched_skills:
        skills = vals.pop('current_applicant_skill_ids', []) \
            + vals.pop('applicant_skill_ids', [])
        _reconcile_applicant_skills(self, skills)
    for field_name, value in vals.items():
        setattr(self, field_name, value)
    if vals:
        self.save()
    if touched_skills and self.pool_applicant_id and not self.is_pool_applicant():
        self._map_applicant_skill_ids_to_talent_skill_ids()
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
            '_map_applicant_skill_ids_to_talent_skill_ids':
                _map_applicant_skill_ids_to_talent_skill_ids,
            # ``create`` no tiene previa que relevar (verificado: 0 hits de
            # "def create" en hr_recruitment/models/hr_applicant.py) — se
            # instala como classmethod nuevo, no como wrap_method.
            'create': classmethod(create),
            'write': write,
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

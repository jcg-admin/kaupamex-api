"""``hr.individual.skill.mixin`` — el nivel de una habilidad ligada a un
"individuo" (empleado o puesto).

Adaptación fiel de Odoo hr_skills/models/hr_individual_skill_mixin.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 537 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 12 campos + 16 métodos
=====================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``skill_id`` / ``skill_level_id`` / ``skill_type_id`` /
       ``valid_from`` / ``valid_to`` / ``display_warning_message``
       (``:47-63``)
     - portados verbatim (columnas reales)
   * - ``level_progress`` / ``color`` / ``levels_count`` /
       ``certification_skill_type_count`` / ``is_certification``
       (related/compute sin store, ``:54-62``)
     - propiedades — delegan en ``skill_level``/``skill_type``
   * - ``_linked_field_name`` (``:17-18``)
     - portado — abstracto, ``NotImplementedError``
   * - ``_get_passive_fields`` (``:20-34``)
     - portado verbatim (``[]``)
   * - ``_can_edit_certification_validity_period`` (``:36-40``)
     - portado verbatim (``True``)
   * - ``_default_skill_type_id`` (``:42-45``)
     - portado (DIVERGENCIA 1 — sin ``self.env.context``)
   * - ``_check_not_overlapping_regular_skill`` (``:68-110``)
     - portado (DIVERGENCIA 2 — adaptado a instancia única, ver abajo)
   * - ``_get_overlapping_individual_skill`` (``:111-195``)
     - BLOQUEADO — la forma multi-vals-dict sólo tiene sentido para validar
       un lote de comandos ANTES de tocar la BD (ver DIVERGENCIA 2); su
       invariante ya está cubierta por
       ``_check_not_overlapping_regular_skill`` adaptada
   * - ``_check_date`` (``:196-206``) / ``_check_skill_type``
       (``:207-213``) / ``_check_skill_level`` (``:214-219``)
     - portados — wireados a ``clean()``
   * - ``_compute_certification_skill_type_count`` (``:220-225``)
     - portado
   * - ``_onchange_is_certification`` (``:226-231``)
     - portado (divergencia) — sin motor de ``@api.onchange``
   * - ``_compute_skill_id`` (``:232-239``) / ``_compute_skill_level_id``
       (``:240-248``)
     - portados
   * - ``_compute_display_name`` (``:249-253``)
     - portado — ``__str__``
   * - ``_onchange_valid_date`` (``:254-256``)
     - portado (divergencia) — sin motor de ``@api.onchange``
   * - ``_expire_individual_skills`` (``:257-295``)
     - BLOQUEADO — ver DIVERGENCIA 3
   * - ``_create_individual_skills`` (``:296-416``)
     - BLOQUEADO — ídem
   * - ``_write_individual_skills`` (``:417-480``)
     - BLOQUEADO — ídem
   * - ``_get_transformed_commands`` (``:481-537``)
     - BLOQUEADO — ídem

Los números de línea de esta tabla se midieron con ``grep -n`` contra el
archivo fuente citado arriba (``odoo-tools@622ddc2a``), no reconstruidos
de memoria — la primera versión de esta tabla usaba un conteo de 342
líneas para un archivo de 537; se corrigió al medirlo.

Divergencias declaradas
========================

1. **``_default_skill_type_id`` sin contexto de request.** La referencia
   decide con ``self.env.context.get('certificate_skill')`` cuál rama de
   ``search`` usar. Sin contexto de request en este ORM, el default es
   siempre "el primer tipo existente" — la rama ``certificate_skill``
   (primer tipo QUE SEA certificación) queda para quien instancie pasando
   ``skill_type=`` explícito.

2. **``_check_not_overlapping_regular_skill`` — de lote a instancia única.**
   La referencia valida N comandos ANTES de escribir ninguno (para que un
   ``create`` con varias skills nuevas se rechace atómicamente si dos de
   ellas chocan entre sí). Aquí, sin el protocolo de comandos (ver
   divergencia 3), la validación es por instancia — ``clean()`` compara
   ``self`` contra sus hermanos YA GUARDADOS del mismo ``_linked_field_
   name()``. Es la misma invariante de negocio (una sola habilidad regular
   activa por ``skill_id``; certificaciones no duplicadas por rango de
   fecha) aplicada registro a registro en vez de en lote.

3. **El protocolo de comandos x2many no existe en este ORM — bloqueo
   colectivo de las cuatro funciones de traducción.** ``_expire_
   individual_skills``, ``_create_individual_skills``,
   ``_write_individual_skills`` y ``_get_transformed_commands`` existen
   ÚNICAMENTE para traducir listas de comandos Odoo (``[(0,0,vals)]``,
   ``[(1,id,vals)]``, ``[(2,id)]``) — el mecanismo con el que Odoo escribe
   un one2many anidado desde el ``vals`` de un padre
   (``employee.write({'employee_skill_ids': [...]})``) — en OTRA lista de
   comandos que aplica archivado-no-borrado y evita duplicados. En este
   stack un one2many se escribe con llamadas directas al manager
   (``EmployeeSkill.objects.create(...)``), no con listas de comandos: no
   hay transporte que traducir. Portarlas construiría infraestructura para
   un protocolo que este ORM no tiene. El **consumidor natural** de esta
   lógica (archivar en vez de borrar una habilidad reciente; no duplicar
   una certificación) es la capa de serializer DRF que reciba el payload
   anidado — no construida en este pase (sin vistas, ver el manifest).
   Sucesor: el serializer de ``hr.employee.skill``/``hr.job.skill`` cuando
   se pida esa capa.
"""
from datetime import date

import fields
import models

from addons.base.models import TimeStampedModel
from addons.hr_skills.models.hr_skill_type import HrSkillType
from exceptions import ValidationError


def _default_skill_type():
    """≙ ``_default_skill_type_id`` (``:41-44``) — ver DIVERGENCIA 1."""
    return (HrSkillType.objects.order_by('sequence', 'name')
            .values_list('pk', flat=True).first())


def _dates_overlap(start_a, end_a, start_b, end_b):
    """¿Los intervalos ``[start_a, end_a]`` y ``[start_b, end_b]`` se
    solapan? ``end_a``/``end_b`` en ``None`` significa "sin fin" (abierto).
    Helper propio del puerto — la forma en instancia única de la
    comparación que ``_get_overlapping_individual_skill`` hacía en lote."""
    if end_a is not None and start_b > end_a:
        return False
    if end_b is not None and start_a > end_b:
        return False
    return True


class HrIndividualSkillMixin(TimeStampedModel):
    """``hr.individual.skill.mixin`` — nivel de habilidad de un individuo."""

    _name = 'hr.individual.skill.mixin'
    _description = 'Skill level'
    _order = 'skill_type_id, skill_level_id'
    _rec_name = 'skill_id'

    skill = fields.Many2one(
        'hr_skills.HrSkill', on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_skill_set',
        verbose_name='Habilidad',
        help_text='Odoo skill_id (compute+store, readonly=False, '
                  'required) — poblado por _compute_skill_id() o directo.',
    )
    skill_level = fields.Many2one(
        'hr_skills.HrSkillLevel', on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_skill_level_set',
        verbose_name='Nivel',
        help_text='Odoo skill_level_id (compute+store, readonly=False, '
                  'required) — poblado por _compute_skill_level_id() o '
                  'directo.',
    )
    skill_type = fields.Many2one(
        'hr_skills.HrSkillType', on_delete=models.CASCADE,
        default=_default_skill_type,
        related_name='%(app_label)s_%(class)s_skill_type_set',
        verbose_name='Tipo de habilidad',
    )
    valid_from = fields.Date(
        default=date.today, verbose_name='Inicio de validez',
    )
    valid_to = fields.Date(null=True, blank=True, verbose_name='Fin de validez')
    display_warning_message = fields.Boolean(
        default=False, verbose_name='Mostrar advertencia',
        help_text='Odoo display_warning_message — poblado por '
                  '_onchange_valid_date() (divergencia: sin motor de '
                  'onchange, no auto-wireado).',
    )

    class Meta:
        abstract = True

    def __str__(self):
        """≙ ``_compute_display_name`` (``:236-239``)."""
        skill_name = self.skill.name if self.skill_id else ''
        level_name = self.skill_level.name if self.skill_level_id else ''
        return f'{skill_name}: {level_name}'

    # ------------------------------------------------------------------
    # Propiedades — related/compute sin store
    # ------------------------------------------------------------------

    @property
    def level_progress(self):
        """≙ ``level_progress`` (``related='skill_level_id.level_progress'``)."""
        return self.skill_level.level_progress if self.skill_level_id else 0

    @property
    def color(self):
        """≙ ``color`` (``related='skill_type_id.color'``)."""
        return self.skill_type.color if self.skill_type_id else 0

    @property
    def levels_count(self):
        """≙ ``levels_count`` (``related='skill_type_id.levels_count'``)."""
        return self.skill_type.levels_count if self.skill_type_id else 0

    @property
    def is_certification(self):
        """≙ ``is_certification`` (``related='skill_type_id.is_certification'``)."""
        return bool(self.skill_type_id and self.skill_type.is_certification)

    @property
    def certification_skill_type_count(self):
        """≙ ``certification_skill_type_count`` — la propiedad que expone
        ``_compute_certification_skill_type_count`` (``:208-210``)."""
        return self._compute_certification_skill_type_count()

    # ------------------------------------------------------------------
    # Métodos — comportamiento por sub-modelo
    # ------------------------------------------------------------------

    def _linked_field_name(self):
        """≙ ``_linked_field_name`` (``:17-18``) — abstracto; devuelve el
        nombre del campo Django (sin ``_id``) que liga con el individuo
        (``'employee'``/``'job'``)."""
        raise NotImplementedError()

    def _get_passive_fields(self):
        """≙ ``_get_passive_fields`` (``:20-33``) — verbatim (``[]``)."""
        return []

    def _can_edit_certification_validity_period(self):
        """≙ ``_can_edit_certification_validity_period`` (``:35-39``) —
        verbatim (``True``)."""
        return True

    # ------------------------------------------------------------------
    # Validaciones — ≙ los cuatro ``@api.constrains``, wireadas a clean()
    # ------------------------------------------------------------------

    def clean(self):
        """Consolida los cuatro ``@api.constrains`` de la referencia — no
        hay motor de dependencias que los dispare por separado."""
        super().clean()
        self._check_date()
        if self.skill_type_id:
            self._check_skill_type()
            self._check_skill_level()
        self._check_not_overlapping_regular_skill()

    def _check_not_overlapping_regular_skill(self):
        """≙ ``_check_not_overlapping_regular_skill`` (``:65-105``) —
        DIVERGENCIA 2: instancia única contra sus hermanos ya guardados
        (ver docstring del módulo)."""
        if not self.skill_id:
            return
        field_name = self._linked_field_name()
        linked_id = getattr(self, f'{field_name}_id')
        siblings = (type(self).objects
                    .filter(**{field_name: linked_id, 'skill': self.skill_id})
                    .exclude(pk=self.pk))
        if self.is_certification:
            if not self._can_edit_certification_validity_period():
                return
            duplicate = siblings.filter(
                skill_level=self.skill_level_id,
                valid_from=self.valid_from, valid_to=self.valid_to,
            )
            if duplicate.exists():
                raise ValidationError(
                    'Ya existe una certificación idéntica para este '
                    'individuo (misma habilidad, nivel y periodo de '
                    'validez).',
                )
            return
        for sibling in siblings:
            if _dates_overlap(self.valid_from, self.valid_to,
                               sibling.valid_from, sibling.valid_to):
                raise ValidationError(
                    f'{self.skill.name if self.skill_id else ""} se solapa '
                    f'con una habilidad existente del {sibling.valid_from} '
                    f'al {sibling.valid_to}.',
                )

    def _check_date(self):
        """≙ ``_check_date`` (``:183-192``)."""
        if self.valid_to and self.valid_from and self.valid_from > self.valid_to:
            raise ValidationError(
                f'{self} — la fecha de fin de validez es anterior a la de '
                'inicio.',
            )

    def _check_skill_type(self):
        """≙ ``_check_skill_type`` (``:194-198``)."""
        if self.skill_id and self.skill.skill_type_id != self.skill_type_id:
            raise ValidationError(
                f'La habilidad {self.skill.name} y el tipo '
                f'{self.skill_type.name} no coinciden.',
            )

    def _check_skill_level(self):
        """≙ ``_check_skill_level`` (``:200-206``)."""
        if (self.skill_level_id
                and self.skill_level.skill_type_id != self.skill_type_id):
            raise ValidationError(
                f'El nivel {self.skill_level.name} no es válido para el '
                f'tipo de habilidad {self.skill_type.name}.',
            )

    def _compute_certification_skill_type_count(self):
        """≙ ``_compute_certification_skill_type_count`` (``:208-210``)."""
        return HrSkillType.objects.filter(is_certification=True).count()

    def _onchange_is_certification(self):
        """≙ ``_onchange_is_certification`` (``:213-217``) — DIVERGENCIA:
        sin motor de ``@api.onchange``, no auto-wireado."""
        self.valid_from = date.today()
        if not self.is_certification:
            self.valid_to = None

    def _compute_skill_id(self):
        """≙ ``_compute_skill_id`` (``:219-225``)."""
        if self.skill_type_id:
            first_skill = self.skill_type.skill_ids.order_by(
                'sequence', 'name',
            ).first()
            self.skill = first_skill
        else:
            self.skill = None
        return self.skill

    def _compute_skill_level_id(self):
        """≙ ``_compute_skill_level_id`` (``:227-234``)."""
        if not self.skill_id:
            self.skill_level = None
        else:
            levels = self.skill_type.skill_level_ids
            default = levels.filter(default_level=True).first()
            self.skill_level = default or levels.order_by('level_progress').first()
        return self.skill_level

    def _onchange_valid_date(self):
        """≙ ``_onchange_valid_date`` (``:241-243``) — DIVERGENCIA: sin
        motor de ``@api.onchange``, no auto-wireado."""
        self.display_warning_message = bool(
            self.valid_to and self.valid_from and self.valid_to < self.valid_from,
        )

    # ------------------------------------------------------------------
    # BLOQUEADO — protocolo de comandos x2many (ver DIVERGENCIA 3)
    # ------------------------------------------------------------------

    def _expire_individual_skills(self):
        """BLOQUEADO — ver DIVERGENCIA 3 del docstring del módulo."""
        raise NotImplementedError(
            'Protocolo de comandos x2many sin equivalente en este ORM — '
            'ver DIVERGENCIA 3 de hr_individual_skill_mixin.py.',
        )

    def _create_individual_skills(self, vals_list):
        """BLOQUEADO — ver DIVERGENCIA 3."""
        raise NotImplementedError(
            'Protocolo de comandos x2many sin equivalente en este ORM — '
            'ver DIVERGENCIA 3 de hr_individual_skill_mixin.py.',
        )

    def _write_individual_skills(self, commands):
        """BLOQUEADO — ver DIVERGENCIA 3."""
        raise NotImplementedError(
            'Protocolo de comandos x2many sin equivalente en este ORM — '
            'ver DIVERGENCIA 3 de hr_individual_skill_mixin.py.',
        )

    def _get_transformed_commands(self, commands, individuals):
        """BLOQUEADO — ver DIVERGENCIA 3."""
        raise NotImplementedError(
            'Protocolo de comandos x2many sin equivalente en este ORM — '
            'ver DIVERGENCIA 3 de hr_individual_skill_mixin.py.',
        )

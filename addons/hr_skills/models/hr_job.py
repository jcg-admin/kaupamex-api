"""Extensión de ``hr.job`` — las habilidades requeridas por un puesto.

Adaptación de Odoo hr_skills/models/hr_job.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3, 66 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Porte símbolo por símbolo — 3 campos + 4 métodos
==================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``job_skill_ids`` (One2many, ``:8-13``)
     - sin código — reverso automático de
       ``hr_skills.HrJobSkill.job`` (``related_name='job_skill_ids'``)
   * - ``current_job_skill_ids`` (compute+search, readonly=False,
       ``:14-19``)
     - propiedad de sólo lectura (la parte ``compute``); la parte
       ``search`` queda BLOQUEADA (ver abajo)
   * - ``skill_ids`` (Many2many, compute+store, ``:20-24``)
     - portado — columna real; recómputo ``_compute_skill_ids()``
       disponible
   * - ``_compute_current_job_skill_ids`` (``:26-31``)
     - portado — el cuerpo de la propiedad de arriba
   * - ``_search_current_job_skill_ids`` (``:33-48``)
     - BLOQUEADO — usa ``fields.Domain``, no exportado en este árbol
       (``docs: source/fields/__init__.py`` — sucesor tarea **#356**); sin
       ``Domain`` no hay con qué construir el predicado de búsqueda que
       consumiría un futuro filtro DRF sobre este campo
   * - ``_compute_skill_ids`` (``:50-53``)
     - portado
   * - ``create`` (``:55-60``) / ``write`` (``:62-66``)
     - BLOQUEADOS — protocolo de comandos x2many (ver DIVERGENCIA 3 de
       ``hr_individual_skill_mixin.py``)
"""
from datetime import date

import fields
import models

from orm.model_classes import extend_model


def _compute_current_job_skill_ids(self):
    """≙ ``_compute_current_job_skill_ids`` (``:26-30``)."""
    today = date.today()
    return self.job_skill_ids.filter(
        models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=today),
    )


def current_job_skill_ids(self):
    """≙ ``current_job_skill_ids`` — la propiedad de sólo lectura."""
    return self._compute_current_job_skill_ids()


def _compute_skill_ids(self):
    """≙ ``_compute_skill_ids`` (``:47-50``)."""
    skill_ids = list(
        self.job_skill_ids.values_list('skill_id', flat=True).distinct(),
    )
    self.skill_ids.set(skill_ids)
    return self.skill_ids


def apply_hr_skills_hr_job_extensions():
    """Cuelga sobre ``hr.job`` lo que ``hr_skills`` le añade — ≙ ``_inherit``."""
    extend_model(
        'hr', 'HrJob',
        campos={
            'skill_ids': fields.Many2many(
                'hr_skills.HrSkill', blank=True,
                related_name='jobs_with_skill',
                help_text='Odoo skill_ids (compute+store) — sincronizar '
                          'con _compute_skill_ids().',
            ),
        },
        metodos={
            '_compute_current_job_skill_ids': _compute_current_job_skill_ids,
            '_compute_skill_ids': _compute_skill_ids,
        },
        propiedades={
            'current_job_skill_ids': current_job_skill_ids,
        },
    )

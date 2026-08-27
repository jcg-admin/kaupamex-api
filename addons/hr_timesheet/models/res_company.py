"""``res.company`` — configuración de hoja de horas (Odoo ``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/res_company.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 66 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST: 1 clase (``_inherit``), 3 campos + 2 ``@api.model`` default
callbacks, 4 métodos.

Campos — 3 de 3 portados
============================

.. list-table::
   :header-rows: 1

   * - Campo de la referencia (línea)
     - Desenlace
   * - ``project_time_mode_id`` (:19-22)
     - **portado** — FK ``uom.Uom``, ``default=_default_hours_uom``
   * - ``timesheet_encode_uom_id`` (:23-24)
     - **portado** — ídem
   * - ``internal_project_id`` (:25-29)
     - **portado** — FK ``project.Project``

``_default_project_time_mode_id``/``_default_timesheet_encode_uom_id``
(:11-17) — **divergencia de mecanismo**: la referencia resuelve
``self.env.ref('uom.product_uom_hour')`` (búsqueda por xmlid, sesión). Aquí
se busca por ``name='Hours'`` directo sobre ``uom.Uom`` — sin sesión ni
mecanismo de xmlid. Si la fila semilla no existe todavía (medido: ``grep
-rn "'Hours'" addons/uom/migrations/`` → 0 hits, el seed de UOM de tiempo es
data pendiente, no de este addon), el default resuelve ``None`` — el campo
es ``null=True``, así que no rompe la migración.

Métodos — desenlace por símbolo
==================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Desenlace
   * - ``_check_internal_project_id_company`` (:31-34)
     - **portado** — ``clean()``, misma validación (el proyecto interno
       debe pertenecer a la misma compañía).
   * - ``create`` (:36-42)
     - **BLOQUEADO** — llama a ``_create_internal_project_task`` en cada
       alta de compañía; ver el siguiente símbolo.
   * - ``_create_internal_project_task`` (:44-66)
     - **BLOQUEADO** — crea un proyecto + dos tareas semilla
       (``env.ref`` para el stage, ``sudo()``, ``with_company``); es
       provisión de datos de alta de compañía, no esquema. Sucesor: si
       ``hr_timesheet`` necesita auto-provisión de proyecto interno, se
       implementa como comando de gestión (``kaupamex-bin``), no como
       hook de modelo — mismo criterio que el resto del árbol para
       seed data (ver ``BOOTSTRAP_COMPANY_CODE``/``company_create`` en
       ``.claude/CLAUDE.md``).
"""
import fields
import models

from addons.base.models import ResCompany
from addons.project.models import Project
from addons.uom.models import Uom
from exceptions import ValidationError
from orm.method_chain import chain_method


def _add_if_absent(model, name, field):
    """Idéntico al de ``models/hr_timesheet.py`` de este mismo addon."""
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def _default_hours_uom():
    """≙ ``_default_project_time_mode_id``/``_default_timesheet_encode_uom_id``
    (``odoo19c: hr_timesheet/models/res_company.py:11-17``) — ver divergencia
    en el docstring del módulo."""
    return Uom.objects.filter(name='Hours').first()


def _check_internal_project_id_company(self):
    """≙ ``_check_internal_project_id_company`` (``odoo19c: :31-34``)."""
    if self.internal_project_id and self.internal_project_id.company_id \
            and self.internal_project_id.company_id != self:
        raise ValidationError({
            'internal_project_id': 'El proyecto interno de una compañía '
                                    'debe pertenecer a esa compañía.',
        })


def apply_hr_timesheet_res_company_extensions():
    """Cuelga los 3 campos + ``clean()`` sobre ``base.ResCompany``.

    La llama ``HrTimesheetConfig.ready()``.
    """
    _add_if_absent(ResCompany, 'project_time_mode_id', fields.Many2one(
        Uom, on_delete=models.SET_NULL, null=True, blank=True,
        default=_default_hours_uom, related_name='+',
        help_text='Odoo project_time_mode_id. Unidad de tiempo usada en '
                  'proyectos y tareas.',
    ))
    _add_if_absent(ResCompany, 'timesheet_encode_uom_id', fields.Many2one(
        Uom, on_delete=models.SET_NULL, null=True, blank=True,
        default=_default_hours_uom, related_name='+',
        help_text='Odoo timesheet_encode_uom_id. Unidad de captura de la '
                  'hoja de horas.',
    ))
    _add_if_absent(ResCompany, 'internal_project_id', fields.Many2one(
        Project, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
        help_text='Odoo internal_project_id. Proyecto por defecto para la '
                  'hoja de horas generada desde ausencias.',
    ))

    chain_method(ResCompany, 'clean', _check_internal_project_id_company)

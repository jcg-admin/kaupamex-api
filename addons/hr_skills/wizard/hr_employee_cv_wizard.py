"""``hr.employee.cv.wizard`` — asistente "Imprimir CV".

Adaptación de Odoo hr_skills/wizard/hr_employee_cv_wizard.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 44 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla
==========================================================

Mismo criterio que ``addons/account_debit_note/wizard/
account_debit_note.py`` (ver su docstring): el estado del wizard no vive en
una fila — lo pasa el llamador como parámetros.

Porte símbolo por símbolo — 8 campos + 2 métodos
==================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``employee_ids`` / ``color_primary`` / ``color_secondary`` /
       ``show_skills`` / ``show_contact`` / ``show_others`` (``:13-20``)
     - portados — parámetros de ``compute_can_show_others``/``build_cv_url``
   * - ``can_show_others`` / ``can_show_skills`` (compute, ``:22-23``)
     - portados — ``compute_can_show_others(employees)``
   * - ``_compute_can_show_others`` (``:25-29``)
     - portado — el cuerpo de ``compute_can_show_others``
   * - ``action_validate`` (``:31-44``)
     - portado PARCIAL — la URL se construye (``build_cv_url``); el
       ``ir.actions.act_url`` que la envuelve queda BLOQUEADO (acción de
       cliente Odoo, familia (b)) y además su destino (``/print/cv``, motor
       de reporte PDF) está fuera de scope de este pase (sin ``report/``,
       ver el manifest)

Divergencia declarada — ``werkzeug.urls.url_encode`` → ``urllib.parse``
==========================================================================

``werkzeug`` NO es dependencia del proyecto (medido: ``grep -i werkzeug
uv.lock`` → 0 hits). ``urllib.parse.urlencode`` (stdlib) es el sustituto
directo — misma codificación de query string.
"""
from urllib.parse import urlencode

from addons.hr_skills.models.hr_resume_line import HrResumeLine
from orm.models_transient import TransientModel


class HrEmployeeCvWizard(TransientModel):
    """Asistente "Imprimir CV" — ≙ ``hr.employee.cv.wizard``.

    Sin tabla (``TransientModel``, ``managed = False``): el estado del
    wizard lo pasa el llamador como argumentos de los classmethods.
    """

    class Meta:
        abstract = True
        managed = False

    #: ≙ los defaults de ``color_primary``/``color_secondary`` (``:13-14``)
    #: cuando no hay ``company`` con los suyos propios.
    DEFAULT_COLOR = '#666666'

    @classmethod
    def compute_can_show_others(cls, employees):
        """≙ ``_compute_can_show_others`` (``:23-27``) — DIVERGENCIA de
        firma: la referencia asigna dos campos del wizard vía
        ``@api.depends``; aquí devuelve un ``dict`` con ambos, recibiendo
        el queryset de empleados como argumento."""
        return {
            'can_show_others': HrResumeLine.objects.filter(
                employee__in=employees, line_type__isnull=True,
            ).exists(),
            'can_show_skills': any(
                employee.skill_ids.exists() for employee in employees
            ),
        }

    @classmethod
    def build_cv_url(cls, employees, color_primary=None, color_secondary=None,
                      show_skills=True, show_contact=True, show_others=True,
                      company=None):
        """≙ la construcción de URL dentro de ``action_validate``
        (``:29-40``) — la parte con lógica real; el ``ir.actions.act_url``
        que la envuelve queda BLOQUEADO (ver la tabla del docstring del
        módulo)."""
        color_primary = color_primary or (
            company.primary_color if company is not None else None
        ) or cls.DEFAULT_COLOR
        color_secondary = color_secondary or (
            company.secondary_color if company is not None else None
        ) or cls.DEFAULT_COLOR
        params = {
            'employee_ids': ','.join(str(e.pk) for e in employees),
            'color_primary': color_primary,
            'color_secondary': color_secondary,
        }
        if show_skills:
            params['show_skills'] = 1
        if show_contact:
            params['show_contact'] = 1
        if show_others:
            params['show_others'] = 1
        return '/print/cv?' + urlencode(params)

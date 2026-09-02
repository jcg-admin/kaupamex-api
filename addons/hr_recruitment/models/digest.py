"""``digest.digest`` — el KPI de nuevos empleados en el correo periódico
(Odoo ``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/digest.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 26 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 2 de 4 símbolos
====================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``kpi_hr_recruitment_new_colleagues`` (``:9``)
     - portado
   * - ``kpi_hr_recruitment_new_colleagues_value`` (``:10``)
     - BLOQUEADO — su ``compute`` depende del símbolo siguiente
   * - ``_compute_kpi_hr_recruitment_new_colleagues_value`` (``:12-17``)
     - BLOQUEADO por ``_compute_kpi_hr_recruitment_new_colleagues_value``
       sin portar — trabajo no hecho (tarea #159), no la divergencia que esta
       tabla decía. Delega en
       ``_calculate_company_based_kpi``, que a esta fecha SÍ existe en
       ``addons.digest.models.digest.DigestDigest`` (lo portó
       ``addons/crm/models/digest.py`` — ver su sección "Lo que este
       porte DESBLOQUEÓ"); la premisa de que era "divergencia de
       mecanismo, no portado" quedó stale. Lo que sigue faltando es que
       alguien escriba y cuelgue el compute — trabajo no hecho, no
       ausencia de mecanismo. Sucesor: tarea **#159**.
   * - ``_compute_kpis_actions`` (``:19-22``)
     - portado — ``overrides=`` (:mod:`orm.method_chain`) sobre el
       ``_compute_kpis_actions`` base, portado en el mismo pase (tarea
       #158, ``addons/digest/models/digest.py``).

Sólo se portan la columna booleana y el gancho de acciones — el valor
calculado del KPI queda para la tarea #159 (arriba).
"""
import fields
from orm.model_classes import extend_model

#: El xml_id que la fuente concatena con ``?menu_id=<id>`` — aquí sin
#: resolver, misma forma que ``addons/crm/models/digest.py`` y el docstring
#: del método base en ``addons/digest/models/digest.py`` declaran.
ACTION_OPEN_MY_EMPLOYEES = 'hr.open_view_employee_list_my'


def _compute_kpis_actions(self, previous, company, user):
    """≙ ``_compute_kpis_actions`` de ``hr_recruitment`` (``:19-22``).

    Encadena con ``previous`` —el ``_compute_kpis_actions`` base, hoy
    ``{}`` (o lo que ``crm`` ya haya añadido, según el orden de
    ``INSTALLED_APPS``: las dos extensiones añaden claves distintas y
    conmutan)— y agrega la única clave de este addon.
    """
    res = previous(company, user)
    res['kpi_hr_recruitment_new_colleagues'] = ACTION_OPEN_MY_EMPLOYEES
    return res


def apply_hr_recruitment_digest_extensions():
    """Cuelga sobre ``digest.digest`` lo que ``hr_recruitment`` le añade —
    ≙ ``_inherit`` (parcial declarado, ver docstring del módulo).

    ``_compute_kpis_actions`` va por ``overrides=``
    (:func:`orm.method_chain.wrap_method`): necesita el diccionario que la
    implementación previa ya devolvió, para agregarle su clave.
    """
    extend_model(
        'digest', 'DigestDigest',
        campos={
            'kpi_hr_recruitment_new_colleagues': fields.Boolean(
                default=False, verbose_name='Nuevos empleados',
                help_text='Odoo kpi_hr_recruitment_new_colleagues ("New '
                          'Employees"). Su valor calculado '
                          '(kpi_hr_recruitment_new_colleagues_value) queda '
                          'BLOQUEADO por '
                          '``_compute_kpi_hr_recruitment_new_colleagues_value`` '
                          '-- tarea #159, ver docstring del módulo.',
            ),
        },
        overrides={
            '_compute_kpis_actions': _compute_kpis_actions,
        },
    )

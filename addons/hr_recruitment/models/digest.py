"""``digest.digest`` — el KPI de nuevos empleados en el correo periódico
(Odoo ``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/digest.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 26 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte — 4 de 4 símbolos, 0 bloqueados
======================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``kpi_hr_recruitment_new_colleagues`` (``:9``)
     - portado — columna ``Boolean`` (migración ``digest/0003``)
   * - ``kpi_hr_recruitment_new_colleagues_value`` (``:10``)
     - portado — ``compute`` sin ``store`` → campo no persistido; lo
       sirve su ``_compute_…_value`` vía ``compute_kpi_value``
   * - ``_compute_kpi_hr_recruitment_new_colleagues_value`` (``:12-17``)
     - portado — delega en
       ``_calculate_company_based_kpi('hr.employee', …)``
       (tarea #159; hasta ella este archivo lo declaraba bloqueado por una
       causa que ya no existía, ver :ref:`h-api-1012`)
   * - ``_compute_kpis_actions`` (``:19-22``)
     - portado — ``overrides=`` (:mod:`orm.method_chain`) sobre el
       ``_compute_kpis_actions`` base (tarea #158)

Divergencias declaradas — de forma, no de alcance
=================================================

- **El compute recibe ``(start, end)`` y devuelve el valor.** La fuente
  escribe ``digest[campo]`` a través de
  ``_calculate_company_based_kpi``; aquí
  ese genérico devuelve el conteo y ``compute_kpi_value``
  (``addons/digest/models/digest.py``) es quien despacha — el mismo contrato
  que ``crm`` y ``account`` cumplen.
- **``_compute_kpis_actions`` no resuelve ``?menu_id=<id>``:** el xml_id va
  sin resolver, como en ``crm`` y ``account`` (sin cliente web de Odoo no hay
  menú que resolver).
- **La guarda de grupo levanta ``AccessError`` igual que la fuente**, con el
  mismo identificador externo y mensaje; si el grupo no está sembrado,
  ``has_group`` es falso y la guarda niega — fail-closed.
"""
import fields
from exceptions import AccessError
from orm.environments import get_current_user
from orm.model_classes import extend_model
from tools.translate import _

#: El identificador externo que la fuente consulta, verbatim (``:13``).
GROUP_HR_RECRUITMENT_USER = 'hr_recruitment.group_hr_recruitment_user'

#: El xml_id que la fuente concatena con ``?menu_id=<id>`` — aquí sin
#: resolver, misma forma que ``addons/crm/models/digest.py`` y el docstring
#: del método base en ``addons/digest/models/digest.py`` declaran.
ACTION_OPEN_MY_EMPLOYEES = 'hr.open_view_employee_list_my'



def _compute_kpi_hr_recruitment_new_colleagues_value(self, start, end):
    """≙ ``_compute_kpi_hr_recruitment_new_colleagues_value`` (``:12-17``).

    Empleados creados en la ventana, acotados a la compañía del digest —
    el genérico ``_calculate_company_based_kpi`` sobre ``hr.employee``. La
    guarda de grupo y su mensaje son verbatim de la fuente.
    """
    user = get_current_user()
    if not (user is not None and user.has_group(GROUP_HR_RECRUITMENT_USER)):
        raise AccessError(
            _("Do not have access, skip this data for user's digest email"))
    return self._calculate_company_based_kpi('hr.employee', start, end)

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
    ≙ ``_inherit``.

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
                          'Employees").',
            ),
            'kpi_hr_recruitment_new_colleagues_value': fields.Integer(
                store=False, null=True, blank=True,
                verbose_name='Nuevos empleados (valor)',
                help_text='Odoo kpi_hr_recruitment_new_colleagues_value — '
                          'compute sin store; lo sirve '
                          '_compute_kpi_hr_recruitment_new_colleagues_value.',
            ),
        },
        metodos={
            '_compute_kpi_hr_recruitment_new_colleagues_value':
                _compute_kpi_hr_recruitment_new_colleagues_value,
        },
        overrides={
            '_compute_kpis_actions': _compute_kpis_actions,
        },
    )

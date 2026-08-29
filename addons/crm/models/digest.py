"""``digest.digest`` — los dos KPIs de CRM en el correo periódico (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/crm/models/digest.py`` (LGPL-3, 38 líneas) —
atribución y aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 6 de 7 símbolos
=================================

(7 = 3 métodos + 4 campos.)

.. list-table::
   :header-rows: 1
   :widths: 44 12 44

   * - Símbolo
     - Estado
     - Nota
   * - ``kpi_crm_lead_created`` (``:11``)
     - portado
     - columna ``Boolean``, como sus hermanos de ``digest``
   * - ``kpi_crm_lead_created_value`` (``:12``)
     - portado
     - ``compute`` sin ``store`` → lo sirve su ``_compute_…_value``
   * - ``kpi_crm_opportunities_won`` (``:13``)
     - portado
     - columna ``Boolean``
   * - ``kpi_crm_opportunities_won_value`` (``:14``)
     - portado
     - ídem
   * - ``_compute_kpi_crm_lead_created_value`` (``:16``)
     - portado
     - delega en ``_calculate_company_based_kpi``
   * - ``_compute_kpi_crm_opportunities_won_value`` (``:22``)
     - portado
     - ídem, con ``date_field`` y dominio adicional
   * - ``_compute_kpis_actions`` (``:33``)
     - BLOQUEADO por ``_compute_kpis_actions`` — ``addons.digest`` lo lista
       entre los símbolos pendientes de integrar (punto 7 de su docstring),
       así que no hay eslabón previo del que relevarse. Sucesor: **#158**.

Lo que este porte DESBLOQUEÓ
============================

``_calculate_company_based_kpi`` y ``_get_company_field`` **no existían** en
``addons.digest``: su docstring los declaraba divergencia de mecanismo porque
los dos KPIs base (``ResUsersLog``, ``MailMessage``) no tienen FK a compañía y
se acotaban por el usuario. Esa razón **no aplica a ``crm.lead``**, que declara
``company_id`` directo, así que el genérico se portó en el mismo pase
(``addons/digest/models/digest.py``) en vez de declararse bloqueado aquí.

Efecto lateral medido: con el genérico portado, el KPI de
``hr_recruitment/models/digest.py`` deja de estar bloqueado por él — su
docstring todavía lo cita como causa de dos de sus tres aristas. Cerrarlo es
la tarea **#159**.

Divergencias declaradas
=======================

- **La guarda de grupo levanta ``AccessError`` igual que la fuente**, con el
  mismo identificador externo. ``sales_team.group_sale_salesman`` todavía no
  está sembrado (la siembra pertenece a la migración de ``sales_team``, ver
  ``src/addons/base/data/res_groups_data.py``), así que hoy la guarda niega
  siempre — fail-closed, el desenlace correcto de un permiso que no se puede
  afirmar. Sucesor: tarea **#157**.
- **``probability = '100'`` se compara como número.** La fuente escribe la
  cadena ``'100'`` en su dominio y su motor la coacciona; aquí el campo es
  numérico y el filtro va con el valor numérico. Mismo conjunto.
"""
from exceptions import AccessError
from orm.environments import get_current_user
from orm.model_classes import extend_model
from tools.translate import _

import fields

#: El identificador externo que la fuente consulta, verbatim.
GROUP_SALE_SALESMAN = 'sales_team.group_sale_salesman'


def _assert_salesman():
    """≙ el ``if not … raise AccessError`` de los dos computes (``:17-18``).

    Mensaje verbatim de la fuente.
    """
    user = get_current_user()
    if not (user is not None and user.has_group(GROUP_SALE_SALESMAN)):
        raise AccessError(
            _("Do not have access, skip this data for user's digest email"))


def _compute_kpi_crm_lead_created_value(self, start, end):
    """≙ ``_compute_kpi_crm_lead_created_value`` (``:16-20``)."""
    _assert_salesman()
    return self._calculate_company_based_kpi('crm.lead', start, end)


def _compute_kpi_crm_opportunities_won_value(self, start, end):
    """≙ ``_compute_kpi_crm_opportunities_won_value`` (``:22-31``).

    ``date_field='date_closed'`` y el dominio adicional
    ``type='opportunity'`` + ``probability=100``, como la fuente.
    """
    _assert_salesman()
    return self._calculate_company_based_kpi(
        'crm.lead', start, end,
        date_field='date_closed',
        additional_domain={'type': 'opportunity', 'probability': 100},
    )


def apply_crm_extensions():
    """Cuelga los cuatro campos y los dos computes. La llama ``CrmConfig.ready()``."""
    extend_model(
        'digest', 'DigestDigest',
        campos={
            'kpi_crm_lead_created': fields.Boolean(
                default=False, verbose_name='Nuevas iniciativas',
                help_text='Odoo kpi_crm_lead_created ("New Leads").',
            ),
            'kpi_crm_opportunities_won': fields.Boolean(
                default=False, verbose_name='Oportunidades ganadas',
                help_text='Odoo kpi_crm_opportunities_won '
                          '("Opportunities Won").',
            ),
        },
        metodos={
            '_compute_kpi_crm_lead_created_value':
                _compute_kpi_crm_lead_created_value,
            '_compute_kpi_crm_opportunities_won_value':
                _compute_kpi_crm_opportunities_won_value,
        },
    )

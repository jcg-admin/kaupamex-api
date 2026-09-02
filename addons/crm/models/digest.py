"""``digest.digest`` — los dos KPIs de CRM en el correo periódico (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/crm/models/digest.py`` (LGPL-3, 38 líneas) —
atribución y aviso de licencia preservados (DEC-KX-03).

Porte — 7 de 7 símbolos, 0 bloqueados
======================================

(7 = 3 métodos + 4 campos.) ``_compute_kpis_actions`` se desbloqueó al
portarse el método base — ver la tarea #158 en ``addons/digest/models/
digest.py``.

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
   * - ``_compute_kpis_actions`` (``:33-38``)
     - portado
     - ``overrides=`` (:mod:`orm.method_chain`) — cuelga sobre el
       ``_compute_kpis_actions`` base, que ya existe (tarea #158)

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
- **``_compute_kpis_actions`` no resuelve ``?menu_id=<id>``.** La fuente
  concatena el id de ``crm.crm_menu_root`` (``self.env.ref(...).id``)
  porque el correo enlaza al cliente web de Odoo, que resuelve el menú al
  navegar. Este árbol no tiene ese cliente: el valor es el xml_id **sin
  resolver**, misma forma que ``CrmLostReason.action_lost_leads`` y
  ``UtmCampaign.action_redirect_to_leads_opportunities`` ya usan (ver el
  docstring del método base en ``addons/digest/models/digest.py``).
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


#: El grupo que abre la vista de todos los leads en vez de sólo el pipeline.
GROUP_USE_LEAD = 'crm.group_use_lead'

#: Los dos xml_id que la fuente concatena con ``?menu_id=...`` — aquí sin
#: resolver (ver la divergencia declarada arriba).
ACTION_PIPELINE = 'crm.crm_lead_action_pipeline'
ACTION_ALL_LEADS = 'crm.crm_lead_all_leads'


def _compute_kpis_actions(self, previous, company, user):
    """≙ ``_compute_kpis_actions`` de ``crm`` (``:33-38``).

    Encadena con ``previous`` —el ``_compute_kpis_actions`` base, hoy
    ``{}``— y añade las dos claves de este addon: el mismo xml_id sin
    resolver para ambas, salvo que ``user`` pertenezca a
    ``crm.group_use_lead``, en cuyo caso el KPI de leads apunta a la vista
    de todos los leads en vez de sólo al pipeline. Usa ``user`` —el
    parámetro, no ``get_current_user()``— porque es exactamente lo que
    hace la fuente (``user.has_group(...)``, no ``self.env.user``): el
    destinatario del correo puede no ser el actor de la sesión.
    """
    res = previous(company, user)
    res['kpi_crm_lead_created'] = ACTION_PIPELINE
    res['kpi_crm_opportunities_won'] = ACTION_PIPELINE
    if user is not None and user.has_group(GROUP_USE_LEAD):
        res['kpi_crm_lead_created'] = ACTION_ALL_LEADS
    return res


def apply_crm_extensions():
    """Cuelga los cuatro campos, los dos computes y la acción.

    La llama ``CrmConfig.ready()``. ``_compute_kpis_actions`` va por
    ``overrides=`` (:func:`orm.method_chain.wrap_method`) — necesita el
    diccionario que la implementación previa ya devolvió, para mutarlo, no
    un resultado con el que combinar el propio.
    """
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
        overrides={
            '_compute_kpis_actions': _compute_kpis_actions,
        },
    )

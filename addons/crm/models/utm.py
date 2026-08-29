"""``utm.campaign`` — lo que ``crm`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/crm/models/utm.py`` (LGPL-3, 30 líneas) —
atribución y aviso de licencia preservados (DEC-KX-03).

Cobertura: 3 métodos + 2 campos — **3 portados, 0 bloqueados**
=============================================================

.. list-table::
   :header-rows: 1
   :widths: 34 12 54

   * - Símbolo
     - Estado
     - Nota
   * - ``use_leads`` (campo, ``:10``)
     - portado
     - ``compute`` sin ``store`` → ``property`` (``extend_model(propiedades=)``)
   * - ``crm_lead_count`` (campo, ``:11``)
     - portado
     - ídem; su ``groups=`` es la guarda del compute, ver abajo
   * - ``_compute_use_leads`` (``:13``)
     - portado
     -
   * - ``_compute_crm_lead_count`` (``:16``)
     - portado
     - ``_read_group`` → ``values_list().annotate(Count())``
   * - ``action_redirect_to_leads_opportunities`` (``:24``)
     - portado
     - devuelve el ``act_window`` con el XML ID, sin resolverlo

Divergencias declaradas
=======================

- **Los dos campos son ``property``, no columna.** La fuente los declara
  ``compute=`` sin ``store=True``: se calculan al leerlos y no ocupan columna.
  Es la vía que ``extend_model(propiedades=…)`` existe para expresar, y la que
  ya usan ``account_edi_ubl_cii`` y ``crm_lost_reason``.
- **``groups='sales_team.group_sale_salesman'`` se porta como guarda de
  lectura, no como metadata del campo.** Allá el ORM oculta el campo a quien
  no está en el grupo; aquí una ``property`` no tiene esa capa, así que la
  comprobación entra en el cuerpo — ``has_group`` decide, con el mismo
  identificador externo.
- **El grupo todavía no está sembrado.** ``sales_team.group_sale_salesman`` no
  tiene fila: la siembra pertenece a la migración de ``sales_team``, como
  declara ``src/addons/base/data/res_groups_data.py``. Mientras tanto
  ``has_group`` devuelve ``False`` y el conteo sale 0 — fail-closed, que es el
  desenlace correcto de un permiso que no se puede afirmar. Sucesor: tarea
  **#157**.
- **``_for_xml_id`` no se resuelve.** ``action_redirect_to_leads_opportunities``
  devuelve el diccionario con la clave ``xml_id`` en vez del ``act_window``
  materializado: sin las vistas XML de la fuente no hay ventana que abrir. Es
  la misma forma que ``CrmLostReason.action_lost_leads`` y
  ``CrmLead.action_schedule_meeting`` ya usan en este addon.
"""
from django.db.models import Count

import models

from orm.environments import get_current_user
from orm.model_classes import extend_model
from tools.translate import _

#: Los dos identificadores externos que la fuente consulta, verbatim.
GROUP_SALE_SALESMAN = 'sales_team.group_sale_salesman'
GROUP_USE_LEAD = 'crm.group_use_lead'


def _user_has_group(ext_id):
    """¿El usuario en contexto pertenece a ese grupo?

    ``False`` sin usuario en contexto — cron, migración o test sin sesión. La
    fuente no tiene ese caso porque ``self.env.user`` siempre existe; aquí es
    la misma lectura fail-closed que ``utm_mixin`` ya declara.
    """
    user = get_current_user()
    return bool(user is not None and user.has_group(ext_id))


def _compute_use_leads(self):
    """≙ ``_compute_use_leads`` (``:13-14``)."""
    return _user_has_group(GROUP_USE_LEAD)


def _compute_crm_lead_count(self):
    """≙ ``_compute_crm_lead_count`` (``:16-22``).

    La fuente agrupa con ``_read_group`` sobre ``crm.lead`` con
    ``active_test=False``; aquí el agrupamiento es
    ``values_list().annotate(Count())`` y el ``active_test=False`` se expresa
    no filtrando por ``active`` — este ORM no oculta los archivados.

    Sobre ``self``, no sobre el lote: la fuente reparte el resultado entre las
    campañas de ``self.ids``; una ``property`` se lee de una en una.
    """
    if not _user_has_group(GROUP_SALE_SALESMAN):
        return 0
    CrmLead = models.apps.get_model('crm', 'CrmLead')
    grouped = dict(CrmLead.objects.filter(campaign_id=self.pk)
                   .values_list('campaign_id')
                   .annotate(n=Count('pk')))
    return grouped.get(self.pk, 0)


def action_redirect_to_leads_opportunities(self):
    """≙ ``action_redirect_to_leads_opportunities`` (``:24-30``)."""
    view = 'crm.crm_lead_all_leads' if self.use_leads else 'crm.crm_lead_opportunities'
    return {
        'name': _('Iniciativas'),
        'type': 'ir.actions.act_window',
        'xml_id': view,
        'res_model': 'crm.lead',
        'view_mode': 'list,kanban,graph,pivot,form,calendar',
        'domain': [('campaign_id', 'in', [self.pk])],
        'context': {'active_test': False, 'create': False},
    }


def apply_crm_extensions():
    """Cuelga los dos campos y la acción. La llama ``CrmConfig.ready()``."""
    extend_model(
        'utm.campaign',
        propiedades={
            'use_leads': _compute_use_leads,
            'crm_lead_count': _compute_crm_lead_count,
        },
        metodos={
            '_compute_use_leads': _compute_use_leads,
            '_compute_crm_lead_count': _compute_crm_lead_count,
            'action_redirect_to_leads_opportunities':
                action_redirect_to_leads_opportunities,
        },
    )

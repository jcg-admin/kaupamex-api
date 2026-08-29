"""``res.partner`` — lo que ``crm`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/crm/models/res_partner.py`` (LGPL-3, 61
líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

Cobertura: 5 métodos + 2 campos — **7 portados, 0 bloqueados**
=============================================================

.. list-table::
   :header-rows: 1
   :widths: 40 12 48

   * - Símbolo
     - Estado
     - Nota
   * - ``opportunity_ids`` (campo, ``:8``)
     - portado
     - ``One2many`` inverso → ``property`` sobre el ``related_name``
   * - ``opportunity_count`` (campo, ``:9``)
     - portado
     - ``compute`` sin ``store`` → ``property``
   * - ``_fetch_children_partners_for_hierarchy`` (``:15``)
     - portado
     - ``child_of`` → recorrido por niveles, como ``BasePartnerMerge``
   * - ``_get_contact_opportunities_domain`` (``:22``)
     - portado
     -
   * - ``_compute_opportunity_count`` (``:25``)
     - portado
     - ``_read_group`` → ``values_list().annotate(Count())``
   * - ``_compute_application_statistics_hook`` (``:39``)
     - portado
     - ``chain_method`` con ``combine=``: la fuente hace ``super()`` y **suma**
   * - ``action_view_opportunity`` (``:49``)
     - portado
     - devuelve el ``act_window`` con su XML ID, sin resolverlo

Divergencias declaradas
=======================

- **``opportunity_ids`` no declara columna.** Es el lado inverso de
  ``CrmLead.partner_id``, y en Django ese lado ya existe como ``related_name``.
  La ``property`` sólo le da el nombre de la fuente y el filtro
  ``type='opportunity'`` que su ``domain=`` fija.
- **``_fetch_children_partners_for_hierarchy`` recorre por niveles.** La
  fuente resuelve ``child_of`` con el operador de su motor de dominios, que en
  ``res.partner`` se apoya en ``parent_path`` (allá el modelo es
  ``_parent_store``). Aquí ``ResPartner`` **no declara ``parent_path``**
  —medido: ``parent_path`` está en ``ResPartnerCategory``, no en
  ``ResPartner``— así que el descendiente sale del mismo recorrido por niveles
  que ``BasePartnerMerge._descendant_ids`` ya usa para este mismo ``child_of``
  (``src/addons/base/wizard/base_partner_merge.py:648-667``). Mismo conjunto,
  distinto camino; se reusa la forma ya establecida en vez de inventar una
  segunda.
- **``groups='sales_team.group_sale_salesman'`` es guarda de cuerpo**, no
  metadata del campo — misma razón y mismo sucesor que en ``utm.py``: el grupo
  no está sembrado todavía, ``has_group`` devuelve ``False`` y el conteo sale
  0. Tarea **#157**.
- **``_for_xml_id`` no se resuelve** en ``action_view_opportunity``: sin las
  vistas XML de la fuente no hay ventana que materializar, así que se devuelve
  el XML ID. El ``sorted`` que la fuente aplica a ``action['views']`` para
  poner la lista primero no tiene objeto sin esas vistas, y por eso no se
  transcribe: sería ordenar una lista vacía.
"""
from django.db.models import Count

import models
from orm.environments import get_current_user
from orm.method_chain import chain_method
from orm.model_classes import extend_model
from tools.translate import _

from addons.base.models.res_partner import ResPartner

#: ≙ la cabecera que la fuente declara en su clase (la extensión aquí no es clase).
_inherit = 'res.partner'

#: El identificador externo que la fuente consulta, verbatim.
GROUP_SALE_SALESMAN = 'sales_team.group_sale_salesman'


def _user_is_salesman():
    """¿El usuario en contexto es vendedor? ``False`` sin usuario (fail-closed)."""
    user = get_current_user()
    return bool(user is not None and user.has_group(GROUP_SALE_SALESMAN))


def _fetch_children_partners_for_hierarchy(self):
    """≙ ``_fetch_children_partners_for_hierarchy`` (``:15-20``).

    Devuelve ``self`` y toda su descendencia. La fuente lo hace con
    ``child_of`` y ``active_test=False``; aquí el recorrido es por niveles (ver
    la divergencia del docstring del módulo) y los archivados ya entran porque
    este ORM no los oculta.

    La ``exclude(pk__in=seen)`` no es defensiva de más: corta el ciclo si la
    jerarquía tuviera uno, igual que en ``BasePartnerMerge``.
    """
    model = type(self)
    seen = {self.pk}
    frontier = [self.pk]
    while frontier:
        children = list(model.objects
                        .filter(parent_id__in=frontier)
                        .exclude(pk__in=seen)
                        .values_list('pk', flat=True))
        if not children:
            break
        seen.update(children)
        frontier = children
    return model.objects.filter(pk__in=seen)


def _get_contact_opportunities_domain(self):
    """≙ ``_get_contact_opportunities_domain`` (``:22-23``)."""
    ids = list(self._fetch_children_partners_for_hierarchy()
               .values_list('pk', flat=True))
    return [('partner_id', 'in', ids)]


def _compute_opportunity_count(self):
    """≙ ``_compute_opportunity_count`` (``:25-37``).

    La fuente agrupa por ``partner_id`` y **sube por el árbol** sumando a cada
    ancestro que esté en el lote. Aquí el lote es un solo partner, así que el
    ascenso se colapsa en su equivalente exacto: contar las oportunidades de él
    y de toda su descendencia, que es lo mismo que la suma que la fuente hace.
    """
    if not _user_is_salesman():
        return 0
    CrmLead = models.apps.get_model('crm', 'CrmLead')
    ids = list(self._fetch_children_partners_for_hierarchy()
               .values_list('pk', flat=True))
    grouped = CrmLead.objects.filter(partner_id__in=ids).aggregate(n=Count('pk'))
    return grouped['n'] or 0


def _opportunity_ids(self):
    """≙ el campo ``opportunity_ids`` (``:8``), con su ``domain=`` aplicado."""
    CrmLead = models.apps.get_model('crm', 'CrmLead')
    return CrmLead.objects.filter(partner_id=self.pk, type='opportunity')


def _compute_application_statistics_hook(cls, partners):
    """≙ ``_compute_application_statistics_hook`` (``:39-47``).

    Aporta la estadística de oportunidades de cada partner que tenga alguna.
    Recibe ``partners`` y devuelve ``{pk: [estadística, …]}`` — la firma que
    este árbol declara para el enganche (divergencia de ``base``, no de aquí).
    """
    aportado = {}
    if not _user_is_salesman():
        return aportado
    for partner in partners:
        count = partner.opportunity_count
        if count:
            aportado[partner.pk] = [{
                'iconClass': 'fa-star',
                'value': count,
                'label': _('Oportunidades'),
                'tagClass': 'o_tag_color_8',
            }]
    return aportado


def _merge_application_statistics(nuevo, anterior):
    """``combine`` del enganche: funde lo aportado con lo que ya había.

    La fuente escribe ``data_list = super()...`` y luego hace ``append`` sobre
    la lista de cada partner. Aquí el eslabón previo devuelve su propio mapa y
    esta función los funde, que es la misma suma expresada sin mutación.
    """
    fundido = dict(anterior or {})
    for pk, stats in (nuevo or {}).items():
        fundido.setdefault(pk, [])
        fundido[pk] = list(fundido[pk]) + list(stats)
    return fundido


def action_view_opportunity(self):
    """≙ ``action_view_opportunity`` (``:49-61``)."""
    return {
        'name': _('Oportunidades'),
        'type': 'ir.actions.act_window',
        'xml_id': 'crm.crm_lead_opportunities',
        'res_model': 'crm.lead',
        'context': {
            'search_default_filter_won': 1,
            'search_default_filter_ongoing': 1,
            'search_default_filter_lost': 1,
        },
        'domain': [('active', 'in', [True, False])]
                  + self._get_contact_opportunities_domain(),
    }


def apply_crm_extensions():
    """Cuelga los dos campos y los métodos. La llama ``CrmConfig.ready()``."""
    extend_model(
        _inherit,
        propiedades={
            'opportunity_ids': _opportunity_ids,
            'opportunity_count': _compute_opportunity_count,
        },
        metodos={
            '_fetch_children_partners_for_hierarchy':
                _fetch_children_partners_for_hierarchy,
            '_get_contact_opportunities_domain': _get_contact_opportunities_domain,
            '_compute_opportunity_count': _compute_opportunity_count,
            'action_view_opportunity': action_view_opportunity,
        },
    )
    # El enganche es ``@classmethod`` en ``base``: ``chain_method`` reinstala el
    # descriptor y ``func`` recibe ``cls``, como declara su tabla.
    chain_method(ResPartner, '_compute_application_statistics_hook',
                 classmethod(_compute_application_statistics_hook),
                 combine=_merge_application_statistics)

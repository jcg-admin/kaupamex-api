"""``res.users`` — lo que ``crm`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/crm/models/res_users.py`` (LGPL-3, 17 líneas)
— atribución y aviso de licencia preservados (DEC-KX-03).

Cobertura: 1 de 1 símbolo — **1 portado**
==========================================

``_compute_display_name`` (``:6``) marca al líder del equipo con
``--(Team Leader)--`` cuando la etiqueta se pide desde la vista de un equipo.

Dos divergencias de FORMA, las dos heredadas del árbol
======================================================

1. **``_compute_display_name`` DEVUELVE la etiqueta**, no la asigna a
   ``self.display_name``. Es la divergencia 1 que ``orm.models.DisplayNameMixin``
   declara para todo el árbol, y la ejercen ya cinco modelos de ``base``. Por
   eso el enganche usa ``chain_method`` con ``combine=``: la semántica de
   relevo por ``None`` delegaría en el eslabón previo **en vez** de sumarse a
   él, y aquí hay que sumarse — es lo que ``super()._compute_display_name()``
   seguido de ``+=`` significa en la fuente.

2. **``@api.depends_context`` no se declara.** Allá le dice al motor de compute
   qué claves invalidan el valor cacheado; aquí ``display_name`` se calcula al
   leerlo y no hay caché que invalidar, así que el decorador no tiene receptor.
   Las dos claves se leen igual, de ``orm.environments.get_context()``.
"""
from orm.method_chain import chain_method
from tools.translate import _

from orm.environments import get_context

from addons.base.models.res_users import ResUsers
from addons.sales_team.models.crm_team import CrmTeam


def _compute_display_name(self):
    """≙ el cuerpo tras el ``super()`` (``:11-17``).

    Devuelve el marcador del líder, o ``None`` si esta petición no lo pide. El
    ``None`` es lo que :func:`_add_team_leader_marker` lee para dejar la
    etiqueta intacta.
    """
    context = get_context()
    if not context.get('formatted_display_name'):
        return None
    team_id = context.get('crm_formatted_display_name_team', 0)
    if not team_id:
        return None
    team = CrmTeam.objects.filter(pk=team_id).first()
    leader_id = team.user_id if team is not None else None
    if leader_id is not None and leader_id.pk == self.pk:
        return _('(Team Leader)')
    return None


def _add_team_leader_marker(marker, label):
    """≙ el ``user.display_name += " --%s--"`` de la fuente (``:17``).

    ``combine`` de :func:`orm.method_chain.chain_method`: recibe lo que devuelve
    el eslabón nuevo y lo que devolvió el previo, en ese orden.
    """
    return f'{label} --{marker}--' if marker else label


def apply_crm_extensions():
    """Cuelga el marcador de ``res.users``. La llama ``CrmConfig.ready()``."""
    chain_method(ResUsers, '_compute_display_name', _compute_display_name,
                 combine=_add_team_leader_marker)

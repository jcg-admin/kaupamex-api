"""Extensión de ``res.users`` — el análogo nativo de ``_inherit`` (Odoo
``resource``).

Adaptación de Odoo resource/models/res_users.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3).

Mismo patrón que ``resource/models/res_company.py`` de este addon (métodos
asignados sobre la clase — precedente ``bus/models/res_users.py``).

Divergencias declaradas
========================

1. **``resource_ids`` (One2many) se resuelve sin código adicional** — es el
   reverso automático de ``ResourceResource.user``
   (``related_name='resource_resources'``, ver ``resource_resource.py``).
2. **``resource_calendar_id`` (``related='resource_ids.calendar_id'``,
   editable) se expone como propiedad de sólo lectura sobre el PRIMER
   recurso vinculado.** En la referencia un usuario Odoo normalmente tiene
   un único ``resource.resource`` (vía ``hr.employee``); sin ese consumidor
   construido aquí, "el primero" es la mejor aproximación disponible.
3. **NO se porta el override de ``write()``** (propagar el ``tz`` del admin
   a su calendario por defecto en el primer login) — depende de los
   external IDs ``base.user_admin``/``resource.resource_calendar_std``,
   ninguno de los cuales existe como fixture estable en este proyecto
   (mismo criterio que las ramas dependientes de external IDs ya
   documentadas en ``fleet``/``certificate``).
"""
from addons.base.models import ResUsers


def resource_calendar(self):
    """El calendario del primer recurso vinculado al usuario (Odoo
    ``resource_calendar_id``)."""
    resource = self.resource_resources.first()
    return resource.calendar if resource else None


ResUsers.resource_calendar = property(resource_calendar)

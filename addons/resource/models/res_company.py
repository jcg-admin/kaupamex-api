"""Extensión de ``res.company`` — el análogo nativo de ``_inherit`` (Odoo
``resource``).

Adaptación de Odoo resource/models/res_company.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3).

En la referencia un addon extiende un modelo del núcleo declarando
``_inherit = 'res.company'`` en su propio ``models/res_company.py``. Django
no distribuye el *esquema* entre apps (una columna nueva sólo la puede
declarar el addon dueño de la clase — aquí, ``base``), así que los
**métodos** se asignan sobre ``ResCompany`` al importarse — mismo patrón que
``sale_subscription/models/res_company.py`` (precedente ya en este
multi-repo).

Divergencia declarada
======================

La referencia agrega DOS columnas a ``res.company``:

- ``resource_calendar_ids`` (``One2many``) — **sí aplica sin código
  adicional**: es el reverso automático de ``ResourceCalendar.company``
  (``related_name='resource_calendars'``, ver ``resource_calendar.py``).
- ``resource_calendar_id`` (``Many2one`` hacia adelante, el calendario por
  defecto) — **requeriría una columna real en la tabla ``res_company``**,
  que sólo ``base`` puede declarar. Este addon no edita
  ``base/models/res_company.py``; en su lugar, ``ResourceCalendar`` lleva un
  booleano propio ``is_default`` (ver su docstring, divergencia 5) y aquí se
  expone como propiedad de sólo lectura sobre la clase.
"""
from addons.base.models import ResCompany
from addons.resource.models.resource_calendar import ResourceCalendar


def resource_calendar(self):
    """El calendario por defecto de la compañía (Odoo ``resource_calendar_id``)."""
    return ResourceCalendar.objects.filter(company=self, is_default=True).first()


def get_or_create_default_resource_calendar(self):
    """Azúcar sobre ``_create_resource_calendar`` — crea el calendario
    estándar de 40 horas/semana si la compañía aún no tiene uno por defecto."""
    calendar = self.resource_calendar
    if calendar is not None:
        return calendar
    calendar = ResourceCalendar.objects.create(
        name='Horario estándar 40 horas/semana', company=self, is_default=True,
    )
    calendar.create_default_attendances()
    return calendar


ResCompany.resource_calendar = property(resource_calendar)
ResCompany.get_or_create_default_resource_calendar = get_or_create_default_resource_calendar

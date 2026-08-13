"""``resource.mixin`` — modelo abstracto que vincula un registro a un
``resource.resource`` (Odoo ``resource``).

Adaptación fiel de Odoo resource/models/resource_mixin.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

**Cero consumidores hoy.** En la referencia, modelos como ``hr.employee`` o
``mrp.workcenter`` declaran ``_inherit = [..., 'resource.mixin']`` para
obtener un ``resource.resource`` propio. Medido: ``src/addons/mrp/models/
mrp_workcenter.py`` (nuestro puerto) **no** hereda de este mixin ni
referencia ``resource`` — 0 hits (``grep -rn resource src/addons/mrp/models/
mrp_workcenter.py``) — es un corte reducido a ``name``/``costs_hour``/
``time_efficiency``/``capacity``, sin agenda. Se porta igual, como Django
**abstract model** (``Meta.abstract = True``), para que un futuro addon
(``hr``, o una versión ampliada de ``mrp.workcenter``) lo herede sin
reescribirlo — mismo patrón que ``AvatarMixin``/``ImageMixin`` en ``base``.

Divergencias declaradas
=======================

1. **``related_name`` con placeholders ``%(app_label)s_%(class)s_...``** en
   los tres FK — obligatorio en un mixin abstracto que puede tener más de un
   subclase concreta (Django rechaza un ``related_name`` fijo compartido por
   dos modelos distintos); ver la documentación de Django sobre
   ``related_name`` en modelos base abstractos.
2. **``company``/``resource_calendar`` son columnas reales sincronizadas en
   ``save()``**, no ``related=..., store=True`` — mismo criterio que
   ``resource.calendar.leaves``.
3. **``tz`` es una ``@property``** que delega a ``self.resource.tz`` — no
   una columna (la referencia la declara ``related='resource_id.tz',
   readonly=False``, es decir editable-que-escribe-al-recurso; aquí el
   llamador que quiera cambiarla escribe directo en ``self.resource.tz``).
4. **DEFERIDO (no stub) — el mismo motor de intervalos que
   ``resource.calendar``/``resource.resource``:** ``_get_work_days_data_batch``,
   ``_get_leave_days_data_batch``, ``_adjust_to_calendar``,
   ``_list_work_time_per_day``, ``list_leaves``, ``_get_calendars``. Todos
   delegan, directa o indirectamente, en los métodos de intervalos de
   ``ResourceCalendar``/``ResourceResource`` que este porte deja DEFERIDOS
   (ver los docstrings de esos dos módulos) — no tiene sentido portar el
   consumidor sin el motor que consume.
5. **``copy_data`` (duplicar el recurso vinculado al copiar el registro)
   NO se porta** — Django no tiene un equivalente directo de ``copy()``
   sobre un modelo; el patrón de duplicación (si se necesita) lo define el
   futuro consumidor concreto, no este mixin.
"""
import fields
import models

from addons.base.models import ResCompany
from addons.resource.models.resource_resource import ResourceResource


class ResourceMixin(models.Model):
    """Vincula un modelo concreto a un ``resource.resource`` propio (Odoo
    ``resource.mixin``, abstracto)."""

    resource = fields.Many2one(
        'resource.ResourceResource', on_delete=models.PROTECT,
        related_name='%(app_label)s_%(class)s_resource_mixin_set',
        help_text="Odoo resource_id (required, ondelete='restrict').",
    )
    company = fields.Many2one(
        ResCompany, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_resource_mixin_company_set',
        help_text=(
            'Odoo company_id (related=resource_id.company_id, store=True, '
            'readonly=False) — sincronizado en save(), ver divergencia 2.'
        ),
    )
    resource_calendar = fields.Many2one(
        'resource.ResourceCalendar', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_resource_mixin_calendar_set',
        help_text=(
            'Odoo resource_calendar_id (related=resource_id.calendar_id, '
            'store=True, readonly=False) — sincronizado en save().'
        ),
    )

    class Meta:
        abstract = True

    # --------------------------------------------------------------
    # tz (divergencia 3)
    # --------------------------------------------------------------

    @property
    def tz(self):
        return self.resource.tz if self.resource_id else None

    # --------------------------------------------------------------
    # Alta y sincronización (Odoo create() + _prepare_resource_values)
    # --------------------------------------------------------------

    def save(self, *args, **kwargs):
        if not self.resource_id:
            self.resource = self._create_linked_resource()
        if self.resource_id:
            if not self.company_id:
                self.company = self.resource.company
            if not self.resource_calendar_id:
                self.resource_calendar = self.resource.calendar
        super().save(*args, **kwargs)

    def _create_linked_resource(self):
        """Odoo ``_prepare_resource_values`` + creación del recurso — usa el
        nombre del propio registro (``_rec_name`` de la referencia; aquí el
        atributo ``name`` si el subclase lo declara, igual que
        ``AvatarMixin._avatar_name_field``). ``ResourceResource`` se importa
        al top del módulo (no-lazy-imports.md) — sin ciclo, porque
        ``resource_resource.py`` no importa este módulo."""
        values = {'name': getattr(self, 'name', '') or ''}
        if self.company_id:
            values['company'] = self.company
        if self.resource_calendar_id:
            values['calendar'] = self.resource_calendar
        return ResourceResource.objects.create(**values)

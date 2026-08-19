"""``hr.employee`` — ubicación de trabajo por día de la semana.

Adaptación de Odoo hr_homeworking/models/hr_employee.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 78 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 15 símbolos de la referencia
==========================================================

===========================================================  ==================
Símbolo de la referencia (línea)                             Dónde queda aquí
===========================================================  ==================
``monday_location_id`` … ``sunday_location_id`` (``:11-17``) 7 FKs (campos)
``exceptional_location_id`` (``:18-21``)                     property
                                                             ``exceptional_location``
``hr_icon_display`` (``selection_add``, ``:22-24``)          choices ampliadas
                                                             en ``luego``
``today_location_name`` (``:25``)                            property (ver
                                                             divergencia 2)
``_get_current_day_location_field`` (``:27-29``)             classmethod
                                                             verbatim
``get_views`` (``:31-42``)                                   NO portado (ver
                                                             "Lo que no se
                                                             porta")
``_compute_exceptional_location_id`` (``:44-53``)            método verbatim
``_compute_presence_icon`` (``:55-64``)                      método (ver
                                                             divergencia 3)
``_compute_work_location_name`` (``:66-71``)                 override encadenado
``_compute_work_location_type`` (``:73-78``)                 override encadenado
===========================================================  ==================

Lo que no se porta — y por qué
================================

**``get_views`` es capa de vista del cliente Odoo.** Reescribe el ``arch``
XML de las vistas search/list sustituyendo el placeholder
``today_location_name`` por el campo del día en curso. En este árbol no hay
``ir.ui.view`` ni ``get_views`` (medido: ``grep -rn "def get_views"
addons/ src/`` → 0 defs; ``hr/models/res_users.py:87`` ya los declara
BLOQUEADOS, familia (b)/(d) de ``hr_employee.py``).

Divergencias declaradas
=========================

1. **Nombres de campo sin ``_id``** — convención de este árbol
   (``hr/models/hr_employee.py``): ``monday_location`` etc. La constante
   ``DAYS`` (ver ``hr_homeworking.py``) lista los nombres locales.
2. **``today_location_name`` deja de ser placeholder** — en la referencia es
   un ``Char`` vacío que ``get_views`` sustituye por el campo del día; sin
   capa de vista, el símbolo colapsa en una property que devuelve
   directamente el nombre de la ubicación de HOY (excepción del día o
   patrón semanal). Mismo significado, sin el rodeo del ``arch``.
3. **La mitad ``super()._compute_presence_icon()`` está BLOQUEADA** — el
   cómputo base de presencia no existe en ``hr`` (``hr_employee.py:415``:
   ``hr_icon_display`` "BLOQUEADO por hr_presence_state … Sucesor: tarea
   #21"). Este método porta SOLO la mitad de homeworking (icono
   ``presence_<location_type>`` cuando hay ubicación hoy); la mitad de
   presencia entra con la tarea #21 — ``chain_method`` los encadenará solo
   cuando exista.
4. **``groups="hr.group_hr_user"`` de ``exceptional_location_id`` no se
   porta** — no hay usuario ambiente en la capa de modelo; el gate de
   autorización (DEC-11, ``HasCapability``) es de la vista DRF (mismo
   criterio que ``account_fleet/models/fleet_vehicle.py``, divergencia 1).
5. **``employee.sudo()`` → acceso directo** — sin usuario ambiente no hay
   elevación que hacer (mismo criterio del árbol).
"""
from datetime import date

import fields
import models

from addons.hr_homeworking.models.hr_homeworking import DAYS, HrEmployeeLocation
from orm.model_classes import extend_model


def _get_current_day_location_field(cls):
    """≙ ``_get_current_day_location_field``
    (``odoo19c: hr_homeworking/models/hr_employee.py:27-29``) — el nombre
    del campo de ubicación del día en curso. ``@api.model`` → classmethod."""
    return DAYS[date.today().weekday()]


def _compute_exceptional_location_id(self):
    """≙ ``_compute_exceptional_location_id`` (``:44-53``) — la excepción
    de HOY del empleado, o ``None`` (la referencia asigna ``False``)."""
    if self.pk is None:
        return None
    exception = HrEmployeeLocation.objects.filter(
        employee=self, date=date.today(),
    ).select_related('work_location').first()
    return exception.work_location if exception else None


def _current_location(self):
    """La ubicación efectiva de hoy: excepción del día, o patrón semanal.

    Es el ``employee.exceptional_location_id or employee[dayfield]`` que la
    referencia repite en sus cuatro computes — factorizado aquí porque en
    este idioma no hay recordset que recorrer."""
    dayfield = type(self)._get_current_day_location_field()
    return self.exceptional_location or getattr(self, dayfield)


def _compute_presence_icon(self):
    """≙ ``_compute_presence_icon`` (``:55-64``) — SOLO la mitad de
    homeworking; la mitad base (``super()``) está bloqueada por la tarea
    #21 (divergencia 3 del docstring del módulo)."""
    today_location = self._current_location()
    if not today_location:
        return None
    self.hr_icon_display = f'presence_{today_location.location_type}'
    self.show_hr_icon_display = True
    return None


def _compute_work_location_name(self):
    """≙ ``_compute_work_location_name`` (``:66-71``) — override: el nombre
    sale de la ubicación de HOY, no de ``version.work_location``. Devuelve
    siempre un valor (aunque sea ``''``) para que el relevo de
    ``chain_method`` NO caiga a la implementación de ``hr`` — la referencia
    tampoco llama a ``super()`` aquí."""
    current_location = self._current_location()
    self.work_location_name = current_location.name if current_location else ''
    return self.work_location_name


def _compute_work_location_type(self):
    """≙ ``_compute_work_location_type`` (``:73-78``) — override total,
    mismo criterio que ``_compute_work_location_name``."""
    current_location = self._current_location()
    self.work_location_type = (
        current_location.location_type if current_location else ''
    ) or ''
    return self.work_location_type


def today_location_name(self):
    """≙ ``today_location_name`` (``:25``) — ver divergencia 2: el
    placeholder de vista colapsa en el nombre de la ubicación de hoy."""
    current_location = self._current_location()
    return current_location.name if current_location else ''


def _day_location_field(day_field_name, label):
    """Fábrica de los 7 FKs semanales — mismos kwargs, distinta etiqueta."""
    return fields.Many2one(
        'hr.HrWorkLocation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name=label,
        help_text=f'Ubicación de trabajo del día (Odoo {day_field_name}).',
    )


#: ≙ ``selection_add=[('presence_home', …), ('presence_office', …),
#: ('presence_other', …)]`` (``:22-24``) — los tres valores que este addon
#: suma al ``hr_icon_display`` de ``hr.employee``.
HR_ICON_DISPLAY_SELECTION_ADD = [
    ('presence_home', 'En casa'),
    ('presence_office', 'En la oficina'),
    ('presence_other', 'En otra ubicación'),
]


def _extend_hr_icon_display_choices(model):
    """El ``selection_add`` — amplía las choices del campo ya declarado por
    ``hr``. Idempotente por pertenencia (``ready()`` puede correr dos
    veces). ``max_length=28`` del campo admite los tres valores nuevos
    (el más largo, ``presence_office``, mide 15)."""
    field = model._meta.get_field('hr_icon_display')
    existing = {value for value, _label in field.choices}
    field.choices = list(field.choices) + [
        (value, label) for value, label in HR_ICON_DISPLAY_SELECTION_ADD
        if value not in existing
    ]


def apply_hr_homeworking_hr_employee_extensions():
    """Cuelga sobre ``hr.employee`` lo que ``hr_homeworking`` necesita —
    ≙ ``_inherit``. Se invoca desde ``HrHomeworkingConfig.ready()``.

    Los 7 FKs semanales son columnas (migración pendiente en
    ``hr/migrations/`` — la app dueña del modelo; ver ``__init__.py`` del
    addon). Los computes no almacenados son properties."""
    extend_model(
        'hr', 'HrEmployee',
        campos={
            'monday_location': _day_location_field('monday_location_id', 'Monday'),
            'tuesday_location': _day_location_field('tuesday_location_id', 'Tuesday'),
            'wednesday_location': _day_location_field('wednesday_location_id', 'Wednesday'),
            'thursday_location': _day_location_field('thursday_location_id', 'Thursday'),
            'friday_location': _day_location_field('friday_location_id', 'Friday'),
            'saturday_location': _day_location_field('saturday_location_id', 'Saturday'),
            'sunday_location': _day_location_field('sunday_location_id', 'Sunday'),
        },
        metodos={
            '_get_current_day_location_field': classmethod(_get_current_day_location_field),
            '_compute_exceptional_location_id': _compute_exceptional_location_id,
            '_current_location': _current_location,
            '_compute_presence_icon': _compute_presence_icon,
            '_compute_work_location_name': _compute_work_location_name,
            '_compute_work_location_type': _compute_work_location_type,
        },
        propiedades={
            'exceptional_location': _compute_exceptional_location_id,
            'today_location_name': today_location_name,
        },
        luego=_extend_hr_icon_display_choices,
    )

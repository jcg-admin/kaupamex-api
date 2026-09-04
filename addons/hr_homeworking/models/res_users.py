"""``res.users`` — las ubicaciones semanales del empleado, en el usuario.

Adaptación de Odoo hr_homeworking/models/res_users.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 38 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 11 símbolos de la referencia
==========================================================

===========================================================  ==================
Símbolo de la referencia (línea)                             Dónde queda aquí
===========================================================  ==================
``monday_location_id`` … ``sunday_location_id``              7 properties con
(``related='employee_id.*'``, ``readonly=False``, ``:11-17``) setter
``_get_employee_fields_to_sync`` (``:19-20``)                método encadenado
                                                             (``extend_list``)
``SELF_READABLE_FIELDS`` (``:22-24``)                        property envuelta
``SELF_WRITEABLE_FIELDS`` (``:26-28``)                       property envuelta
``_compute_im_status`` (``:30-38``)                          BLOQUEADO (ver
                                                             abajo)
===========================================================  ==================

Lo BLOQUEADO — ``_compute_im_status``
=======================================

Mismo bloqueo que ``res_partner.py`` de este addon: ``base.ResUsers`` no
declara ``im_status`` (infraestructura ``bus`` no portada;
``hr/models/hr_employee.py:144-148``, sucesor tarea **#21**). El sufijo de
ubicación entra con esa familia.

Divergencias declaradas
=========================

1. **``related … readonly=False`` → property con getter y setter** — el
   getter delega en ``self.employee`` (la property que ``hr`` instala:
   el empleado de la empresa activa); el setter escribe en el empleado y
   persiste de inmediato (fiel al write-through del ``related`` de Odoo).
   Sin empleado vinculado, el setter es un no-op silencioso — mismo
   desenlace que el ``related`` de Odoo sobre un ``employee_id`` vacío.
2. **``super()`` → ``chain_method``/envoltura de property** —
   ``_get_employee_fields_to_sync`` se encadena con ``combine=extend_list``
   (la semántica exacta de ``super() + DAYS``);
   ``SELF_READABLE_FIELDS``/``SELF_WRITEABLE_FIELDS`` son properties
   instaladas por ``hr`` (``hr/models/res_users.py:240``), y una property
   no se encadena con ``chain_method`` (falla ruidoso por diseño) — se
   envuelve: la nueva llama al ``fget`` previo y suma ``DAYS``.
3. **Orden de carga** — este módulo asume que ``hr`` ya aplicó sus
   extensiones (``addons.hr`` antes de ``addons.hr_homeworking`` en
   ``INSTALLED_APPS``). Si la property previa no existe, la aportación
   propia se instala sola y lo dice el docstring de la envoltura.
"""
from addons.base.models import ResUsers
from addons.hr_homeworking.models.hr_homeworking import DAYS
from orm.method_chain import chain_method, extend_list
from orm.model_classes import extend_property


def _get_employee_fields_to_sync(self):
    """≙ ``_get_employee_fields_to_sync`` (``:19-20``) — la aportación de
    este addon; ``extend_list`` la suma a la de ``hr`` (``super() +
    DAYS``)."""
    return list(DAYS)


def _day_location_property(day_field_name):
    """Fábrica de las 7 properties ``related='employee_id.<día>'`` con
    ``readonly=False`` (divergencia 1)."""
    def getter(self):
        employee = self.employee
        if employee is None:
            return None
        return getattr(employee, day_field_name)

    def setter(self, value):
        employee = self.employee
        if employee is None:
            return
        setattr(employee, day_field_name, value)
        employee.save(update_fields=[day_field_name])

    getter.__name__ = day_field_name
    getter.__doc__ = (f'≙ ``{day_field_name}_id`` '
                      f'(``related="employee_id.{day_field_name}_id"``, '
                      f'``readonly=False``).')
    return property(getter, setter)


def _add_the_days(self, anterior):
    """≙ ``return super().SELF_*_FIELDS + DAYS`` (``:22-28``).

    ``anterior`` es el ``super()``: lo entrega
    :func:`orm.model_classes.extend_property`, que también aporta la
    idempotencia (``ready()`` puede correr dos veces) y el caso de la property
    ausente. **Era un ayudante privado de este archivo**, copiado de nadie y
    duplicable por cada addon que quisiera sumar a una property; se subió al
    ORM al descubrir que ``hr`` había resuelto lo mismo por otra vía y esa vía
    no instalaba nada (:ref:`h-api-834`).
    """
    return list(anterior or []) + list(DAYS)


def apply_hr_homeworking_res_users_extensions():
    """Cuelga sobre ``res.users`` lo que ``hr_homeworking`` necesita —
    ≙ ``_inherit``. Se invoca desde ``HrHomeworkingConfig.ready()``.

    Todo aquí es no-almacenado (related/hooks): properties y métodos
    directos sobre ``base.ResUsers`` — no hay migración pendiente para
    este archivo."""
    for day_field_name in DAYS:
        if not hasattr(ResUsers, day_field_name):
            setattr(ResUsers, day_field_name,
                    _day_location_property(day_field_name))
    chain_method(ResUsers, '_get_employee_fields_to_sync',
                 _get_employee_fields_to_sync, combine=extend_list)
    extend_property(ResUsers, 'SELF_READABLE_FIELDS', _add_the_days)
    extend_property(ResUsers, 'SELF_WRITEABLE_FIELDS', _add_the_days)

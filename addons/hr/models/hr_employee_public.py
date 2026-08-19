"""``hr.employee.public`` — la proyección pública del empleado (vista SQL).

Adaptación de Odoo hr/models/hr_employee_public.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3, 205 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Qué es en la referencia: un modelo ``_auto = False`` cuyo ``init()`` crea la
vista ``hr_employee_public`` como ``SELECT`` sobre ``hr_employee e JOIN
hr_version v ON v.id = e.current_version_id`` — el subconjunto NO privado
del empleado, consultable por cualquier usuario autenticado sin exponer los
campos personales. Patrón de este árbol para ``_auto = False``:
``base.ResDevice`` (``Meta.managed = False`` + vista creada por migración
``RunSQL``) y ``account.AccountInvoiceReport``.

Porte símbolo por símbolo — 55 símbolos de la referencia
==========================================================

**Atributos de clase de modelo (5)** — verbatim: ``_name``,
``_description``, ``_order``, ``_auto``, ``_log_access``.

**Campos (32)** — dos familias, y la partición la fija la propia referencia
(``_get_fields`` filtra ``field.store and field.column_type``):

- **Columnas de la vista (19 + ``id``)** — declaradas como campos reales
  sobre ``Meta.managed = False``: ``create_date``, ``name``, ``active``,
  ``department_id``, ``job_id``, ``company_id``, ``address_id``,
  ``mobile_phone``, ``work_phone``, ``work_email``, ``work_contact_id``,
  ``work_location_id``, ``user_id``, ``resource_id``, ``color``,
  ``resource_calendar_id``, ``employee_id``, ``parent_id``, ``coach_id``.
  Los nombres ``*_id`` se conservan verbatim con ``db_column`` explícito
  (mismo criterio que ``AccountInvoiceReport``). En este árbol las columnas
  origen se reparten distinto que en la referencia — ``department``/``job``/
  ``address``/``work_location``/``resource_calendar`` viven en
  ``hr_version`` y ``user_id`` en ``resource_resource`` — y ese mapeo lo
  documenta ``_get_fields``.
- **``related``/``compute`` sin store (13 + 10 de imagen)** — propiedades
  que delegan en ``employee_id`` (idéntico a la delegación de
  ``hr_employee.py``): ``member_of_department`` (método con usuario),
  ``job_title``, ``share``, ``phone``, ``email``, ``work_location_name``,
  ``work_location_type``, ``tz``, ``hr_presence_state``,
  ``hr_icon_display``, ``show_hr_icon_display``, ``country_code``,
  ``user_partner_id`` → ``user_partner``, ``birthday_public_display_string``,
  ``newly_hired``, y las diez ``image_*``/``avatar_*``.
  ``im_status``/``last_activity``/``last_activity_time`` BLOQUEADOS por la
  infraestructura de presencia (``bus``) — mismo bloqueo y sucesor (#21)
  que en ``hr_employee.py``. ``child_ids`` es el reverso automático de
  ``parent_id`` (``related_name='child_ids'``).
  ``is_manager``/``is_user`` dependen del usuario del entorno → métodos con
  argumento ``user`` (``_compute_is_manager``/``_compute_is_user``).

**Métodos (18)** — 15 portados, 1 resuelto sin código, 2 BLOQUEADOS:

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_get_selection_hr_icon_display`` (``:81-82``)
     - portado — lee las ``choices`` reales de ``hr.employee``
   * - ``_compute_from_employee`` (``:84-92``)
     - portado — sin ``sudo`` (no hay record rules que eludir)
   * - ``_compute_last_activity`` (``:94-108``)
     - BLOQUEADO por ``presence_ids`` (infra ``bus``) — sucesor #21
   * - ``_compute_country_code`` (``:110-111``)
     - portado — DIVERGENCIA: el empleado de este árbol declara
       ``company_country_code`` (no ``country_code``); se delega a esa
       columna
   * - ``_compute_is_manager`` (``:113-118``)
     - portado — el ``child_of`` se resuelve recorriendo ``parent``
   * - ``_compute_is_user`` (``:120-124``)
     - portado
   * - ``_compute_presence_state`` / ``_compute_presence_icon`` (``:126-131``)
     - portados — delegan; los campos origen quedan en su default mientras
       la presencia esté bloqueada (#21)
   * - ``_compute_member_of_department`` (``:133-134``)
     - portado — DIVERGENCIA: ``hr.employee`` de este árbol no declara
       ``member_of_department``; el subárbol de departamento se decide
       aquí con ``parent_path`` (la ruta materializada de
       ``hr_department.py``)
   * - ``_get_manager_only_fields`` (``:136-137``)
     - portado verbatim (``[]``)
   * - ``_search_part_of_department`` (``:139-146``)
     - portado — queryset en vez de dominio
   * - ``_get_valid_employee_for_user`` (``:148-159``)
     - portado — con ``user`` explícito
   * - ``_compute_manager_only_fields`` (``:161-171``)
     - portado
   * - ``_compute_newly_hired`` (``:173-174``)
     - portado
   * - ``_search_newly_hired`` (``:176-183``)
     - portado — usa ``hr.employee._get_new_hire_field()``
   * - ``_get_fields`` (``:185-193``)
     - portado — el mapeo columna → origen (``e``/``v``/``r``) se declara
       explícito porque este árbol reparte las columnas entre TRES tablas
       (empleado, versión, recurso), no dos
   * - ``init`` (``:195-203``)
     - portado — ``CREATE or REPLACE VIEW`` con el SQL de ``_get_fields``;
       la migración ``RunSQL`` que lo deja instalado es el sucesor (mismo
       flujo que ``ResDevice``); NO se ejecuta en este pase
   * - ``get_avatar_card_data`` (``:205-206``)
     - portado — ``read(fields)`` ≙ dict de atributos pedidos

Divergencias transversales
===========================

1. **``self.env.user`` → argumento ``user``** en todo lo que predica sobre
   el usuario actual.
2. **``sudo()``/``with_context(active_test=False)``** — sin análogo ni
   necesidad: los querysets no filtran ``active`` por defecto.
3. **``id == employee_id``** — en la vista de la referencia el ``id`` del
   registro público ES el id del empleado; aquí igual (``employee_id`` es
   además la FK navegable).
"""
from datetime import timedelta

from django.db import connection
from django.utils import timezone

import fields
import models

from addons.hr.models.hr_employee import HrEmployee


class HrEmployeePublic(models.Model):
    """``hr.employee.public`` — el subconjunto público del empleado.

    Vista SQL (``Meta.managed = False``): las columnas las llena la vista
    que declara ``init()``; el resto delega en ``employee_id``.
    """

    # ---- Atributos de clase de modelo — verbatim (los 5 de la referencia,
    # ``odoo19c: hr/models/hr_employee_public.py:11-16``) ----
    _name = 'hr.employee.public'
    _description = 'Public Employee'
    _order = 'name'
    _auto = False
    _log_access = True  # incluye los campos mágicos (aquí, create_date)

    # ==== Columnas de la vista (ver _get_fields) ====
    create_date = fields.Datetime(
        null=True, blank=True,
        help_text='Odoo create_date — en la vista sale de e.created_at.',
    )
    name = fields.Char(max_length=200, blank=True, default='')
    active = fields.Boolean(default=True)
    department_id = fields.Many2one(
        'hr.HrDepartment', on_delete=models.DO_NOTHING, null=True, blank=True,
        related_name='+', db_column='department_id',
        help_text='Columna de la vista — origen v.department_id.',
    )
    job_id = fields.Many2one(
        'hr.HrJob', on_delete=models.DO_NOTHING, null=True, blank=True,
        related_name='+', db_column='job_id',
        help_text='Origen v.job_id.',
    )
    company_id = fields.Many2one(
        'base.ResCompany', on_delete=models.DO_NOTHING, null=True, blank=True,
        related_name='+', db_column='company_id',
        help_text='Origen e.company_id (columna del ResourceMixin).',
    )
    address_id = fields.Many2one(
        'base.ResPartner', on_delete=models.DO_NOTHING, null=True, blank=True,
        related_name='+', db_column='address_id',
        help_text='Origen v.address_id.',
    )
    mobile_phone = fields.Char(max_length=32, blank=True, default='')
    work_phone = fields.Char(max_length=32, blank=True, default='')
    work_email = fields.Char(max_length=254, blank=True, default='')
    work_contact_id = fields.Many2one(
        'base.ResPartner', on_delete=models.DO_NOTHING, null=True, blank=True,
        related_name='+', db_column='work_contact_id',
        help_text='Origen e.work_contact_id.',
    )
    work_location_id = fields.Many2one(
        'hr.HrWorkLocation', on_delete=models.DO_NOTHING, null=True, blank=True,
        related_name='+', db_column='work_location_id',
        help_text='Origen v.work_location_id.',
    )
    user_id = fields.Many2one(
        'base.ResUsers', on_delete=models.DO_NOTHING, null=True, blank=True,
        related_name='+', db_column='user_id',
        help_text='Origen r.user_id (el vínculo vive en resource_resource).',
    )
    resource_id = fields.Many2one(
        'resource.ResourceResource', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+', db_column='resource_id',
        help_text='Origen e.resource_id.',
    )
    color = fields.Integer(default=0)
    resource_calendar_id = fields.Many2one(
        'resource.ResourceCalendar', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+', db_column='resource_calendar_id',
        help_text='Origen v.resource_calendar_id.',
    )
    employee_id = fields.Many2one(
        HrEmployee, on_delete=models.DO_NOTHING, null=True, blank=True,
        related_name='+', db_column='employee_id',
        help_text='Odoo employee_id — en la vista, e.id (= id del registro).',
    )
    parent_id = fields.Many2one(
        'self', on_delete=models.DO_NOTHING, null=True, blank=True,
        related_name='child_ids', db_column='parent_id',
        help_text='Odoo parent_id ("Manager"); child_ids es su reverso '
                  '("Direct subordinates").',
    )
    coach_id = fields.Many2one(
        'self', on_delete=models.DO_NOTHING, null=True, blank=True,
        related_name='+', db_column='coach_id',
        help_text='Odoo coach_id ("Coach").',
    )

    class Meta:
        managed = False
        db_table = 'hr_employee_public'
        ordering = ['name']
        verbose_name = 'Empleado (público)'
        verbose_name_plural = 'Empleados (públicos)'

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------
    # Delegación a employee_id — los ``related``/compute sin store
    # ------------------------------------------------------------------

    @property
    def job_title(self):
        """≙ ``job_title`` (``related='employee_id.job_title'``)."""
        return self.employee_id_id and self.employee_id.job_title or ''

    @property
    def share(self):
        """≙ ``share``."""
        return bool(self.employee_id_id and self.employee_id.share)

    @property
    def phone(self):
        """≙ ``phone``."""
        return self.employee_id.phone if self.employee_id_id else ''

    @property
    def email(self):
        """≙ ``email``."""
        return self.employee_id.email if self.employee_id_id else ''

    @property
    def work_location_name(self):
        """≙ ``work_location_name``."""
        return self.employee_id.work_location_name if self.employee_id_id else ''

    @property
    def work_location_type(self):
        """≙ ``work_location_type``."""
        return self.employee_id.work_location_type if self.employee_id_id else ''

    @property
    def tz(self):
        """≙ ``tz`` (``related='resource_id.tz'``)."""
        return self.resource_id_id and self.resource.tz or ''

    @property
    def resource(self):
        """Azúcar de navegación sobre la columna ``resource_id``."""
        return self.resource_id

    @property
    def user_partner(self):
        """≙ ``user_partner_id`` (``related='user_id.partner_id'``)."""
        user = self.user_id
        return user.partner if user is not None and user.partner_id else None

    @property
    def birthday_public_display_string(self):
        """≙ ``birthday_public_display_string``."""
        if not self.employee_id_id:
            return 'hidden'
        return self.employee_id.birthday_public_display_string

    @property
    def hr_presence_state(self):
        """≙ ``hr_presence_state`` — delega (origen bloqueado por #21)."""
        return (self.employee_id.hr_presence_state
                if self.employee_id_id else 'out_of_working_hour')

    @property
    def hr_icon_display(self):
        """≙ ``hr_icon_display``."""
        return self.employee_id.hr_icon_display if self.employee_id_id else ''

    @property
    def show_hr_icon_display(self):
        """≙ ``show_hr_icon_display``."""
        return bool(self.employee_id_id and self.employee_id.show_hr_icon_display)

    @property
    def country_code(self):
        """≙ ``country_code`` — ver DIVERGENCIA (``company_country_code``)."""
        return self.employee_id.company_country_code if self.employee_id_id else ''

    @property
    def newly_hired(self):
        """≙ ``newly_hired``."""
        return bool(self.employee_id_id and self.employee_id.newly_hired)

    # Las diez columnas de imagen/avatar delegan al AvatarMixin del empleado.
    @property
    def image_1920(self):
        """≙ ``image_1920`` (``related='employee_id.image_1920'``)."""
        return self.employee_id.image_1920 if self.employee_id_id else None

    @property
    def image_1024(self):
        """≙ ``image_1024``."""
        return self.employee_id.image_1024 if self.employee_id_id else None

    @property
    def image_512(self):
        """≙ ``image_512``."""
        return self.employee_id.image_512 if self.employee_id_id else None

    @property
    def image_256(self):
        """≙ ``image_256``."""
        return self.employee_id.image_256 if self.employee_id_id else None

    @property
    def image_128(self):
        """≙ ``image_128``."""
        return self.employee_id.image_128 if self.employee_id_id else None

    @property
    def avatar_1920(self):
        """≙ ``avatar_1920``."""
        return self.employee_id.avatar_1920 if self.employee_id_id else None

    @property
    def avatar_1024(self):
        """≙ ``avatar_1024``."""
        return self.employee_id.avatar_1024 if self.employee_id_id else None

    @property
    def avatar_512(self):
        """≙ ``avatar_512``."""
        return self.employee_id.avatar_512 if self.employee_id_id else None

    @property
    def avatar_256(self):
        """≙ ``avatar_256``."""
        return self.employee_id.avatar_256 if self.employee_id_id else None

    @property
    def avatar_128(self):
        """≙ ``avatar_128``."""
        return self.employee_id.avatar_128 if self.employee_id_id else None

    # ------------------------------------------------------------------
    # Métodos
    # ------------------------------------------------------------------

    @classmethod
    def _get_selection_hr_icon_display(cls):
        """≙ ``_get_selection_hr_icon_display`` (``:81-82``) — las opciones
        reales del campo de ``hr.employee``."""
        return list(HrEmployee._meta.get_field('hr_icon_display').choices)

    def _compute_from_employee(self, field_names):
        """≙ ``_compute_from_employee`` (``:84-92``) — copia atributos del
        empleado subyacente; devuelve el dict copiado (aquí no hay
        pseudo-campos que asignar)."""
        if isinstance(field_names, str):
            field_names = [field_names]
        employee = self.employee_id if self.employee_id_id else None
        return {
            field_name: getattr(employee, field_name, None) if employee else None
            for field_name in field_names
        }

    def _compute_country_code(self):
        """≙ ``_compute_country_code`` (``:110-111``)."""
        return self.country_code

    def _compute_is_manager(self, user):
        """≙ ``_compute_is_manager`` (``:113-118``) — ¿este empleado está en
        el subárbol de reportes del empleado de ``user``? El ``child_of``
        se resuelve subiendo por ``parent`` desde el empleado propio."""
        user_employee = user.employee if user is not None else None
        if user_employee is None or not self.employee_id_id:
            return False
        current = self.employee_id
        seen = set()
        while current is not None and current.pk not in seen:
            if current.pk == user_employee.pk:
                return True
            seen.add(current.pk)
            current = current.parent if current.parent_id else None
        return False

    def _compute_is_user(self, user):
        """≙ ``_compute_is_user`` (``:120-124``)."""
        user_employee = user.employee if user is not None else None
        return bool(user_employee is not None
                    and self.employee_id_id == user_employee.pk)

    def _compute_presence_state(self):
        """≙ ``_compute_presence_state`` (``:126-127``)."""
        return self.hr_presence_state

    def _compute_presence_icon(self):
        """≙ ``_compute_presence_icon`` (``:129-131``)."""
        return self.hr_icon_display, self.show_hr_icon_display

    def _compute_member_of_department(self, user):
        """≙ ``_compute_member_of_department`` (``:133-134``) — ¿el empleado
        pertenece al subárbol de departamento del empleado de ``user``?
        DIVERGENCIA: se decide con ``parent_path`` (ver docstring del
        módulo)."""
        user_employee = user.employee if user is not None else None
        own_department = self.department_id if self.department_id_id else None
        user_department = (user_employee.department
                          if user_employee is not None else None)
        if own_department is None or user_department is None:
            return False
        return own_department.parent_path.startswith(user_department.parent_path)

    def _get_manager_only_fields(self):
        """≙ ``_get_manager_only_fields`` (``:136-137``) — verbatim."""
        return []

    @classmethod
    def _search_part_of_department(cls, user):
        """≙ ``_search_part_of_department`` (``:139-146``) — el queryset de
        empleados públicos del subárbol de departamento del usuario.
        DIVERGENCIA: sin ``operator``/``value`` de dominio — el único
        operador soportado allá era ``in``, que es lo que un queryset
        expresa."""
        user_employee = cls._get_valid_employee_for_user(user)
        if user_employee is None:
            return cls.objects.none()
        department = user_employee.department
        if department is None:
            return cls.objects.filter(pk=user_employee.pk)
        return cls.objects.filter(
            department_id__parent_path__startswith=department.parent_path,
        )

    @classmethod
    def _get_valid_employee_for_user(cls, user):
        """≙ ``_get_valid_employee_for_user`` (``:148-159``) — el empleado
        del usuario en la empresa activa, o el primero disponible."""
        if user is None:
            return None
        employee = user.employee
        if employee is not None:
            return employee
        user_employees = list(HrEmployee.objects.filter(resource__user=user))
        for candidate in user_employees:
            if candidate.company_id == user.company_id:
                return candidate
        return user_employees[0] if user_employees else None

    def _compute_manager_only_fields(self, user):
        """≙ ``_compute_manager_only_fields`` (``:161-171``) — los campos
        de sólo-gerente, o ``False`` por campo si ``user`` no es gerente."""
        manager_fields = self._get_manager_only_fields()
        if self._compute_is_manager(user):
            employee = self.employee_id if self.employee_id_id else None
            return {
                field_name: getattr(employee, field_name, None) if employee else None
                for field_name in manager_fields
            }
        return {field_name: False for field_name in manager_fields}

    def _compute_newly_hired(self):
        """≙ ``_compute_newly_hired`` (``:173-174``)."""
        return self.newly_hired

    @classmethod
    def _search_newly_hired(cls, negate=False):
        """≙ ``_search_newly_hired`` (``:176-183``) — los públicos cuyos
        empleados son contrataciones de los últimos 90 días.
        DIVERGENCIA: ``operator in/not in`` → bandera ``negate``."""
        # ``_get_new_hire_field`` es método de instancia en ``hr.employee``
        # (fiel a la referencia); una instancia efímera basta para leerlo.
        new_hire_field = HrEmployee()._get_new_hire_field()
        cutoff = timezone.now() - timedelta(days=90)
        new_hire_ids = HrEmployee.objects.filter(
            **{f'{new_hire_field}__gt': cutoff},
        ).values_list('pk', flat=True)
        if negate:
            return cls.objects.exclude(pk__in=list(new_hire_ids))
        return cls.objects.filter(pk__in=list(new_hire_ids))

    @classmethod
    def _get_fields(cls):
        """La lista SELECT de la vista — ≙ ``_get_fields`` (``:185-193``).

        DIVERGENCIA declarada: la referencia decide columna por columna
        entre ``e`` (empleado) y ``v`` (versión) leyendo el metadata de
        ``hr.version``; aquí las columnas están repartidas en TRES tablas
        (``hr_employee e``, ``hr_version v``, ``resource_resource r``) y el
        mapeo se declara explícito — el metadata de este ORM no distingue
        "delegado a la versión" de "propio".
        """
        return ','.join((
            'e.id AS id',
            'e.id AS employee_id',
            'e.name AS name',
            'e.active AS active',
            'e.created_at AS create_date',
            'v.department_id AS department_id',
            'v.job_id AS job_id',
            'e.company_id AS company_id',
            'v.address_id AS address_id',
            'e.mobile_phone AS mobile_phone',
            'e.work_phone AS work_phone',
            'e.work_email AS work_email',
            'e.work_contact_id AS work_contact_id',
            'v.work_location_id AS work_location_id',
            'r.user_id AS user_id',
            'e.resource_id AS resource_id',
            'e.color AS color',
            'v.resource_calendar_id AS resource_calendar_id',
            'e.parent_id AS parent_id',
            'e.coach_id AS coach_id',
        ))

    @classmethod
    def init(cls):
        """Crea o reemplaza la vista — ≙ ``init`` (``:195-203``).

        El JOIN a la versión y al recurso es LEFT: un empleado sin versión
        vigente o sin recurso sigue siendo visible (con esas columnas en
        NULL) — en la referencia el JOIN interno se sostiene porque
        ``current_version_id`` es obligatorio allá; aquí ``version_id`` es
        opcional (ver ``hr_employee.py``).

        NO la ejecuta ningún flujo de este pase: la migración ``RunSQL``
        que la instala es el sucesor (mismo flujo que ``base.ResDevice``).
        """
        sql = (
            f'CREATE or REPLACE VIEW {cls._meta.db_table} as ('
            f'SELECT {cls._get_fields()} '
            'FROM hr_employee e '
            'LEFT JOIN hr_version v ON v.id = e.version_id '
            'LEFT JOIN resource_resource r ON r.id = e.resource_id'
            ')'
        )
        with connection.cursor() as cursor:
            cursor.execute(sql)

    def get_avatar_card_data(self, field_names):
        """≙ ``get_avatar_card_data`` (``:205-206``) — ``read(fields)`` como
        dict de los atributos pedidos."""
        return {field_name: getattr(self, field_name, None)
                for field_name in field_names}

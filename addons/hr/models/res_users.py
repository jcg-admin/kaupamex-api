"""Extensión de ``res.users`` — el usuario y su empleado (Odoo ``hr``).

Adaptación de Odoo hr/models/res_users.py (odoo-tools@622ddc2a, odoo19c:,
LGPL-3, 339 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

El vínculo usuario ↔ empleado en este árbol
=============================================

La referencia tiene ``hr.employee.user_id`` como columna; aquí el vínculo
vive en el recurso (``resource.ResourceResource.user``) y
``hr.HrEmployee.user`` es una propiedad delegada. Por eso todo camino ORM
de este archivo filtra por ``resource__user`` en vez de ``user_id``.

Porte símbolo por símbolo — 55 símbolos de la referencia
==========================================================

**Constantes de módulo (2)**: ``HR_READABLE_FIELDS`` y
``HR_WRITABLE_FIELDS`` — portadas verbatim (los nombres de campo que listan
son los de la referencia: son un contrato de la capa de preferencias, no
punteros a columnas locales).

**Campos (34)** — 30 son ``related='employee_id.*'`` o computes sin store:
propiedades de sólo lectura sobre ``self.employee`` (la delegación pierde el
sufijo ``_id``/``_ids`` en relacionales, mismo criterio que
``hr_employee.py``); los ``private_*``, ``km_home_work`` y
``additional_note`` delegan un nivel más (``employee.version``, donde esas
columnas viven en este árbol). Detalle:

- ``employee_ids`` → propiedad ``employees`` (queryset por
  ``resource__user``); ``employee_id`` → propiedad ``employee`` (la de la
  empresa activa, ``_compute_company_employee``).
- ``job_title``, ``work_phone``, ``mobile_phone``, ``work_email``,
  ``work_location_name``, ``work_location_type``, ``emergency_contact``,
  ``emergency_phone``, ``visa_expire``, ``barcode``, ``pin`` → delegación
  directa al empleado.
- ``category_ids`` → ``category`` (M2M del empleado);
  ``work_contact_id`` → ``work_contact``; ``work_location_id`` →
  ``work_location``; ``employee_resource_calendar_id`` →
  ``employee_resource_calendar``; ``bank_account_ids`` /
  ``employee_bank_account_ids`` → ``bank_accounts`` (una sola propiedad:
  la propia referencia declara el segundo "no longer appears to be in
  use").
- ``private_street``/``street2``/``city``/``state_id``/``zip``/
  ``country_id``/``phone``/``email`` → ``employee.version.private_*``.
- ``km_home_work`` → DIVERGENCIA de nombre en el destino:
  ``hr.version.distance_home_work`` (así se llama la columna aquí); la
  propiedad conserva el nombre de la referencia.
- ``additional_note`` → ``employee.version.additional_note``.
- ``employee_count`` → propiedad.
- ``create_employee`` / ``create_employee_id`` (``store=False``, "technical
  field") → DIVERGENCIA de mecanismo: eran los flags con que el formulario
  de usuario pedía crear/vincular empleado en ``create()``; aquí las dos
  operaciones son llamadas directas (``action_create_employee`` y
  ``_bind_employee``).
- ``is_system`` / ``_compute_is_system`` → BLOQUEADOS por
  ``base.ResUsers._is_system``: este árbol no tiene flag de superusuario
  (la autorización es por capacidades ``authz``; su propio docstring lo
  declara). Sucesor: DESCONOCIDO con condición de cierre — se porta si
  algún día ``authz`` define "usuario de sistema" como predicado.
- ``is_hr_user`` → propiedad (DIVERGENCIA: predica sobre ESTE usuario;
  la referencia computaba el del entorno para cada fila, que es soporte de
  formulario).

**Métodos (19)** — tabla:

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_employee_ids_domain`` (``:57-60``)
     - portado — devuelve el ``Q`` de empresas activas
   * - ``_compute_is_system`` (``:110-112``)
     - BLOQUEADO (ver ``is_system`` arriba)
   * - ``_compute_is_hr_user`` (``:114-117``)
     - portado — cuerpo de la propiedad ``is_hr_user``
   * - ``_compute_employee_count`` (``:119-122``)
     - portado — cuerpo de la propiedad ``employee_count``
   * - ``SELF_READABLE_FIELDS`` / ``SELF_WRITEABLE_FIELDS`` (``:124-131``)
     - portados — DIVERGENCIA: ``base.ResUsers`` no declara la pareja
       (medido: 0 hits), así que no hay ``super()`` que extender; devuelven
       la aportación de ``hr`` y el día que ``base`` porte las suyas se
       encadenan
   * - ``_onchange_private_state_id`` (``:133-136``)
     - BLOQUEADO — ``@api.onchange``, familia (c) de ``hr_employee.py``
   * - ``get_views`` / ``get_view`` (``:138-168``)
     - BLOQUEADOS — vistas del cliente Odoo, familia (b)/(d)
   * - ``create`` (``:170-186``)
     - resuelto con otra forma — ``_bind_employee`` +
       ``action_create_employee`` (los flags transitorios eran el único
       contenido del override; ver campos arriba)
   * - ``_get_employee_fields_to_sync`` (``:188-191``)
     - portado verbatim
   * - ``_get_personal_info_partner_ids_to_notify`` (``:193-199``)
     - portado — lee ``employee.version.hr_responsible``
   * - ``write`` (``:201-249``)
     - portado — método Odoo-style ``write(vals)`` (no existía previo);
       la notificación usa ``MailThread.message_notify`` con cuerpo de
       texto (DIVERGENCIA: sin ``Markup`` ni ``ir.model.fields._get`` —
       los nombres de campo van tal cual)
   * - ``action_get`` (``:251-263``)
     - BLOQUEADO — ``ir.actions.act_window`` + external ids, familia (b)
   * - ``_compute_company_employee`` (``:265-272``)
     - portado — cuerpo de la propiedad ``employee``
   * - ``_search_company_employee`` (``:274-286``)
     - portado — DIVERGENCIA: devuelve el queryset de usuarios con empleado
       (la optimización de inlinear ids con tope ``IN_MAX`` es del planner
       de dominios de Odoo; el ORM de Django compone el JOIN solo)
   * - ``action_create_employee`` (``:288-296``)
     - portado — el ``AccessError`` de empresa se levanta como ``UserError``
       (``exceptions`` de este árbol no declara ``AccessError``; el más
       cercano es ``AccessDenied``, reservado a autenticación)
   * - ``action_open_employees`` (``:298-315``)
     - BLOQUEADO — familia (b)
   * - ``action_related_contact`` (``:317-324``)
     - BLOQUEADO — familia (b)
   * - ``get_formview_action`` (``:326-338``)
     - BLOQUEADO — familia (b)

``_inherit`` lo expresa ``extend_model``; par de Django porque
``base.ResUsers`` no declara ``_name`` (:ref:`h-api-618`, tarea #385).
"""
from django.db import models as dj_models

from addons.base.models import ResPartnerBank
from addons.hr.models.hr_employee import HrEmployee
from addons.hr.models.hr_employee_category import HrEmployeeCategory
from exceptions import UserError
from orm.environments import get_current_companies, get_current_company
from orm.model_classes import extend_model
from tools.translate import _

#: ≙ ``HR_READABLE_FIELDS`` (``odoo19c: hr/models/res_users.py:15-25``) —
#: verbatim: contrato de la capa de preferencias del usuario.
HR_READABLE_FIELDS = [
    'active',
    'child_ids',
    'employee_id',
    'employee_ids',
    'is_hr_user',
    'is_system',
    'employee_resource_calendar_id',
    'work_contact_id',
    'bank_account_ids',
]

#: ≙ ``HR_WRITABLE_FIELDS`` (``:27-51``) — verbatim.
HR_WRITABLE_FIELDS = [
    'additional_note',
    'private_street',
    'private_street2',
    'private_city',
    'private_state_id',
    'private_zip',
    'private_country_id',
    'private_phone',
    'private_email',
    'barcode',
    'category_ids',
    'display_name',
    'emergency_contact',
    'emergency_phone',
    'employee_bank_account_ids',
    'job_title',
    'km_home_work',
    'mobile_phone',
    'pin',
    'visa_expire',
    'work_email',
    'work_location_id',
    'work_phone',
]


def _employee_ids_domain(self):
    """≙ ``_employee_ids_domain`` (``:57-60``) — el ``Q`` que acota los
    empleados del usuario a las empresas activas."""
    company_ids = get_current_companies()
    if not company_ids:
        return dj_models.Q()
    return dj_models.Q(company_id__in=list(company_ids))


def employees(self):
    """≙ ``employee_ids`` (One2many por ``user_id``; aquí el camino real es
    ``resource__user``), acotado por ``_employee_ids_domain``."""
    return HrEmployee.objects.filter(
        self._employee_ids_domain(), resource__user=self,
    )


def _compute_company_employee(self):
    """El empleado de la empresa activa — ≙ ``_compute_company_employee``
    (``:265-272``)."""
    queryset = HrEmployee.objects.filter(resource__user=self)
    company_id = get_current_company()
    if company_id:
        queryset = queryset.filter(company_id=company_id)
    return queryset.first()


def employee(self):
    """≙ ``employee_id`` — la propiedad que expone
    ``_compute_company_employee``."""
    return self._compute_company_employee()


def _search_company_employee(cls, employee_ids):
    """Usuarios cuyos empleados están en ``employee_ids`` — ≙
    ``_search_company_employee`` (``:274-286``). DIVERGENCIA: queryset
    directo (ver docstring del módulo)."""
    return cls.objects.filter(
        resource_resources__hr_hremployee_resource_mixin_set__pk__in=list(employee_ids),
    ).distinct()


def _compute_is_hr_user(self):
    """≙ ``_compute_is_hr_user`` (``:114-117``)."""
    return self.has_group('hr.group_hr_user')


def is_hr_user(self):
    """≙ ``is_hr_user``."""
    return self._compute_is_hr_user()


def _compute_employee_count(self):
    """≙ ``_compute_employee_count`` (``:119-122``) — con archivados
    incluidos (el ``active_test=False`` de la referencia): el reverso no
    filtra por ``active`` por defecto."""
    return HrEmployee.objects.filter(resource__user=self).count()


def employee_count(self):
    """≙ ``employee_count``."""
    return self._compute_employee_count()


def SELF_READABLE_FIELDS(self):
    """≙ ``SELF_READABLE_FIELDS`` (``:124-127``) — la aportación de ``hr``
    (sin base que extender, ver docstring del módulo)."""
    return HR_READABLE_FIELDS + HR_WRITABLE_FIELDS


def SELF_WRITEABLE_FIELDS(self):
    """≙ ``SELF_WRITEABLE_FIELDS`` (``:129-131``)."""
    return HR_WRITABLE_FIELDS


def _bind_employee(self, employee_to_bind):
    """Vincula un empleado existente a este usuario — ≙ la rama
    ``create_employee_id`` de ``create`` (``:176-177``).

    El vínculo vive en el recurso del empleado (ver docstring del módulo).
    """
    if employee_to_bind.resource_id:
        employee_to_bind.resource.user = self
        employee_to_bind.resource.save(update_fields=['user'])
    return employee_to_bind


def _get_employee_fields_to_sync(self):
    """≙ ``_get_employee_fields_to_sync`` (``:188-191``) — verbatim."""
    return ['name', 'email', 'image_1920', 'tz']


def _get_personal_info_partner_ids_to_notify(self, employee_record):
    """≙ ``_get_personal_info_partner_ids_to_notify`` (``:193-199``).

    DIVERGENCIA de firma: el argumento se llama ``employee_record`` para no
    sombrear la propiedad ``employee`` instalada sobre la clase.
    """
    version = employee_record.version if employee_record.version_id else None
    responsible = version.hr_responsible if version is not None and version.hr_responsible_id else None
    if responsible is not None and responsible.partner_id:
        return (
            _('Recibes este mensaje porque eres el responsable de RR.HH. '
              'de este empleado.'),
            [responsible.partner_id],
        )
    return ('', [])


def write(self, vals):
    """Escribe ``vals`` en el usuario y sincroniza a sus empleados — ≙
    ``write`` (``:201-249``).

    No existía un ``write`` previo en ``base.ResUsers`` (Odoo-style): éste
    lo introduce. Notifica al responsable de RR.HH. cuando cambian campos
    personales delegados al empleado, aplica los valores propios del
    usuario, y propaga ``name``/``email``/``tz`` a los empleados vinculados
    (``email`` llega como ``work_email``).

    DIVERGENCIAS: el cuerpo de la notificación es texto (sin ``Markup`` ni
    descripciones de ``ir.model.fields``); ``image_1920`` de la partición
    con/sin imagen no aplica — el avatar del empleado vive en su
    ``AvatarMixin`` y no se sincroniza desde el usuario en este árbol.
    """
    hr_field_names = [
        field_name for field_name in vals
        if field_name in HR_WRITABLE_FIELDS or field_name in HR_READABLE_FIELDS
    ]
    linked_employees = list(HrEmployee.objects.filter(
        _employee_ids_domain(self), resource__user=self,
    ))
    if hr_field_names:
        for employee_record in linked_employees:
            reason_message, partners = self._get_personal_info_partner_ids_to_notify(
                employee_record,
            )
            if partners:
                employee_record.message_notify(
                    partners,
                    body=_(
                        'Actualización de información personal.\n'
                        'Los siguientes campos fueron modificados por '
                        '%(name)s:\n%(fields)s\n%(reason)s',
                        name=employee_record.name,
                        fields=', '.join(hr_field_names),
                        reason=reason_message,
                    ),
                )

    own_field_names = {field.name for field in self._meta.concrete_fields}
    changed = []
    for field_name, value in vals.items():
        if field_name in own_field_names:
            setattr(self, field_name, value)
            changed.append(field_name)
    if changed:
        self.save(update_fields=changed)

    employee_values = {}
    for field_name in [f for f in self._get_employee_fields_to_sync() if f in vals]:
        employee_values[field_name] = vals[field_name]
    if employee_values:
        if 'email' in employee_values:
            employee_values['work_email'] = employee_values.pop('email')
        # ``tz`` vive en el recurso; ``ResourceMixin`` lo expone como
        # propiedad escribible sobre el empleado.
        for employee_record in linked_employees:
            for field_name, value in employee_values.items():
                setattr(employee_record, field_name, value)
            employee_record.save()
    return True


def action_create_employee(self):
    """Crea el empleado de este usuario en la empresa activa — ≙
    ``action_create_employee`` (``:288-296``).

    DIVERGENCIA: el ``AccessError`` se levanta como ``UserError`` (ver
    tabla del docstring); ``_sync_user`` de la referencia (familia (e) de
    ``hr_employee.py``, no portado) se reduce a los dos campos que aquí
    tienen destino real.
    """
    company_id = get_current_company()
    permitted = self._get_company_ids()
    if company_id and permitted and company_id not in permitted:
        raise UserError(
            _('No puedes crear un empleado: el usuario no tiene acceso a '
              'la empresa activa.'),
        )
    new_employee = HrEmployee.objects.create(
        name=self.name,
        work_email=self.email or '',
        company_id=company_id or self.company_id,
    )
    return self._bind_employee(new_employee)


# --- delegación al empleado de la empresa activa -------------------------

def job_title(self):
    """≙ ``job_title`` (``related='employee_id.job_title'``)."""
    owner = self.employee
    return owner.job_title if owner is not None else ''


def work_phone(self):
    """≙ ``work_phone``."""
    owner = self.employee
    return owner.work_phone if owner is not None else ''


def mobile_phone(self):
    """≙ ``mobile_phone``."""
    owner = self.employee
    return owner.mobile_phone if owner is not None else ''


def work_email(self):
    """≙ ``work_email``."""
    owner = self.employee
    return owner.work_email if owner is not None else ''


def category(self):
    """≙ ``category_ids`` — el M2M de etiquetas del empleado (queryset
    vacío sin empleado)."""
    owner = self.employee
    return owner.category.all() if owner is not None else HrEmployeeCategory.objects.none()


def work_contact(self):
    """≙ ``work_contact_id``."""
    owner = self.employee
    return owner.work_contact if owner is not None and owner.work_contact_id else None


def work_location(self):
    """≙ ``work_location_id`` (delegado dos veces: empleado → versión)."""
    owner = self.employee
    return owner.work_location if owner is not None else None


def work_location_name(self):
    """≙ ``work_location_name``."""
    owner = self.employee
    return owner.work_location_name if owner is not None else ''


def work_location_type(self):
    """≙ ``work_location_type``."""
    owner = self.employee
    return owner.work_location_type if owner is not None else ''


def _version_of_employee(user):
    """La versión vigente del empleado del usuario, o ``None`` — helper
    propio del puerto para los ocho ``private_*`` de abajo."""
    owner = user.employee
    if owner is None or not owner.version_id:
        return None
    return owner.version


def private_street(self):
    """≙ ``private_street`` (aquí vive en ``hr.version``)."""
    version = _version_of_employee(self)
    return version.private_street if version is not None else ''


def private_street2(self):
    """≙ ``private_street2``."""
    version = _version_of_employee(self)
    return version.private_street2 if version is not None else ''


def private_city(self):
    """≙ ``private_city``."""
    version = _version_of_employee(self)
    return version.private_city if version is not None else ''


def private_state(self):
    """≙ ``private_state_id``."""
    version = _version_of_employee(self)
    return version.private_state if version is not None and version.private_state_id else None


def private_zip(self):
    """≙ ``private_zip``."""
    version = _version_of_employee(self)
    return version.private_zip if version is not None else ''


def private_country(self):
    """≙ ``private_country_id``."""
    version = _version_of_employee(self)
    return version.private_country if version is not None and version.private_country_id else None


def private_phone(self):
    """≙ ``private_phone`` (columna del empleado en este árbol)."""
    owner = self.employee
    return owner.private_phone if owner is not None else ''


def private_email(self):
    """≙ ``private_email``."""
    owner = self.employee
    return owner.private_email if owner is not None else ''


def km_home_work(self):
    """≙ ``km_home_work`` — DIVERGENCIA de nombre en el destino: la columna
    aquí es ``hr.version.distance_home_work``."""
    version = _version_of_employee(self)
    return version.distance_home_work if version is not None else 0


def additional_note(self):
    """≙ ``additional_note`` (columna de ``hr.version``)."""
    version = _version_of_employee(self)
    return version.additional_note if version is not None else ''


def bank_accounts(self):
    """≙ ``bank_account_ids`` y ``employee_bank_account_ids`` — la propia
    referencia declara el segundo en desuso; una sola propiedad cubre
    ambos."""
    owner = self.employee
    if owner is None:
        return ResPartnerBank.objects.none()
    return owner.bank_account.all()


def emergency_contact(self):
    """≙ ``emergency_contact``."""
    owner = self.employee
    return owner.emergency_contact if owner is not None else ''


def emergency_phone(self):
    """≙ ``emergency_phone``."""
    owner = self.employee
    return owner.emergency_phone if owner is not None else ''


def visa_expire(self):
    """≙ ``visa_expire``."""
    owner = self.employee
    return owner.visa_expire if owner is not None else None


def barcode(self):
    """≙ ``barcode``."""
    owner = self.employee
    return owner.barcode if owner is not None else ''


def pin(self):
    """≙ ``pin``."""
    owner = self.employee
    return owner.pin if owner is not None else ''


def employee_resource_calendar(self):
    """≙ ``employee_resource_calendar_id``
    (``related='employee_id.resource_calendar_id'``)."""
    owner = self.employee
    return owner.resource_calendar if owner is not None and owner.resource_calendar_id else None


def apply_hr_res_users_extensions():
    """Cuelga sobre ``res.users`` lo que ``hr`` le añade — ≙ ``_inherit``."""
    extend_model(
        'base', 'ResUsers',
        metodos={
            '_employee_ids_domain': _employee_ids_domain,
            '_compute_company_employee': _compute_company_employee,
            '_search_company_employee': classmethod(_search_company_employee),
            '_compute_is_hr_user': _compute_is_hr_user,
            '_compute_employee_count': _compute_employee_count,
            '_bind_employee': _bind_employee,
            '_get_employee_fields_to_sync': _get_employee_fields_to_sync,
            '_get_personal_info_partner_ids_to_notify': _get_personal_info_partner_ids_to_notify,
            'write': write,
            'action_create_employee': action_create_employee,
        },
        propiedades={
            'employees': employees,
            'employee': employee,
            'is_hr_user': is_hr_user,
            'employee_count': employee_count,
            'SELF_READABLE_FIELDS': SELF_READABLE_FIELDS,
            'SELF_WRITEABLE_FIELDS': SELF_WRITEABLE_FIELDS,
            'job_title': job_title,
            'work_phone': work_phone,
            'mobile_phone': mobile_phone,
            'work_email': work_email,
            'category': category,
            'work_contact': work_contact,
            'work_location': work_location,
            'work_location_name': work_location_name,
            'work_location_type': work_location_type,
            'private_street': private_street,
            'private_street2': private_street2,
            'private_city': private_city,
            'private_state': private_state,
            'private_zip': private_zip,
            'private_country': private_country,
            'private_phone': private_phone,
            'private_email': private_email,
            'km_home_work': km_home_work,
            'additional_note': additional_note,
            'bank_accounts': bank_accounts,
            'emergency_contact': emergency_contact,
            'emergency_phone': emergency_phone,
            'visa_expire': visa_expire,
            'barcode': barcode,
            'pin': pin,
            'employee_resource_calendar': employee_resource_calendar,
        },
    )

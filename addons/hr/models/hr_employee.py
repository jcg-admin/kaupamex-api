"""``hr.employee`` — un empleado (Odoo ``hr``).

Adaptación de Odoo hr/models/hr_employee.py (odoo-tools@622ddc2a, odoo19c:,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia (172 ``def`` reportaba un grep amplio
que también contaba asignaciones ``    _foo = ...``; el conteo real de
métodos de la clase, por AST, es **120**; ver
``calibration-verified-numbers.md``): 114 símbolos de clase (7 atributos de
ORM + 2 constraints + 105 campos) y 120 métodos.

Premisa verificada
===================

``_inherits = {'hr.version': 'version_id'}`` (``:43``) es el mecanismo que
gobierna la mitad del archivo: en Odoo 19, ``department_id``, ``job_id``,
``job_title``, ``address_id``, todo el bloque de fechas de contrato
(``contract_date_start``…``contract_type_id``) y el calendario efectivo
(``resource_calendar_id``) **no se declaran en este archivo** — viven en
``hr.version`` y llegan a ``hr.employee`` por delegación (grep confirmado:
``department_id``/``job_id``/``job_title`` dan **0 hits** como asignación de
campo en este archivo). ``hr.version`` **no existe** en este árbol (medido:
``grep -rln "hr.version\\|HrVersion" addons/ src/`` → 0 hits) y está fuera de
la lista de escribibles de esta tarea. Django no tiene ``_inherits``
(herencia por delegación) — no hay forma de fingir esta mitad sin el modelo
delegado real.

**Desenlace:** se portan TODOS los símbolos que la clase declara
**directamente** (no delegados) — campos + métodos que no dependen de
``version_id``/contrato/calendario del contrato/framework de acciones
Odoo/ACL por grupo. Todo lo que depende de esas cuatro familias queda
bloqueado, con su pieza faltante nombrada. Sucesores: ``hr.version`` ya
está portado (tarea #513); la reconexión de los ~83 métodos y ~70 campos
aquí bloqueados es la tarea **#524**.

Cobertura completa símbolo a símbolo: ver el hallazgo :ref:`h-api-683`.

Actualización (tarea #513, H-API-690) — ``hr.version`` ya existe
====================================================================

``hr.version`` **no era un addon separado** (premisa corregida en
``hr_version.py``): es un modelo del propio addon ``hr``
(``odoo19c: addons/hr/models/hr_version.py``), ahora portado a
``addons/hr/models/hr_version.py``. La columna ``version`` (FK real,
sustituta de la delegación ``_inherits`` que Django no tiene) más 23
propiedades conectan los grupos "Identidad de versión", "Contrato" y
"Puesto/departamento" de la tabla histórica de abajo — ver la sección
"Delegación a hr.version — PORTADO" en el cuerpo de la clase.

Aquel pase **no portó ningún método**: conectarlos exigía releer cada uno
contra el ``hr.version`` recién construido, y eso es lo que hace la tarea
#524 (abajo).

Actualización (tarea #524, H-API-712) — familia (a) reconectada
====================================================================

Porte BLOQUEADO — 64 de 120 símbolos

Aritmética medida por AST en este pase (no a ojo — el defecto de
:ref:`h-api-711` es exactamente ése), con el mismo comando que fija
``porte-completo-no-parcial.md``:

===========================================================  ====
métodos de ``HrEmployee`` en ``odoo19c``                      120
presentes aquí **con el mismo nombre**                         44
resueltos con **otra forma** (property, ``save()``/``clean()``) 20
sin resolver                                                   56
===========================================================  ====

Antes de este pase los presentes por nombre eran **20**; la familia (a)
aporta los **24** que faltaban: ``_get_first_versions``,
``_get_first_versions_filtered``, ``_get_first_version_date``,
``_get_first_contract_date``, ``_get_version``,
``_compute_current_version_id``, ``_cron_update_current_version_id``,
``_compute_work_location_name``, ``_compute_work_location_type``,
``_get_all_contract_dates``, ``_get_contract_dates``, ``_is_in_contract``,
``check_no_existing_contract``, ``_get_contract_versions``,
``_get_contracts``, ``_get_versions_with_contract_overlap_with_period``,
``_get_all_versions_with_contract_overlap_with_period``,
``create_version``, ``create_contract``, ``_get_departure_date``,
``_get_tz``, ``_get_tz_batch``, ``_get_version_periods`` y
``_get_calendar_periods``.

Lo que la reconexión confirma, y era la premisa de la tarea: **no es
delegación a** ``self.version``. Nueve de los veinticuatro agregan sobre
**todo** el historial (``self.versions``, el reverso de
``hr.HrVersion.employee``): ``_get_all_contract_dates`` recorre los
intervalos de contrato de todas las versiones, ``_get_first_versions_filtered``
corta la serie en el primer hueco de 4 días, y ``_get_contract_versions``
particiona el historial por ``contract_date_start``.

Mixins heredados — mismo orden que ``_inherit`` de la referencia
==================================================================

``MailThread, MailActivityMixin, ResourceMixin, AvatarMixin,
TimeStampedModel`` — orden fiel a
``_inherit = ['mail.thread.main.attachment', 'mail.activity.mixin',
'resource.mixin', 'avatar.mixin']`` (``:40``), con ``TimeStampedModel`` al
final (mismo patrón que ``ResPartner``/``StockPicking`` en este árbol).

- **``mail.thread.main.attachment``** → se porta como ``MailThread`` a
  secas: el "main attachment" es una variante que fija el adjunto principal
  del chatter; ``MailThread`` de este árbol no distingue esa variante
  (DIVERGENCIA de mecanismo).
- **``resource.mixin``** da ``resource``, ``company`` y ``resource_calendar``
  YA sincronizados en ``save()`` — por eso ``company_id``/``resource_calendar_id``
  de la referencia **no se redeclaran aquí**: ya están, heredados. La
  referencia los hace ``required=True``/delegados-al-contrato; aquí quedan
  opcionales (``company``, mismo D-2 que ``hr_department.py``) o apuntando al
  calendario del recurso en vez del contrato (``resource_calendar``,
  DIVERGENCIA — ver tabla abajo).
- **``avatar.mixin``** da ``image_1920``…``image_128`` + los cinco
  ``avatar_*`` generados.

.. list-table:: Divergencias de campo (declaradas, no bloqueadas)
   :header-rows: 1

   * - Símbolo
     - Desenlace
     - Detalle
   * - ``company_id`` (``required=True``)
     - DIVERGENCIA
     - Llega de ``ResourceMixin.company`` — opcional + ``SET_NULL``, mismo
       criterio D-2 que el resto de la familia ``hr`` en este árbol.
   * - ``resource_calendar_id`` (``related='version_id.resource_calendar_id'``)
     - DIVERGENCIA
     - Llega de ``ResourceMixin.resource_calendar`` (calendario del
       *recurso*, sincronizado en su ``save()``) en vez del calendario del
       *contrato vigente* — no hay contrato sin ``hr.version``.
   * - ``name``/``active`` (``related='resource_id.*', store=True``)
     - DIVERGENCIA
     - Se portan como columnas propias (no ``related``) — mismo D-3 que
       ``hr_department.py``/``hr_job.py``. ``ResourceMixin._create_linked_resource``
       ya lee ``getattr(self, 'name', '')`` para nombrar el recurso, así que
       el valor viaja igual al crear.
   * - ``user_id``, ``user_partner_id``, ``share``, ``phone``, ``email``,
       ``is_user_active`` (``related=...``)
     - DIVERGENCIA
     - Propiedades de sólo lectura que delegan a ``self.resource.user`` —
       mismo criterio que la divergencia 1 de ``resource_resource.py``
       (``avatar_128``/``share``/``email``/``phone`` como ``@property``).
       Quien necesite reasignar el usuario escribe en ``self.resource.user``,
       igual que la ``tz`` de ``ResourceMixin``.
   * - ``im_status`` (``related='user_id.im_status'``)
     - BLOQUEADO por ``base.ResUsers.im_status``
     - ``base.ResUsers`` no declara ``im_status`` — es infraestructura de
       presencia (``bus``) no portada aquí. Sucesor: tarea **#21**
       (integración de la familia ``bus``).
   * - ``lang`` (``Selection`` dinámico vía ``_lang_get``)
     - DIVERGENCIA
     - Se porta como ``Char`` (código de ``base.ResLang.code``) en vez de
       ``Selection`` de opciones dinámicas — este ORM no resuelve un
       ``Selection`` contra una tabla en tiempo de metadata. ``_lang_get``
       SÍ se porta como classmethod (ver métodos).
   * - ``certificate`` (``Selection`` dinámico vía ``_get_certificate_selection``)
     - DIVERGENCIA
     - ``TextChoices`` fijo (``Certificate``) — mismo criterio que
       ``hr_work_location.py::LocationType``. ``_get_certificate_selection``
       se conserva como método (devuelve la misma lista, ver métodos).
   * - ``employee_properties`` (``fields.Properties``)
     - BLOQUEADO por ``company_id.employee_properties_definition``
     - ``PropertiesBaseDefinitionMixin`` existe en ``base`` pero el cableado
       específico a ``company_id.employee_properties_definition`` no está
       construido — mecanismo transversal, fuera de alcance de este archivo.
       Sucesor: tarea **#515**.

.. list-table:: Campos delegados a ``hr.version`` — RESUELTOS (tarea #513)
   :header-rows: 1

.. note::
   Tabla histórica de H-API-683 — los 23 campos de abajo (``version_ids`` es
   el reverso automático, no cuenta) ya se conectaron como propiedades sobre
   ``self.version`` en la sección "Delegación a hr.version — PORTADO" del
   cuerpo de la clase (tarea #513, H-API-690). Se conserva la tabla como
   registro del análisis original.

   * - Grupo
     - Símbolos
     - Motivo
   * - Identidad de versión
     - ``version_id``, ``current_version_id``, ``current_date_version``,
       ``version_ids``, ``versions_count``, ``version_revision``
     - Delegan directamente en ``hr.version`` (``:46-74``), inexistente.
   * - Contrato
     - ``contract_date_start``, ``contract_date_end``, ``trial_date_end``,
       ``contract_wage``, ``date_start``, ``date_end``, ``is_current``,
       ``is_past``, ``is_future``, ``is_in_contract``,
       ``structure_type_id``, ``contract_type_id``
     - ``related='version_id.*', inherited=True`` (``:179-190``).
   * - Puesto/departamento (no declarados en este archivo)
     - ``department_id``, ``job_id``, ``job_title``, ``address_id``,
       ``work_location_id``
     - Grep confirmado: 0 apariciones como campo en
       ``hr_employee.py``; viven en ``hr.version`` y llegan por
       delegación. ``work_location_name``/``work_location_type`` de este
       archivo SÍ están declarados aquí y su cómputo, que lee
       ``version_id.work_location_id`` (``:515-523``), quedó reconectado en
       la tarea #524.

Métodos — resumen (detalle completo en :ref:`h-api-683`)
===========================================================

- **PORTADOS CON EL MISMO NOMBRE: 44** — los 20 previos más los 24 de la
  familia (a) que lista la sección "Actualización (tarea #524)":

  ``_compute_coach``, ``_compute_current_version_id``,
  ``_compute_work_contact_details``, ``_compute_work_location_name``,
  ``_compute_work_location_type``, ``_create_work_contacts``,
  ``_cron_update_current_version_id``, ``_get_age``,
  ``_get_all_contract_dates``,
  ``_get_all_versions_with_contract_overlap_with_period``,
  ``_get_calendar_periods``, ``_get_certificate_selection``,
  ``_get_contract_dates``, ``_get_contract_versions``, ``_get_contracts``,
  ``_get_departure_date``,
  ``_get_employee_m2o_to_empty_on_archived_employees``,
  ``_get_first_contract_date``, ``_get_first_version_date``,
  ``_get_first_versions``, ``_get_first_versions_filtered``,
  ``_get_new_hire_field``, ``_get_related_partners``, ``_get_tz``,
  ``_get_tz_batch``, ``_get_user_m2o_to_empty_on_archived_employees``,
  ``_get_version``, ``_get_version_periods``,
  ``_get_versions_with_contract_overlap_with_period``,
  ``_inverse_work_contact_details``, ``_is_in_contract``, ``_lang_get``,
  ``_mail_get_partner_fields``, ``_phone_get_number_fields``,
  ``_remove_work_contact_id``, ``_sync_salary_distribution``,
  ``action_toggle_primary_bank_account_trust``,
  ``check_no_existing_contract``, ``create_contract``, ``create_version``,
  ``generate_random_barcode``, ``get_accounts_with_fixed_allocations``,
  ``get_bank_account_salary_allocation``, ``get_remaining_percentage``.

- **RESUELTOS CON OTRA FORMA: 20** — ocho ``_compute_*`` que aquí son
  ``@property`` (``newly_hired_computed``, ``versions_count``,
  ``version_revision``, ``is_trusted_bank_account``,
  ``has_multiple_bank_accounts``, ``primary_bank_account``,
  ``related_partners_count_computed``, y ``_compute_version_id``, que la
  FK real ``version`` sustituye); seis inlinados en ``save()``/``clean()``
  (``_compute_legal_name``, ``_compute_birthday_public_display_string``,
  ``_compute_work_permit_name``, ``_verify_pin``, ``_verify_barcode``,
  ``_check_salary_distribution``); y los seis del avatar —
  ``_compute_avatar`` + las cinco
  ``_compute_avatar_{1920,1024,512,256,128}``: la referencia las
  sobreescribe con la firma ``(self, avatar_field, image_field)`` para caer
  al avatar del usuario si el empleado no tiene imagen propia; la
  ``AvatarMixin`` de este árbol declara ``_compute_avatar(self,
  image_field)`` (una firma distinta, ver su docstring) — no hay override
  compatible sin tocar ``avatar_mixin.py`` (fuera de la lista de
  escribibles). El avatar generado (inicial + color por hash) sigue
  funcionando vía la mixin; lo que falta es el *fallback al avatar del
  usuario*.
- **SIN RESOLVER: 56** — cuatro familias, tras la tarea #524. La familia
  (a) original (``version_id``/contrato/calendario) ya no aparece entera:
  quedan de ella sólo las seis piezas que dependen de mecanismos ajenos a
  ``hr.version``:

  - BLOQUEADO por ``resource.mixin._get_calendars`` — ``_get_calendars`` es
    un ``super()`` sobre la mixin, que no lo declara; y ``_get_calendar_tz_batch``
    lo consume. Sucesor: tarea **#514**.
  - BLOQUEADO por ``resource.ResourceCalendar._work_intervals_batch`` — el
    motor de intervalos, del que cuelgan ``_get_unusual_days``,
    ``_employee_attendance_intervals``, ``_get_expected_attendances`` y
    ``_get_calendar_attendances``. Sucesor: tarea **#514**.
  - BLOQUEADO por ``base.ResCompany.contract_expiration_notice_period`` —
    ``notify_expiring_contract_work_permit`` lee ese plazo y su hermano
    ``work_permit_expiration_notice_period``, que ``ResCompany`` no declara
    (medido: 0 apariciones en ``addons/`` y ``src/``). Sucesor: tarea **#515**.
  - DIVERGENCIA de mecanismo — ``_search_version_id`` y ``_field_to_sql``
    traducen un dominio Odoo a SQL; aquí la FK ``version`` es una columna
    real y se filtra con el ORM de Django directamente. No es un bloqueo:
    ``orm.Domain`` **existe** (``src/orm/domains.py``, portada por la tarea
    #356), así que citarla como pieza faltante sería falso. Lo que no hace
    falta es la traducción, no la clase.

  Las otras tres familias no cambian: (b) el framework de acciones cliente
  de Odoo, sin equivalente en este stack DRF+React
  (``action_related_contacts``, ``action_create_user(s)``,
  ``action_open_versions``, ``action_open_allocation_wizard``,
  ``action_archive``, ``action_unarchive``, ``get_import_templates``,
  ``get_avatar_card_data``, ``_get_store_avatar_card_fields``); (c)
  ``@api.onchange`` — mecanismo de formulario reactivo ausente
  (``_onchange_user``, ``_onchange_timezone``, ``_onchange_company_id``,
  ``_onchange_contract_template_id``, ``_onchange_contract_date_start``,
  ``_onchange_private_state_id``, ``_onchange_phone_validation_employee``);
  (d) ACL por grupo / mecanismos de recordset Odoo sin equivalente
  (``check_field_access_rights``, ``_has_field_access``, ``_check_access``,
  ``_check_private_fields``, ``_copy_cache_from``, ``get_view``,
  ``get_views``, ``_search``, ``search_fetch``, ``fetch``,
  ``_compute_display_name``, ``_load_demo_data``, ``_load_scenario``,
  ``get_formview_id``, ``get_formview_action``, ``_search_newly_hired``); y
  (e) la mecánica ``_inherits`` de alta/baja (``new``, ``create``,
  ``write``, ``unlink``, ``_create``, ``_prepare_create_values``,
  ``_sync_user``, ``_prepare_resource_values``,
  ``_get_partner_count_depends`` [``@api.depends`` dinámico, sin consumidor
  propio aquí], ``_compute_presence_icon``, ``_compute_presence_state``,
  ``_get_employee_working_now``, ``_compute_last_activity``).

Sucesores de lo que sigue sin resolver: ``hr.version`` ya está portado
(#513) y su familia (a) reconectada (#524). El motor de intervalos de
``resource.calendar``/``resource.resource`` (ya DEFERIDO por falta de
consumidor en ``resource_resource.py`` / ``resource_mixin.py`` de este
mismo addon padre) es la tarea **#514**; los plazos de aviso de contrato en
``ResCompany`` y el cableado de ``employee_properties`` son la tarea
**#515**.
"""
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from random import choice
from string import digits
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.utils import timezone

import fields
import models

from exceptions import UserError
from tools.translate import _

from addons.base.models import (
    ResCountry,
    ResLang,
    ResPartner,
    ResPartnerBank,
    TimeStampedModel,
)
from addons.base.models.avatar_mixin import AvatarMixin
from addons.mail.models import MailActivityMixin, MailThread
from addons.resource.models.resource_mixin import ResourceMixin

from .hr_employee_category import HrEmployeeCategory
from .hr_version import HrVersion


class HrEmployee(MailThread, MailActivityMixin, ResourceMixin, AvatarMixin, TimeStampedModel):
    """``hr.employee`` — un empleado.

    Con ``hr.version`` ya portado (#513) y su familia de métodos reconectada
    (#524), este puerto cubre identidad personal, contacto de trabajo,
    cuentas bancarias con su distribución de nómina, los mixins de
    chatter/actividad/avatar/recurso, y el historial de versiones: puesto,
    departamento, contrato y sus fechas. Lo que sigue sin resolver está
    contado en la cabecera del módulo.
    """

    # Atributos de clase de modelo — los 5 no delegados que la referencia
    # declara verbatim (``odoo19c: hr/models/hr_employee.py:37-42``).
    # ``_inherits`` queda fuera: es el mecanismo que este ORM no tiene, y
    # lo sustituye la FK ``version`` de abajo.
    _name = 'hr.employee'
    _description = "Employee"
    _order = 'name'
    _mail_post_access = 'read'
    _primary_email = 'work_email'

    class Certificate(models.TextChoices):
        """≙ ``_get_certificate_selection`` (``:444-451``), fijo (ver DIVERGENCIA)."""

        GRADUATE = 'graduate', 'Bachillerato'
        BACHELOR = 'bachelor', 'Licenciatura'
        MASTER = 'master', 'Maestría'
        DOCTOR = 'doctor', 'Doctorado'
        OTHER = 'other', 'Otro'

    # --- versión vigente (tarea #513 — el mecanismo que desbloquea la
    # mitad delegada del archivo, ver "Delegación a hr.version" abajo) -----
    version = fields.Many2one(
        HrVersion, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Versión vigente',
        help_text='Odoo version_id — la ``hr.version`` que ``_inherits`` '
                  'delegaba. Aquí es una FK real (Django no tiene '
                  'delegación de campos); ``hr.HrVersion.employee`` '
                  '(``related_name=\'versions\'``) es el reverso — el '
                  'historial completo es ``self.versions.all()``.',
    )

    # --- resource and user (parte NO delegada) --------------------------
    name = fields.Char(
        verbose_name='Nombre del empleado',
        help_text='Odoo name (related=resource_id.name — aquí columna '
                  'propia, ver divergencia del docstring del módulo).',
    )
    active = fields.Boolean(
        default=True, verbose_name='Activo',
        help_text='Odoo active (related=resource_id.active — columna propia).',
    )
    hr_presence_state = fields.Selection(
        choices=[
            ('present', 'Presente'),
            ('absent', 'Ausente'),
            ('archive', 'Archivado'),
            ('out_of_working_hour', 'Fuera de horario')],
        default='out_of_working_hour', verbose_name='Estado de presencia',
        help_text='BLOQUEADO por ``base.ResUsers.presence_ids`` — el cómputo '
                  '(_compute_presence_state) necesita la presencia del '
                  'usuario, infra bus no portada. El campo queda en su '
                  'default. Sucesor: tarea #21.',
    )
    last_activity = fields.Date(
        null=True, blank=True, verbose_name='Última actividad',
        help_text='BLOQUEADO por ``base.ResUsers.presence_ids`` — el cómputo '
                  '(_compute_last_activity) necesita la presencia del '
                  'usuario, infra bus no portada. Sucesor: tarea #21.',
    )
    last_activity_time = fields.Char(blank=True, default='')
    hr_icon_display = fields.Selection(
        choices=[
            ('presence_present', 'Presente'),
            ('presence_out_of_working_hour', 'Fuera de horario'),
            ('presence_absent', 'Ausente'),
            ('presence_archive', 'Archivado'),
            ('presence_undetermined', 'Indeterminado')],
        blank=True, default='',
        help_text='BLOQUEADO por ``hr_presence_state`` — _compute_presence_icon '
                  'deriva de ese campo, que queda en su default. '
                  'Sucesor: tarea #21.',
    )
    show_hr_icon_display = fields.Boolean(default=False)
    newly_hired = fields.Boolean(
        default=False, verbose_name='Recién contratado',
        help_text='Odoo newly_hired — recomputar con newly_hired property; '
                  'este campo persiste el último valor calculado.',
    )

    company_country_code = fields.Char(blank=True, default='')
    work_phone = fields.Char(blank=True, default='', verbose_name='Teléfono de trabajo')
    mobile_phone = fields.Char(blank=True, default='', verbose_name='Celular de trabajo')
    work_email = fields.Char(blank=True, default='', verbose_name='Correo de trabajo')
    work_contact = fields.Many2one(
        ResPartner, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employee_work_contacts',
        verbose_name='Contacto de trabajo',
        help_text='Odoo work_contact_id.',
    )

    # --- private info -----------------------------------------------------
    legal_name = fields.Char(
        blank=True, default='', verbose_name='Nombre legal',
        help_text='Odoo legal_name (compute+store+readonly=False — se '
                  'rellena desde name en save() si está vacío).',
    )
    private_phone = fields.Char(blank=True, default='', verbose_name='Teléfono privado')
    private_email = fields.Char(blank=True, default='', verbose_name='Correo privado')
    lang = fields.Char(
        blank=True, default='', verbose_name='Idioma',
        help_text='Código de base.ResLang.code (Odoo lang — Selection '
                  'dinámico, ver divergencia del docstring del módulo).',
    )
    place_of_birth = fields.Char(blank=True, default='', verbose_name='Lugar de nacimiento')
    country_of_birth = fields.Many2one(
        ResCountry, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_employees_born_here', verbose_name='País de nacimiento',
    )
    birthday = fields.Date(null=True, blank=True, verbose_name='Fecha de nacimiento')
    birthday_public_display = fields.Boolean(default=False, verbose_name='Mostrar a todos los empleados')
    birthday_public_display_string = fields.Char(blank=True, default='hidden')

    bank_account = fields.Many2many(
        ResPartnerBank, blank=True, related_name='hr_employees',
        db_table='hr_employee_bank_account_rel',
        verbose_name='Cuentas bancarias',
        help_text='Odoo bank_account_ids — cuentas para pagar la nómina.',
    )
    salary_distribution = fields.Json(
        null=True, blank=True, default=dict, verbose_name='Distribución de nómina',
        help_text='Odoo salary_distribution: {"<bank_account_id>": '
                  '{"sequence", "amount", "amount_is_percentage"}}.',
    )

    permit_no = fields.Char(blank=True, default='', verbose_name='No. de permiso de trabajo')
    visa_no = fields.Char(blank=True, default='', verbose_name='No. de visa')
    visa_expire = fields.Date(null=True, blank=True, verbose_name='Vencimiento de visa')
    work_permit_expiration_date = fields.Date(null=True, blank=True, verbose_name='Vencimiento de permiso de trabajo')
    has_work_permit = fields.Binary(null=True, blank=True, verbose_name='Permiso de trabajo (archivo)')
    work_permit_scheduled_activity = fields.Boolean(default=False)
    work_permit_name = fields.Char(blank=True, default='')
    certificate = fields.Selection(
        choices=Certificate.choices, blank=True, default='',
        verbose_name='Nivel de estudios',
    )
    study_field = fields.Char(blank=True, default='', verbose_name='Área de estudio')
    study_school = fields.Char(blank=True, default='', verbose_name='Institución')
    emergency_contact = fields.Char(blank=True, default='')
    emergency_phone = fields.Char(blank=True, default='')

    work_location_name = fields.Char(
        blank=True, default='',
        help_text='Odoo work_location_name — lo materializa '
                  '_compute_work_location_name desde version.work_location '
                  'al guardar (tarea #524).',
    )
    work_location_type = fields.Selection(
        choices=[('home', 'Casa'), ('office', 'Oficina'), ('other', 'Otra')],
        blank=True, default='',
        help_text='Odoo work_location_type — lo materializa '
                  '_compute_work_location_type desde version.work_location '
                  'al guardar (tarea #524).',
    )

    # --- employee in company ----------------------------------------------
    parent = fields.Many2one(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children', verbose_name='Gerente',
        help_text='Odoo parent_id.',
    )
    coach = fields.Many2one(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coached_employees', verbose_name='Coach',
        help_text='Odoo coach_id — sincronizado desde parent en save(), '
                  'ver _compute_coach.',
    )
    category = fields.Many2many(
        HrEmployeeCategory, blank=True, related_name='employees',
        db_table='hr_employee_category_rel', verbose_name='Etiquetas',
    )

    # --- misc ---------------------------------------------------------
    color = fields.Integer(default=0, verbose_name='Índice de color')
    barcode = fields.Char(
        blank=True, null=True,
        verbose_name='ID de gafete',
        help_text='Odoo barcode — identificación del empleado. Unicidad vía '
                  'Meta.constraints (``hr_employee_barcode_uniq``), no aquí.',
    )
    pin = fields.Char(blank=True, default='', verbose_name='PIN')
    id_card = fields.Binary(null=True, blank=True, verbose_name='Copia de identificación')
    driving_license = fields.Binary(null=True, blank=True, verbose_name='Licencia de conducir')
    private_car_plate = fields.Char(blank=True, default='')
    related_partners_count = fields.Integer(default=0)

    class Meta:
        db_table = 'hr_employee'
        ordering = ['name']
        verbose_name = 'Empleado'
        verbose_name_plural = 'Empleados'
        # ``_user_uniq`` de la referencia (``:248-251``) está
        # BLOQUEADO por ``user_id`` — aquí es una property, no una columna,
        # y una UniqueConstraint de base de datos necesita la columna.
        # Sucesor: tarea #515.
        constraints = [
            # ``_barcode_uniq`` (``:244-247``) — ``unique=True`` en el campo
            # ya lo cubre a nivel de columna; se declara también aquí para
            # que el nombre de la restricción sea el de la referencia.
            models.UniqueConstraint(
                fields=['barcode'], name='hr_employee_barcode_uniq',
                condition=models.Q(barcode__isnull=False),
            ),
        ]

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------
    # Delegación a resource.user — propiedades de sólo lectura
    # (DIVERGENCIA, ver docstring del módulo)
    # ------------------------------------------------------------------

    @property
    def user(self):
        """≙ ``user_id`` (``related='resource_id.user_id'``)."""
        return self.resource.user if self.resource_id else None

    @property
    def user_partner(self):
        """≙ ``user_partner_id``."""
        return self.user.partner if self.user else None

    @property
    def share(self):
        """≙ ``share`` (``related='user_id.share'``)."""
        return bool(self.user and self.user.share)

    @property
    def phone(self):
        """≙ ``phone`` (``related='user_id.phone'``)."""
        return self.user.phone if self.user else ''

    @property
    def email(self):
        """≙ ``email`` (``related='user_id.email'``)."""
        return self.user.email if self.user else ''

    @property
    def is_user_active(self):
        """≙ ``is_user_active`` (``related='user_id.active'``)."""
        return bool(self.user and self.user.is_active)

    @property
    def currency(self):
        """≙ ``currency_id`` (``related='company_id.currency_id'``)."""
        return self.company.currency if self.company_id else None

    # ------------------------------------------------------------------
    # Delegación a hr.version — PORTADO (tarea #513, cierra H-API-683)
    #
    # Las 24 columnas que la referencia declara ``related='version_id.*',
    # inherited=True`` (grupos "Identidad de versión", "Contrato" y
    # "Puesto/departamento" del docstring del módulo) leen ahora a través de
    # ``self.version`` — mismo patrón que las propiedades de
    # ``resource.user`` de arriba. Sin versión asignada, cada propiedad
    # devuelve el valor vacío de su tipo (``None``/``''``/``False``/
    # ``Decimal('0.00')``), nunca levanta.
    # ------------------------------------------------------------------

    @property
    def current_version(self):
        """≙ ``current_version_id`` — alias de ``version`` en este puerto.

        En la referencia son dos campos distintos (``version_id`` es la base
        ``_inherits``; ``current_version_id`` se recalcula sobre ella vía
        ``_compute_current_version_id``). Aquí una sola FK cumple ambos
        roles — no hay recómputo que diverja de la base.
        """
        return self.version

    @property
    def current_date_version(self):
        """≙ ``current_date_version`` (``related='version_id.date_version'``)."""
        return self.version.date_version if self.version_id else None

    @property
    def versions_count(self):
        """≙ ``versions_count`` (``:198``).

        DIVERGENCIA: ``version_ids`` en sí no necesita property — es el
        reverso automático de ``hr.HrVersion.employee``
        (``related_name='versions'``): ``self.versions.all()``.
        """
        return self.versions.count()

    @property
    def version_revision(self):
        """≙ ``version_revision`` (``:199``) — posición 1-based en el
        historial ordenado por ``date_version``."""
        if not self.version_id:
            return 0
        ordered_ids = list(
            self.versions.order_by('date_version').values_list('pk', flat=True),
        )
        return ordered_ids.index(self.version_id) + 1 if self.version_id in ordered_ids else 0

    @property
    def contract_date_start(self):
        """≙ ``contract_date_start`` (``related='version_id.contract_date_start'``)."""
        return self.version.contract_date_start if self.version_id else None

    @property
    def contract_date_end(self):
        """≙ ``contract_date_end`` (``related='version_id.contract_date_end'``)."""
        return self.version.contract_date_end if self.version_id else None

    @property
    def trial_date_end(self):
        """≙ ``trial_date_end`` (``related='version_id.trial_date_end'``)."""
        return self.version.trial_date_end if self.version_id else None

    @property
    def contract_wage(self):
        """≙ ``contract_wage`` (``related='version_id.contract_wage'``)."""
        if not self.version_id:
            return Decimal('0.00')
        return self.version.contract_wage

    @property
    def date_start(self):
        """≙ ``date_start`` (``related='version_id.date_start'``)."""
        return self.version.date_start if self.version_id else None

    @property
    def date_end(self):
        """≙ ``date_end`` (``related='version_id.date_end'``)."""
        return self.version.date_end if self.version_id else None

    @property
    def is_current(self):
        """≙ ``is_current`` (``related='version_id.is_current'``)."""
        return bool(self.version_id and self.version.is_current)

    @property
    def is_past(self):
        """≙ ``is_past`` (``related='version_id.is_past'``)."""
        return bool(self.version_id and self.version.is_past)

    @property
    def is_future(self):
        """≙ ``is_future`` (``related='version_id.is_future'``)."""
        return bool(self.version_id and self.version.is_future)

    @property
    def is_in_contract(self):
        """≙ ``is_in_contract`` (``related='version_id.is_in_contract'``)."""
        return bool(self.version_id and self.version.is_in_contract)

    @property
    def structure_type(self):
        """≙ ``structure_type_id`` (``related='version_id.structure_type_id'``)."""
        return self.version.structure_type if self.version_id else None

    @property
    def contract_type(self):
        """≙ ``contract_type_id`` (``related='version_id.contract_type_id'``)."""
        return self.version.contract_type if self.version_id else None

    @property
    def department(self):
        """≙ ``department_id`` — no declarado en la referencia; vive en
        ``hr.version`` y llega por delegación (``_inherits``)."""
        return self.version.department if self.version_id else None

    @property
    def job(self):
        """≙ ``job_id`` — idem ``department_id``, delegado."""
        return self.version.job if self.version_id else None

    @property
    def job_title(self):
        """≙ ``job_title`` — no declarado en la referencia; vive en
        ``hr.version`` y llega por delegación (``_inherits``, ``:131``)."""
        return self.version.job_title if self.version_id else ''

    @property
    def address(self):
        """≙ ``address_id`` — idem ``department_id``, delegado."""
        return self.version.address if self.version_id else None

    @property
    def work_location(self):
        """≙ ``work_location_id`` — idem ``department_id``, delegado."""
        return self.version.work_location if self.version_id else None

    @property
    def departure_reason(self):
        """≙ ``departure_reason_id`` — idem ``department_id``, delegado."""
        return self.version.departure_reason if self.version_id else None

    @property
    def departure_description(self):
        """≙ ``departure_description`` — idem ``department_id``, delegado."""
        return self.version.departure_description if self.version_id else ''

    @property
    def departure_date(self):
        """≙ ``departure_date`` — idem ``department_id``, delegado.

        Lo consume ``_get_departure_date`` (tarea #524).
        """
        return self.version.departure_date if self.version_id else None

    # ------------------------------------------------------------------
    # Historial de versiones — PORTADO (tarea #524)
    #
    # Familia (a) de :ref:`h-api-683`: lo que la referencia resuelve leyendo
    # ``version_id``/``version_ids``/contrato/calendario. La reconexión NO es
    # delegación a ``self.version``: la mayoría agrega sobre **todo** el
    # historial (``self.versions``, el reverso de ``hr.HrVersion.employee``).
    #
    # Dos divergencias de forma que aplican a toda la sección y no se repiten
    # en cada docstring:
    #
    # 1. El argumento que la referencia llama ``date`` se llama aquí
    #    ``on_date`` — ``date`` es el tipo importado a nivel de módulo, y
    #    sombrearlo rompe ``date.today()`` dentro del propio método. Mismo
    #    criterio ya aplicado en ``hr_version.py::_is_in_contract``.
    # 2. Los métodos que la referencia ejecuta sobre un recordset
    #    (``_get_tz_batch``, ``_get_contracts``, ``_get_contract_versions``…)
    #    son ``classmethod`` que reciben ``employees`` — mismo patrón que
    #    ``web/models/models.py::web_read(cls, records, …)``.
    # ------------------------------------------------------------------

    def _get_first_versions(self, before_date=None):
        """≙ ``_get_first_versions`` (``:453-458``) — el historial completo.

        DIVERGENCIA: ``self.env.context['before_date']`` → argumento
        explícito. Este ORM no tiene contexto de entorno.
        """
        versions = self.versions.all()
        if before_date:
            return [version for version in versions
                    if version.date_start and version.date_start <= before_date]
        return list(versions)

    def _get_first_versions_filtered(self, no_gap=True, before_date=None):
        """≙ ``_get_first_versions_filtered`` (``:460-486``).

        Devuelve el tramo de versiones que forma la ocupación más antigua
        **continua**: al recorrer el historial de la más nueva a la más
        vieja, un hueco de 4 días o más entre el fin de una y el inicio de
        la siguiente corta la serie.

        BLOQUEADO por ``base.ResUsers.has_group`` — la referencia levanta
        ``AccessError`` si quien llama no está en ``hr.group_hr_user``
        (``:462-463``); medido: 0 apariciones de ``has_group`` y de
        ``group_hr_user`` en ``addons/`` y ``src/``. Es la familia (d) del
        resumen de métodos del módulo. Sucesor: tarea **#573**
        (:ref:`h-api-718`).
        """
        def remove_gap(versions):
            # Un hueco de más de 4 días no se considera la misma ocupación;
            # las versiones llegan ya ordenadas de más nueva a más vieja.
            if not versions:
                return []
            if len(versions) == 1:
                return versions
            current_version = versions[0]
            older_versions = versions[1:]
            current_date = current_version.date_start
            for index, other_version in enumerate(older_versions):
                # date_end vacío se trata como error y corta el recorrido.
                other_end = other_version.date_end or date(2100, 1, 1)
                gap = (current_date - other_end).days if current_date else 0
                current_date = other_version.date_start
                if gap >= 4:
                    return older_versions[0:index] + [current_version]
            return older_versions + [current_version]

        versions = sorted(
            self._get_first_versions(before_date=before_date),
            key=lambda version: (version.date_start or date.min),
            reverse=True,
        )
        if no_gap:
            versions = remove_gap(versions)
        return versions

    def _get_first_version_date(self, no_gap=True):
        """≙ ``_get_first_version_date`` (``:488-490``)."""
        versions = self._get_first_versions_filtered(no_gap=no_gap)
        starts = [version.date_start for version in versions if version.date_start]
        return min(starts) if starts else None

    def _get_first_contract_date(self, no_gap=True):
        """≙ ``_get_first_contract_date`` (``:492-495``)."""
        versions = [version for version in self._get_first_versions_filtered(no_gap=no_gap)
                    if version.contract_date_start]
        starts = [version.contract_date_start for version in versions]
        return min(starts) if starts else None

    def _get_version(self, on_date=None):
        """≙ ``_get_version`` (``:557-567``) — la versión vigente en la fecha.

        Si no hay ninguna válida devuelve la primera del empleado; ``None``
        si el empleado no tiene historial.
        """
        on_date = on_date or date.today()
        versions = list(self.versions.filter(active=True).order_by('date_version'))
        if not versions:
            versions = list(self.versions.all().order_by('date_version'))
        if not versions:
            return None
        filtered = [version for version in versions
                    if version.date_version and version.date_version <= on_date]
        if not filtered:
            return versions[0]
        return max(filtered, key=lambda version: version.date_version)

    def _compute_current_version_id(self):
        """≙ ``_compute_current_version_id`` (``:526-540``) — recalcula la FK.

        La referencia lo declara ``@api.depends('version_ids.date_version',
        'version_ids.active', 'active')``; aquí no hay recómputo automático,
        así que lo invoca ``save()`` y el cron. No escribe si el resultado
        no cambia — misma guarda que la referencia (``:538-540``).
        """
        version = self.versions.filter(
            date_version__lte=date.today(),
        ).order_by('-date_version').first()
        if version is None:
            version = self.versions.order_by('date_version').first()
        if version is not None and self.version_id != version.pk:
            self.version = version
        return version

    @classmethod
    def _cron_update_current_version_id(cls):
        """≙ ``_cron_update_current_version_id`` (``:542-543``).

        La referencia recalcula el campo sobre todo el modelo; aquí escribe
        la FK de los empleados cuya versión vigente cambió.
        """
        updated = 0
        for employee in cls.objects.all():
            previous = employee.version_id
            employee._compute_current_version_id()
            if employee.version_id != previous:
                cls.objects.filter(pk=employee.pk).update(version=employee.version_id)
                updated += 1
        return updated

    def _compute_work_location_name(self):
        """≙ ``_compute_work_location_name`` (``:515-519``)."""
        self.work_location_name = (
            self.work_location.name if self.work_location else ''
        ) or ''
        return self.work_location_name

    def _compute_work_location_type(self):
        """≙ ``_compute_work_location_type`` (``:520-524``).

        DIVERGENCIA: la referencia cae a ``'other'``; aquí el campo admite
        vacío y sólo se rellena cuando hay ubicación, para no inventar un
        tipo en un empleado sin versión.
        """
        location = self.work_location
        self.work_location_type = (location.location_type if location else '') or ''
        return self.work_location_type

    # --- contrato ------------------------------------------------------

    def _get_all_contract_dates(self):
        """≙ ``_get_all_contract_dates`` (``:753-761``).

        Intervalos ``(date_from, date_to)`` en que el empleado está en
        contrato. Un contrato indefinido tiene ``date_to`` en ``None``.
        """
        # ``.order_by()`` sin argumentos LIMPIA el orden por defecto del
        # modelo (``HrVersion.Meta.ordering = ['date_version']``). Sin él,
        # Django añade ``date_version`` al ``SELECT DISTINCT`` y dos
        # versiones del MISMO contrato devuelven el intervalo dos veces —
        # medido sobre la query generada. Ver H-API-713.
        rows = self.versions.filter(
            contract_date_start__isnull=False,
        ).order_by().values_list(
            'contract_date_start', 'contract_date_end',
        ).distinct()
        return sorted(rows, key=lambda row: row[0])

    def _get_contract_dates(self, on_date):
        """≙ ``_get_contract_dates`` (``:763-772``).

        DIVERGENCIA: la referencia devuelve ``(False, False)`` cuando no hay
        contrato; aquí ``(None, None)`` — mismo valor falsy, tipo correcto
        para una columna de fecha de este ORM.
        """
        for date_from, date_to in self._get_all_contract_dates():
            if date_from <= on_date and (date_to is None or date_to >= on_date):
                return date_from, date_to
        return None, None

    def _is_in_contract(self, on_date):
        """≙ ``_is_in_contract`` (``:667-668``)."""
        return self._get_contract_dates(on_date) != (None, None)

    def check_no_existing_contract(self, on_date):
        """≙ ``check_no_existing_contract`` (``:385-391``)."""
        if isinstance(on_date, str):
            on_date = date.fromisoformat(on_date)
        if self._is_in_contract(on_date):
            raise ValidationError(
                _('El empleado ya está en contrato el %s. Elige una fecha '
                  'fuera de los contratos existentes.', on_date.isoformat()),
            )

    @classmethod
    def _get_contract_versions(cls, employees, date_start=None, date_end=None,
                               domain=None):
        """≙ ``_get_contract_versions`` (``:713-751``).

        Devuelve ``{employee_id: {contract_date_start: [versiones]}}``.
        La referencia lo resuelve con ``_read_group`` agrupando por
        ``employee_id`` y ``date_version:day``; aquí es la misma partición
        hecha en Python sobre el queryset ordenado.

        DIVERGENCIA: el argumento ``domain`` es un ``models.Q``, no un
        dominio Odoo — es el equivalente de este ORM.
        """
        version_filter = models.Q(contract_date_start__isnull=False)
        employee_ids = [employee.pk for employee in employees if employee.pk]
        if employee_ids:
            version_filter &= models.Q(employee_id__in=employee_ids)
        if date_start:
            version_filter &= (
                models.Q(contract_date_end__isnull=True)
                | models.Q(contract_date_end__gte=date_start)
            )
        if date_end:
            version_filter &= models.Q(contract_date_start__lte=date_end)
        if domain is not None:
            version_filter &= domain

        contract_versions_by_employee = {}
        versions = HrVersion.objects.filter(version_filter).order_by(
            'employee_id', 'date_version', 'pk',
        )
        for version in versions:
            by_contract = contract_versions_by_employee.setdefault(
                version.employee_id, {},
            )
            by_contract.setdefault(version.contract_date_start, []).append(version)
        return contract_versions_by_employee

    @classmethod
    def _get_contracts(cls, employees, date_start=None, date_end=None,
                       use_latest_version=True, domain=None):
        """≙ ``_get_contracts`` (``:670-711``).

        Para cada empleado, la versión que representa cada contrato: la
        vigente al final del periodo (``use_latest_version=True``) o la del
        inicio. Devuelve ``{employee_id: [versiones]}``.
        """
        contract_versions_by_employee = cls._get_contract_versions(
            employees, date_start, date_end, domain,
        )
        contracts_by_employee = {}
        for employee_id, by_contract in contract_versions_by_employee.items():
            selected = contracts_by_employee.setdefault(employee_id, [])
            for contract_versions in by_contract.values():
                if not use_latest_version:
                    continue
                effective_date = date_end
                if effective_date:
                    correct = [version for version in contract_versions
                               if version.date_version <= effective_date]
                    chosen = correct[-1] if correct else contract_versions[0]
                else:
                    chosen = contract_versions[-1]
                if chosen not in selected:
                    selected.append(chosen)
        return contracts_by_employee

    def _get_versions_with_contract_overlap_with_period(self, date_from, date_to):
        """≙ ``_get_versions_with_contract_overlap_with_period`` (``:1767-1775``)."""
        return list(self.versions.filter(
            models.Q(contract_date_start__isnull=False)
            & models.Q(contract_date_start__lte=date_to)
            & (models.Q(contract_date_end__gte=date_from)
               | models.Q(contract_date_end__isnull=True)),
        ).order_by('date_version', 'pk'))

    @classmethod
    def _get_all_versions_with_contract_overlap_with_period(cls, date_from, date_to):
        """≙ ``_get_all_versions_with_contract_overlap_with_period``
        (``:1633-1640``) — el mismo corte sobre todos los empleados,
        activos y archivados."""
        versions = []
        for employee in cls.objects.all():
            versions.extend(
                employee._get_versions_with_contract_overlap_with_period(
                    date_from, date_to,
                ),
            )
        return versions

    def create_version(self, values):
        """≙ ``create_version`` (``:569-640``) — copia la versión vigente.

        Copia la versión efectiva en ``date_version`` y aplica ``values``
        encima. Si ya existe una versión en esa fecha exacta, la devuelve
        sin duplicar (``:583-584``). Cuando el contrato conserva su inicio
        pero cambia su fin, sincroniza el fin en todas las versiones del
        mismo contrato (``:596-605``).

        DIVERGENCIA: sin ``sudo()``, ``check_access`` ni ``env.protecting``
        (mecanismos de ACL y de caché de la referencia, ``:606-608`` y
        ``:630``); la copia de campos es campo a campo sobre la instancia en
        vez de ``copy_data()``.
        """
        version_date = values.get('date_version')
        if not version_date:
            raise ValueError('date_version is required')
        if isinstance(version_date, str):
            version_date = date.fromisoformat(version_date)
        elif hasattr(version_date, 'date') and not isinstance(version_date, date):
            version_date = version_date.date()

        version_to_copy = self._get_version(version_date)
        if version_to_copy is None:
            version_to_copy = self.versions.order_by('date_version', 'pk').first()
        if version_to_copy is not None and version_to_copy.date_version == version_date:
            return version_to_copy

        date_from, date_to = self._get_contract_dates(version_date)
        contract_date_start = values.get('contract_date_start', date_from)
        contract_date_end = values.get('contract_date_end', date_to)
        if isinstance(contract_date_start, str):
            contract_date_start = date.fromisoformat(contract_date_start)
        if isinstance(contract_date_end, str):
            contract_date_end = date.fromisoformat(contract_date_end)

        if contract_date_start == date_from and contract_date_end != date_to:
            HrVersion.objects.filter(
                employee_id=self.pk, contract_date_start=date_from,
            ).update(contract_date_end=contract_date_end)

        copy_values = self._prepare_version_copy_values(version_to_copy)
        copy_values.update({
            'date_version': version_date,
            'employee': self,
            'contract_date_start': contract_date_start,
            'contract_date_end': contract_date_end,
        })
        if 'active' in values:
            copy_values['active'] = values['active']
        for field_name, field_value in values.items():
            if field_name == 'date_version':
                continue
            copy_values[field_name] = field_value
        return HrVersion.objects.create(**copy_values)

    def _prepare_version_copy_values(self, version):
        """Los valores copiables de ``version`` — ≙ ``copy_data()`` (``:625``).

        Símbolo propio de este puerto: la referencia usa el ``copy_data()``
        genérico del ORM, que no existe aquí. Copia las columnas concretas
        (no M2M ni la pk) de la versión de origen.
        """
        if version is None:
            return {}
        skip = ('employee', 'created_at', 'updated_at')
        values = {}
        for field in HrVersion._meta.concrete_fields:
            if field.primary_key or field.name in skip:
                continue
            # Se indexa por ``field.name`` (no por ``attname``) para que las
            # claves coincidan con las de ``values`` en ``create_version`` y
            # una relación no llegue dos veces (``job`` y ``job_id``).
            values[field.name] = getattr(version, field.name)
        return values

    def create_contract(self, on_date):
        """≙ ``create_contract`` (``:643-665``).

        Supone que no hay contrato vigente en ``on_date``. Si ya existe una
        versión en esa fecha sin contrato, le escribe las fechas; si no,
        crea una versión nueva. El fin del contrato se corta el día antes
        del siguiente contrato futuro, si lo hay.
        """
        if isinstance(on_date, str):
            on_date = date.fromisoformat(on_date)

        contracts = self._get_contract_versions([self], None, None).get(self.pk, {})
        future_contract_dates = [start for start in contracts if start > on_date]
        new_contract_date_end = (
            min(future_contract_dates) - timedelta(days=1)
            if future_contract_dates else None
        )

        version_same_date = self.versions.filter(date_version=on_date).first()
        if version_same_date is not None:
            version_same_date.contract_date_start = on_date
            version_same_date.contract_date_end = new_contract_date_end
            version_same_date.save()
            return version_same_date

        return self.create_version({
            'date_version': on_date,
            'contract_date_start': on_date,
            'contract_date_end': new_contract_date_end,
        })

    def _get_departure_date(self):
        """≙ ``_get_departure_date`` (``:1759-1765``) — default del wizard
        de baja: sólo hay fecha de salida si el contrato ya terminó."""
        end = self.date_end
        if end and end < date.today():
            return self.departure_date
        return None

    # --- zona horaria y periodos de versión ----------------------------

    def _get_tz(self):
        """≙ ``_get_tz`` (``:1545-1550``) — la primera zona válida entre el
        calendario del empleado, la suya, la de la empresa y ``UTC``."""
        if self.resource_calendar_id and self.resource_calendar.tz:
            return self.resource_calendar.tz
        if self.tz:
            return self.tz
        company_calendar = self.company.resource_calendar if self.company_id else None
        if company_calendar is not None and company_calendar.tz:
            return company_calendar.tz
        return 'UTC'

    @classmethod
    def _get_tz_batch(cls, employees):
        """≙ ``_get_tz_batch`` (``:1552-1556``) — ``{employee_id: tz}``."""
        return {employee.pk: employee._get_tz() for employee in employees}

    @classmethod
    def _get_version_periods(cls, employees, start, stop, field=None,
                             check_contract=False):
        """≙ ``_get_version_periods`` (``:1594-1624``).

        Trocea ``[start, stop]`` en los tramos que cubre cada versión, en
        UTC. Devuelve ``{employee_id: [(desde, hasta, valor)]}``, donde el
        valor es ``getattr(version, field)`` o la versión misma.

        ``start`` y ``stop`` deben traer zona (``tzinfo``): los extremos de
        cada tramo se calculan en la zona de la versión y se comparan con
        ellos, y Python no compara un ``datetime`` con zona contra uno sin
        ella. La referencia opera en UTC naíf y no necesita decirlo.

        DIVERGENCIA: zonas con ``zoneinfo`` de la biblioteca estándar, no
        ``pytz`` — misma decisión que ``resource_calendar_leaves.py``.
        """
        if field and not hasattr(HrVersion, field):
            raise UserError(
                _('El campo %(field_name)s no existe en este modelo '
                  '(hr.version).', field_name=field),
            )
        version_periods_by_employee = {}
        for employee in employees:
            if check_contract:
                versions = employee._get_versions_with_contract_overlap_with_period(
                    start.date(), stop.date(),
                )
            else:
                versions = [
                    version for version in employee.versions.order_by('date_version')
                    if version.date_start and version.date_start <= stop.date()
                    and (version.date_end is None or version.date_end >= start.date())
                ]
            periods = version_periods_by_employee.setdefault(employee.pk, [])
            for version in versions:
                # Contrato totalmente flexible: sin calendario, manda la
                # zona del propio empleado (≙ ``:1617-1618``).
                tz_name = (
                    version.resource_calendar.tz
                    if version.resource_calendar_id and version.resource_calendar.tz
                    else (employee._get_tz())
                )
                tz = ZoneInfo(tz_name)
                date_start = datetime.combine(
                    version.date_start, time.min, tzinfo=tz,
                ).astimezone(ZoneInfo('UTC'))
                if version.date_end:
                    date_end = datetime.combine(
                        version.date_end + timedelta(days=1), time.min, tzinfo=tz,
                    ).astimezone(ZoneInfo('UTC'))
                else:
                    date_end = stop
                periods.append((
                    max(date_start, start),
                    min(date_end, stop),
                    getattr(version, field) if field else version,
                ))
        return version_periods_by_employee

    @classmethod
    def _get_calendar_periods(cls, employees, start, stop, check_contract=True):
        """≙ ``_get_calendar_periods`` (``:1626-1631``) — los mismos tramos,
        con el calendario de cada versión como valor."""
        return cls._get_version_periods(
            employees, start, stop, 'resource_calendar', check_contract,
        )

    # ------------------------------------------------------------------
    # Identidad / clasificación — PORTADOS
    # ------------------------------------------------------------------

    @classmethod
    def _lang_get(cls):
        """Idiomas activos — ≙ ``self.env['res.lang'].get_installed()`` (``:76-78``)."""
        return list(ResLang.objects.filter(active=True).values_list('code', 'name'))

    @classmethod
    def _get_certificate_selection(cls):
        """≙ ``_get_certificate_selection`` (``:443-451``) — lista, no ``TextChoices``.

        Se conserva la forma de método (además de ``Certificate``, ver
        DIVERGENCIA del docstring del módulo) porque un consumidor puede
        preferir la lista de tuplas cruda.
        """
        return list(cls.Certificate.choices)

    def _get_new_hire_field(self):
        """≙ ``_get_new_hire_field`` (``:419-420``): ``'create_date'`` → ``created_at``."""
        return 'created_at'

    @property
    def newly_hired_computed(self):
        """≙ ``_compute_newly_hired`` (``:422-431``) — contratado hace < 90 días.

        Nombrado distinto de ``newly_hired`` (el campo persistido) porque
        Django no recomputa columnas al leer; ``save()`` sincroniza el
        campo con este valor (ver ``save()``).
        """
        field_name = self._get_new_hire_field()
        reference_value = getattr(self, field_name, None)
        if not reference_value:
            return False
        threshold = timezone.now() - timedelta(days=90)
        if hasattr(reference_value, 'hour'):
            return reference_value > threshold
        return reference_value > threshold.date()

    def _get_age(self, target_date=None):
        """≙ ``_get_age`` (``:1753-1757``).

        DIVERGENCIA: la referencia usa ``dateutil.relativedelta``, que no es
        dependencia de este proyecto (medido: 0 apariciones en
        ``pyproject.toml``/``uv.lock`` fuera de este archivo antes del
        fix). Años completos calculados a mano — mismo resultado que
        ``relativedelta(target_date, birthday).years``.
        """
        if target_date is None:
            target_date = date.today()
        if not self.birthday:
            return 0
        years = target_date.year - self.birthday.year
        if (target_date.month, target_date.day) < (self.birthday.month, self.birthday.day):
            years -= 1
        return years

    def generate_random_barcode(self):
        """≙ ``generate_random_barcode`` (``:1541-1543``)."""
        self.barcode = '041' + ''.join(choice(digits) for _ in range(9))

    def _phone_get_number_fields(self):
        """≙ ``_phone_get_number_fields`` (``:1783-1784``)."""
        return ['mobile_phone']

    def _mail_get_partner_fields(self, introspect_fields=False):
        """≙ ``_mail_get_partner_fields`` (``:1786-1787``)."""
        return ['work_contact_id', 'user_partner_id']

    # ------------------------------------------------------------------
    # Manager / coach — PORTADO (simplificado, ver nota)
    # ------------------------------------------------------------------

    def _compute_coach(self, previous_parent_id=None):
        """≙ ``_compute_coach`` (``:812-820``).

        La referencia compara el coach actual contra el manager PREVIO
        (``version._origin.parent_id``) — Django no tiene ``_origin`` fuera
        de ``save()``; aquí se recibe explícitamente ese valor previo,
        leído por el llamador (típicamente ``save()``, con un
        ``self.__class__.objects.filter(pk=self.pk).values('parent_id')``
        antes de escribir).
        """
        manager = self.parent
        if manager and (self.coach_id == previous_parent_id or not self.coach_id):
            self.coach = manager
        elif not self.coach_id:
            self.coach = None

    # ------------------------------------------------------------------
    # Contacto de trabajo — PORTADO
    # ------------------------------------------------------------------

    def _create_work_contacts(self):
        """≙ ``_create_work_contacts`` (``:799-810``).

        DIVERGENCIA: no pasa ``company_id`` al crear el contacto — el
        ``base.ResPartner`` de este árbol no declara ese campo (medido:
        0 apariciones en ``res_partner.py``; sólo existe ``company_name``,
        un Char de razón social escrita a mano, no la FK de la referencia).
        """
        if self.work_contact_id:
            raise ValueError('El empleado ya tiene un contacto de trabajo.')
        work_contact = ResPartner.objects.create(
            email=self.work_email,
            phone=self.work_phone,
            name=self.name,
            image_1920=self.image_1920,
        )
        self.work_contact = work_contact

    def _compute_work_contact_details(self):
        """≙ ``_compute_work_contact_details`` (``:822-828``)."""
        if self.work_contact_id and self.work_contact.employee_work_contacts.count() <= 1:
            self.work_phone = self.work_contact.phone
            self.work_email = self.work_contact.email

    def _inverse_work_contact_details(self):
        """≙ ``_inverse_work_contact_details`` (``:830-842``)."""
        if not self.work_contact_id:
            self._create_work_contacts()
            return
        if self.work_contact.employee_work_contacts.count() <= 1:
            self.work_contact.email = self.work_email
            self.work_contact.phone = self.work_phone
            self.work_contact.save(update_fields=['email', 'phone'])

    def _remove_work_contact_id(self, user, employee_company=None):
        """≙ ``_remove_work_contact_id`` (``:1314-1323``)."""
        employee_company = employee_company or self.company_id
        old_partner_employees = user.partner.employee_work_contacts.exclude(
            pk=self.pk,
        ).filter(company_id=employee_company)
        old_partner_employees = [
            e for e in old_partner_employees if not e.user
        ]
        for employee in old_partner_employees:
            employee.work_contact = None
            employee.save(update_fields=['work_contact'])

    def _get_related_partners(self):
        """≙ ``_get_related_partners`` (``:959-960``)."""
        partners = []
        if self.work_contact_id:
            partners.append(self.work_contact)
        if self.user_partner:
            partners.append(self.user_partner)
        return partners

    @property
    def related_partners_count_computed(self):
        """≙ ``_compute_related_partners_count`` (``:955-957``)."""
        return len({p.pk for p in self._get_related_partners()})

    # ------------------------------------------------------------------
    # Cuentas bancarias / distribución de nómina — PORTADOS
    # ------------------------------------------------------------------

    @property
    def primary_bank_account(self):
        """≙ ``_compute_primary_bank_account_id`` (``:1824-1834``)."""
        accounts = list(self.bank_account.all())
        if not accounts:
            return None
        distribution = self.salary_distribution or {}
        return min(
            accounts,
            key=lambda acc: distribution.get(str(acc.pk), {}).get('sequence', float('inf')),
        )

    @property
    def is_trusted_bank_account(self):
        """≙ ``_compute_is_trusted_bank_account`` (``:274-276``)."""
        account = self.primary_bank_account
        return bool(account and account.allow_out_payment)

    @property
    def has_multiple_bank_accounts(self):
        """≙ ``_compute_has_multiple_bank_accounts`` (``:278-284``)."""
        return self.bank_account.count() > 1

    def get_accounts_with_fixed_allocations(self):
        """≙ ``get_accounts_with_fixed_allocations`` (``:1836-1840``)."""
        distribution = self.salary_distribution or {}
        return [
            account for account in self.bank_account.all()
            if not distribution.get(str(account.pk), {}).get('amount_is_percentage', True)
        ]

    def get_bank_account_salary_allocation(self, account_id):
        """≙ ``get_bank_account_salary_allocation`` (``:1842-1844``)."""
        info = (self.salary_distribution or {}).get(str(account_id), {})
        return info.get('amount', 0), info.get('amount_is_percentage')

    def get_remaining_percentage(self):
        """≙ ``get_remaining_percentage`` (``:1846-1856``)."""
        distribution = self.salary_distribution or {}
        allocated = sum(
            values.get('amount', 0.0)
            for values in distribution.values()
            if values.get('amount_is_percentage')
        )
        return max(0.0, 100.0 - allocated)

    def action_toggle_primary_bank_account_trust(self):
        """≙ ``action_toggle_primary_bank_account_trust`` (``:1872-1875``)."""
        account = self.primary_bank_account
        if account is None:
            return
        account.allow_out_payment = not account.allow_out_payment
        account.save(update_fields=['allow_out_payment'])

    def _sync_salary_distribution(self):
        """≙ ``_sync_salary_distribution`` (``:287-329``) — puerto fiel del
        algoritmo de redistribución al agregar/quitar cuentas bancarias.

        Se invoca explícitamente (no hay ``@api.depends`` sobre M2M en este
        ORM — DIVERGENCIA de mecanismo: el llamador dispara la
        sincronización tras modificar ``bank_account``, no ocurre sola).
        """
        current = dict(self.salary_distribution or {})
        current_ids = {int(k) for k in current}
        account_ids = set(self.bank_account.values_list('pk', flat=True))

        added_ids = account_ids - current_ids
        removed_ids = current_ids - account_ids
        unchanged_ids = account_ids & current_ids

        ordered = sorted(
            ((i, data) for i, data in current.items() if int(i) in unchanged_ids),
            key=lambda kv: (
                not kv[1].get('amount_is_percentage'),
                kv[1].get('sequence', float('inf')),
            ),
        )
        new_distribution = dict(ordered)

        removed_percentage = sum(
            current[str(i)]['amount']
            for i in removed_ids
            if str(i) in current and current[str(i)]['amount_is_percentage']
        )
        if removed_percentage and ordered:
            first_id = ordered[0][0]
            if new_distribution[first_id]['amount_is_percentage']:
                new_distribution[first_id]['amount'] += removed_percentage

        total_allocated = sum(
            d['amount'] for d in new_distribution.values() if d['amount_is_percentage']
        )
        remaining = max(0.0, 100.0 - total_allocated)
        seq = max((d.get('sequence', 0) for d in new_distribution.values()), default=0)
        currency = self.currency
        amount = currency.round(remaining / len(added_ids)) if added_ids and currency else 0.0
        added_ids = list(added_ids)
        for i, new_id in enumerate(added_ids):
            seq += 1
            if i == len(added_ids) - 1:
                amount = remaining
            new_distribution[str(new_id)] = {
                'amount': amount,
                'amount_is_percentage': True,
                'sequence': seq,
            }
            remaining -= amount

        self.salary_distribution = new_distribution

    def clean(self):
        """Validaciones — ≙ ``_verify_pin`` + ``_verify_barcode`` +
        ``_check_salary_distribution`` (``:1291-1303``, ``:331-350``)."""
        super().clean()
        if self.pin and not self.pin.isdigit():
            raise ValidationError('El PIN debe ser una secuencia de dígitos.')
        if self.barcode and not (
            re.match(r'^[A-Za-z0-9]+$', self.barcode) and len(self.barcode) <= 18
        ):
            raise ValidationError(
                'El ID de gafete debe ser alfanumérico, sin acentos y de '
                'máximo 18 caracteres.',
            )
        distribution = self.salary_distribution or {}
        if distribution:
            total = 0
            check_total = False
            for values in distribution.values():
                amount = values.get('amount')
                is_percentage = values.get('amount_is_percentage', True)
                if is_percentage and (
                    not isinstance(amount, (int, float)) or not (0 <= amount <= 100)
                ):
                    raise ValidationError(
                        'Cada porcentaje de distribución debe ser un número '
                        'entre 0 y 100.',
                    )
                if is_percentage:
                    check_total = True
                    total += amount
            if check_total and abs(total - 100.0) > 1e-4:
                raise ValidationError(
                    'La distribución total de nómina en cuentas bancarias '
                    'debe sumar exactamente 100%.',
                )

    def save(self, *args, **kwargs):
        """Materializa los ``compute``/``inverse`` que la referencia recalcula
        sola: ``legal_name``, ``work_contact``↔``work_phone``/``work_email``,
        ``coach`` (desde ``parent``), ``birthday_public_display_string``,
        ``work_permit_name``, ``newly_hired``. ``ResourceMixin.save()``
        (llamado por ``super()``) crea el ``resource`` ligado si falta.
        """
        previous_parent_id = None
        if self.pk:
            previous = self.__class__.objects.filter(pk=self.pk).values(
                'parent_id',
            ).first()
            if previous:
                previous_parent_id = previous['parent_id']

        if not self.legal_name:
            self.legal_name = self.name

        self._compute_coach(previous_parent_id)

        if self.birthday and self.birthday_public_display:
            self.birthday_public_display_string = self.birthday.strftime('%d %B')
        else:
            self.birthday_public_display_string = 'hidden'

        name_part = self.name.replace(' ', '_') + '_' if self.name else ''
        permit_part = '_' + self.permit_no if self.permit_no else ''
        self.work_permit_name = f'{name_part}work_permit{permit_part}'

        self.newly_hired = self.newly_hired_computed if self.pk else False

        # Historial de versiones (tarea #524): la referencia recalcula estos
        # tres con ``@api.depends``; aquí los materializa el guardado, igual
        # que legal_name o work_permit_name de arriba. Sin pk no hay
        # historial que leer todavía.
        if self.pk:
            self._compute_current_version_id()
        self._compute_work_location_name()
        self._compute_work_location_type()

        super().save(*args, **kwargs)

        # Post-save: lo que depende del pk (bank_account M2M, related_partners
        # count) se sincroniza tras la escritura, igual que el patrón
        # parent_path de hr_department.py.
        new_related_count = self.related_partners_count_computed
        if new_related_count != self.related_partners_count:
            self.related_partners_count = new_related_count
            self.__class__.objects.filter(pk=self.pk).update(
                related_partners_count=new_related_count,
            )

    # ------------------------------------------------------------------
    # Archivado — PORTADO parcial (los helpers; la orquestación multi-
    # registro y el wizard de salida siguen sin resolver: familia (b) del
    # resumen de métodos del módulo)
    # ------------------------------------------------------------------

    def _get_employee_m2o_to_empty_on_archived_employees(self):
        """≙ ``_get_employee_m2o_to_empty_on_archived_employees`` (``:1478-1479``)."""
        return ['parent', 'coach']

    def _get_user_m2o_to_empty_on_archived_employees(self):
        """≙ ``_get_user_m2o_to_empty_on_archived_employees`` (``:1481-1482``)."""
        return []

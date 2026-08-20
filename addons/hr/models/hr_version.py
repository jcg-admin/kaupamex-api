"""``hr.version`` — la versión de carrera de un empleado (Odoo ``hr``).

Adaptación de Odoo hr/models/hr_version.py (odoo-tools@622ddc2a, odoo19c:,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Corrección de premisa (tarea #513)
====================================

La tarea que origina este archivo asumía que ``hr_version`` era un **addon
separado**, ausente del árbol, y pedía construir ``addons/hr_version/`` como
paquete Django nuevo (con su propio ``apps.py``/``__manifest__.py`` en
``INSTALLED_APPS``). Medido antes de escribir una sola línea:

- ``find $ODOO19C/addons -maxdepth 1 -iname "*hr_version*"`` → **0 hits**, en
  Community 19, Enterprise 19 (``odoo19pro-main``) y Enterprise 18/Community 18.
- ``grep -rl "hr_version" $ODOO19C/addons/hr/`` → hr/models/hr_version.py,
  hr/models/__init__.py, hr/models/hr_employee.py, hr/tests/test_hr_version.py.

``hr.version`` es un **modelo declarado dentro del addon ``hr``**
(``odoo19c: addons/hr/models/hr_version.py``), no un addon propio. Por
``referencia-odoo-gobierna-las-decisiones.md`` y la segunda cláusula de
``atributos-de-clase-de-modelo.md`` (el SITIO del archivo se lee contra la
referencia antes de crear uno), el hogar correcto es
``addons/hr/models/hr_version.py`` — el mismo directorio donde ya vive
``hr_employee.py``. Django deriva ``LOCAL_APPS`` del grafo de addons
(``src/config/settings/base.py:_local_apps``); ``addons.hr`` **ya está**
instalada, así que este modelo entra al registro sin tocar
``INSTALLED_APPS`` — no hace falta editar ``src/config/settings/base.py``.

Ver :ref:`h-api-690` para la evidencia completa y el resto de la corrección.

Premisa verificada (Nivel 0a — grep + cita PROVEN)
====================================================

``hr_employee.py`` (``:22-23``) ya documentaba correctamente que
``hr.version`` no existía en este árbol —*"grep -rln 'hr.version\\|HrVersion'
addons/ src/ → 0 hits"*— y declaraba BLOQUEADOS ~70 campos y 83 métodos por su
ausencia. Este archivo cierra esa ausencia. No cambia la premisa de
``hr_employee.py`` (Django no tiene ``_inherits``); construye el modelo
delegado y conecta el subconjunto de campos que ``hr_employee.py`` ya nombró
como bloqueados por él.

Medido por AST sobre la referencia (``odoo19c: addons/hr/models/hr_version.py``,
712 líneas): 1 clase, 7 atributos de clase (5 simples + 2 objetos de tabla:
``Constraint`` + ``UniqueIndex``), 63 campos, 46 métodos.

Desenlace de este porte (NÚCLEO, no exhaustivo — ver hallazgo)
==================================================================

- **Campos: 63/63 con desenlace.** 45 COLUMNA (dato persistido), 14 PROPERTY
  (``related=``/``compute=`` puro sin ``store`` verdadero), 3 divergencia de
  mecanismo (``km_home_work`` pasa de compute+store a property con setter,
  como ``ResourceCalendar.flexible_hours`` ya hace en este árbol), y 1
  campo (``member_of_department``) BLOQUEADO por
  ``_get_valid_employee_for_user`` — la marca completa vive junto a
  ``department``.
- **Métodos: 14/46 PORTADOS** (13 verbatim + ``_default_salary_structure``
  adaptado como ``_default_salary_structure_for_company``), 12 realizados
  como property (divergencia de mecanismo, declarada en el docstring de
  cada una) y 20 BLOQUEADOS por ``self.env`` (sesión/recordset a nivel de
  modelo) — las aristas por símbolo, en 3 familias, viven en el docstring
  de la clase. Conteos medidos por AST contra la fuente, no estimados.
- **Atributos de clase: 7/7** — ``_name``/``_description``/``_order``/
  ``_rec_name``/``_mail_post_access`` verbatim; ``_inherit`` traducido a
  mixins (mismo patrón que ``hr_employee.py``); los dos objetos de tabla
  (``Constraint``, ``UniqueIndex``) → ``Meta.constraints``.
"""
from datetime import date, timedelta
from decimal import Decimal

import fields
import models

from addons.base.models import ResCountry, ResUsers, TimeStampedModel
from addons.base.models.res_country import ResCountryState
from addons.hr.models.hr_payroll_structure_type import HrPayrollStructureType
from addons.mail.models import MailActivityMixin, MailThread


class HrVersion(MailThread, MailActivityMixin, TimeStampedModel):
    """``hr.version`` — una versión (tramo de contrato/puesto) de un empleado.

    Un empleado tiene N ``hr.version`` a lo largo de su carrera (altas,
    cambios de puesto, renovaciones de contrato); ``hr.employee.version``
    (ver ``hr_employee.py``) apunta a la que está vigente. Es el mecanismo
    que la referencia delega vía ``_inherits`` — aquí una FK real más
    propiedades que leen a través de ella, porque Django no tiene
    delegación de campos.

    BLOQUEADO — tres familias, con la pieza que falta nombrada:

    (a) **Sincronización compute→store sin trigger automático.** Django no
        tiene ``@api.depends``: un campo declarado ``compute=`` en la
        referencia se persiste aquí como columna corriente, y el valor lo
        asigna quien escribe el registro (no hay recómputo automático).
        Afecta a: ``_compute_company_id``, ``_compute_job_title``,
        ``_inverse_job_title``, ``_compute_is_custom_job_title``,
        ``_compute_structure_type_id``, ``_inverse_resource_calendar_id``.
        Sucesor: tarea **#558** — señales ``pre_save`` que repliquen
        estos seis cómputos.
    (b) **Sesión/usuario activo (``self.env.user``/``self.env.company``),
        ausente a nivel de modelo.** Afecta a: ``_get_valid_employee_for_user``,
        ``_compute_part_of_department``, ``_search_part_of_department``,
        ``_get_default_address_id``, ``_get_hr_responsible_domain``.
        Sucesor: tarea **#559** — pasar el usuario/compañía activos por
        parámetro desde la capa de vista (DRF), no leerlos del modelo.
    (c) **Framework ORM de recordset por lotes** (``create(vals_list)``
        batch, ``write(vals)`` con sincronización cruzada entre versiones,
        ``@api.constrains`` con ``_read_group`` (``_check_dates``),
        ``@api.ondelete`` (``_unlink_except_last_version``), campos con
        ``search=`` (``_search_start_date``, ``_search_end_date``),
        ``get_formview_action``, y las dos ``ir.actions.act_window``
        (``action_open_version``, ``action_open_version_form_view``) — sin
        equivalente en este stack DRF+React, misma familia (b)/(e) que
        ``hr_employee.py`` ya declaró bloqueada. Sucesor: tarea **#525**
        — ``_check_dates`` en particular es validación de negocio real
        (solapamiento de contratos) y merece su propio método
        ``validate_no_overlapping_contract()`` invocado desde la capa de
        servicio, no heredado de ``clean()``.
    """

    _name = 'hr.version'
    _description = 'Version'
    _mail_post_access = 'read'
    _order = 'date_version'
    _rec_name = 'name'

    class Sex(models.TextChoices):
        """≙ el ``Selection`` inline de ``sex`` (``:81-85``)."""

        MALE = 'male', 'Masculino'
        FEMALE = 'female', 'Femenino'
        OTHER = 'other', 'Otro'

    class DistanceUnit(models.TextChoices):
        """≙ el ``Selection`` inline de ``distance_home_work_unit`` (``:102-105``)."""

        KM = 'kilometers', 'km'
        MILES = 'miles', 'mi'

    class MaritalStatus(models.TextChoices):
        """≙ ``_get_marital_status_selection`` (``:656-663``), fijo (ver métodos)."""

        SINGLE = 'single', 'Soltero(a)'
        MARRIED = 'married', 'Casado(a)'
        COHABITANT = 'cohabitant', 'Unión libre'
        WIDOWER = 'widower', 'Viudo(a)'
        DIVORCED = 'divorced', 'Divorciado(a)'

    class EmployeeType(models.TextChoices):
        """≙ el ``Selection`` inline de ``employee_type`` (``:119-126``)."""

        EMPLOYEE = 'employee', 'Empleado'
        WORKER = 'worker', 'Obrero'
        STUDENT = 'student', 'Estudiante'
        TRAINEE = 'trainee', 'Becario'
        CONTRACTOR = 'contractor', 'Contratista'
        FREELANCE = 'freelance', 'Freelance'

    # --- identidad de la versión ------------------------------------------
    employee = fields.Many2one(
        'hr.HrEmployee', on_delete=models.CASCADE, null=True, blank=True,
        related_name='versions', verbose_name='Empleado',
        help_text='Odoo employee_id — el "dueño" de la versión. Un empleado '
                  'tiene N versiones (historial de carrera); '
                  'hr.HrEmployee.version apunta a la vigente.',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions', verbose_name='Empresa',
        help_text='Odoo company_id (compute+store, default=env.company). '
                  'El auto-sync desde employee.company está '
                  'BLOQUEADO por ``api.depends`` — sin trigger de recómputo, '
                  'lo asigna quien escribe (familia (a)).',
    )
    name = fields.Char(blank=True, default='', verbose_name='Nombre')
    active = fields.Boolean(default=True, verbose_name='Activa')
    date_version = fields.Date(verbose_name='Fecha de versión')
    last_modified_by = fields.Many2one(
        ResUsers, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions_last_modified',
        verbose_name='Modificado por última vez por',
        help_text='Odoo last_modified_uid. DIVERGENCIA: sin default=env.uid '
                  '(usuario de sesión, ausente a nivel de modelo — familia b).',
    )
    last_modified_at = fields.Datetime(
        null=True, blank=True, verbose_name='Modificado por última vez el',
        help_text='Odoo last_modified_date.',
    )

    # --- información personal ----------------------------------------------
    country = fields.Many2one(
        ResCountry, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions_nationality', verbose_name='Nacionalidad',
        help_text='Odoo country_id — "Nationality (Country)".',
    )
    identification_no = fields.Char(
        blank=True, default='', verbose_name='No. de identificación',
        help_text='Odoo identification_id.',
    )
    ssn = fields.Char(
        blank=True, default='', verbose_name='No. de seguridad social',
        help_text='Odoo ssnid.',
    )
    passport_no = fields.Char(
        blank=True, default='', verbose_name='No. de pasaporte',
        help_text='Odoo passport_id.',
    )
    passport_expiration_date = fields.Date(null=True, blank=True, verbose_name='Vencimiento de pasaporte')
    sex = fields.Selection(
        choices=Sex.choices, blank=True, default='', verbose_name='Sexo',
    )
    private_street = fields.Char(blank=True, default='', verbose_name='Calle (privada)')
    private_street2 = fields.Char(blank=True, default='', verbose_name='Calle 2 (privada)')
    private_city = fields.Char(blank=True, default='', verbose_name='Ciudad (privada)')
    private_state = fields.Many2one(
        ResCountryState, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions_private', verbose_name='Estado (privado)',
    )
    private_zip = fields.Char(blank=True, default='', verbose_name='C.P. (privado)')
    private_country = fields.Many2one(
        ResCountry, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions_private', verbose_name='País (privado)',
    )
    distance_home_work = fields.Integer(default=0, verbose_name='Distancia casa-trabajo')
    distance_home_work_unit = fields.Selection(
        choices=DistanceUnit.choices, default=DistanceUnit.KM,
        verbose_name='Unidad de distancia',
    )
    marital = fields.Selection(
        choices=MaritalStatus.choices, default=MaritalStatus.SINGLE,
        verbose_name='Estado civil',
        help_text='DIVERGENCIA: la referencia resuelve las opciones vía '
                  '_get_marital_status_selection (método, se porta abajo); '
                  'aquí son fijas (TextChoices), mismo criterio que Certificate '
                  'en hr_employee.py.',
    )
    spouse_complete_name = fields.Char(blank=True, default='', verbose_name='Nombre del cónyuge')
    spouse_birthdate = fields.Date(null=True, blank=True, verbose_name='Fecha de nacimiento del cónyuge')
    children = fields.Integer(default=0, verbose_name='Hijos dependientes')

    # --- información laboral ------------------------------------------------
    employee_type = fields.Selection(
        choices=EmployeeType.choices, default=EmployeeType.EMPLOYEE,
        verbose_name='Tipo de empleado',
    )
    department = fields.Many2one(
        'hr.HrDepartment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions', verbose_name='Departamento',
    )
    # member_of_department (``odoo19c: addons/hr/models/hr_version.py:128``):
    # BLOQUEADO por ``_get_valid_employee_for_user`` — el cómputo compara el
    # departamento de la versión contra el del empleado del usuario ACTIVO,
    # y su búsqueda (``_search_part_of_department``) hace lo mismo; sin
    # sesión a nivel de modelo (familia (b) del docstring de la clase) no
    # hay valor que persistir ni property que derivar. Sucesor: el mismo de
    # la familia (b).
    job = fields.Many2one(
        'hr.HrJob', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions', verbose_name='Puesto',
    )
    job_title = fields.Char(
        blank=True, default='', verbose_name='Título del puesto',
        help_text='Odoo job_title (compute+inverse+store). BLOQUEADO el '
                  'auto-sync desde job.name — familia (a); se asigna directo.',
    )
    is_custom_job_title = fields.Boolean(
        default=False, verbose_name='Título de puesto personalizado',
        help_text='Odoo is_custom_job_title (compute+store). BLOQUEADO el '
                  'auto-sync — familia (a).',
    )
    address = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions_work_address', verbose_name='Dirección de trabajo',
        help_text='Odoo address_id. DIVERGENCIA: sin default (la referencia '
                  'usa self.env.company.partner_id.address_get([\'default\']) '
                  '— sesión, familia b, ver _get_default_address_id BLOQUEADO).',
    )
    work_location = fields.Many2one(
        'hr.HrWorkLocation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions', verbose_name='Lugar de trabajo',
    )
    departure_reason = fields.Many2one(
        'hr.HrDepartureReason', on_delete=models.PROTECT, null=True, blank=True,
        related_name='hr_versions', verbose_name='Motivo de baja',
    )
    departure_description = fields.Html(blank=True, default='', verbose_name='Información adicional de baja')
    departure_date = fields.Date(null=True, blank=True, verbose_name='Fecha de baja')

    resource_calendar = fields.Many2one(
        'resource.ResourceCalendar', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions', verbose_name='Horario de trabajo',
        help_text='Odoo resource_calendar_id (inverse=_inverse_resource_calendar_id). '
                  'BLOQUEADO el inverse (sincroniza employee.resource.calendar '
                  'cuando esta versión es la vigente) — familia (a).',
    )

    # --- contrato -------------------------------------------------------
    contract_date_start = fields.Date(null=True, blank=True, verbose_name='Inicio de contrato')
    contract_date_end = fields.Date(null=True, blank=True, verbose_name='Fin de contrato')
    trial_date_end = fields.Date(null=True, blank=True, verbose_name='Fin de periodo de prueba')
    contract_template = fields.Many2one(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions_using_template', verbose_name='Plantilla de contrato',
        help_text='Odoo contract_template_id — otra hr.version sin employee_id.',
    )
    structure_type = fields.Many2one(
        'hr.HrPayrollStructureType', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions', verbose_name='Tipo de estructura salarial',
        help_text='Odoo structure_type_id (compute+store, default='
                  '_default_salary_structure). DIVERGENCIA: sin default de '
                  'campo — se porta _default_salary_structure_for_company como '
                  'helper explícito (ver métodos); BLOQUEADO el auto-sync '
                  '(_compute_structure_type_id) — familia (a).',
    )
    wage = fields.Monetary(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Salario', help_text='Odoo wage — salario mensual bruto.',
    )
    contract_type = fields.Many2one(
        'hr.HrContractType', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions', verbose_name='Tipo de contrato',
    )
    additional_note = fields.Text(blank=True, default='', verbose_name='Nota adicional')
    hr_responsible = fields.Many2one(
        ResUsers, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_versions_responsible', verbose_name='Responsable de RH',
        help_text='Odoo hr_responsible_id. DIVERGENCIA: sin default=env.user '
                  'ni domain dinámico (_get_hr_responsible_domain, familia b).',
    )

    class Meta:
        db_table = 'hr_version'
        ordering = ['date_version']
        verbose_name = 'Versión de empleado'
        verbose_name_plural = 'Versiones de empleado'
        constraints = [
            # ≙ ``_check_contract_start_date_defined`` (``:197-200``).
            models.CheckConstraint(
                condition=models.Q(contract_date_end__isnull=True)
                | models.Q(contract_date_start__isnull=False),
                name='hr_version_contract_start_required',
            ),
            # ≙ ``_check_unique_date_version`` (``:202-205``) — índice único
            # parcial: un empleado no puede tener dos versiones activas con
            # la misma fecha efectiva.
            models.UniqueConstraint(
                fields=['employee', 'date_version'],
                condition=models.Q(active=True) & models.Q(employee__isnull=False),
                name='hr_version_unique_active_date_version',
            ),
        ]

    def __str__(self):
        return self.display_name

    # ------------------------------------------------------------------
    # Propiedades — PORTADAS (``related=``/``compute=`` sin store real, o
    # divergencia de mecanismo a property+setter como ``flexible_hours`` de
    # ``ResourceCalendar`` ya hace en este árbol)
    # ------------------------------------------------------------------

    @property
    def display_name(self):
        """≙ ``_compute_display_name`` (``:389-391``).

        DIVERGENCIA: la referencia formatea ``date_version`` con el locale
        del usuario vía babel (``format_date_abbr``); aquí ISO llano — sin
        sesión de idioma a nivel de modelo (familia b).
        """
        if self.employee_id and self.date_version:
            return f'{self.employee.name} — {self.date_version.isoformat()}'
        return self.name or ''

    @property
    def km_home_work(self):
        """≙ ``km_home_work`` (``_compute_km_home_work`` ``:553-555`` +
        ``_inverse_km_home_work`` ``:557-562``; campo ``:100-101``).

        DIVERGENCIA declarada: property+setter en vez de columna espejo —
        mismo criterio que ``ResourceCalendar.flexible_hours`` en este árbol.
        """
        if self.distance_home_work_unit == self.DistanceUnit.MILES:
            return round(self.distance_home_work * 1.609)
        return self.distance_home_work

    @km_home_work.setter
    def km_home_work(self, value):
        if self.distance_home_work_unit == self.DistanceUnit.MILES:
            self.distance_home_work = round(value / 1.609)
        else:
            self.distance_home_work = value

    @property
    def allowed_country_states(self):
        """≙ ``allowed_country_state_ids`` (``_compute_allowed_country_state_ids``
        ``:230-237``; campo ``:90``) — filtro de UI."""
        if self.private_country_id:
            return self.private_country.state_ids.all()
        return ResCountryState.objects.all()

    @property
    def date_start(self):
        """≙ ``_compute_dates`` — mitad ``date_start`` (``:564-568``)."""
        if not self.date_version:
            return None
        if self.contract_date_start:
            return max(self.date_version, self.contract_date_start)
        return self.date_version

    @property
    def date_end(self):
        """≙ ``_compute_dates`` — mitad ``date_end`` (``:569-580``).

        Busca la siguiente versión del mismo empleado por ``date_version``
        (misma query que la referencia hace con ``search(..., limit=1)``,
        aquí con el manager de Django).
        """
        if not self.employee_id or not self.date_version:
            return self.contract_date_end
        next_version = HrVersion.objects.filter(
            employee_id=self.employee_id, date_version__gt=self.date_version,
        ).order_by('date_version').first()
        date_version_end = None
        if next_version:
            date_version_end = next_version.date_version - timedelta(days=1)
        if date_version_end and self.contract_date_end:
            return min(date_version_end, self.contract_date_end)
        if date_version_end:
            return date_version_end
        return self.contract_date_end

    @property
    def is_current(self):
        """≙ ``_compute_is_current`` (``:393-396``)."""
        today = date.today()
        start = self.date_start
        end = self.date_end
        return bool(start) and start <= today and (not end or end >= today)

    @property
    def is_past(self):
        """≙ ``_compute_is_past`` (``:398-401``)."""
        end = self.date_end
        return bool(end) and end < date.today()

    @property
    def is_future(self):
        """≙ ``_compute_is_future`` (``:403-406``)."""
        start = self.date_start
        return bool(start) and start > date.today()

    @property
    def is_in_contract(self):
        """≙ ``_compute_is_in_contract`` (``:408-410``)."""
        return self._is_in_contract()

    @property
    def is_fully_flexible(self):
        """≙ ``_is_fully_flexible`` (``:431-434``) — sin calendario asignado."""
        return not self.resource_calendar_id

    @property
    def is_flexible(self):
        """≙ mitad ``is_flexible`` de ``_compute_is_flexible`` (``:436-440``)."""
        if self.is_fully_flexible:
            return True
        return bool(self.resource_calendar_id and self.resource_calendar.flexible_hours)

    @property
    def tz(self):
        """≙ ``tz`` (``related='employee_id.tz'``, ``:153``)."""
        return self.employee.tz if self.employee_id else None

    @property
    def active_employee(self):
        """≙ ``active_employee`` (``related='employee_id.active'``, ``:176``)."""
        return bool(self.employee_id and self.employee.active)

    @property
    def currency(self):
        """≙ ``currency_id`` (``related='company_id.currency_id'``, ``:177``)."""
        return self.company.currency if self.company_id else None

    @property
    def company_country(self):
        """≙ ``company_country_id`` (``related='company_id.country_id'``, ``:182-183``)."""
        return self.company.country if self.company_id else None

    @property
    def country_code(self):
        """≙ ``country_code`` (``related='company_country_id.code'``, ``:184``)."""
        company_country = self.company_country
        return company_country.code if company_country else ''

    @property
    def contract_wage(self):
        """≙ ``_compute_contract_wage`` (``:460-463``)."""
        return self._get_contract_wage()

    # ------------------------------------------------------------------
    # Métodos — PORTADOS (13/46; sin dependencia de env/acción/onchange/
    # recordset por lotes — ver las tres familias BLOQUEADAS en el docstring)
    # ------------------------------------------------------------------

    @classmethod
    def _get_marital_status_selection(cls):
        """≙ ``_get_marital_status_selection`` (``:655-663``)."""
        return list(cls.MaritalStatus.choices)

    def check_contract_finished(self):
        """≙ ``check_contract_finished`` (``:280-282``)."""
        if self.contract_date_start and not self.contract_date_end:
            raise ValueError(
                'Antes de crear un nuevo contrato, cierra el actual '
                'fijando una fecha de fin.'
            )

    def _is_in_contract(self, on_date=None):
        """≙ ``_is_in_contract`` (``:412-416``)."""
        on_date = on_date or date.today()
        if not self.contract_date_start:
            return False
        start = self.date_start
        end = self.date_end
        return bool(start) and start <= on_date and (not end or end >= on_date)

    def _is_overlapping_period(self, date_from, date_to):
        """≙ ``_is_overlapping_period`` (``:418-429``)."""
        if not (self.contract_date_start and date_from and date_to):
            return False
        period_start = date_from or date.min
        period_end = date_to or date.max
        contract_end = self.date_end or date.max
        start = self.date_start or date.min
        return period_start <= contract_end and start <= period_end

    def _get_contract_wage_field(self):
        """≙ ``_get_contract_wage_field`` (``:471-473``)."""
        return 'wage'

    def _get_contract_wage(self):
        """≙ ``_get_contract_wage`` (``:465-469``)."""
        if not self.pk:
            return Decimal('0.00')
        return getattr(self, self._get_contract_wage_field())

    def _get_normalized_wage(self):
        """≙ ``_get_normalized_wage`` (``:475-486``)."""
        wage = self._get_contract_wage()
        if self.resource_calendar_id:
            hours_per_week = self.resource_calendar.hours_per_week
            if not hours_per_week:
                return Decimal('0.00')
            return wage * 12 / 52 / Decimal(str(hours_per_week))
        return wage

    def _get_salary_costs_factor(self):
        """≙ ``_get_salary_costs_factor`` (``:672-674``)."""
        return 12.0

    def _is_struct_from_country(self, country_code):
        """≙ ``_is_struct_from_country`` (``:676-679``)."""
        return bool(
            self.structure_type_id
            and self.structure_type.country_id
            and self.structure_type.country.code == country_code
        )

    def _get_tz(self):
        """≙ ``_get_tz`` (``:681-685``)."""
        if self.resource_calendar_id and self.resource_calendar.tz:
            return self.resource_calendar.tz
        return self.tz

    @classmethod
    def _get_whitelist_fields_from_template(cls):
        """≙ ``_get_whitelist_fields_from_template`` (``:442-446``)."""
        return [
            'job', 'department', 'contract_type', 'structure_type', 'wage',
            'resource_calendar', 'hr_responsible',
        ]

    def get_values_from_contract_template(self, contract_template):
        """≙ ``get_values_from_contract_template`` (``:448-458``).

        DIVERGENCIA: la referencia excluye campos ``related`` inspeccionando
        ``self.env['hr.version']._fields[field].related`` — sin ese registro
        de metadatos aquí, la whitelist ya sólo nombra columnas propias
        (ver ``_get_whitelist_fields_from_template``), así que el filtro es
        redundante y se omite.
        """
        if not contract_template:
            return {}
        whitelist = self._get_whitelist_fields_from_template()
        return {
            field: getattr(contract_template, f'{field}_id', None)
            or getattr(contract_template, field)
            for field in whitelist
        }

    @staticmethod
    def _default_salary_structure_for_company(company):
        """≙ ``_default_salary_structure`` (``:46-50``).

        DIVERGENCIA: la referencia la usa como ``default=`` de campo
        (necesita ``self`` con env ya resuelto); aquí es un helper explícito
        que la capa de servicio invoca con la compañía activa, no un
        ``default=`` de campo (familia b).
        """
        country = getattr(company, 'country', None)
        structure = HrPayrollStructureType.objects.filter(country=country).first()
        if structure:
            return structure
        return HrPayrollStructureType.objects.filter(country__isnull=True).first()

    def _check_ssnid(self):
        """≙ ``_check_ssnid`` (``:501-505``) — no-op en la referencia.

        La referencia lo declara vacío (``pass``) a propósito: cada
        localización añade su propia validación. Se porta idéntico, como
        punto de extensión documentado, no como validación real.
        """
        return None

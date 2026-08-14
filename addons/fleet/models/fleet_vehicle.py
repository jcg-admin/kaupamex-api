"""``fleet.vehicle`` — el vehículo (Odoo ``fleet``).

Adaptación fiel de Odoo fleet/models/fleet_vehicle.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3). Es el modelo con más campos y lógica
del addon (532 líneas en la referencia); se documentan aquí todas las
divergencias, por ser el corte donde más deferidos hay.

Divergencias documentadas
=========================

1. **No hereda ``avatar.mixin``** — mismo motivo que ``FleetVehicleModel``:
   la referencia redeclara ``image_128 = fields.Image(related='model_id.
   image_128', readonly=True)``, un passthrough de sólo lectura. Aquí es
   ``@property``.

2. **Los campos ``compute=..., store=True, readonly=False`` de la referencia
   (color, seats, doors, model_year, transmission, fuel_type, power,
   horsepower, horsepower_tax, co2, co2_standard, category_id, vehicle_range,
   range_unit, electric_assistance, trailer_hook, brand_id) son "default
   heredado del modelo, pero editable y persistido por instancia" — el
   idioma de Odoo 17+ para "cópialo del padre, pero el usuario puede
   sobreescribirlo". Allá **también son columnas** (``store=True``), así que
   portarlos como campos reales es fidelidad, no un rodeo: lo único que
   diverge es el **disparador**. El motor ``@api.depends`` que recopia en
   cada cambio de ``model_id`` no existe aquí, y su equivalente es el método
   explícito ``sync_fields_from_model()`` (≙ ``_load_fields_from_model``),
   que invoca el llamador. NO se dispara en ``save()`` para no pisar en
   silencio un valor que el usuario ya editó.

3. **``name`` ES columna, igual que en la referencia** —
   ``compute='_compute_vehicle_name', store=True``
   (``odoo19c: fleet/models/fleet_vehicle.py:38``): se guarda para poder
   ordenar y buscar por texto. Aquí se declara como ``fields.Char`` y lo
   calcula ``save()`` a partir de ``compute_vehicle_name()``.

   Hasta ``api@<pendiente>`` era una ``@property``, justificada por una
   convención nuestra ("compute → @property/método") que contradecía a la
   referencia en el único punto donde ésta es explícita: allá el campo se
   almacena **para** poder ordenarlo. Es el defecto que
   ``referencia-odoo-gobierna-las-decisiones`` describe — nuestra costumbre
   sobreescribiendo la forma de la fuente. Ver :ref:`h-api-362`.

4. **``odometer`` (compute+inverse) → ``@property`` con setter**, fiel al
   patrón ``_get_odometer``/``_set_odometer``: leer devuelve el último valor
   de ``fleet.vehicle.odometer``; asignar crea una fila nueva (mismo efecto
   que ``FleetVehicleLogServices.odometer`` — ver ese archivo).

5. **DEFERIDO (no stub) — dependencias de datos semilla no portados:**
   la referencia usa external IDs XML como ``fleet.fleet_vehicle_state_new_
   request``/``fleet_vehicle_state_waiting_list`` (default de ``state_id`` y
   ramas de ``create()``/``write()`` para el flujo de "conductor futuro") y
   ``fleet.fleet_group_user`` (dominio ACL del manager). Sin un fixture
   estable de ``fleet.vehicle.state``, esas ramas no se portan:
   - ``_get_default_state`` (default de ``state`` — queda ``null=True``).
   - La propagación de ``plan_to_change_car``/``plan_to_change_bike`` a
     *otros* vehículos del mismo conductor futuro, en ``create()``/``write()``.
   - El recordatorio ``activity_schedule`` al cambiar de conductor
     ("Specify the End date of...").
   - ``_track_subtype`` (subtype de mensaje ``fleet.mt_fleet_driver_updated``).
   - El dominio ACL de ``manager`` (grupo ``fleet.fleet_group_user``) — el
     campo se porta sin el ``domain=`` (es un filtro de UI, no una
     restricción de datos).

6. **``service_activity`` (compute, depende de ``log_services.activity_
   state``)** SÍ se porta como ``@property`` — ``MailThread.activity_ids``
   ya expone ``MailActivity`` con su propiedad ``state``
   (overdue/today/planned), así que el agregado es reproducible sin datos
   semilla adicionales.

7. **NO se portan los helpers de navegación de vista** (devuelven
   diccionarios ``ir.actions.act_window``, sin equivalente DRF):
   ``return_action_to_open``, ``act_show_log_cost``, ``open_assignation_
   logs``, ``action_send_email``, ``action_open_odometer_report``,
   ``_get_analytic_name`` (usado sólo por el addon no portado
   ``fleet_account``). **SÍ se porta** ``accept_driver_change`` (antes
   ``action_accept_driver_change``): tiene lógica de negocio real (reasigna
   conductor), no sólo navegación.
"""
from datetime import date

import fields
import models

from addons.base.models import SystemParameter, TimeStampedModel
from addons.mail.models import MailThread

from .fleet_vehicle_assignation_log import FleetVehicleAssignationLog
from .fleet_vehicle_model import FUEL_TYPES
from .fleet_vehicle_odometer import FleetVehicleOdometer

# Mapeo modelo → vehículo para sync_fields_from_model (Odoo
# MODEL_FIELDS_TO_VEHICLE). Algunos campos no comparten nombre exacto:
# 'default_co2' del modelo alimenta 'co2' del vehículo, y
# 'default_fuel_type' alimenta 'fuel_type'.
MODEL_FIELDS_TO_VEHICLE = {
    'transmission': 'transmission',
    'model_year': 'model_year',
    'electric_assistance': 'electric_assistance',
    'color': 'color',
    'seats': 'seats',
    'doors': 'doors',
    'trailer_hook': 'trailer_hook',
    'default_co2': 'co2',
    'co2_standard': 'co2_standard',
    'default_fuel_type': 'fuel_type',
    'power': 'power',
    'horsepower': 'horsepower',
    'horsepower_tax': 'horsepower_tax',
    'category': 'category',
    'vehicle_range': 'vehicle_range',
    'power_unit': 'power_unit',
    'range_unit': 'range_unit',
    'brand': 'brand',
}


class FleetVehicle(MailThread, TimeStampedModel):
    """``fleet.vehicle`` — un vehículo concreto de la flota."""

    ODOMETER_UNITS = [('kilometers', 'km'), ('miles', 'mi')]
    TRANSMISSIONS = [('manual', 'Manual'), ('automatic', 'Automática')]
    POWER_UNITS = [('power', 'kW'), ('horsepower', 'Caballos de fuerza (hp)')]
    CO2_EMISSION_UNITS = [('g/km', 'g/km'), ('g/mi', 'g/mi')]
    CONTRACT_STATES = [
        ('futur', 'Próximo'),
        ('open', 'En curso'),
        ('expired', 'Vencido'),
        ('closed', 'Cerrado'),
    ]
    FRAME_TYPES = [('diamant', 'Diamante'), ('trapez', 'Trapecio'), ('wave', 'Wave')]
    RANGE_UNITS = [('km', 'km'), ('mi', 'mi')]

    name = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Marca/Modelo/Placa. Odoo name (compute + store): se '
                  'almacena para poder ordenar y buscar por texto. Lo '
                  'calcula save() con compute_vehicle_name().',
    )
    description = fields.Html(blank=True, default='', help_text='Odoo description.')
    active = fields.Boolean(default=True, help_text='Odoo active.')
    manager = fields.Many2one(
        'base.ResUsers', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fleet_vehicles_managed',
        help_text='Gestor de flota (Odoo manager_id). El ``domain=`` de la '
                   'referencia (grupo fleet.fleet_group_user) no se porta '
                   '— ver punto 5 del docstring del módulo.',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fleet_vehicles', help_text='Odoo company_id.',
    )
    license_plate = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Placa (Odoo license_plate).',
    )
    vin_sn = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Número de chasís/VIN (Odoo vin_sn).',
    )
    driver = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fleet_vehicles_driven',
        help_text='Conductor actual (Odoo driver_id).',
    )
    future_driver = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fleet_vehicles_future_driven',
        help_text='Próximo conductor (Odoo future_driver_id).',
    )
    model = fields.Many2one(
        'fleet.FleetVehicleModel', on_delete=models.PROTECT,
        related_name='vehicles', help_text='Odoo model_id (required).',
    )
    # related='model_id.brand_id', store=True, readonly=False (punto 2).
    brand = fields.Many2one(
        'fleet.FleetVehicleModelBrand', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vehicles_by_brand',
        help_text='Odoo brand_id (related+store; ver sync_fields_from_model).',
    )
    next_assignation_date = fields.Date(
        null=True, blank=True, help_text='Odoo next_assignation_date.',
    )
    order_date = fields.Date(null=True, blank=True, help_text='Odoo order_date.')
    acquisition_date = fields.Date(
        null=True, blank=True, default=date.today,
        help_text='Fecha de alta (Odoo acquisition_date).',
    )
    write_off_date = fields.Date(
        null=True, blank=True,
        help_text='Fecha de baja de placas (Odoo write_off_date).',
    )
    contract_date_start = fields.Date(
        null=True, blank=True, default=date.today,
        help_text='Odoo contract_date_start.',
    )
    color = fields.Char(max_length=50, blank=True, default='', help_text='Odoo color (sync).')
    state = fields.Many2one(
        'fleet.FleetVehicleState', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vehicles',
        help_text='Estado del kanban (Odoo state_id). Sin default — ver '
                   'punto 5 del docstring del módulo.',
    )
    location = fields.Char(max_length=150, blank=True, default='', help_text='Odoo location.')
    seats = fields.Integer(null=True, blank=True, help_text='Odoo seats (sync).')
    model_year = fields.Integer(null=True, blank=True, help_text='Odoo model_year (sync).')
    doors = fields.Integer(null=True, blank=True, help_text='Odoo doors (sync).')
    tags = fields.Many2many(
        'fleet.FleetVehicleTag', blank=True,
        db_table='fleet_vehicle_vehicle_tag_rel', related_name='vehicles',
        help_text='Odoo tag_ids.',
    )
    odometer_unit = fields.Selection(
        max_length=10, choices=ODOMETER_UNITS, default='kilometers',
        help_text='Odoo odometer_unit.',
    )
    transmission = fields.Selection(
        max_length=9, choices=TRANSMISSIONS, null=True, blank=True,
        help_text='Odoo transmission (sync).',
    )
    fuel_type = fields.Selection(
        max_length=23, choices=FUEL_TYPES, null=True, blank=True,
        help_text='Odoo fuel_type (sync de default_fuel_type).',
    )
    power_unit = fields.Selection(
        max_length=10, choices=POWER_UNITS, default='power',
        help_text='Odoo power_unit.',
    )
    horsepower = fields.Float(null=True, blank=True, help_text='Odoo horsepower (sync).')
    horsepower_tax = fields.Float(null=True, blank=True, help_text='Odoo horsepower_tax (sync).')
    power = fields.Float(null=True, blank=True, help_text='Potencia en kW (Odoo power, sync).')
    co2 = fields.Float(
        null=True, blank=True,
        help_text='Emisiones CO₂ (Odoo co2, sync de default_co2).',
    )
    co2_standard = fields.Char(
        max_length=150, blank=True, default='', help_text='Odoo co2_standard (sync).',
    )
    category = fields.Many2one(
        'fleet.FleetVehicleModelCategory', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vehicles',
        help_text='Odoo category_id (related+store; ver sync_fields_from_model).',
    )
    car_value = fields.Float(
        null=True, blank=True,
        help_text='Valor de catálogo con IVA (Odoo car_value).',
    )
    net_car_value = fields.Float(
        null=True, blank=True, help_text='Valor de compra (Odoo net_car_value).',
    )
    residual_value = fields.Float(null=True, blank=True, help_text='Odoo residual_value.')
    plan_to_change_car = fields.Boolean(default=False, help_text='Odoo plan_to_change_car.')
    plan_to_change_bike = fields.Boolean(default=False, help_text='Odoo plan_to_change_bike.')
    frame_type = fields.Selection(
        max_length=7, choices=FRAME_TYPES, null=True, blank=True,
        help_text='Odoo frame_type (bicicletas).',
    )
    electric_assistance = fields.Boolean(
        default=False, help_text='Odoo electric_assistance (sync).',
    )
    frame_size = fields.Float(null=True, blank=True, help_text='Odoo frame_size.')
    vehicle_properties = fields.Properties(
        null=True, blank=True,
        help_text='Propiedades dinámicas del vehículo (Odoo vehicle_properties). '
                   'Sin validación de esquema contra model.vehicle_properties_'
                   'definition (deferido).',
    )
    vehicle_range = fields.Integer(null=True, blank=True, help_text='Odoo vehicle_range (sync).')
    range_unit = fields.Selection(
        max_length=2, choices=RANGE_UNITS, default='km', help_text='Odoo range_unit (sync).',
    )

    class Meta:
        db_table = 'fleet_vehicle'
        ordering = ['license_plate', 'acquisition_date']
        verbose_name = 'Vehículo'
        verbose_name_plural = 'Vehículos'

    def __str__(self):
        return self.name or self.compute_vehicle_name()

    # --- compute → @property (punto 3) ------------------------------------

    def compute_vehicle_name(self):
        """≙ ``_compute_vehicle_name`` — "Marca/Modelo/Placa".

        Devuelve el valor; quien lo persiste es ``save()``. La referencia lo
        recalcula por ``@api.depends('model_id.brand_id.name', 'model_id.name',
        'license_plate')``; aquí el disparador es el propio guardado, que es
        cuando esos tres cambian en esta fila. Un cambio de ``name`` en la
        **marca** o el **modelo** no repropaga a los vehículos ya guardados —
        divergencia declarada, del mismo tipo que la del punto 2.
        """
        brand_name = self.model.brand.name if self.model_id and self.model.brand_id else ''
        model_name = self.model.name if self.model_id else ''
        plate = self.license_plate or 'Sin placa'
        return f'{brand_name}/{model_name}/{plate}'

    @property
    def image_128(self):
        """``related='model_id.image_128', readonly=True``."""
        return self.model.image_128 if self.model_id else None

    @property
    def currency(self):
        """``related='company_id.currency_id'``."""
        return self.company.currency if self.company_id else None

    @property
    def country(self):
        """``related='company_id.country_id'``."""
        return self.company.country if self.company_id else None

    @property
    def country_code(self):
        """``related='country_id.code'``."""
        country = self.country
        return getattr(country, 'code', '') if country else ''

    @property
    def vehicle_type(self):
        """``related='model_id.vehicle_type'``."""
        return self.model.vehicle_type if self.model_id else None

    @property
    def co2_emission_unit(self):
        """``_compute_co2_emission_unit`` — depende de ``range_unit``."""
        return 'g/km' if self.range_unit == 'km' else 'g/mi'

    # --- odometer: compute+inverse → property con setter (punto 4) --------

    @property
    def odometer(self):
        """``_get_odometer`` — el último valor registrado, o 0."""
        last = self.odometer_logs.order_by('-value').first()
        return last.value if last else 0

    @odometer.setter
    def odometer(self, value):
        """``_set_odometer`` — crea una fila nueva en el histórico."""
        if not value:
            return
        FleetVehicleOdometer.objects.create(
            value=value, date=date.today(), vehicle=self, driver=self.driver,
        )

    # --- contadores agregados (compute) → @property ------------------------

    @property
    def contract_count(self):
        return self.log_contracts.count()

    @property
    def service_count(self):
        return self.log_services.count()

    @property
    def odometer_count(self):
        return self.odometer_logs.count()

    @property
    def history_count(self):
        return self.assignation_logs.count()

    @property
    def service_activity(self):
        """``_compute_service_activity`` — agregado de ``activity_ids.state``
        de las bitácoras de servicio (excluye ``planned``); punto 6."""
        states = set()
        for service in self.log_services.all():
            for activity in service.activity_ids:
                if activity.state and activity.state != 'planned':
                    states.add(activity.state)
        return sorted(states)[0] if states else 'none'

    @property
    def has_open_contract(self):
        """Espeja ``FleetVehicleLogContract.has_open_contract`` para este
        vehículo: ¿tiene algún contrato ``open`` vigente?"""
        return self.log_contracts.filter(
            state='open', expiration_date__gte=date.today(),
        ).exists()

    @property
    def contract_state(self):
        """``_compute_contract_reminder`` — estado del contrato más reciente
        (por ``expiration_date``) entre los no cerrados."""
        latest = (
            self.log_contracts.exclude(state='closed')
            .exclude(expiration_date__isnull=True)
            .order_by('-expiration_date')
            .first()
        )
        return latest.state if latest else ''

    @property
    def contract_renewal_overdue(self):
        latest = (
            self.log_contracts.exclude(state='closed')
            .exclude(expiration_date__isnull=True)
            .order_by('-expiration_date')
            .first()
        )
        return bool(latest and latest.expiration_date < date.today())

    @property
    def contract_renewal_due_soon(self):
        latest = (
            self.log_contracts.exclude(state='closed')
            .exclude(expiration_date__isnull=True)
            .order_by('-expiration_date')
            .first()
        )
        if not latest or self.contract_renewal_overdue:
            return False
        delay = int(SystemParameter.get_param('fleet.delay_alert_contract', default=30))
        return (latest.expiration_date - date.today()).days < delay

    # --- sincronización model → vehicle (punto 2) ---------------------------

    def sync_fields_from_model(self, field_names=None):
        """Copia campos de ``self.model`` (Odoo ``_load_fields_from_model``).

        No se dispara automáticamente en ``save()`` — el llamador decide
        cuándo (p. ej. al asignar ``model`` por primera vez desde el
        serializer). ``field_names`` restringe qué campos del vehículo se
        sincronizan; por defecto, todos los de ``MODEL_FIELDS_TO_VEHICLE``.
        """
        if not self.model_id:
            return
        wanted = set(field_names) if field_names is not None else None
        for model_field, vehicle_field in MODEL_FIELDS_TO_VEHICLE.items():
            if wanted is not None and vehicle_field not in wanted:
                continue
            value = getattr(self.model, model_field)
            if value:
                setattr(self, vehicle_field, value)

    # --- historial de conductor ---------------------------------------------

    def create_driver_history(self):
        """``create_driver_history`` — registra la asignación actual."""
        FleetVehicleAssignationLog.objects.create(
            vehicle=self, driver=self.driver, date_start=date.today(),
        )

    def accept_driver_change(self):
        """``action_accept_driver_change`` — confirma futuro → actual.

        Libera este vehículo de otros conductores del mismo tipo que ya
        tenían a ``future_driver`` como actual, y realiza el cambio.

        ``vehicle_type`` es una ``@property`` (delega en ``model.vehicle_
        type``, punto 1 del docstring del módulo) — no una columna, así que
        el filtro cruza la relación real ``model__vehicle_type``.
        """
        type(self).objects.filter(
            driver=self.future_driver, model__vehicle_type=self.vehicle_type,
        ).exclude(pk=self.pk).update(
            driver=None, plan_to_change_car=False, plan_to_change_bike=False,
        )
        self.plan_to_change_bike = False
        self.plan_to_change_car = False
        self.driver = self.future_driver
        self.future_driver = None
        self.save()

    # --- save() — odometer y cierre de bitácoras al desactivar --------------

    def save(self, *args, **kwargs):
        """Puntos del ``write()`` de la referencia que SÍ se portan:

        - Crear historial de conductor cuando ``driver`` cambia (aquí:
          detectado comparando contra el valor previo en BD).
        - Cerrar (``active=False``) contratos y servicios cuando el vehículo
          se desactiva. Se ejecuta siempre que ``active`` es False —a
          diferencia de la referencia, que sólo dispara en la transición—;
          es idempotente (UPDATE sin filas tras la primera vez), documentado
          como simplificación aceptada.

        NO se porta: la validación "el odómetro no puede bajar" (vivía en
        ``write()`` sobre el campo plano; aquí ``odometer`` es una property
        con setter — el check equivalente iría en el serializer, que es
        quien recibe el valor bruto).
        """
        creating = self.pk is None
        previous_driver_id = None
        if not creating:
            previous_driver_id = (
                type(self).objects.filter(pk=self.pk)
                .values_list('driver_id', flat=True).first()
            )
        # ``name`` es columna, como en la referencia: se calcula aquí. Si el
        # llamador acotó las columnas con update_fields, hay que añadirla —
        # si no, la asignación se descarta en silencio y la fila queda con el
        # nombre viejo.
        self.name = self.compute_vehicle_name()
        update_fields = kwargs.get('update_fields')
        if update_fields:
            kwargs['update_fields'] = list(dict.fromkeys([*update_fields, 'name']))
        super().save(*args, **kwargs)
        if self.driver_id and self.driver_id != previous_driver_id:
            self.create_driver_history()
        if not self.active:
            self.log_contracts.update(active=False)
            self.log_services.update(active=False)

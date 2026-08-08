"""``fleet.vehicle.log.contract`` — contrato de un vehículo (Odoo ``fleet``).

Adaptación fiel de Odoo fleet/models/fleet_vehicle_log_contract.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

DEFERIDO (no stub):

- ``scheduler_manage_contract_expiration``/``run_scheduler`` — tarea de cron
  (Odoo ``ir.cron``) que además referencia el external ID
  ``fleet.mail_act_fleet_contract_to_renew`` (tipo de actividad semilla no
  portado). La infraestructura de cron sí existe (``base.IrCron``), pero sin
  el dato semilla el recordatorio no tiene tipo de actividad al que apuntar.
- La derivación automática de ``state`` (futur/open/expired) por fecha en
  cada ``write()`` — se porta como método explícito ``sync_state_from_dates``
  (no autodisparado; ver más abajo), para no mutar el estado en cada
  ``save()`` sin que el llamador lo pida.
- El recordatorio ``activity_reschedule`` al cambiar ``expiration_date``/
  ``user`` — depende del mismo external ID no portado.
"""
from datetime import date

import calendar

import fields
import models

from addons.base.models import TimeStampedModel
from addons.mail.models import MailThread


class FleetVehicleLogContract(MailThread, TimeStampedModel):
    """``fleet.vehicle.log.contract`` — seguro, leasing, mantenimiento, etc."""

    STATE_FUTUR = 'futur'
    STATE_OPEN = 'open'
    STATE_EXPIRED = 'expired'
    STATE_CLOSED = 'closed'
    STATES = [
        (STATE_FUTUR, 'Próximo'),
        (STATE_OPEN, 'En curso'),
        (STATE_EXPIRED, 'Vencido'),
        (STATE_CLOSED, 'Cancelado'),
    ]
    FREQUENCIES = [
        ('no', 'No'),
        ('daily', 'Diaria'),
        ('weekly', 'Semanal'),
        ('monthly', 'Mensual'),
        ('yearly', 'Anual'),
    ]

    vehicle = fields.Many2one(
        'fleet.FleetVehicle', on_delete=models.CASCADE,
        related_name='log_contracts', help_text='Odoo vehicle_id (required).',
    )
    cost_subtype = fields.Many2one(
        'fleet.FleetServiceType', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contracts',
        help_text='Tipo de costo (Odoo cost_subtype_id). El ``domain=[(category, '
                   '=, contract)]`` de la referencia es un filtro de UI, no se '
                   'porta como restricción de datos.',
    )
    amount = fields.Monetary(
        max_digits=12, decimal_places=2, null=True, blank=True, help_text='Odoo amount.',
    )
    date = fields.Date(null=True, blank=True, help_text='Fecha del gasto (Odoo date).')
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fleet_contracts', help_text='Odoo company_id.',
    )
    active = fields.Boolean(default=True, help_text='Odoo active.')
    user = fields.Many2one(
        'base.ResUsers', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fleet_contracts_responsible',
        help_text='Responsable (Odoo user_id; el default desde '
                   'vehicle.manager_id no se auto-aplica — ver sync_defaults).',
    )
    start_date = fields.Date(
        null=True, blank=True, help_text='Odoo start_date (default hoy).',
    )
    expiration_date = fields.Date(
        null=True, blank=True,
        help_text='Odoo expiration_date (default: un año después de start_date; '
                   'ver next_year_date()).',
    )
    insurer = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fleet_contracts_insured', help_text='Odoo insurer_id.',
    )
    ins_ref = fields.Char(
        max_length=64, blank=True, default='', help_text='Odoo ins_ref.',
    )
    state = fields.Selection(
        max_length=7, choices=STATES, default=STATE_OPEN, help_text='Odoo state.',
    )
    notes = fields.Html(blank=True, default='', help_text='Odoo notes.')
    cost_generated = fields.Monetary(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Odoo cost_generated.',
    )
    cost_frequency = fields.Selection(
        max_length=7, choices=FREQUENCIES, default='monthly',
        help_text='Odoo cost_frequency.',
    )
    services = fields.Many2many(
        'fleet.FleetServiceType', blank=True,
        db_table='fleet_vehicle_log_contract_service_rel',
        related_name='contracts_included_in', help_text='Odoo service_ids.',
    )

    class Meta:
        db_table = 'fleet_vehicle_log_contract'
        ordering = ['-state', 'expiration_date']
        verbose_name = 'Contrato de vehículo'
        verbose_name_plural = 'Contratos de vehículo'

    def __str__(self):
        """``_compute_contract_name``."""
        return self.name

    @staticmethod
    def next_year_date(start_date):
        """``compute_next_year_date`` — un año después de ``start_date``.

        La referencia usa ``dateutil.relativedelta(years=1)``, pero
        ``dateutil`` **no es dependencia de este proyecto**: el precedente es
        ``base/models/ir_cron.py::_add_months``, que replicó el mismo
        comportamiento con stdlib en vez de añadir el paquete. Aquí basta con
        el *clamping* del día: 29-feb + 1 año → 28-feb, que es exactamente lo
        que hace ``relativedelta``.
        """
        year = start_date.year + 1
        day = min(start_date.day, calendar.monthrange(year, start_date.month)[1])
        return start_date.replace(year=year, day=day)

    @property
    def name(self):
        vehicle_name = self.vehicle.name if self.vehicle_id else ''
        if self.cost_subtype_id and self.cost_subtype.name:
            return f'{self.cost_subtype.name} {vehicle_name}'
        return vehicle_name

    @property
    def purchaser(self):
        """``related='vehicle_id.driver_id'``."""
        return self.vehicle.driver if self.vehicle_id else None

    @property
    def days_left(self):
        """``_compute_days_left`` — días hasta el vencimiento.

        0 si está vencido y sigue abierto; -1 si está cerrado.
        """
        if self.expiration_date and self.state in (self.STATE_OPEN, self.STATE_EXPIRED):
            diff = (self.expiration_date - date.today()).days
            return diff if diff > 0 else 0
        return -1

    @property
    def expires_today(self):
        if self.expiration_date and self.state in (self.STATE_OPEN, self.STATE_EXPIRED):
            return (self.expiration_date - date.today()).days == 0
        return False

    @property
    def has_open_contract(self):
        """``_compute_has_open_contract`` — otro contrato abierto y vigente
        del MISMO vehículo (excluyendo este)."""
        if not self.vehicle_id:
            return False
        qs = type(self).objects.filter(
            vehicle_id=self.vehicle_id, state=self.STATE_OPEN,
            expiration_date__gte=date.today(),
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        return qs.exists()

    def sync_defaults(self):
        """Rellena ``user``/``start_date``/``expiration_date`` con los
        defaults que la referencia calcula vía ``default=lambda`` — aquí
        explícito porque dependen de otro campo (``vehicle``/``start_date``),
        no de un valor estático."""
        if not self.start_date:
            self.start_date = self.date or None
        if self.vehicle_id and not self.user_id and self.vehicle.manager_id:
            self.user = self.vehicle.manager
        if self.start_date and not self.expiration_date:
            self.expiration_date = self.next_year_date(self.start_date)

    def sync_state_from_dates(self):
        """``write()`` — deriva ``state`` de las fechas cuando no está
        cerrado. NO se auto-invoca en ``save()``; el llamador la ejecuta
        cuando ``start_date``/``expiration_date`` cambian."""
        if self.state == self.STATE_CLOSED or not self.start_date:
            return
        today = date.today()
        if today < self.start_date:
            self.state = self.STATE_FUTUR
        elif not self.expiration_date or self.start_date <= today <= self.expiration_date:
            self.state = self.STATE_OPEN
        else:
            self.state = self.STATE_EXPIRED

    def action_close(self):
        self.state = self.STATE_CLOSED
        self.save(update_fields=['state'])

    def action_draft(self):
        self.state = self.STATE_FUTUR
        self.save(update_fields=['state'])

    def action_open(self):
        self.state = self.STATE_OPEN
        self.save(update_fields=['state'])

    def action_expire(self):
        self.state = self.STATE_EXPIRED
        self.save(update_fields=['state'])

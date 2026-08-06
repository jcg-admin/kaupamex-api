"""``account.lock_exception`` — Adaptación de Odoo addons/account/models/account_lock_exception.py
(odoo-tools@622ddc2a, odoo19c:).

Excepción temporal a un candado de fecha (lock date) de ``res.company``: 19
absorbió y expandió lo que en 18e era el addon ``account_lock`` en este
modelo, con los candados ahora vivos como campos en ``ResCompany``
(``hard_lock_date``, ``fiscalyear_lock_date``, ``tax_lock_date``,
``sale_lock_date``, ``purchase_lock_date`` — Odoo ``SOFT_LOCK_DATE_FIELDS`` +
``hard_lock_date``, ``account/models/company.py:57-66``). Se porta la forma
de 19c, no la del addon viejo (directiva de la tarea).

**Pendiente declarado (fuera de este alcance):** ``base.ResCompany`` NO
declara todavía ``hard_lock_date``/``fiscalyear_lock_date``/``tax_lock_date``/
``sale_lock_date``/``purchase_lock_date`` — verificado
(``grep -n "lock_date" base/models/res_company.py`` → 0 hits). Sin esos
campos, los computados no-almacenados de la referencia
(``fiscalyear_lock_date``/``tax_lock_date``/``sale_lock_date``/
``purchase_lock_date`` en ``AccountLock_Exception``, que reflejan
``company[field]`` con la excepción aplicada) no tienen fuente — se omiten
aquí. Se porta el núcleo persistido (la excepción en sí: qué campo, qué
usuario, qué fecha, hasta cuándo) y ``applies_to()`` como sustituto explícito
de esos computados. Pertenece a otra familia (candados de ``ResCompany``);
ver H-API en el resumen del agente.

``state`` es ``compute`` no-almacenado en la referencia
(``active``/``revoked``/``expired`` derivado de ``active``+``end_datetime``);
se porta como propiedad Python (mismo criterio que ``mail_mail.subject`` — sin
compute-engine en este ORM, ver docstring de ``mail_mail.py``), no como
columna.
"""
from django.utils import timezone

import fields
import models
from exceptions import UserError

# Fiel a Odoo account/models/company.py:57-66 (SOFT_LOCK_DATE_FIELDS).
LOCK_DATE_FIELD_CHOICES = [
    ('fiscalyear_lock_date', 'Candado global'),
    ('tax_lock_date', 'Candado de declaración de impuestos'),
    ('sale_lock_date', 'Candado de ventas'),
    ('purchase_lock_date', 'Candado de compras'),
]


class AccountLockException(models.Model):
    """``account.lock_exception`` — excepción temporal a un candado de fecha."""

    STATE_ACTIVE = 'active'
    STATE_REVOKED = 'revoked'
    STATE_EXPIRED = 'expired'

    active = fields.Boolean(
        default=True, help_text='Vigente (Odoo active).',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='lock_exceptions',
        help_text='Empresa (Odoo company_id, requerido).',
    )
    # Sin user, la excepción aplica a todos (Odoo: "An exception w/o user_id
    # is an exception for everyone").
    user = fields.Many2one(
        'base.ResUsers', on_delete=models.CASCADE, null=True, blank=True,
        related_name='lock_exceptions',
        help_text='Usuario beneficiario; vacío = para todos (Odoo user_id).',
    )
    reason = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Motivo de la excepción (Odoo reason).',
    )
    # Sin end_datetime, la excepción es indefinida (Odoo: "valid forever").
    end_datetime = fields.Datetime(
        null=True, blank=True,
        help_text='Fin de vigencia; vacío = indefinida (Odoo end_datetime).',
    )
    lock_date_field = fields.Selection(
        max_length=32, choices=LOCK_DATE_FIELD_CHOICES,
        help_text='Candado que esta excepción modifica (Odoo lock_date_field, '
                  'requerido).',
    )
    lock_date = fields.Date(
        null=True, blank=True,
        help_text='Fecha a la que se mueve el candado (Odoo lock_date).',
    )
    company_lock_date = fields.Date(
        null=True, blank=True,
        help_text='Candado original de la empresa al crear la excepción '
                  '(Odoo company_lock_date, técnico, no editable).',
    )

    class Meta:
        db_table = 'account_lock_exception'
        ordering = ['-id']
        verbose_name = 'Excepción de candado contable'
        verbose_name_plural = 'Excepciones de candado contable'
        indexes = [
            models.Index(
                fields=['company', 'user', 'end_datetime'],
                name='account_lock_exc_active_idx',
                condition=models.Q(active=True),
            ),
        ]

    def __str__(self) -> str:
        return f'Excepción de candado #{self.pk}'

    @property
    def state(self):
        """Estado derivado (Odoo ``_compute_state``, no-almacenado)."""
        if not self.active:
            return self.STATE_REVOKED
        if self.end_datetime and self.end_datetime < timezone.now():
            return self.STATE_EXPIRED
        return self.STATE_ACTIVE

    def applies_to(self, field_name):
        """¿Esta excepción, vigente, mueve el candado ``field_name``?

        Sustituto explícito de los computados no-almacenados
        ``fiscalyear_lock_date``/``tax_lock_date``/``sale_lock_date``/
        ``purchase_lock_date`` de la referencia — devuelve ``lock_date`` si
        aplica y la excepción está ``active``, o ``None``. El llamador
        (candado en ``ResCompany``, pendiente) resuelve el máximo con la
        fecha propia de la empresa.
        """
        if self.state != self.STATE_ACTIVE:
            return None
        return self.lock_date if self.lock_date_field == field_name else None

    def revoke(self):
        """Revoca una excepción activa (Odoo ``action_revoke``, simplificado:
        sin el chequeo de grupo ``account.group_account_manager`` — modelo de
        capacidades del proyecto, DEC-11, se aplica en la capa de vista, no
        aquí)."""
        if self.state != self.STATE_ACTIVE:
            raise UserError('Solo se puede revocar una excepción activa.')
        self.active = False
        self.end_datetime = timezone.now()
        self.save(update_fields=['active', 'end_datetime'])

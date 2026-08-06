"""``account.analytic.account`` (Odoo ``analytic``).

Adaptación fiel de Odoo analytic/models/analytic_account.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3), simplificada por la misma razón
documentada en ``analytic_plan.py``: sin el sistema de columna dinámica por
plan, esta cuenta se referencia desde ``account.analytic.line`` por una FK
única (``AccountAnalyticLine.account``), no por una columna ``x_planN_id``
generada en runtime.

Lo que SÍ se porta: estructura (``name``, ``code``, ``active``, ``plan``,
``company``, ``partner``), los "related" ``root_plan_id``/``color`` (aquí
``@property``, sin columna — Django no re-materializa un ``related`` como
columna propia salvo que se declare ``store=True`` con una señal, que no se
implementa en este corte), ``balance``/``debit``/``credit`` (recomputados por
agregación sobre ``lines``, sin conversión de moneda — ver docstring del
método) y la constricción de consistencia de compañía.

Lo que NO se porta: ``write()`` override (mueve datos entre columnas por
plan — depende 100% de la magia de columna dinámica), ``copy_data`` (botón
"duplicar" del cliente web), ``web_read``/``_read_group_select``/
``_read_group_postprocess_aggregate`` (agregación del cliente web de Odoo,
sin análogo en esta API DRF).
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum

import fields
import models

from addons.mail.models import MailThread


class AccountAnalyticAccount(MailThread, models.Model):
    """``account.analytic.account`` — cuenta analítica (centro de costo)."""

    name = fields.Char(
        max_length=255, db_index=True, verbose_name='Cuenta analítica',
        help_text='Odoo name (requerido, traducible, index=trigram en la '
                   'referencia — aquí índice simple de MariaDB).',
    )
    code = fields.Char(
        max_length=64, blank=True, default='', db_index=True,
        verbose_name='Referencia', help_text='Odoo code.',
    )
    active = fields.Boolean(default=True, verbose_name='Activo')
    plan = fields.Many2one(
        'analytic.AccountAnalyticPlan', on_delete=models.PROTECT,
        related_name='accounts', verbose_name='Plan',
        help_text=(
            'Odoo plan_id (requerido). on_delete=PROTECT: un plan con '
            'cuentas no se puede borrar por accidente (Odoo no fija '
            'ondelete explícito aquí; PROTECT es la adaptación segura).'
        ),
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='analytic_accounts', verbose_name='Empresa',
    )
    partner = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='analytic_accounts', verbose_name='Cliente',
        help_text='Odoo partner_id.',
    )

    class Meta:
        db_table = 'account_analytic_account'
        ordering = ['plan', 'name']
        verbose_name = 'Cuenta analítica'
        verbose_name_plural = 'Cuentas analíticas'
        # ADDON NO INSTALADO TODAVÍA — ver el comentario extenso en
        # ``analytic_plan.py::AccountAnalyticPlan.Meta`` (mismo precedente
        # que ``onboarding``).
        app_label = 'analytic'

    def __str__(self):
        """Fiel a ``_compute_display_name`` (odoo19c: líneas 104-112),
        simplificado: usa ``partner.name`` en vez de
        ``partner_id.commercial_partner_id.name`` (sin jerarquía comercial
        de partner en este corte)."""
        name = self.name
        if self.code:
            name = f'[{self.code}] {name}'
        if self.partner_id:
            name = f'{name} - {self.partner.name}'
        return name

    def clean(self):
        """Fiel a ``_check_company_consistency`` (odoo19c: líneas 95-102),
        simplificado a igualdad directa de compañía (sin ``child_of`` de
        sucursales — ver docstring del módulo)."""
        super().clean()
        if self.pk is not None and self.company_id is not None:
            if self.lines.exclude(company_id=self.company_id).exists():
                raise ValidationError({
                    'company': 'ANALYTIC_ACCOUNT_COMPANY_MISMATCH_WITH_LINES',
                })

    # -- "related" fields de la referencia, sin columna propia --------------

    @property
    def root_plan(self):
        """Odoo ``root_plan_id`` (``related="plan_id.root_id", store=True``)."""
        return self.plan.root

    @property
    def color(self):
        """Odoo ``color`` (``related='plan_id.color'``)."""
        return self.plan.color

    @property
    def currency(self):
        """Odoo ``currency_id`` (``related="company_id.currency_id"``)."""
        return self.company.currency if self.company_id else None

    # -- balance/debit/credit — Odoo _compute_debit_credit_balance ----------

    @property
    def credit(self):
        """Suma de líneas con importe >= 0.

        Simplificación: la referencia convierte cada línea a la moneda de
        ``env.company`` antes de sumar (``_compute_debit_credit_balance``,
        odoo19c: líneas 162-203); aquí se suma directo en la moneda de la
        línea, sin conversión de tipo de cambio (fuera de alcance de este
        corte — no hay infraestructura de fx invocada desde este addon).
        """
        total = self.lines.filter(amount__gte=0).aggregate(total=Sum('amount'))['total']
        return total if total is not None else Decimal('0.00')

    @property
    def debit(self):
        total = self.lines.filter(amount__lt=0).aggregate(total=Sum('amount'))['total']
        return -total if total is not None else Decimal('0.00')

    @property
    def balance(self):
        return self.credit - self.debit

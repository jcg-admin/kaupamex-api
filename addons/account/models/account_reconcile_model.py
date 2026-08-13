"""``account.reconcile.model``/``account.reconcile.model.line`` — reglas de
conciliación automática (Odoo ``account``).

Adaptación de Odoo ``addons/account/models/account_reconcile_model.py``
(odoo-tools@622ddc2a, odoo19c:, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03).

**Ojo con la versión — 19 retiró un modelo que existe en 18.**
``account.reconcile.model.partner.mapping`` está en ``odoo18c:
account_reconcile_model.py:11-12`` (mapeo partner ↔ regex de reconciliación
bancaria) pero **19 no lo tiene** (medido: 0 hits de esa clase en
``odoo19c: addons/account/models/account_reconcile_model.py``). Gobierna 19
(`referencia-odoo-gobierna-las-decisiones.md`): NO se porta.

Divergencias declaradas (DEC-KX-03):

1. **Sin ``mail.thread``** — la referencia hereda ``_inherit = ['mail.thread']``
   en ``AccountReconcileModel`` (``tracking=True`` en varios campos). Ningún
   addon de mensajería está portado en este árbol. Se porta el modelo sin
   herencia de mensajería; los ``tracking=True`` de la referencia se leen como
   metadata de UI, no de dato.
2. **Sin motor de matching bancario** — ``AccountReconcileModelLine`` en la
   referencia hereda ``analytic.mixin`` (distribución analítica) y el propio
   ``AccountReconcileModel`` orquesta un wizard de conciliación bancaria
   (``account.bank.statement.line``, no portado en este monolito). Se portan
   los **campos de la regla** (qué journal/monto/etiqueta dispara la regla,
   qué líneas genera) y la validación server-side; el **algoritmo de
   aplicación** de la regla contra un extracto bancario real queda DEFERIDO —
   depende de ``account.bank.statement.line``, ausente.
3. **``next_activity_type_id``** (actividad de seguimiento CRM-style) —
   DEFERIDO, depende de ``mail.activity.type``, no portado.
4. **``mapped_partner_id``/``can_be_proposed``** se portan como métodos
   explícitos (``compute_mapped_partner_id``/``compute_can_be_proposed``), NO
   como columnas recalculadas en cada ``save()`` — dependen de ``line_ids``
   (modelo hijo), que se crea DESPUÉS del padre; recalcular en ``save()`` del
   padre vería líneas desactualizadas. El llamador invoca el método tras
   modificar ``line_ids`` (mismo criterio que ``resource_mixin.py``: relación
   cruzada a otro modelo → método explícito, no ``@api.depends`` automático).
5. **``AccountReconcileModelLine.company``** SÍ se porta como columna real
   sincronizada en ``save()`` (no ``@property``) porque la referencia lo
   declara ``related='model_id.company_id', store=True`` — mismo patrón que
   ``resource_mixin.py`` divergencia #2 (related+store=True → columna
   sincronizada, related sin store → ``@property``).
6. **``action_reconcile_stat``/``copy_data``** — acciones de UI (abrir vista
   filtrada, texto de "(copy)"). NO se portan: no hay comportamiento de datos
   que verificar, son acciones de ventana de Odoo.
7. **``match_amount_min``/``match_amount_max`` son ``Monetary``, no ``Float``**
   — la referencia los declara ``fields.Float``. Se elevan a ``Monetary``
   porque son umbrales de comparación contra un **importe monetario** del
   extracto bancario (invariante del cluster: la conciliación es aritmética
   de dinero, ``Decimal``, nunca ``float``). ``AccountReconcileModelLine.amount``
   SÍ se preserva como ``Float`` — no es dinero por sí mismo, es un
   multiplicador/porcentaje o un número extraído por regex, fiel a la
   referencia.
"""
import re

from django.conf import settings

import fields
import models
from exceptions import UserError
from tools.translate import _


class AccountReconcileModel(models.Model):
    """``account.reconcile.model`` — regla que propone conciliaciones."""

    TRIGGERS = [
        ('manual', 'Manual'),
        ('auto_reconcile', 'Automática'),
    ]
    MATCH_AMOUNTS = [
        ('lower', 'Es menor o igual a'),
        ('greater', 'Es mayor o igual a'),
        ('between', 'Está entre'),
    ]
    MATCH_LABELS = [
        ('contains', 'Contiene'),
        ('not_contains', 'No contiene'),
        ('match_regex', 'Coincide con regex'),
    ]

    active            = fields.Boolean(
        default=True, help_text='Regla activa (Odoo active).',
    )
    name              = fields.Char(
        max_length=255, help_text='Nombre de la regla (Odoo name, requerido).',
    )
    sequence          = fields.Integer(
        default=10, help_text='Orden de aplicación (Odoo sequence).',
    )
    company           = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE,
        related_name='reconcile_models',
        help_text='Empresa (Odoo company_id, requerido).',
    )
    trigger           = fields.Selection(
        max_length=16, choices=TRIGGERS, default='manual',
        help_text='Aplicación manual o automática al validar el extracto '
                   '(Odoo trigger, requerido).',
    )
    can_be_proposed   = fields.Boolean(
        default=False,
        help_text='Odoo can_be_proposed (computado, ver '
                   'compute_can_be_proposed — no automático en save()).',
    )
    mapped_partner    = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='+',
        help_text='Odoo mapped_partner_id (computado, ver '
                   'compute_mapped_partner_id).',
    )
    match_journal_ids = fields.Many2many(
        'account.AccountJournal', blank=True, related_name='reconcile_models',
        help_text='Diarios donde aplica la regla (Odoo match_journal_ids).',
    )
    match_amount      = fields.Selection(
        max_length=8, choices=MATCH_AMOUNTS, blank=True, default='',
        help_text='Condición sobre el monto del extracto (Odoo match_amount).',
    )
    match_amount_min  = fields.Monetary(
        max_digits=16, decimal_places=2, null=True, blank=True,
        help_text='Odoo match_amount_min.',
    )
    match_amount_max  = fields.Monetary(
        max_digits=16, decimal_places=2, null=True, blank=True,
        help_text='Odoo match_amount_max.',
    )
    match_label       = fields.Selection(
        max_length=16, choices=MATCH_LABELS, blank=True, default='',
        help_text='Condición sobre la etiqueta del extracto (Odoo match_label).',
    )
    match_label_param = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Parámetro de match_label (Odoo match_label_param).',
    )
    match_partner_ids = fields.Many2many(
        settings.AUTH_USER_MODEL, blank=True, related_name='+',
        help_text='Restringe la regla a estos contactos (Odoo '
                   'match_partner_ids).',
    )

    class Meta:
        db_table = 'account_reconcile_model'
        ordering = ['sequence', 'id']
        verbose_name = 'Regla de conciliación'
        verbose_name_plural = 'Reglas de conciliación'

    def __str__(self) -> str:
        return self.name

    # -- validación -----------------------------------------------------------
    def _check_match_label_param(self):
        """Odoo ``_check_match_label_param``: el regex debe compilar."""
        if self.match_label == 'match_regex':
            try:
                re.compile(self.match_label_param)
            except re.error:
                raise UserError(_('El regex no es válido.'))

    def save(self, *args, **kwargs):
        self._check_match_label_param()
        return super().save(*args, **kwargs)

    # -- computo explícito (divergencia #4) ------------------------------------
    def compute_can_be_proposed(self):
        """Odoo ``_compute_can_be_proposed``: sin destino de partner mapeado
        Y (hay condición de etiqueta, monto, partners o dispara automático)."""
        self.can_be_proposed = bool(
            not self.mapped_partner_id
            and (self.match_label or self.match_amount
                 or self.match_partner_ids.exists()
                 or self.trigger == 'auto_reconcile')
        )
        self.save(update_fields=['can_be_proposed'])
        return self.can_be_proposed

    def compute_mapped_partner(self):
        """Odoo ``_compute_partner_mapping``: si la regla tiene exactamente una
        línea con partner fijo y sin cuenta fija, y usa match_label, esa línea
        define el partner que se propone."""
        lines = list(self.line_ids.all())
        is_partner_mapping = bool(
            self.match_label and len(lines) == 1
            and lines[0].partner_id and not lines[0].account_id
        )
        self.mapped_partner = lines[0].partner if is_partner_mapping else None
        self.save(update_fields=['mapped_partner'])
        return self.mapped_partner

    def set_manual(self):
        """Odoo ``action_set_manual``."""
        self.trigger = 'manual'
        self.save(update_fields=['trigger'])

    def set_auto_reconcile(self):
        """Odoo ``action_set_auto_reconcile``."""
        self.trigger = 'auto_reconcile'
        self.save(update_fields=['trigger'])


class AccountReconcileModelLine(models.Model):
    """``account.reconcile.model.line`` — línea que la regla genera al aplicarse."""

    AMOUNT_TYPES = [
        ('fixed', 'Fijo'),
        ('percentage', 'Porcentaje del saldo'),
        ('percentage_st_line', 'Porcentaje del extracto'),
        ('regex', 'Extraído de la etiqueta'),
    ]

    model         = fields.Many2one(
        'account.AccountReconcileModel', on_delete=models.CASCADE,
        related_name='line_ids',
        help_text='Regla a la que pertenece (Odoo model_id).',
    )
    company       = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, null=True, blank=True,
        related_name='reconcile_model_lines',
        help_text='Odoo company_id (related=model_id.company_id, store=True '
                   '— columna sincronizada en save(), ver divergencia #5).',
    )
    sequence      = fields.Integer(
        default=10, help_text='Orden dentro de la regla (Odoo sequence).',
    )
    account       = fields.Many2one(
        'account.AccountAccount', on_delete=models.CASCADE, null=True,
        blank=True, related_name='reconcile_model_lines',
        help_text='Cuenta destino de la línea generada (Odoo account_id).',
    )
    partner       = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='+',
        help_text='Contacto de la línea generada (Odoo partner_id).',
    )
    label         = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Etiqueta de la línea generada (Odoo label).',
    )
    amount_type   = fields.Selection(
        max_length=24, choices=AMOUNT_TYPES, default='percentage',
        help_text='Cómo se calcula el monto de la línea (Odoo amount_type, '
                   'requerido).',
    )
    amount_string = fields.Char(
        max_length=255, default='100',
        help_text='Valor crudo del monto: porcentaje, fijo, o regex sobre la '
                   'etiqueta del extracto (Odoo amount_string, requerido).',
    )
    amount        = fields.Float(
        default=0.0,
        help_text='amount_string parseado a float (Odoo amount, computado '
                   'en save() — Odoo lo declara compute+store).',
    )

    class Meta:
        db_table = 'account_reconcile_model_line'
        ordering = ['sequence', 'id']
        verbose_name = 'Línea de regla de conciliación'
        verbose_name_plural = 'Líneas de regla de conciliación'

    def __str__(self) -> str:
        return self.label or f'Línea #{self.pk}'

    # -- computo ------------------------------------------------------------
    def _compute_float_amount(self):
        """Odoo ``_compute_float_amount``: parsea amount_string a float."""
        try:
            self.amount = float(self.amount_string)
        except (TypeError, ValueError):
            self.amount = 0.0

    def _sync_company(self):
        """Divergencia #5: sincroniza el ``related='model_id.company_id',
        store=True`` de la referencia como columna real."""
        self.company = self.model.company if self.model_id else None

    def _validate_amount(self):
        """Odoo ``_validate_amount``: el monto declarado debe tener sentido
        para el amount_type elegido."""
        if self.amount_type == 'fixed' and self.amount == 0:
            raise UserError(_('El monto no es un número.'))
        if self.amount_type == 'percentage_st_line' and self.amount == 0:
            raise UserError(_('El porcentaje del extracto no puede ser 0.'))
        if self.amount_type == 'percentage' and self.amount == 0:
            raise UserError(_('El porcentaje del saldo no puede ser 0.'))
        if self.amount_type == 'regex':
            try:
                re.compile(self.amount_string)
            except re.error:
                raise UserError(_('El regex no es válido.'))

    def save(self, *args, **kwargs):
        self._compute_float_amount()
        self._sync_company()
        self._validate_amount()
        return super().save(*args, **kwargs)

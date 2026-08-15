"""``account.payment.term`` / ``account.payment.term.line`` — plazos de pago
(Odoo ``account``).

Adaptación de Odoo ``addons/account/models/account_payment_term.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:``).

Núcleo portado: campos persistidos (``name``, ``active``, ``note``,
``company``, ``sequence``, ``display_on_invoice``, ``discount_percentage``,
``discount_days``, ``early_pay_discount_computation``, ``early_discount``),
``_check_lines``, ``_get_amount_due_after_discount``, ``_compute_terms``,
``_get_amount_by_date``, ``_get_last_discount_date`` en ``AccountPaymentTerm``;
y ``value``/``value_amount``/``delay_type``/``days_next_month``/``nb_days`` +
``_get_due_date``/``_check_valid_char_value``/``_check_percent``/
``_compute_display_days_next_month`` en ``AccountPaymentTermLine``.

``_currency_round`` (H-API-325, tarea #115): delega en ``ResCurrency.round()``
cuando hay moneda — el redondeo por divisa ya no se reimplementa aquí, sólo
se conserva el valor por defecto de 2 decimales para el caso sin compañía
(``self.currency`` es ``None``, ver la propiedad ``currency`` abajo), que
``ResCurrency.round()`` no puede resolver por no tener a quién preguntarle.

No portado (declarado, no improvisado):

- ``fiscal_country_codes``/``currency_id`` (computados de ``company_id``/
  ``env.companies``) y todo el bloque ``example_*``
  (``example_amount``/``example_date``/``example_invalid``/
  ``example_preview``/``example_preview_discount``): son ayudas de
  presentación del formulario (vista previa en el UI de Odoo), sin
  consumidor en este núcleo de backend.
- ``_compute_discount_computation`` (early_pay_discount_computation según
  ``country_code`` BE/NL de la compañía): requiere el país fiscal de
  ``res.company``, que no está resuelto en este core (ver docstring de
  ``base/models/res_company.py``, aún sin país fiscal derivado). Se porta el
  campo como valor por defecto fijo (``'included'``), documentado — no se
  fabrica la regla BE/NL sin el dato de país que la sustenta.
- ``_unlink_except_referenced_terms`` (``@api.ondelete``, guarda contra
  borrar un plazo referenciado desde ``account.move.invoice_payment_term_id``):
  ``AccountMove`` en este árbol **no tiene** ese campo todavía (no forma
  parte de este cluster) — no hay nada que verificar. Cuando se porte esa FK
  a ``AccountMove``, este guard se re-evalúa.
- ``copy_data`` (duplicado con sufijo "(copy)" al nombre): ayuda de UI para
  el botón "Duplicar" de Odoo, sin consumidor de duplicación en este árbol.
- ``cash_rounding`` (parámetro de ``_compute_terms``): se omite el parámetro
  entero — la firma de ``_compute_terms`` aquí no lo declara. ``account.cash.
  rounding`` puede existir en el árbol (portado en paralelo por otro cluster,
  ver ``account_cash_rounding.py``), pero cablear el ajuste de redondeo de
  efectivo al cómputo de cuotas no es parte de este cluster de pagos; queda
  para quien integre facturación con redondeo de efectivo.
- ``format_date``/``formatLang`` (i18n de fechas/montos para el preview del
  UI): sin consumidor de presentación en este core.
- ``dateutil.relativedelta``: **no es dependencia de este proyecto**
  (precedente: ``base/models/ir_cron.py::_add_months`` y
  ``fleet/models/fleet_vehicle_log_contract.py::next_year_date``, ambos
  documentan la misma ausencia). Este archivo reimplementa el cómputo de
  fecha con ``calendar``/``datetime`` de la stdlib (``_shift_month``/
  ``_end_of_month`` abajo), replicando el mismo *clamping* observable de
  ``relativedelta`` para overflow de día de mes.

Sibling-dependientes, NO auto-invocadas en ``save()`` (documentado, no
improvisado)
=====================================================================

``AccountPaymentTermLine._compute_days`` y
``AccountPaymentTermLine._compute_value_amount`` en la referencia dependen de
las **demás** líneas del mismo ``payment_id`` (``payment_id.line_ids[-2]``,
suma de las líneas ``percent`` hermanas). Este ORM no tiene el motor de
recómputo cross-row de Odoo (que reevalúa "las líneas hermanas" en cada
cambio del O2M en memoria, antes de guardar). Auto-invocar estos métodos
dentro de ``save()`` de una sola línea vería un ``payment.line_ids`` a medio
crear (fila por fila) y produciría valores incorrectos según el orden de
alta — peor que no computarlos. Se portan como métodos explícitos,
invocables por el llamador (servicio/vista) una vez que todas las líneas del
plazo existen, mismo patrón que ``AccountMove.compute_amount_total()``
(portado como método explícito, no automático — ver ``account_move.py``).
``AccountPaymentTerm._check_lines`` es el mismo caso a nivel del padre:
valida la suma de porcentajes de ``line_ids``, así que también es explícito.
"""
import calendar
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

import api
import fields
import models
from exceptions import ValidationError
from tools.translate import _

VALUE_TYPES = [
    ('percent', 'Porcentaje'),
    ('fixed', 'Fijo'),
]
DELAY_TYPES = [
    ('days_after', 'Días después de la fecha de factura'),
    ('days_after_end_of_month', 'Días después de fin de mes'),
    ('days_after_end_of_next_month', 'Días después de fin del mes siguiente'),
    ('days_end_of_month_on_the', 'Fin de mes en el día'),
]
EARLY_PAY_DISCOUNT_COMPUTATIONS = [
    ('included', 'Al pago anticipado'),
    ('excluded', 'Nunca'),
    ('mixed', 'Siempre (sobre la factura)'),
]


# -- Sustituto local de dateutil.relativedelta (no es dependencia; ver
# docstring del módulo y el precedente base/models/ir_cron.py::_add_months) --
def _end_of_month(d):
    """Último día del mes de ``d`` (Odoo ``date_utils.end_of(d, 'month')``)."""
    last_day = calendar.monthrange(d.year, d.month)[1]
    return d.replace(day=last_day)


def _shift_month(d, months, day=None):
    """Suma ``months`` meses calendario a ``d``. Si ``day`` se indica, fija el
    día del mes resultante (clamped al último día — equivalente observable a
    ``relativedelta(months=months, day=day)``); si no, clampa al propio día
    de ``d`` (overflow de ``relativedelta(months=months)``, p. ej. 31-ene + 1
    mes → 28/29-feb)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    target_day = day if day is not None else d.day
    return d.replace(year=year, month=month, day=min(target_day, last_day))


def _currency_round(currency, amount):
    """Redondeo por moneda — delega en ``ResCurrency.round()`` (H-API-325,
    tarea #115) cuando hay ``currency``. Sin moneda (plazo sin compañía, ver
    la propiedad ``currency`` de ``AccountPaymentTerm`` abajo), usa 2
    decimales ``ROUND_HALF_UP`` — no hay unidad monetaria de la que derivar
    ``rounding``/``decimal_places``, así que este caso no puede centralizarse
    en ``ResCurrency`` (ningún registro al que preguntarle)."""
    if currency is not None:
        return currency.round(amount)
    quantum = Decimal('0.01')
    return Decimal(amount).quantize(quantum, rounding=ROUND_HALF_UP)


class AccountPaymentTerm(models.Model):
    """``account.payment.term`` — plazo de pago (distribución en cuotas)."""

    name                          = fields.Char(
        max_length=255,
        help_text='Nombre del plazo de pago (Odoo name, requerido).',
    )
    active                        = fields.Boolean(
        default=True,
        help_text='Si es falso, oculta el plazo sin borrarlo (Odoo active).',
    )
    note                          = fields.Html(
        blank=True, default='',
        help_text='Descripción para la factura (Odoo note).',
    )
    company                       = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='payment_terms',
        null=True, blank=True,
        help_text='Empresa (Odoo company_id; sin compañía = plazo global).',
    )
    sequence                      = fields.Integer(
        default=10, help_text='Orden de presentación (Odoo sequence).',
    )
    display_on_invoice             = fields.Boolean(
        default=True,
        help_text='Muestra las fechas de las cuotas en la factura (Odoo display_on_invoice).',
    )
    discount_percentage            = fields.Monetary(
        max_digits=5, decimal_places=2, default=Decimal('2.0'),
        help_text='% de descuento por pronto pago (Odoo discount_percentage).',
    )
    discount_days                  = fields.Integer(
        default=10,
        help_text='Días antes de que expire el pronto pago (Odoo discount_days).',
    )
    early_pay_discount_computation = fields.Selection(
        max_length=8, choices=EARLY_PAY_DISCOUNT_COMPUTATIONS, default='included',
        help_text=(
            'Tratamiento fiscal del descuento (Odoo early_pay_discount_'
            'computation). Valor por defecto fijo — la derivación BE/NL por '
            'país de la compañía no está portada (ver docstring del módulo).'
        ),
    )
    early_discount                 = fields.Boolean(
        default=False, help_text='Activa el pronto pago (Odoo early_discount).',
    )

    class Meta:
        db_table = 'account_payment_term'
        ordering = ['sequence', 'id']
        verbose_name = 'Plazo de pago'
        verbose_name_plural = 'Plazos de pago'

    def __str__(self) -> str:
        return self.name

    # -- Odoo _check_lines (constrains line_ids, early_discount) -------------
    def _check_lines(self):
        """Valida las cuotas (Odoo ``_check_lines``): la suma de las líneas
        ``percent`` debe dar 100%, y el pronto pago sólo aplica a plazos de
        una única línea al 100%. Explícito — ver docstring del módulo
        (sibling-dependiente, no se dispara solo con ``save()``)."""
        total_percent = sum(
            (line.value_amount for line in self.line_ids.all() if line.value == 'percent'),
            Decimal('0'),
        )
        if total_percent != Decimal('100'):
            raise ValidationError(
                _('El plazo de pago debe tener al menos una línea de '
                  'porcentaje y la suma de los porcentajes debe ser 100%.'))
        line_count = self.line_ids.count()
        if line_count > 1 and self.early_discount:
            raise ValidationError(
                _('El pronto pago sólo puede usarse con plazos de pago de '
                  'una única línea al 100%.'))
        if self.early_discount and self.discount_percentage <= 0:
            raise ValidationError(_('El % de pronto pago debe ser positivo.'))
        if self.early_discount and self.discount_days <= 0:
            raise ValidationError(
                _('Los días de pronto pago deben ser positivos.'))

    # -- Odoo _get_amount_due_after_discount ----------------------------------
    def _get_amount_due_after_discount(self, total_amount, untaxed_amount):
        """Importe tras aplicar el pronto pago (Odoo
        ``_get_amount_due_after_discount``, sin el ajuste de
        ``cash_rounding``/contexto de factura activa — no portados, ver
        docstring del módulo)."""
        if not self.early_discount:
            return total_amount
        percentage = self.discount_percentage / Decimal('100')
        if self.early_pay_discount_computation in ('excluded', 'mixed'):
            discount_amount = (total_amount - untaxed_amount) * percentage
        else:
            discount_amount = total_amount * percentage
        return _currency_round(self.currency, total_amount - discount_amount)

    @property
    def currency(self):
        """Odoo ``currency_id`` (``compute='_compute_currency_id'``): moneda
        de la compañía, o ``None`` si el plazo no tiene compañía."""
        return self.company.currency if self.company_id else None

    # -- Odoo _get_last_discount_date -----------------------------------------
    def _get_last_discount_date(self, date_ref):
        """Última fecha válida para el pronto pago (Odoo
        ``_get_last_discount_date``)."""
        if not date_ref:
            return None
        if not self.early_discount:
            return False
        return date_ref + timedelta(days=self.discount_days or 0)

    # -- Odoo _compute_terms ---------------------------------------------------
    def _compute_terms(self, date_ref, currency, tax_amount, tax_amount_currency,
                        sign, untaxed_amount, untaxed_amount_currency):
        """Distribución del plazo en cuotas (Odoo ``_compute_terms``).

        Firma sin ``company``/``cash_rounding`` (ver docstring del módulo):
        la moneda "de la compañía" se resuelve de ``self.currency`` en vez de
        recibir ``company`` aparte, porque este núcleo ya deriva la moneda de
        la compañía del propio plazo (``self.company.currency``).
        """
        company_currency = self.currency
        total_amount = tax_amount + untaxed_amount
        total_amount_currency = tax_amount_currency + untaxed_amount_currency
        rate = (
            abs(total_amount_currency / total_amount) if total_amount else Decimal('0')
        )

        pay_term = {
            'total_amount': total_amount,
            'discount_percentage': self.discount_percentage if self.early_discount else Decimal('0'),
            'discount_date': (
                date_ref + timedelta(days=self.discount_days or 0)
                if self.early_discount else False
            ),
            'discount_balance': Decimal('0'),
            'line_ids': [],
        }

        if self.early_discount:
            discount_percentage = self.discount_percentage / Decimal('100')
            if self.early_pay_discount_computation in ('excluded', 'mixed'):
                pay_term['discount_balance'] = _currency_round(
                    company_currency, total_amount - untaxed_amount * discount_percentage)
                pay_term['discount_amount_currency'] = _currency_round(
                    currency, total_amount_currency - untaxed_amount_currency * discount_percentage)
            else:
                pay_term['discount_balance'] = _currency_round(
                    company_currency, total_amount * (Decimal('1') - discount_percentage))
                pay_term['discount_amount_currency'] = _currency_round(
                    currency, total_amount_currency * (Decimal('1') - discount_percentage))

        residual_amount = total_amount
        residual_amount_currency = total_amount_currency

        lines = list(self.line_ids.all())
        for i, line in enumerate(lines):
            term_vals = {
                'date': line._get_due_date(date_ref),
                'company_amount': Decimal('0'),
                'foreign_amount': Decimal('0'),
            }

            on_balance_line = i == len(lines) - 1
            if on_balance_line:
                term_vals['company_amount'] = residual_amount
                term_vals['foreign_amount'] = residual_amount_currency
            elif line.value == 'fixed':
                term_vals['company_amount'] = (
                    sign * _currency_round(company_currency, line.value_amount / rate)
                    if rate else Decimal('0')
                )
                term_vals['foreign_amount'] = sign * _currency_round(currency, line.value_amount)
            else:
                line_amount = _currency_round(
                    company_currency, total_amount * (line.value_amount / Decimal('100')))
                line_amount_currency = _currency_round(
                    currency, total_amount_currency * (line.value_amount / Decimal('100')))
                term_vals['company_amount'] = line_amount
                term_vals['foreign_amount'] = line_amount_currency

            residual_amount -= term_vals['company_amount']
            residual_amount_currency -= term_vals['foreign_amount']
            pay_term['line_ids'].append(term_vals)

        return pay_term

    # -- Odoo _get_amount_by_date ----------------------------------------------
    @api.model
    def _get_amount_by_date(self, terms):
        """Agrupa las cuotas de ``_compute_terms`` por fecha (Odoo
        ``_get_amount_by_date``)."""
        terms_lines = sorted(terms['line_ids'], key=lambda t: t.get('date'))
        amount_by_date = {}
        for term in terms_lines:
            key = term['date']
            results = amount_by_date.setdefault(key, {'date': key, 'amount': Decimal('0')})
            results['amount'] += term['foreign_amount']
        return amount_by_date


class AccountPaymentTermLine(models.Model):
    """``account.payment.term.line`` — cuota de un plazo de pago."""

    value                    = fields.Selection(
        max_length=8, choices=VALUE_TYPES, default='percent',
        help_text='Tipo de valuación de la cuota (Odoo value, requerido).',
    )
    value_amount             = fields.Monetary(
        max_digits=7, decimal_places=2, default=Decimal('100.0'),
        help_text='Importe/porcentaje de la cuota (Odoo value_amount).',
    )
    delay_type               = fields.Selection(
        max_length=32, choices=DELAY_TYPES, default='days_after',
        help_text='Base del cómputo de la fecha de vencimiento (Odoo delay_type).',
    )
    days_next_month          = fields.Char(
        max_length=2, blank=True, default='10',
        help_text='Día del mes siguiente (Odoo days_next_month, sólo con '
                   'delay_type=days_end_of_month_on_the).',
    )
    nb_days                  = fields.Integer(
        default=0, help_text='Días de la cuota (Odoo nb_days).',
    )
    payment                  = fields.Many2one(
        'account.AccountPaymentTerm', on_delete=models.CASCADE,
        related_name='line_ids',
        help_text='Plazo de pago al que pertenece (Odoo payment_id, requerido).',
    )

    class Meta:
        db_table = 'account_payment_term_line'
        ordering = ['id']
        verbose_name = 'Cuota de plazo de pago'
        verbose_name_plural = 'Cuotas de plazo de pago'

    def __str__(self) -> str:
        return f'{self.get_value_display()} {self.value_amount}'

    # -- Odoo _get_due_date (sin dateutil — ver docstring del módulo) --------
    def _get_due_date(self, date_ref):
        """Fecha de vencimiento de la cuota (Odoo ``_get_due_date``)."""
        due_date = date_ref
        if self.delay_type == 'days_after_end_of_month':
            return _end_of_month(due_date) + timedelta(days=self.nb_days)
        if self.delay_type == 'days_after_end_of_next_month':
            return _end_of_month(_shift_month(due_date, 1)) + timedelta(days=self.nb_days)
        if self.delay_type == 'days_end_of_month_on_the':
            try:
                days_next_month = int(self.days_next_month)
            except (TypeError, ValueError):
                days_next_month = 1
            shifted = due_date + timedelta(days=self.nb_days)
            if not days_next_month:
                return _end_of_month(shifted)
            return _shift_month(shifted, 1, day=days_next_month)
        return due_date + timedelta(days=self.nb_days)

    # -- Odoo _check_valid_char_value (constrains days_next_month) -----------
    def _check_valid_char_value(self):
        if self.days_next_month and self.days_next_month.isnumeric():
            if not (0 <= int(self.days_next_month) <= 31):
                raise ValidationError(_('Los días deben estar entre 0 y 31.'))
        else:
            raise ValidationError(
                _('Los días deben ser un número entre 0 y 31.'))

    # -- Odoo _check_percent (constrains value, value_amount) ----------------
    def _check_percent(self):
        if self.value == 'percent' and (self.value_amount < 0 or self.value_amount > 100):
            raise ValidationError(
                _('El porcentaje de las líneas del plazo de pago debe estar entre 0 y 100.'))

    # -- Odoo _compute_display_days_next_month --------------------------------
    @property
    def display_days_next_month(self):
        """≙ ``display_days_next_month`` / ``_compute_display_days_next_month``
        (``:300``, ``:339-341``).

        Sin store: visible sólo cuando
        ``delay_type='days_end_of_month_on_the'``. Portado como propiedad
        (single-record, sin dependencia de hermanas) en vez de un método
        ``_compute_*`` + campo persistido — no hay UI que requiera el campo
        materializado en la base."""
        return self.delay_type == 'days_end_of_month_on_the'

    # -- Odoo _compute_days (sibling-dependiente, ver docstring del módulo) --
    def _compute_days(self):
        """Días por defecto de una línea nueva: los de la línea anterior + 30
        (Odoo ``_compute_days``). Explícito — requiere que ``payment.line_ids``
        ya exista completo; no se auto-invoca en ``save()``."""
        siblings = list(self.payment.line_ids.exclude(pk=self.pk).order_by('id'))
        if not self.nb_days and siblings:
            self.nb_days = siblings[-1].nb_days + 30

    # -- Odoo _compute_value_amount (sibling-dependiente) ---------------------
    def _compute_value_amount(self):
        """Porcentaje por defecto de una línea nueva: 100 menos la suma de
        las líneas ``percent`` hermanas (Odoo ``_compute_value_amount``).
        Explícito — mismo motivo que ``_compute_days``."""
        if self.value == 'fixed':
            self.value_amount = Decimal('0')
            return
        siblings = self.payment.line_ids.exclude(pk=self.pk).filter(value='percent')
        amount = sum((s.value_amount for s in siblings), Decimal('0'))
        self.value_amount = Decimal('100') - amount

    def save(self, *args, **kwargs):
        self._check_valid_char_value()
        self._check_percent()
        return super().save(*args, **kwargs)

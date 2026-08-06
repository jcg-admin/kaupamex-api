"""``account.move`` — asiento contable / factura (Odoo ``account``).

Portación fiel de ``account_move.py`` (Odoo 18/19). Campos núcleo: ``name``,
``ref``, ``date``, ``state`` (draft/posted/cancel), ``move_type``
(entry/out_invoice/…), ``journal``, ``partner``, ``currency``, ``company``,
``amount_total``. Se porta la invariante de doble entrada (Odoo
``_check_balanced``): al postear, la suma de debe == suma de haber.
"""
from decimal import Decimal

import api
from django.conf import settings
from django.db.models import Q
import fields
import models
from addons.account.models.sequence_mixin import SequenceMixin
from exceptions import UserError
from tools.translate import _


class AccountMove(SequenceMixin, models.Model):
    """``account.move`` — asiento contable (o factura si ``move_type`` != entry).

    Hereda ``SequenceMixin`` igual que la referencia lo declara en su
    ``_inherit`` (``odoo19c: account_move.py:74``), con
    ``_sequence_index = "journal_id"`` (``:79``): la serie se segmenta por
    diario. Ver :ref:`h-api-339` para por qué el número vive además como
    columna entera.
    """

    #: Los tres atributos de configuración del mixin, espejo de la referencia.
    sequence_field = 'name'
    sequence_date_field = 'date'
    sequence_index = 'journal'

    STATES = [
        ('draft', 'Borrador'),
        ('posted', 'Publicado'),
        ('cancel', 'Cancelado'),
    ]
    MOVE_TYPES = [
        ('entry', 'Asiento contable'),
        ('out_invoice', 'Factura de cliente'),
        ('out_refund', 'Nota de crédito de cliente'),
        ('in_invoice', 'Factura de proveedor'),
        ('in_refund', 'Nota de crédito de proveedor'),
        ('out_receipt', 'Recibo de venta'),
        ('in_receipt', 'Recibo de compra'),
    ]
    # Prefijo de secuencia por move_type (Odoo deriva el nombre de la secuencia
    # del diario; aquí un prefijo estable por tipo, único con el código de diario).
    SEQUENCE_PREFIXES = {
        'out_invoice': 'INV',
        'out_refund': 'RINV',
        'in_invoice': 'BILL',
        'in_refund': 'RBILL',
        'out_receipt': 'RCPT',
        'in_receipt': 'PRCPT',
        'entry': 'MISC',
    }

    name         = fields.Char(
        max_length=255, blank=True, default='/',
        help_text='Número del asiento (Odoo name; "/" hasta postear).',
    )
    # `sequence_prefix` y `sequence_number` los declara SequenceMixin — no se
    # repiten aquí. Son las dos mitades consultables de `name`; ver H-API-339.
    ref          = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Referencia (Odoo ref).',
    )
    date         = fields.Date(
        help_text='Fecha contable (Odoo date, requerido).',
    )
    state        = fields.Selection(
        max_length=8, choices=STATES, default='draft',
        help_text='Estado (Odoo state).',
    )
    move_type    = fields.Selection(
        max_length=16, choices=MOVE_TYPES, default='entry',
        help_text='Tipo de asiento (Odoo move_type).',
    )
    journal      = fields.Many2one(
        'account.AccountJournal', on_delete=models.PROTECT, related_name='moves',
        help_text='Diario (Odoo journal_id, requerido).',
    )
    partner      = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='account_moves',
        help_text='Contacto (Odoo partner_id → res.partner ≡ party).',
    )
    currency     = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='moves',
        help_text='Moneda (Odoo currency_id).',
    )
    company      = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='moves',
        help_text='Empresa (Odoo company_id).',
    )
    amount_total = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Total del asiento (Odoo amount_total, computado de líneas).',
    )

    class Meta:
        db_table = 'account_move'
        ordering = ['-date', '-id']
        verbose_name = 'Asiento contable'
        verbose_name_plural = 'Asientos contables'
        constraints = [
            # ``odoo19c: account_move.py:785-788`` — UniqueIndex sobre
            # ``(name, journal_id) WHERE state='posted' AND name != '/'``.
            # Es **parcial** a propósito: sin el predicado, los borradores
            # (todos con ``'/'``) chocarían entre sí. Es la restricción que
            # convierte una colisión de numeración en un error inmediato en
            # vez de en dos documentos con el mismo número.
            models.UniqueConstraint(
                fields=['name', 'journal'],
                condition=Q(state='posted') & ~Q(name='/'),
                name='account_move_unique_name_journal',
            ),
        ]
        indexes = [
            # Los dos índices que la referencia crea en ``init()`` del mixin
            # (``odoo19c: sequence_mixin.py:56-57``), con su orden descendente:
            # el primero sirve al «cuál es el último de este prefijo», el
            # segundo al «cuál fue el último prefijo usado en este diario».
            models.Index(
                fields=['journal', '-sequence_prefix', '-sequence_number', 'name'],
                name='account_move_sequence_idx',
            ),
            models.Index(
                fields=['journal', '-id', 'sequence_prefix'],
                name='account_move_sequence_idx2',
            ),
        ]

    def __str__(self) -> str:
        return self.name if self.name != '/' else f'(borrador #{self.pk})'

    # -- Odoo _check_balanced + _post -------------------------------------
    def is_balanced(self):
        """Suma de debe == suma de haber (Odoo ``_check_balanced``)."""
        agg = self.line_ids.aggregate(
            d=models.Sum('debit'), c=models.Sum('credit'))
        debit = agg['d'] or Decimal('0')
        credit = agg['c'] or Decimal('0')
        return debit == credit

    def compute_amount_total(self):
        """Total = suma del debe de las líneas (Odoo amount_total simplificado)."""
        agg = self.line_ids.aggregate(d=models.Sum('debit'))
        self.amount_total = agg['d'] or Decimal('0.00')
        return self.amount_total

    @api.constrains('line_ids')
    def _check_balanced(self):
        """Invariante de doble entrada (Odoo ``_check_balanced``): debe == haber.

        Odoo lanza ``UserError`` si el asiento no cuadra; se replica.
        """
        if not self.is_balanced():
            raise UserError(_('El asiento no está balanceado (debe ≠ haber).'))

    def _sequence_base(self):
        """El prefijo del asiento: ``{tipo}/{diario}/{año}/``."""
        prefix = self.SEQUENCE_PREFIXES.get(self.move_type, 'MISC')
        return f'{prefix}/{self.journal.code}/{self.date.year}/'

    # -- ganchos de sequence.mixin ----------------------------------------

    def get_starting_sequence(self):
        """El nombre base con el que arranca una serie que aún no existe.

        ≙ ``_get_starting_sequence`` (``odoo19c: account_move.py:4249``), que
        compone código de diario + año + relleno. Aquí el prefijo lleva además
        el discriminador de ``move_type``: es nuestro equivalente del
        ``journal.refund_sequence`` de la referencia, que separa la serie de
        notas de crédito de la de facturas. Al ir dentro del prefijo, la
        separación la aplica el propio filtro de prefijo y no hace falta un
        predicado extra en el dominio.

        Arranca en ``00000`` porque ``set_next_sequence`` incrementa después.

        **Sin portar:** la rama ``is_staggered_year`` de la referencia, que
        cambia el año a ``%y-%y`` y el relleno a 4 dígitos cuando el ejercicio
        fiscal no cierra el 31/12. Bloqueada por dependencia medida:
        ``ResCompany`` no tiene ``fiscalyear_last_day`` ni
        ``fiscalyear_last_month``. Mismo bloqueo que el cuarto miembro de la
        sección (``_get_sequence_date_range``, que aquí no se redefine).
        Sucesor registrado: tarea #154.
        """
        return f'{self._sequence_base()}00000'

    def get_last_sequence_domain(self, queryset, relaxed=False):
        """Acota la serie a este diario y al periodo de la fecha.

        ≙ ``_get_last_sequence_domain`` (``odoo19c: account_move.py:4177``).
        Cuatro capas, en el mismo orden que la referencia:

        1. sin fecha o sin diario no hay serie que consultar → ``WHERE FALSE``;
        2. la base del mixin segmenta por diario y descarta los que aún no
           tienen número (``name == '/'``);
        3. el tipo de asiento — nuestro equivalente del ``refund_sequence`` de
           la referencia, que separa la serie de notas de crédito de la de
           facturas. **Aunque el tipo ya está dentro del prefijo, hace falta
           aquí**: el prefijo de la serie se deduce de la fila más reciente del
           dominio, así que sin este filtro la primera nota de crédito heredaría
           el prefijo de la última factura y seguiría *su* numeración;
        4. en modo estricto, la ventana de fechas del periodo, deducida del
           nombre de un asiento de referencia — el último con fecha anterior o
           igual, y si no hay, el primero de la serie.

        **Aquí NO se filtra por ``state``**, aunque la intuición diga que sólo
        los publicados consumen número. La referencia filtra ``name != '/'``,
        no el estado, y esa diferencia importa: un asiento **cancelado**
        conserva su número, así que debe seguir contando para el MAX. Si se
        excluyera, el siguiente asiento propondría un número ya usado y el
        UNIQUE parcial lo rechazaría. En la práctica el efecto buscado se
        cumple igual, porque el número sólo se asigna al publicar.
        """
        if not self.date or not self.journal_id:
            return queryset.none()
        queryset = super().get_last_sequence_domain(queryset, relaxed=relaxed)
        queryset = queryset.filter(move_type=self.move_type)
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        if relaxed:
            return queryset
        reference = (queryset.filter(date__lte=self.date).order_by('-date').first()
                     or queryset.order_by('date').first())
        reset = self.deduce_sequence_number_reset(reference.name) if reference else 'year'
        start, end = self.get_sequence_date_range(reset)
        return queryset.filter(date__gte=start, date__lte=end)

    def must_check_date_sequence(self):
        """Sólo un asiento publicado tiene número que validar contra su fecha.

        ≙ ``_must_check_constrains_date_sequence`` (``odoo19c:
        account_move.py:4173``), sin el término ``quick_edit_mode``, que es una
        conveniencia de la interfaz de la referencia y no existe aquí.
        """
        return self.state == 'posted'

    def post(self):
        """Publica el asiento (Odoo ``_post``): exige doble entrada balanceada.

        Rechaza postear un asiento vacío o desbalanceado. Recalcula
        ``amount_total`` y, si el ``name`` sigue en ``'/'`` (borrador), asigna la
        secuencia del diario (Odoo asigna el número al postear).
        """
        if not self.line_ids.exists():
            raise UserError(_('No se puede publicar un asiento sin líneas.'))
        self._check_balanced()
        self.compute_amount_total()
        if not self.name or self.name == '/':
            # `set_next_sequence` toma el advisory lock del prefijo ANTES de
            # leer el último número, y deja `name`, `sequence_prefix` y
            # `sequence_number` sincronizados entre sí. La versión anterior
            # leía el MAX sin lock: dos transacciones concurrentes proponían
            # el mismo número.
            self.set_next_sequence()
        self.state = 'posted'
        self.constrains_date_sequence()
        self.save(update_fields=[
            'name', 'sequence_prefix', 'sequence_number', 'state',
            'amount_total',
        ])
        return True

    def button_cancel(self):
        """Cancela el asiento (Odoo ``button_cancel``)."""
        self.state = 'cancel'
        self.save(update_fields=['state'])
        return True

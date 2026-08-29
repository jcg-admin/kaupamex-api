"""``account.move.line`` — apunte contable (Odoo ``account``).

Portación fiel de ``account_move_line.py`` (Odoo 18/19). Campos núcleo:
``move``, ``account``, ``name``, ``debit``, ``credit``, ``balance``
(= debit - credit, Odoo ``_compute_balance``), ``display_type``, ``quantity``,
``price_unit``, ``currency``.

``full_reconcile`` y ``matching_number`` — Adaptación de Odoo
``addons/account/models/account_move_line.py`` (odoo-tools@622ddc2a,
odoo19c:). Añadidos aquí (no en el archivo original del puerto) porque la
conciliación cuelga de los apuntes: ``account.partial.reconcile`` y
``account.full.reconcile`` (``account_partial_reconcile.py``,
``account_full_reconcile.py``) necesitan un destino de FK y una columna
donde escribir el resultado del algoritmo de agrupamiento
(``AccountPartialReconcile._update_matching_number``). ``matched_debit_ids``/
``matched_credit_ids`` de la referencia son el reverso de las FK
``debit_move_id``/``credit_move_id`` de ``account.partial.reconcile``
(``related_name`` en ese archivo, sin columna propia aquí — mismo patrón que
``Many2one``/reverse FK del resto del puerto). ``amount_residual`` /
``reconciled`` (booleano derivado) quedan DEFERIDOS: dependen de
``amount_currency`` multi-moneda que este modelo no porta todavía.
"""
from decimal import Decimal

import api
import fields
import models
from addons.analytic.models.analytic_mixin import AnalyticMixin
from addons.product.models.product_supplierinfo import ProductSupplierinfo


class AccountMoveLine(AnalyticMixin, models.Model):
    """``account.move.line`` — línea (apunte) de un asiento contable."""

    _name = 'account.move.line'
    _inherit = ["analytic.mixin"]
    _description = "Journal Item"
    _order = "date desc, move_name desc, id"
    _check_company_auto = True
    _rec_names_search = ['name', 'move_id', 'product_id']

    DISPLAY_TYPES = [
        ('product', 'Producto'),
        ('tax', 'Impuesto'),
        ('cogs', 'Costo de venta'),
        ('payment_term', 'Plazo de pago'),
        ('line_section', 'Sección'),
        ('line_note', 'Nota'),
        ('rounding', 'Redondeo'),
    ]

    move        = fields.Many2one(
        'account.AccountMove', on_delete=models.CASCADE, related_name='line_ids',
        help_text='Asiento al que pertenece (Odoo move_id, requerido).',
    )
    account     = fields.Many2one(
        'account.AccountAccount', on_delete=models.PROTECT, related_name='move_lines',
        null=True, blank=True,
        help_text='Cuenta contable (Odoo account_id).',
    )
    name        = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Etiqueta del apunte (Odoo name).',
    )
    debit       = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Debe (Odoo debit).',
    )
    credit      = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Haber (Odoo credit).',
    )
    balance     = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Saldo = debe - haber (Odoo balance, computado).',
    )
    display_type = fields.Selection(
        max_length=16, choices=DISPLAY_TYPES, blank=True, default='',
        help_text='Tipo de línea (Odoo display_type).',
    )
    quantity    = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('1.0'),
        help_text='Cantidad (Odoo quantity).',
    )
    price_unit  = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0'),
        help_text='Precio unitario (Odoo price_unit).',
    )
    currency    = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='move_lines',
        help_text='Moneda (Odoo currency_id).',
    )
    full_reconcile = fields.Many2one(
        'account.AccountFullReconcile', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='reconciled_line_ids',
        help_text='Conciliación total que agrupa este apunte (Odoo '
                   'full_reconcile_id). Nulo mientras no exista match total.',
    )
    matching_number = fields.Char(
        max_length=16, blank=True, default='',
        help_text="Odoo matching_number: 'P<id>' mientras la conciliación es "
                   "parcial (id del grupo, asignado por "
                   "AccountPartialReconcile._update_matching_number); el id "
                   "de account.full.reconcile como texto cuando es total. "
                   "Vacío si el apunte no está conciliado.",
    )

    # ------------------------------------------------------------------
    # Las ocho columnas que ``account.invoice.report`` lee de este apunte
    # (tarea #989), de ``odoo19c: account/models/account_move_line.py``
    # (LGPL-3: copia + adaptacion con atribucion). Cubren ademas ``journal``
    # y ``partner`` de la tarea **#526**; ``analytic_distribution``, el tercer
    # campo que aquella pide, no lo lee la vista y sigue en su alcance.
    # ------------------------------------------------------------------
    journal_id = fields.Many2one(
        'account.AccountJournal', on_delete=models.PROTECT,
        null=True, blank=True, related_name='lines', db_index=True,
        verbose_name='Diario',
        db_column='journal_id',
        help_text='Odoo journal_id (account_move_line.py:42). La fuente lo '
                  'declara related a move_id.journal_id con store=True; aqui '
                  'es columna propia que save() copia del asiento, que es como '
                  'este arbol materializa un related almacenado.',
    )
    company_id = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE,
        null=True, blank=True, related_name='move_lines', db_index=True,
        verbose_name='Empresa',
        db_column='company_id',
        help_text='Odoo company_id (account_move_line.py:55). Related a '
                  'move_id.company_id, materializado en save().',
    )
    company_currency_id = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='move_lines_as_company_currency',
        verbose_name='Moneda de la empresa',
        db_column='company_currency_id',
        help_text='Odoo company_currency_id ("Company Currency", '
                  'account_move_line.py:59). Related a '
                  'move_id.company_currency_id, materializado en save().',
    )
    partner_id = fields.Many2one(
        'base.ResPartner', on_delete=models.PROTECT,
        null=True, blank=True, related_name='move_lines',
        verbose_name='Contacto',
        db_column='partner_id',
        help_text='Odoo partner_id ("Partner", account_move_line.py:152). '
                  'Apunta a res.partner igual que la fuente. El asiento padre '
                  'apunta al modelo de usuario -- ese desnivel es la tarea '
                  '#142, y este campo ya nace del lado correcto.',
    )
    product_id = fields.Many2one(
        'product.ProductProduct', on_delete=models.PROTECT,
        null=True, blank=True, related_name='move_lines', db_index=True,
        verbose_name='Producto',
        db_column='product_id',
        help_text='Odoo product_id ("Product", account_move_line.py:363).',
    )
    product_uom_id = fields.Many2one(
        'uom.Uom', on_delete=models.PROTECT,
        null=True, blank=True, related_name='move_lines',
        verbose_name='Unidad',
        db_column='product_uom_id',
        help_text='Odoo product_uom_id ("Unit", account_move_line.py:372). '
                  'La calcula compute_product_uom_id(), que save() invoca. El '
                  'domain= de la fuente no tiene analogo declarativo en Django '
                  'y se acota al elegir filtered_sellers.',
    )
    price_subtotal = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Subtotal',
        help_text='Odoo price_subtotal ("Subtotal", account_move_line.py:400). '
                  'Base sin impuestos. La fuente la calcula en _compute_totals; '
                  'ver el bloqueo declarado en ese metodo.',
    )
    price_total = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Total',
        help_text='Odoo price_total ("Total", account_move_line.py:405). Base '
                  'mas impuestos. Misma procedencia que price_subtotal.',
    )

    class Meta:
        db_table = 'account_move_line'
        ordering = ['move', 'id']
        verbose_name = 'Apunte contable'
        verbose_name_plural = 'Apuntes contables'

    def __str__(self) -> str:
        return f'{self.name or self.account} {self.debit}/{self.credit}'

    @api.depends('debit', 'credit')
    def _compute_balance(self):
        # Odoo _compute_balance: balance = debit - credit.
        self.balance = (self.debit or Decimal('0.00')) - (self.credit or Decimal('0.00'))

    def _compute_partner_id(self):
        """El contacto del apunte -- ≙ ``odoo19c: :533-535``.

        La fuente escribe ``line.move_id.partner_id.commercial_partner_id``.
        Ese recorrido es, por definicion, el campo ``commercial_partner`` que
        el asiento ya calcula, asi que aqui se lee de ahi en vez de repetir el
        rodeo por la delegacion de usuario que la tarea **#142** tiene abierta.
        """
        self.partner_id = self.move.commercial_partner_id if self.move_id else None

    def _compute_product_uom_id(self):
        """La unidad del producto -- ≙ ``odoo19c: :883-891``.

        Las DOS ramas de la fuente corren. La de compra pide al proveedor
        filtrado su unidad de compra; la general toma la del propio producto.

        Ninguna esta bloqueada, y la cita de bloqueo que este metodo llevaba
        era falsa: ``filtered_suppliers`` existe
        (``product_supplierinfo.py:302``, la equivalencia declarada de
        ``_get_filtered_supplier``), y ``seller_ids`` es un gestor sobre
        ``product.template``. Es la misma clase de defecto que
        :ref:`h-api-910` y :ref:`h-api-911` -- una cita de bloqueo dirige el
        trabajo de quien la lea, asi que se mide antes de escribirla.

        El ``filtered(lambda l: l.parent_state == 'draft')`` de la fuente se
        expresa contra el estado del asiento padre: ``parent_state`` es el
        related que la fuente declara sobre ``move_id.state``.
        """
        if self.move_id and self.move.state != 'draft':
            return
        if not self.product_id:
            self.product_uom_id = None
            return
        product_uom = self.product_id.uom
        if self.move_id and self.move.is_purchase_document():
            sellers = list(self.product_id.product_tmpl.seller_ids.all())
            filtered_sellers = ProductSupplierinfo.filtered_suppliers(
                sellers, self.company_id, self.product_id)
            first_seller = filtered_sellers[0] if filtered_sellers else None
            self.product_uom_id = getattr(first_seller, 'product_uom', None) or product_uom
            return
        self.product_uom_id = product_uom

    def _compute_totals(self):
        """Base e impuestos del apunte -- ≙ ``odoo19c: :411-...``.

        BLOQUEADO por ``tax_ids`` -- la fuente reparte ``price_unit`` y
        ``quantity`` entre base e impuesto llamando a ``compute_all`` sobre los
        impuestos del apunte, y este modelo no declara esa relacion (medido: la
        cadena ``tax`` aparece 1 vez en el archivo, y es prosa). El motor si
        existe: ``AccountTax.compute_all`` (``account_tax.py:411``), de modo que
        el bloqueo es del dato, no del mecanismo. Falta tambien ``discount``.
        Sucesor: tarea **#990**.
        """
        raise NotImplementedError(
            'AccountMoveLine._compute_totals esta BLOQUEADO por ``tax_ids`` -- '
            'el apunte no declara sus impuestos, asi que no hay que repartir. '
            'El motor compute_all si existe (account_tax.py:411). '
            'Sucesor: tarea #990.')

    def _inverse_partner_id(self):
        """Recalcula la cuenta al cambiar el contacto -- ≙ ``odoo19c: :1393-1397``.

        BLOQUEADO por ``_conditional_add_to_compute`` -- el mecanismo que marca
        un campo almacenado para recalculo selectivo. Medido: 0 declaraciones en
        ``src/orm``. Su sucesor es la tarea **#191**, la decision sobre construir
        el motor de dependencias.
        """
        raise NotImplementedError(
            'AccountMoveLine._inverse_partner_id esta BLOQUEADO por '
            '``_conditional_add_to_compute`` -- no hay recalculo selectivo de '
            'campo almacenado en este ORM. Sucesor: tarea #191.')

    def _inverse_product_id(self):
        """Recalcula la cuenta al cambiar el producto -- ≙ ``odoo19c: :1399-1404``.

        BLOQUEADO por ``_conditional_add_to_compute`` -- misma pieza y mismo
        sucesor que ``_inverse_partner_id``: tarea **#191**.
        """
        raise NotImplementedError(
            'AccountMoveLine._inverse_product_id esta BLOQUEADO por '
            '``_conditional_add_to_compute`` -- no hay recalculo selectivo de '
            'campo almacenado en este ORM. Sucesor: tarea #191.')

    def save(self, *args, **kwargs):
        """Materializa los related y corre los compute que tienen sus insumos.

        Los tres ``related`` de la fuente -- ``journal``, ``company`` y
        ``company_currency`` -- se declaran ``store=True`` alli; aqui son
        columna propia y se copian del asiento en cada guardado, que es como
        este arbol materializa un related almacenado sin motor de
        ``@api.depends`` (decision abierta en la tarea **#191**).
        """
        self._compute_balance()
        if self.move_id:
            self.journal_id = self.move.journal
            self.company_id = self.move.company
            self.company_currency_id = getattr(self.move.company, 'currency', None)
            self._compute_partner_id()
        self._compute_product_uom_id()
        return super().save(*args, **kwargs)

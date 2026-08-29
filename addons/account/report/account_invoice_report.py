"""``account.invoice.report`` + los reportes de factura -- adaptacion de
``odoo19c: addons/account/report/account_invoice_report.py``
(``odoo-tools@622ddc2a``, LGPL-3 -- atribucion y aviso de licencia
preservados, DEC-KX-03).

La fuente declara TRES clases. Sus formas divergen entre si en la
referencia misma, y el porte respeta esa diferencia:

- ``AccountInvoiceReport`` (``models.Model``, ``_auto = False`` +
  ``_table_query``) -- y **no** es una vista SQL. Medido
  2026-08-29T10:54:55: ``odoo19c: odoo/orm/models.py:488-497`` envuelve el
  ``_table_query`` en ``SQL("(%s)", table_query)`` y lo entrega como la
  clausula FROM de cada consulta; ``odoo/orm/registry.py:954`` lo confirma
  desde el otro lado, excluyendo del barrido de tablas ausentes a todo
  modelo con ``_table_query``. Aqui es un modelo Django con
  ``Meta.managed = False``.

  **La referencia usa DOS mecanismos bajo ``_auto = False``, y este archivo
  los confundia.** Su docstring citaba el precedente de ``ResDevice``
  (``managed=False`` + ``RunSQL``) y declaraba pendiente emitir un
  ``CREATE OR REPLACE VIEW``. ``ResDevice`` si crea vista -- lleva
  ``_auto = False`` **y** ``def init(self)``
  (``odoo19c: base/models/res_device.py:178,230``) -- pero este modelo lleva
  la otra forma, y emitir el DDL seria inventar algo que la fuente no tiene.
  Ademas congelaria en DDL un SQL que depende de ``get_current_companies()``
  en tiempo de consulta. Censo: **12** archivos con ``_table_query`` frente a
  **21** archivos de reporte con ``def init(self)``; las dos formas estan
  pobladas. Lo que falta es el gestor que ponga la subconsulta en el FROM.
  Sucesor: tarea **#991**.

- ``ReportAccountReport_Invoice`` / ``..._With_Payments`` (ambas
  ``models.AbstractModel``) -- ensambladores de datos para una plantilla
  QWeb, sin tabla propia. Aqui son clases planas con ``classmethod`` --
  **mismo patron** que ``ReportBaseReport_Irmodulereference`` en
  ``src/addons/base/report/report_base_report_irmodulereference.py`` (el
  precedente "formulario, no tabla" ya fijado en este arbol para
  ``AbstractModel``).

Cobertura del porte -- Porte BLOQUEADO — 44 de 45 símbolos
===========================================================

Los 45 simbolos estan en forma; uno solo no corre.

.. list-table::
   :header-rows: 1

   * - Clase
     - Simbolos
     - Estado
   * - ``AccountInvoiceReport``
     - 33 atributos (6 de clase de modelo + 27 campos) + 5 metodos
     - portado; ``_read_group_select`` BLOQUEADO por ``read_group`` — el
       override no tiene despachador base al que engancharse.
   * - ``ReportAccountReportInvoice``
     - 3 de la fuente (``_name``, ``_description``, 1 metodo) -> 2 aqui
       (``REPORT_NAME`` colapsa los dos primeros + 1 metodo)
     - portado y funcional
   * - ``ReportAccountReportInvoiceWithPayments``
     - 4 de la fuente (``_name``, ``_description``, ``_inherit``, 1
       metodo) -> 2 aqui (``REPORT_NAME`` + herencia Python + 1 metodo)
     - portado y funcional

**Por que las 5 clases con contraparte exacta de nombre importan para el
gate.** ``scripts/check_model_class_attributes.py`` empareja clases por
nombre IDENTICO entre este archivo y el de la referencia. Se conserva
``AccountInvoiceReport`` verbatim (ya es un nombre limpio) para que el gate
mida su cabecera de ORM; las dos clases ``AbstractModel`` se renombran sin
guion bajo interno (mismo criterio que
``ReportBaseReportIrmodulereference``, que tampoco conservo el guion bajo
mangled de su fuente ``ReportBaseReport_Irmodulereference``) -- el gate no
las empareja por eso, y esta bien: no son modelos Django, su cabecera de
ORM no aplica.

**Los cuatro productores de SQL estan PORTADOS (2026-08-29).** El bloqueo
que este docstring declaraba -- ``ResCurrency._get_simple_currency_table``
ausente -- se cerro con la tarea #511: los ocho metodos de la tabla de
divisas viven en ``addons/account/models/res_currency.py`` y
``_from()`` los invoca. ``_table_query``, ``_select``, ``_from`` y
``_where`` son hoy el porte verbatim de la fuente.

**Lo que sigue sin correr, y su dueno cambio.** ``_read_group_select`` esta
BLOQUEADO por ``read_group`` — la fuente
llama ``super()._read_group_select(...)`` para todo agregado que no sea
``price_average``. Medido: **0 declaraciones** de ``read_group`` en
``src/orm``. Lo que NO lo bloquea es ``_field_to_sql`` -- ese si existe
(``src/orm/models.py:1388``, misma firma que la fuente), asi que la cita a
la tarea #291 que este docstring hacia era falsa. Sucesor correcto: tarea
**#473**.

**Las 14 columnas ESTAN PORTADAS (2026-08-29, tarea #989).** El bloqueo que
este parrafo declaraba -- que el SQL leia 14 columnas que las dos tablas de
asiento no declaraban -- se cerro: seis en ``account_move``
(``invoice_user_id``, ``fiscal_position_id``, ``invoice_date``,
``invoice_date_due``, ``invoice_currency_rate``, ``commercial_partner_id``) y
ocho en ``account_move_line`` (``product_id``, ``journal_id``, ``company_id``,
``company_currency_id``, ``partner_id``, ``price_subtotal``, ``price_total``,
``product_uom_id``), con su migracion ``account/migrations/0022``.

Las otras cinco tablas que el ``FROM`` toca ya estaban completas para este SQL:
``res_partner.country_id``, ``product_product.{product_tmpl_id,
standard_price}``, ``product_template.{categ_id, uom_id}``, ``uom_uom.factor`` y
``account_account.account_type`` -- 8 de 8.

**Lo que las columnas nuevas NO traen todavia, y esta declarado.** Dos de ellas
nacen en cero porque su compute esta BLOQUEADO por ``tax_ids`` -- el apunte no
declara sus impuestos, de modo que ``_compute_totals`` no tiene que repartir.
El motor si existe (``AccountTax.compute_all``, ``account_tax.py:411``), asi que
el bloqueo es del dato. Sucesor: tarea **#990**. La vista los leera como 0.00
hasta entonces, que es un valor honesto y no una ausencia de columna.

*Metrica:* columnas de la sentencia ``_select``/``_from`` cruzadas contra
``Model._meta.get_fields()`` del esquema vivo (``django.setup()``).
*Ciega a:* el tipo y la nulabilidad de la columna -- comprueba que el
nombre resuelva, no que su forma coincida con la de la fuente.

**Que SI se porta, completo.** Los 27 campos y los 6 atributos de clase de
modelo (``_name``, ``_description``, ``_auto``, ``_rec_name``, ``_order``,
``_depends``) son forma pura y describen el contrato completo de la vista.
"""
import fields
import models

from addons.account.models.account_move import AccountMove
from addons.base.models.res_company import ResCompany
from addons.base.models.res_currency import ResCurrency
from orm.environments import get_current_companies
from tools.sql import SQL

#: Subconjunto de ``AccountMove.MOVE_TYPES`` que aplica a este reporte --
#: solo los cuatro tipos de documento de factura/nota de credito
#: (``odoo19c: addons/account/report/account_invoice_report.py:27-32``). Se
#: deriva de ``AccountMove.MOVE_TYPES`` en vez de repetir las etiquetas a
#: mano, para que las dos listas nunca diverjan en texto.
_INVOICE_MOVE_TYPE_KEYS = ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')
_MOVE_TYPE_LABELS_BY_KEY = dict(AccountMove.MOVE_TYPES)
MOVE_TYPE_CHOICES = [
    (key, _MOVE_TYPE_LABELS_BY_KEY[key]) for key in _INVOICE_MOVE_TYPE_KEYS
]


class AccountInvoiceReport(models.Model):
    """``account.invoice.report`` -- estadisticas de facturas (vista SQL).

    Fiel a ``odoo19c: addons/account/report/account_invoice_report.py:13-``.
    Ver el docstring del modulo para el estado del bloqueo de
    ``_select``/``_from``/``_where``/``_read_group_select``.
    """

    # ---- Atributos de clase de modelo (atributos-de-clase-de-modelo.md) ----
    # Verbatim contra la referencia; NO sustituyen a su forma Django en
    # ``Meta`` -- coexisten (``_name``/``_description`` con
    # ``Meta.verbose_name``, ``_order`` con ``Meta.ordering``).
    _name = 'account.invoice.report'
    _description = 'Invoices Statistics'
    _auto = False
    _rec_name = 'invoice_date'
    _order = 'invoice_date desc'

    # ==== Campos de la factura ====
    move_id = fields.Many2one(
        'account.AccountMove', on_delete=models.DO_NOTHING,
        db_column='move_id',
        null=True, blank=True, related_name='+')
    journal_id = fields.Many2one(
        'account.AccountJournal', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        db_column='journal_id',
        help_text='Diario (Odoo journal_id).')
    company_id = fields.Many2one(
        'base.ResCompany', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        db_column='company_id',
        help_text='Compania (Odoo company_id).')
    company_currency_id = fields.Many2one(
        'base.ResCurrency', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        db_column='company_currency_id',
        help_text='Moneda de la compania (Odoo company_currency_id).')
    partner_id = fields.Many2one(
        'base.ResPartner', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        db_column='partner_id',
        help_text='Contacto (Odoo partner_id).')
    commercial_partner_id = fields.Many2one(
        'base.ResPartner', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        db_column='commercial_partner_id',
        help_text='Contacto principal (Odoo commercial_partner_id).')
    country_id = fields.Many2one(
        'base.ResCountry', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        db_column='country_id',
        help_text='Pais (Odoo country_id).')
    invoice_user_id = fields.Many2one(
        'base.ResUsers', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        db_column='invoice_user_id',
        help_text='Comercial (Odoo invoice_user_id).')
    move_type = fields.Selection(
        max_length=16, choices=MOVE_TYPE_CHOICES, null=True, blank=True,
        help_text='Tipo de documento (Odoo move_type).')
    state = fields.Selection(
        max_length=16, choices=AccountMove.STATES, null=True, blank=True,
        help_text='Estatus de la factura (Odoo state).')
    payment_state = fields.Selection(
        max_length=32, choices=AccountMove.PAYMENT_STATES,
        null=True, blank=True,
        help_text='Estatus de pago (Odoo payment_state).')
    fiscal_position_id = fields.Many2one(
        'account.AccountFiscalPosition', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        db_column='fiscal_position_id',
        help_text='Posicion fiscal (Odoo fiscal_position_id).')
    invoice_date = fields.Date(
        null=True, blank=True, help_text='Fecha de factura (Odoo invoice_date).')

    # ==== Campos de la linea de factura ====
    quantity = fields.Float(
        null=True, blank=True,
        help_text='Cantidad de producto (Odoo quantity).')
    product_id = fields.Many2one(
        'product.ProductProduct', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        db_column='product_id',
        help_text='Producto (Odoo product_id).')
    product_uom_id = fields.Many2one(
        'uom.Uom', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        db_column='product_uom_id',
        help_text='Unidad (Odoo product_uom_id).')
    product_categ_id = fields.Many2one(
        'product.ProductCategory', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        db_column='product_categ_id',
        help_text='Categoria de producto (Odoo product_categ_id).')
    invoice_date_due = fields.Date(
        null=True, blank=True,
        help_text='Fecha de vencimiento (Odoo invoice_date_due).')
    account_id = fields.Many2one(
        'account.AccountAccount', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        db_column='account_id',
        help_text='Cuenta de ingreso/gasto (Odoo account_id).')
    price_subtotal_currency = fields.Float(
        null=True, blank=True,
        help_text='Importe sin impuestos en la moneda del documento '
                   '(Odoo price_subtotal_currency).')
    price_subtotal = fields.Float(
        null=True, blank=True,
        help_text='Importe sin impuestos (Odoo price_subtotal).')
    price_total = fields.Float(
        null=True, blank=True, help_text='Total (Odoo price_total).')
    price_total_currency = fields.Float(
        null=True, blank=True,
        help_text='Total en la moneda del documento (Odoo price_total_currency).')
    price_average = fields.Float(
        null=True, blank=True,
        help_text='Precio promedio (Odoo price_average). El '
                   '``aggregator="avg"`` de la fuente no se porta: depende '
                   'de ``_read_group_select``, BLOQUEADO -- ver el '
                   'docstring del modulo.')
    price_margin = fields.Float(
        null=True, blank=True, help_text='Margen (Odoo price_margin).')
    inventory_value = fields.Float(
        null=True, blank=True,
        help_text='Valor de inventario (Odoo inventory_value).')
    currency_id = fields.Many2one(
        'base.ResCurrency', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        db_column='currency_id',
        help_text='Moneda del documento (Odoo currency_id).')

    #: Verbatim contra la fuente (``odoo19c: :58-71``) -- documenta de que
    #: campos de que modelos depende el recalculo de la vista SQL. Inerte
    #: en este ORM: no existe mecanismo de auto-refresco de vista por
    #: dependencia declarada (la vista se recrea via migracion, no via
    #: un trigger de ``_depends``). Se conserva como documentacion viva del
    #: contrato, fiel al atributo de clase de la referencia.
    _depends = {
        'account.move': [
            'name', 'state', 'move_type', 'partner_id', 'invoice_user_id',
            'fiscal_position_id', 'invoice_date', 'invoice_date_due',
            'invoice_payment_term_id', 'partner_bank_id',
            'invoice_currency_rate',
        ],
        'account.move.line': [
            'quantity', 'price_subtotal', 'price_total', 'amount_residual',
            'balance', 'amount_currency', 'move_id', 'product_id',
            'product_uom_id', 'account_id', 'journal_id', 'company_id',
            'currency_id', 'partner_id',
        ],
        'product.product': ['product_tmpl_id', 'standard_price'],
        'product.template': ['categ_id'],
        'uom.uom': ['factor', 'name'],
        'res.currency.rate': ['currency_id', 'name'],
        'res.partner': ['country_id'],
    }

    class Meta:
        app_label = 'account'
        managed = False
        db_table = 'account_invoice_report'
        ordering = ['-invoice_date']
        verbose_name = 'Estadistica de factura'
        verbose_name_plural = 'Estadisticas de factura'

    @property
    def _table_query(self):
        """≙ ``_table_query`` (``odoo19c: :78-80``): la vista completa.

        La fuente compone ``_select() + _from() + _where()`` con un ``SQL`` de
        tres marcadores. Aquí igual: la clase ``SQL`` de ``tools.sql`` es el
        porte fiel de la de la referencia y compone anidando.
        """
        return SQL('%s %s %s', self._select(), self._from(), self._where())

    @classmethod
    def _select(cls):
        """≙ ``_select`` (``odoo19c: :81-127``).

        Verbatim de la fuente. Las columnas monetarias se multiplican por
        ``account_currency_table.rate``, la tasa que produce ``_from()``: sin
        ella un reporte multi-empresa sumaría importes de divisas distintas
        como si fueran la misma.
        """
        return SQL(
            '''
            SELECT
                line.id,
                line.move_id,
                line.product_id,
                line.account_id,
                line.journal_id,
                line.company_id,
                line.company_currency_id,
                line.partner_id AS commercial_partner_id,
                account.account_type AS user_type,
                move.state,
                move.move_type,
                move.partner_id,
                move.invoice_user_id,
                move.fiscal_position_id,
                move.payment_state,
                move.invoice_date,
                move.invoice_date_due,
                uom_template.id                                             AS product_uom_id,
                template.categ_id                                           AS product_categ_id,
                line.quantity * COALESCE(uom_line.factor, 1) / NULLIF(COALESCE(uom_template.factor, 1), 0.0) * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                                                                            AS quantity,
                line.price_subtotal * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                                                                            AS price_subtotal_currency,
                -line.balance * account_currency_table.rate                         AS price_subtotal,
                line.price_total * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                / move.invoice_currency_rate
                                                                            AS price_total,
                line.price_total * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                                                                            AS price_total_currency,
                -COALESCE(
                   -- Average line price
                   (line.balance / NULLIF(line.quantity, 0.0)) * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                   -- convert to template uom
                   / NULLIF(COALESCE(uom_line.factor, 1), 0.0) * COALESCE(uom_template.factor, 1),
                   0.0) * account_currency_table.rate                               AS price_average,
                CASE
                    WHEN move.move_type NOT IN ('out_invoice', 'out_receipt', 'out_refund') THEN 0.0
                    WHEN move.move_type = 'out_refund' THEN account_currency_table.rate * (-line.balance + (line.quantity * COALESCE(uom_line.factor, 1) / NULLIF(COALESCE(uom_template.factor, 1), 0.0)) * COALESCE(product.standard_price -> line.company_id::text, to_jsonb(0.0))::float)
                    ELSE account_currency_table.rate * (-line.balance - (line.quantity * COALESCE(uom_line.factor, 1) / NULLIF(COALESCE(uom_template.factor, 1), 0.0)) * COALESCE(product.standard_price -> line.company_id::text, to_jsonb(0.0))::float)
                END
                                                                            AS price_margin,
                account_currency_table.rate * line.quantity * COALESCE(uom_line.factor, 1) / NULLIF(COALESCE(uom_template.factor, 1), 0.0) * (CASE WHEN move.move_type IN ('out_invoice','in_refund','out_receipt') THEN -1 ELSE 1 END)
                    * COALESCE(product.standard_price -> line.company_id::text, to_jsonb(0.0))::float                    AS inventory_value,
                COALESCE(partner.country_id, commercial_partner.country_id) AS country_id,
                line.currency_id                                            AS currency_id
            ''',
        )

    @classmethod
    def _from(cls):
        """≙ ``_from`` (``odoo19c: :128-141``).

        El JOIN con la tabla de divisas es lo que convierte cada importe a la
        moneda de la empresa que lee. Lo produce
        ``ResCurrency._get_simple_currency_table`` sobre las empresas
        ACTIVADAS.

        DIVERGENCIA DE MECANISMO, declarada: la fuente pasa ``self.env.companies``,
        que es un recordset; aquí las empresas activadas son PKs
        (``get_current_companies()``) y se materializan con el gestor de
        Django. El conjunto es el mismo — cambia cómo se nombra.
        """
        companies = list(ResCompany.objects.filter(pk__in=get_current_companies()))
        return SQL(
            '''
            FROM account_move_line line
                LEFT JOIN res_partner partner ON partner.id = line.partner_id
                LEFT JOIN product_product product ON product.id = line.product_id
                LEFT JOIN account_account account ON account.id = line.account_id
                LEFT JOIN product_template template ON template.id = product.product_tmpl_id
                LEFT JOIN uom_uom uom_line ON uom_line.id = line.product_uom_id
                LEFT JOIN uom_uom uom_template ON uom_template.id = template.uom_id
                INNER JOIN account_move move ON move.id = line.move_id
                LEFT JOIN res_partner commercial_partner ON commercial_partner.id = move.commercial_partner_id
                JOIN %(currency_table)s ON account_currency_table.company_id = line.company_id
            ''',
            currency_table=ResCurrency._get_simple_currency_table(companies),
        )

    @classmethod
    def _where(cls):
        """≙ ``_where`` (``odoo19c: :142-148``). Verbatim de la fuente."""
        return SQL(
            '''
            WHERE move.move_type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'out_receipt', 'in_receipt')
                AND line.account_id IS NOT NULL
                AND line.display_type = 'product'
            ''',
        )

    def _read_group_select(self, aggregate_spec, query):
        """≙ ``_read_group_select`` (``odoo19c: :149-156``).

        BLOQUEADO por ``read_group`` — el bloqueo cambió de dueño.
        ``_field_to_sql`` **sí**
        existe aquí (``src/orm/models.py:1388``, misma firma que la fuente),
        así que la cita anterior a la tarea #291 era falsa. Lo que falta es el
        método al que este override se engancha: ``read_group`` no existe en
        ``src/orm`` — medido, 0 declaraciones. Sin el despachador base, la
        rama ``super()._read_group_select(...)`` de la fuente no tiene a
        quién llamar y el override no tiene quién lo invoque.

        Sucesor: tarea **#473** (completar la superficie ``read_group``).
        """
        raise NotImplementedError(
            'AccountInvoiceReport._read_group_select esta BLOQUEADO por '
            '``read_group`` — el override necesita ese despachador base, y '
            'src/orm no lo declara (medido: 0 def read_group). _field_to_sql '
            'si existe (src/orm/models.py:1388). Sucesor: tarea #473.'
        )


class ReportAccountReportInvoice:
    """>= ``report.account.report_invoice`` (``odoo19c:
    addons/account/report/account_invoice_report.py:180-183``): factura sin
    lineas de pago.

    Adaptacion de forma: la fuente es ``models.AbstractModel``; aqui es una
    clase plana con ``classmethod`` -- el patron "formulario, no tabla" ya
    fijado por
    ``src/addons/base/report/report_base_report_irmodulereference.py``.
    """

    #: ``report_name`` del reporte al que sirve
    #: (``odoo19c: addons/account/report/account_invoice_report.py:181``).
    REPORT_NAME = 'account.report_invoice'

    @classmethod
    def _get_report_values(cls, docids, data=None):
        """>= ``_get_report_values`` (``odoo19c: :185-196``).

        Portado y funcional para la parte que no depende de campos
        ausentes (``doc_ids``/``doc_model``/``docs``). Los codigos QR se
        aislan en :meth:`_qr_code_urls`, que si esta BLOQUEADO -- ver su
        docstring.

        :param docids: ids de ``account.move`` a incluir en el reporte.
        :param data: datos adicionales del reporte; se les fusiona
            ``report_type`` en la subclase con pagos.
        """
        docs = AccountMove.objects.filter(pk__in=docids)
        return {
            'doc_ids': docids,
            'doc_model': 'account.move',
            'docs': docs,
            'qr_code_urls': cls._qr_code_urls(docs, data),
        }

    @classmethod
    def _qr_code_urls(cls, docs, data):
        """Genera la URL de codigo QR por factura -- BLOQUEADO.

        La fuente pregunta ``invoice.display_qr_code`` y llama
        ``invoice._generate_qr_code(silent_errors=...)`` por cada
        documento (``odoo19c: :187-192``). Medido en este arbol:
        ``grep -rn "display_qr_code\\|_generate_qr_code"
        addons/account/`` -> **0** apariciones -- ninguno de los dos existe
        en ``AccountMove`` (``addons/account/models/account_move.py``,
        fuera de mi alcance de escritura en la tarea #398).

        No se degrada en silencio a ``{}``: eso seria el OK silencioso que
        ``check_silent_oks`` existe para impedir -- un reporte que
        "funciona" pero nunca muestra el QR, sin ninguna senal de que
        falta. Se levanta en cuanto hay al menos un documento a resolver;
        con ``docs`` vacio no hay nada que el metodo deba resolver, asi
        que no bloquea el caso trivial.
        """
        if not docs:
            return {}
        raise NotImplementedError(
            'AccountMove.display_qr_code / AccountMove._generate_qr_code '
            'no estan portados (addons/account/models/account_move.py, '
            'fuera de mi alcance de escritura en la tarea #398). Ver '
            'hallazgo H-API-682, sucesor: tarea #512.'
        )


class ReportAccountReportInvoiceWithPayments(ReportAccountReportInvoice):
    """>= ``report.account.report_invoice_with_payments`` (``odoo19c:
    addons/account/report/account_invoice_report.py:199-``): factura CON
    lineas de pago.

    El ``_inherit = ['report.account.report_invoice']`` de la fuente
    (``:201``) se adapta como herencia Python de
    :class:`ReportAccountReportInvoice` -- mismo mecanismo de reuso, forma
    nativa del lenguaje.
    """

    #: ``report_name`` del reporte al que sirve
    #: (``odoo19c: addons/account/report/account_invoice_report.py:200``).
    REPORT_NAME = 'account.report_invoice_with_payments'

    @classmethod
    def _get_report_values(cls, docids, data=None):
        """>= ``_get_report_values`` (``odoo19c: :204-206``): agrega
        ``report_type`` al resultado de la clase base.
        """
        result = super()._get_report_values(docids, data)
        result['report_type'] = data.get('report_type') if data else ''
        return result

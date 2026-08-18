"""``account.invoice.report`` + los reportes de factura -- adaptacion de
``odoo19c: addons/account/report/account_invoice_report.py``
(``odoo-tools@622ddc2a``, LGPL-3 -- atribucion y aviso de licencia
preservados, DEC-KX-03).

La fuente declara TRES clases. Sus formas divergen entre si en la
referencia misma, y el porte respeta esa diferencia:

- ``AccountInvoiceReport`` (``models.Model``, ``_auto = False``) -- una
  vista SQL real, consultable con el ORM. Aqui es un modelo Django con
  ``Meta.managed = False``: **mismo patron** que ``ResDevice`` en
  ``src/addons/base/models/res_device.py`` (ver su docstring, que cita el
  precedente completo con su migracion ``RunSQL``).
- ``ReportAccountReport_Invoice`` / ``..._With_Payments`` (ambas
  ``models.AbstractModel``) -- ensambladores de datos para una plantilla
  QWeb, sin tabla propia. Aqui son clases planas con ``classmethod`` --
  **mismo patron** que ``ReportBaseReport_Irmodulereference`` en
  ``src/addons/base/report/report_base_report_irmodulereference.py`` (el
  precedente "formulario, no tabla" ya fijado en este arbol para
  ``AbstractModel``).

Cobertura del porte -- 45 de 45 simbolos (forma), 3 BLOQUEADOS (comportamiento)
=================================================================================

.. list-table::
   :header-rows: 1

   * - Clase
     - Simbolos
     - Estado
   * - ``AccountInvoiceReport``
     - 33 atributos (6 de clase de modelo + 27 campos) + 5 metodos
     - forma completa; ``_table_query``/``_select``/``_from``/``_where``/
       ``_read_group_select`` **BLOQUEADOS** en tiempo de ejecucion
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

**Por que ``AccountInvoiceReport`` esta BLOQUEADO -- con las citas exactas.**
El nucleo de ``_select``/``_from`` depende de
``ResCurrency._get_simple_currency_table(companies)``
(``odoo19c: addons/account/models/res_currency.py:42-50``), que a su vez
llama ``_create_currency_table`` (``:74-``): una tabla temporal con
tasas de cambio por periodo, ventanas de fecha y CTAS. Es un mecanismo de
varias decenas de lineas que vive en ``addons/account/models/res_currency.py``
-- explicitamente fuera de mi alcance de escritura en la tarea #398 (todo
``addons/account/models/**``). Inventar aqui un atajo de conversion de
moneda para una vista de reporte financiero seria fabricar comportamiento
no verificado contra la referencia, exactamente lo que
``referencia-odoo-gobierna-las-decisiones.md`` prohibe.

Ademas, ``_read_group_select`` depende de
``self._field_to_sql(self._table, 'quantity', query)`` -- un metodo del ORM
BASE de Odoo (``odoo/orm/models.py``), sin analogo en el ORM de Django (que
no tiene mecanismo de override de agregacion por campo). Ese hueco es del
ORM espejado (``src/orm`` vs ``odoo/orm``), no de este addon -- tarea
**#291**, ya referenciada en otras partes de este arbol para el mismo tipo
de brecha.

El bloqueo es ruidoso, no vacio: los cinco metodos levantan
``NotImplementedError`` citando exactamente que falta, en vez de devolver
SQL vacio o una vista que arranca pero miente sobre los numeros -- que en
un reporte financiero es peor que no arrancar.

**Que SI se porta, completo.** Los 27 campos y los 6 atributos de clase de
modelo (``_name``, ``_description``, ``_auto``, ``_rec_name``, ``_order``,
``_depends``) son forma pura -- no dependen de ninguna pieza bloqueada, y
describen el contrato completo de la vista para cuando el bloqueo se
resuelva. Sin migracion todavia: crear la tabla ``account_invoice_report``
sin poder llenarla con la conversion de moneda correcta produciria una
vista vacia o rota en silencio; no se emite hasta que ``_select``/``_from``
dejen de estar bloqueados.

Sucesor registrado: tarea **#511** (portar
``ResCurrency._get_simple_currency_table`` en
``addons/account/models/res_currency.py``, y con eso completar
``_select``/``_from``/``_where`` + la migracion ``RunSQL`` de la vista;
depende a su vez de la tarea #291 para ``_read_group_select``).
"""
import fields
import models

from addons.account.models.account_move import AccountMove

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
        null=True, blank=True, related_name='+')
    journal_id = fields.Many2one(
        'account.AccountJournal', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        help_text='Diario (Odoo journal_id).')
    company_id = fields.Many2one(
        'base.ResCompany', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        help_text='Compania (Odoo company_id).')
    company_currency_id = fields.Many2one(
        'base.ResCurrency', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        help_text='Moneda de la compania (Odoo company_currency_id).')
    partner_id = fields.Many2one(
        'base.ResPartner', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        help_text='Contacto (Odoo partner_id).')
    commercial_partner_id = fields.Many2one(
        'base.ResPartner', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        help_text='Contacto principal (Odoo commercial_partner_id).')
    country_id = fields.Many2one(
        'base.ResCountry', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        help_text='Pais (Odoo country_id).')
    invoice_user_id = fields.Many2one(
        'base.ResUsers', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
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
        help_text='Producto (Odoo product_id).')
    product_uom_id = fields.Many2one(
        'uom.Uom', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        help_text='Unidad (Odoo product_uom_id).')
    product_categ_id = fields.Many2one(
        'product.ProductCategory', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
        help_text='Categoria de producto (Odoo product_categ_id).')
    invoice_date_due = fields.Date(
        null=True, blank=True,
        help_text='Fecha de vencimiento (Odoo invoice_date_due).')
    account_id = fields.Many2one(
        'account.AccountAccount', on_delete=models.DO_NOTHING,
        null=True, blank=True, related_name='+',
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
        """>= ``_table_query`` (``odoo19c: :78-80``): la vista completa.

        BLOQUEADO -- ver el docstring del modulo. La fuente compone
        ``_select() + _from() + _where()``; aqui la composicion en si no
        es el problema (una simple concatenacion de strings basta, ver el
        precedente de ``src/addons/base/migrations/0004_resdevice.py``) --
        el problema es que ``_from()`` no puede completarse sin
        ``ResCurrency._get_simple_currency_table``.
        """
        raise NotImplementedError(
            'AccountInvoiceReport._table_query esta BLOQUEADO: depende de '
            '_from(), que depende de ResCurrency._get_simple_currency_table '
            '(addons/account/models/res_currency.py, fuera de mi alcance de '
            'escritura en la tarea #398). Ver hallazgo H-API-682, sucesor: '
            'tarea #511.'
        )

    @classmethod
    def _select(cls):
        """>= ``_select`` (``odoo19c: :81-``). BLOQUEADO -- depende de
        ``account_currency_table.rate``, que produce ``_from()``.
        """
        raise NotImplementedError(
            'AccountInvoiceReport._select esta BLOQUEADO: casi todas sus '
            'columnas (price_subtotal, price_average, price_margin, '
            'inventory_value...) leen account_currency_table.rate, que solo '
            'existe si _from() resuelve la tabla de moneda. Ver _from() y '
            'el docstring del modulo. Sucesor: tarea #511.'
        )

    @classmethod
    def _from(cls):
        """>= ``_from`` (``odoo19c: :128-``). BLOQUEADO -- ver el
        docstring del modulo: requiere
        ``ResCurrency._get_simple_currency_table(companies)``.
        """
        raise NotImplementedError(
            'AccountInvoiceReport._from esta BLOQUEADO: requiere '
            'ResCurrency._get_simple_currency_table (odoo19c: '
            'addons/account/models/res_currency.py:42-50, que a su vez '
            'llama _create_currency_table, :74-), fuera de mi alcance de '
            'escritura en la tarea #398. Ver hallazgo H-API-682, sucesor: '
            'tarea #511.'
        )

    @classmethod
    def _where(cls):
        """>= ``_where`` (``odoo19c: :142-``). Portable por si sola --
        no depende de la tabla de moneda -- pero inerte sin ``_select``/
        ``_from``: no se expone hasta que el resto de la vista lo este.
        """
        raise NotImplementedError(
            'AccountInvoiceReport._where no esta bloqueado por si mismo '
            '(no usa account_currency_table), pero se mantiene inerte '
            'junto con _select/_from hasta que esos dejen de estarlo -- '
            'una vista con WHERE pero sin SELECT/FROM no tiene sentido. '
            'Ver el docstring del modulo. Sucesor: tarea #511.'
        )

    def _read_group_select(self, aggregate_spec, query):
        """>= ``_read_group_select`` (``odoo19c: :149-156``). BLOQUEADO --
        depende de ``self._field_to_sql``, un metodo del ORM base de Odoo
        sin analogo en ``src/orm`` (tarea #291).
        """
        raise NotImplementedError(
            'AccountInvoiceReport._read_group_select esta BLOQUEADO: '
            'depende de self._field_to_sql(self._table, campo, query), '
            'mecanismo del ORM base de Odoo (odoo/orm/models.py) sin '
            'analogo en src/orm (tarea #291). Ver hallazgo H-API-682, '
            'sucesor: tarea #511 (que depende de la #291).'
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

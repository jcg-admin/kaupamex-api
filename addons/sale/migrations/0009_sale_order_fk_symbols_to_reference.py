"""Los diez ``Many2one`` de ``sale.order`` recuperan el símbolo de la fuente.

``0008`` los declaró sin el sufijo ``_id`` que la referencia usa
(``partner_invoice_id``, ``pricelist_id``, ``user_id``…), que es la **forma A**
de ADR-029: símbolo divergente, columna fiel. ADR-029 fija la **forma C** —
símbolo verbatim de la fuente **y** columna verbatim, vía ``db_column``.

El renombre es de **símbolo de Python**, no de columna: ``0008`` ya había
creado las columnas con el nombre correcto (Django le añade ``_id`` al nombre
del campo), así que ``RenameField`` seguido de ``AlterField`` con
``db_column`` deja la tabla exactamente igual. Se declara igual porque el
estado de las migraciones tiene que reflejar el modelo; sin él,
``makemigrations --check`` queda en rojo permanente.
"""
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


_RENOMBRES = [
    'pending_email_template', 'journal', 'partner_invoice', 'partner_shipping',
    'fiscal_position', 'payment_term', 'preferred_payment_method_line',
    'pricelist', 'currency', 'user',
]


class Migration(migrations.Migration):

    dependencies = [
        ('sale', '0008_port_sale_order_header_and_fields'),
        ('account', '0021_accountmove_posted_before'),
        ('base', '0065_rescompany_account_price_include_and_more'),
        ('mail', '0001_initial'),
        ('product', '0012_port_sale_extension_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        *(migrations.RenameField(
            model_name='saleorder', old_name=viejo, new_name=f'{viejo}_id',
        ) for viejo in _RENOMBRES),
        migrations.AlterField(
            model_name='saleorder', name='pending_email_template_id',
            field=models.ForeignKey(
                blank=True, db_column='pending_email_template_id', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to='mail.mailtemplate',
                verbose_name='Plantilla del correo pendiente',
                help_text='Odoo pending_email_template_id ("Pending Email '
                          'Template"). La plantilla del correo que queda por '
                          'enviar de forma asíncrona.',
            ),
        ),
        migrations.AlterField(
            model_name='saleorder', name='journal_id',
            field=models.ForeignKey(
                blank=True, db_column='journal_id', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to='account.accountjournal',
                verbose_name='Diario de facturación',
                help_text='Odoo journal_id ("Invoicing Journal"). Si se fija, '
                          'el pedido factura en este diario; si no, se usa el '
                          'diario de ventas de menor secuencia. Acotado por '
                          'SALE_JOURNAL_DOMAIN.',
            ),
        ),
        migrations.AlterField(
            model_name='saleorder', name='partner_invoice_id',
            field=models.ForeignKey(
                blank=True, db_column='partner_invoice_id', db_index=True,
                null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to='base.respartner',
                verbose_name='Dirección de facturación',
                help_text='Odoo partner_invoice_id ("Invoice Address"). '
                          'index="btree_not_null" en la fuente: aquí el índice '
                          'lo pone Django con la FK; el tramo parcial se '
                          'declara en Meta.indexes cuando el volumen lo '
                          'justifique.',
            ),
        ),
        migrations.AlterField(
            model_name='saleorder', name='partner_shipping_id',
            field=models.ForeignKey(
                blank=True, db_column='partner_shipping_id', db_index=True,
                null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to='base.respartner',
                verbose_name='Dirección de entrega',
                help_text='Odoo partner_shipping_id ("Delivery Address").',
            ),
        ),
        migrations.AlterField(
            model_name='saleorder', name='fiscal_position_id',
            field=models.ForeignKey(
                blank=True, db_column='fiscal_position_id', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to='account.accountfiscalposition',
                verbose_name='Posición fiscal',
                help_text='Odoo fiscal_position_id ("Fiscal Position"). Adapta '
                          'impuestos y cuentas para un cliente o pedido '
                          'concreto; su valor por omisión sale del cliente.',
            ),
        ),
        migrations.AlterField(
            model_name='saleorder', name='payment_term_id',
            field=models.ForeignKey(
                blank=True, db_column='payment_term_id', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to='account.accountpaymentterm',
                verbose_name='Condiciones de pago',
                help_text='Odoo payment_term_id ("Payment Terms"). Acotado por '
                          'PAYMENT_TERM_DOMAIN: los de la empresa del pedido o '
                          'los compartidos (company_id vacío).',
            ),
        ),
        migrations.AlterField(
            model_name='saleorder', name='preferred_payment_method_line_id',
            field=models.ForeignKey(
                blank=True, db_column='preferred_payment_method_line_id',
                null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to='account.accountpaymentmethodline',
                verbose_name='Método de pago',
                help_text='Odoo preferred_payment_method_line_id ("Payment '
                          'Method"). Acotado por '
                          'PREFERRED_PAYMENT_METHOD_DOMAIN: entrante y de la '
                          'empresa del pedido.',
            ),
        ),
        migrations.AlterField(
            model_name='saleorder', name='pricelist_id',
            field=models.ForeignKey(
                blank=True, db_column='pricelist_id', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to='product.productpricelist',
                verbose_name='Tarifa',
                help_text='Odoo pricelist_id ("Pricelist"). Cambiarla sólo '
                          'afecta a las líneas que se añadan después. Acotada '
                          'por PRICELIST_DOMAIN.',
            ),
        ),
        migrations.AlterField(
            model_name='saleorder', name='currency_id',
            field=models.ForeignKey(
                blank=True, db_column='currency_id', null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+', to='base.rescurrency',
                verbose_name='Divisa',
                help_text='Odoo currency_id (compute, store=True, precompute, '
                          "ondelete='restrict'). Sale de la tarifa, o de la "
                          'empresa si el pedido no tiene tarifa. PROTECT ≙ '
                          'restrict.',
            ),
        ),
        migrations.AlterField(
            model_name='saleorder', name='user_id',
            field=models.ForeignKey(
                blank=True, db_column='user_id', db_index=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sale_orders_as_salesperson',
                to=settings.AUTH_USER_MODEL, verbose_name='Vendedor',
                help_text='Odoo user_id ("Salesperson"). NO es el cliente '
                          '—ese es ``partner``—: es quien atiende la venta. '
                          'Acotado por SALESPERSON_GROUP: usuario interno del '
                          'grupo de ventas de la empresa del pedido.',
            ),
        ),
    ]

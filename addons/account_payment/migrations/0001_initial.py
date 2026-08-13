"""Crea los 4 modelos RELATED de ``models/links.py`` — DEC-SALE-01.

Ninguno agrega columnas a ``account``/``payment`` (fuera del alcance de
este agente); cada uno es una tabla propia de ``account_payment`` con
FK/OneToOne hacia los modelos que extiende. Ver ``models/links.py`` para la
correspondencia con los campos de la referencia.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('account', '0017_accountmoveline_vehicle'),
        ('payment', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountPaymentTransaction',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID',
                    ),
                ),
                (
                    'payment',
                    models.OneToOneField(
                        help_text='El account.payment dueño de este enlace.',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='payment_transaction_link',
                        to='account.accountpayment',
                    ),
                ),
                (
                    'transaction',
                    models.ForeignKey(
                        blank=True, null=True,
                        help_text='Transacción de pago (Odoo payment_transaction_id).',
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='account_payment_links',
                        to='payment.payment',
                    ),
                ),
                (
                    'token',
                    models.ForeignKey(
                        blank=True, null=True,
                        help_text='Tarjeta guardada usada (Odoo payment_token_id).',
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='account_payment_links',
                        to='payment.savedcard',
                    ),
                ),
                (
                    'source_payment',
                    models.ForeignKey(
                        blank=True, null=True,
                        help_text='Pago original del que ESTE pago es reembolso '
                                  '(Odoo source_payment_id — related a través de la '
                                  'transacción en la referencia; aquí, FK directa '
                                  'por simplicidad).',
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='refund_links',
                        to='account.accountpayment',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Enlace pago↔transacción',
                'verbose_name_plural': 'Enlaces pago↔transacción',
                'db_table': 'account_payment_transaction_link',
            },
        ),
        migrations.CreateModel(
            name='AccountMoveTransactionLink',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID',
                    ),
                ),
                (
                    'move',
                    models.ForeignKey(
                        help_text='Factura/asiento (Odoo invoice_ids, lado inverso).',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='transaction_links',
                        to='account.accountmove',
                    ),
                ),
                (
                    'transaction',
                    models.ForeignKey(
                        help_text='Transacción de pago (Odoo transaction_ids).',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='invoice_links',
                        to='payment.payment',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Enlace factura↔transacción',
                'verbose_name_plural': 'Enlaces factura↔transacción',
                'db_table': 'account_move_transaction_link',
            },
        ),
        migrations.CreateModel(
            name='AccountPaymentMethodLineProvider',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID',
                    ),
                ),
                (
                    'method_line',
                    models.OneToOneField(
                        help_text='Línea de método de pago del diario.',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='provider_link',
                        to='account.accountpaymentmethodline',
                    ),
                ),
                (
                    'provider',
                    models.ForeignKey(
                        blank=True, null=True,
                        help_text='Pasarela que procesa esta línea (Odoo '
                                  'payment_provider_id).',
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='method_lines',
                        to='payment.paymentgateway',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Enlace línea de método↔pasarela',
                'verbose_name_plural': 'Enlaces línea de método↔pasarela',
                'db_table': 'account_payment_method_line_provider',
            },
        ),
        migrations.CreateModel(
            name='PaymentGatewayJournal',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID',
                    ),
                ),
                (
                    'gateway',
                    models.OneToOneField(
                        help_text='La pasarela dueña de este enlace.',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='journal_link',
                        to='payment.paymentgateway',
                    ),
                ),
                (
                    'journal',
                    models.ForeignKey(
                        blank=True, null=True,
                        help_text='Diario donde se postean los pagos exitosos de '
                                  'la pasarela.',
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='payment_gateways',
                        to='account.accountjournal',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Enlace pasarela↔diario',
                'verbose_name_plural': 'Enlaces pasarela↔diario',
                'db_table': 'payment_gateway_journal_link',
            },
        ),
        migrations.AddConstraint(
            model_name='accountmovetransactionlink',
            constraint=models.UniqueConstraint(
                fields=('move', 'transaction'),
                name='unique_move_transaction_link',
            ),
        ),
    ]

"""Tablas satélite de ``account_check_printing`` — ≙ los 6 + 4 + 3 campos
que la referencia agrega a ``res.company``/``account.journal``/
``account.payment`` (RELATED OneToOne, DEC-SALE-01 — ver los docstrings de
``models/res_company.py``, ``models/account_journal.py`` y
``models/account_payment.py``).

Escrita a mano (no generada por ``makemigrations``): este addon no está en
``INSTALLED_APPS`` en este pase (fuera de alcance — ver ``__init__.py`` del
paquete), así que Django no puede descubrir la app para generarla. Los
campos coinciden 1:1 con los tres modelos de ``models/``.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('account', '0017_accountmoveline_vehicle'),
        ('base', '0019_respartnerbank_include_reference_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CheckPrintingCompanySettings',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'layout',
                    models.CharField(
                        choices=[('disabled', 'Ninguno')], default='disabled',
                        help_text='Formato del papel donde se imprimen los '
                        'cheques. "Ninguno" desactiva la impresión (Odoo '
                        'account_check_printing_layout).',
                        max_length=64, verbose_name='Diseño de cheque',
                    ),
                ),
                (
                    'date_label',
                    models.BooleanField(
                        default=True,
                        help_text='Imprime la etiqueta de fecha según CPA. '
                        'Desactivar si el talonario preimpreso ya la trae '
                        '(Odoo account_check_printing_date_label).',
                        verbose_name='Imprimir etiqueta de fecha',
                    ),
                ),
                (
                    'multi_stub',
                    models.BooleanField(
                        default=False,
                        help_text='Permite que el detalle del talón use '
                        'varias páginas si no cabe en una sola (Odoo '
                        'account_check_printing_multi_stub).',
                        verbose_name='Talón de cheque en varias páginas',
                    ),
                ),
                (
                    'margin_top',
                    models.FloatField(
                        default=0.25,
                        help_text='Ajusta el margen del cheque generado, '
                        'en pulgadas (Odoo account_check_printing_margin_top).',
                        verbose_name='Margen superior',
                    ),
                ),
                (
                    'margin_left',
                    models.FloatField(
                        default=0.25,
                        help_text='Odoo account_check_printing_margin_left.',
                        verbose_name='Margen izquierdo',
                    ),
                ),
                (
                    'margin_right',
                    models.FloatField(
                        default=0.25,
                        help_text='Odoo account_check_printing_margin_right.',
                        verbose_name='Margen derecho',
                    ),
                ),
                (
                    'company',
                    models.OneToOneField(
                        help_text='Empresa (Odoo _inherit res.company).',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='check_printing_settings', to='base.rescompany',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Ajustes de impresión de cheques (empresa)',
                'verbose_name_plural': 'Ajustes de impresión de cheques (empresas)',
                'db_table': 'account_check_printing_company_settings',
            },
        ),
        migrations.CreateModel(
            name='CheckPrintingJournalSettings',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'manual_sequencing',
                    models.BooleanField(
                        default=False,
                        help_text='Marcar si los cheques preimpresos no '
                        'vienen numerados (Odoo check_manual_sequencing).',
                        verbose_name='Numeración manual',
                    ),
                ),
                (
                    'layout',
                    models.CharField(
                        blank=True, default='',
                        help_text='Vacío = usa el de la empresa (Odoo '
                        'bank_check_printing_layout).',
                        max_length=64, verbose_name='Diseño de cheque',
                    ),
                ),
                (
                    'journal',
                    models.OneToOneField(
                        help_text='Diario (Odoo _inherit account.journal).',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='check_printing_settings',
                        to='account.accountjournal',
                    ),
                ),
                (
                    'sequence',
                    models.ForeignKey(
                        blank=True,
                        help_text='Secuencia de numeración de cheques de '
                        'este diario (Odoo check_sequence_id).',
                        null=True, on_delete=django.db.models.deletion.SET_NULL,
                        related_name='+', to='base.irsequence',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Ajustes de impresión de cheques (diario)',
                'verbose_name_plural': 'Ajustes de impresión de cheques (diarios)',
                'db_table': 'account_check_printing_journal_settings',
            },
        ),
        migrations.CreateModel(
            name='CheckPrintingPaymentInfo',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'check_number',
                    models.CharField(
                        blank=True, db_index=True, default='',
                        help_text='Número de cheque impreso o asignado a '
                        'este pago (Odoo check_number).',
                        max_length=32,
                    ),
                ),
                (
                    'is_sent',
                    models.BooleanField(
                        default=False,
                        help_text='Marca que el cheque ya se imprimió — '
                        'evita reimprimirlo (Odoo is_sent, campo genérico '
                        'de account.payment que este núcleo tampoco '
                        'declara; se porta aquí porque sólo esta '
                        'funcionalidad lo necesita).',
                        verbose_name='Cheque impreso',
                    ),
                ),
                (
                    'payment',
                    models.OneToOneField(
                        help_text='Pago (Odoo _inherit account.payment).',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='check_printing_info', to='account.accountpayment',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Datos de impresión de cheque',
                'verbose_name_plural': 'Datos de impresión de cheques',
                'db_table': 'account_check_printing_payment_info',
            },
        ),
    ]

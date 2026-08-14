# Migración inicial de ``account_tax_python`` — tabla satélite
# ``AccountTaxFormula`` (OneToOne a ``account.AccountTax``). Ver el
# docstring de ``models/account_tax.py`` para por qué es tabla satélite y
# no un campo agregado a ``account_tax`` (esa vía exige una migración en
# ``account/migrations/``, fuera de este alcance).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('account', '0016_accounttax_l10n_mx_factor_type_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountTaxFormula',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'formula',
                    models.TextField(
                        default='price_unit * 0.10',
                        help_text=(
                            'Calcula el monto del impuesto (Odoo formula).'
                            '\n\n:param base: float, monto real sobre el '
                            'que se aplica el impuesto\n:param price_unit: '
                            'float\n:param quantity: float\n:param '
                            'product: un objeto que representa el '
                            'producto\n'
                        ),
                    ),
                ),
                (
                    'tax',
                    models.OneToOneField(
                        help_text=(
                            'Impuesto al que pertenece esta fórmula (Odoo '
                            '_inherit account.tax vía los campos formula/'
                            'formula_decoded_info). OneToOne: un impuesto '
                            'tiene a lo sumo una fórmula — mismo criterio '
                            'que account_add_gln.PartnerGln.partner.'
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='formula_record',
                        to='account.accounttax',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Fórmula de impuesto (Python)',
                'verbose_name_plural': 'Fórmulas de impuesto (Python)',
                'db_table': 'account_tax_python_formula',
            },
        ),
    ]

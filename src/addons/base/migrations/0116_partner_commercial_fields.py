# ≙ el cómputo que la fuente hace al crear un contacto por el ORM
# (odoo19c: odoo/addons/base/models/res_partner.py:515-528). Las migraciones
# 0106 y 0113 siembran base.partner_root y base.public_partner con el modelo
# histórico, que no calcula nada: en una base construida sólo por
# migraciones sus dos campos almacenados quedaban sin valor, y la regla
# account.account_invoice_rule_portal ([user.commercial_partner_id.id]) no
# se podía evaluar al cargar los datos de account.

from django.db import migrations

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0115_rescompany_purchase_fields'),
    ]

    operations = [
        ComputeStoredFields('base', 'respartner',
                            ['commercial_partner_id',
                             'commercial_company_name']),
    ]

"""``seed_l0_chart`` — carta contable L0 de Kaupamex (H-API-05).

Provisiona el mínimo contable en los libros de la **system company** (Kaupamex,
el operador L0) para que el cobro de suscripción se pueda asentar: un diario de
ventas + una cuenta por-cobrar + una cuenta de ingreso. Sin él,
``SubscriptionInvoice.post_to_ledger()`` falla-fuerte (``UserError``: falta el
diario / las cuentas).

**Idempotente** — el diario se busca por ``(company, code)`` y cada cuenta
por su código entre las cuentas de la empresa (``company_ids``), así que
correrlo N veces deja el mismo estado. Sin línea de IVA: el tratamiento
fiscal del cobro L0 es una decisión aparte (ver
:ref:`diseno-motor-facturacion-recurrente-l0`), y el asiento de suscripción es
por-cobrar (débito) contra ingreso (crédito), sin impuesto.

Vive en ``company`` (dueño del concepto L0/system) y **lee** los modelos de
``account`` — dirección de dependencia permitida (``company`` → ``account``);
``account`` nunca importa ``company`` (DEC-FW-01).
"""

import fields

from addons.base.management.unit_of_work import UnitOfWorkCommand
from addons.account.models import AccountAccount, AccountJournal
from addons.base.models import ResCompany
from orm.environments import env

# Carta contable L0 mínima (códigos alineados con el fixture ``l0_chart``).
_JOURNAL = {'code': 'VEN', 'name': 'Ventas plataforma', 'type': 'sale'}
_ACCOUNTS = [
    {
        'code': '105',
        'name': 'Clientes plataforma',
        'account_type': 'asset_receivable',
        'reconcile': True,
    },
    {
        'code': '401',
        'name': 'Ingreso por suscripciones',
        'account_type': 'income',
    },
]


class Command(UnitOfWorkCommand):
    help = (
        'Siembra (idempotente) la carta contable L0 de Kaupamex: diario de '
        'ventas + cuentas por-cobrar/ingreso de la system company.'
    )

    def handle(self, *args, **options):
        system = ResCompany.get_system()

        journal, journal_created = AccountJournal.objects.get_or_create(
            company=system,
            code=_JOURNAL['code'],
            defaults={'name': _JOURNAL['name'], 'type': _JOURNAL['type']},
        )
        self._report('Diario', journal.code, journal_created)

        for spec in _ACCOUNTS:
            # La cuenta pertenece a sus empresas por ``company_ids``, como en
            # la fuente (``designs/account-account-mc2b.md``).
            account = AccountAccount.objects.filter(
                company_ids=system, code=spec['code']).first()
            created = account is None
            if created:
                account = env()['account.account'].sudo().create({
                    **spec,
                    'company_ids': [fields.Command.set([system.pk])],
                })
            self._report('Cuenta', account.code, created)

    def _report(self, kind, code, created):
        verb = 'creado' if created else 'existía'
        self.stdout.write(f'{kind} {code}: {verb} (system company Kaupamex).')

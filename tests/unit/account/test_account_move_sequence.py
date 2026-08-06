"""RED→GREEN — ``AccountMove.post()`` asigna secuencia de ``name``.

Rebanada 4 (d) de H-API-08: gap destapado por la rebanada 2 — ``post()`` dejaba
``name='/'`` a diferencia de Odoo, que asigna una secuencia por diario/tipo/año
al publicar (``INV/2026/00001``). Se porta la mecánica mínima: ``name`` con la
forma ``{prefijo}/{código-diario}/{año}/{consecutivo}``, único por
(diario, move_type, año). Análogo a Odoo ``account.move._get_last_sequence`` /
``_set_next_sequence``.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import (
    AccountAccount,
    AccountJournal,
    AccountMove,
    AccountMoveLine,
)
from addons.base.models import ResCompany


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def setup(db, company):
    journal = AccountJournal.objects.create(
        name='Ventas', code='VEN', type='sale', company=company)
    receivable = AccountAccount.objects.create(
        code='105', name='Clientes', account_type='asset_receivable',
        company=company)
    income = AccountAccount.objects.create(
        code='401', name='Ventas', account_type='income', company=company)
    return company, journal, receivable, income


def _balanced(company, journal, receivable, income,
              move_type='out_invoice', amount=Decimal('100.00')):
    move = AccountMove.objects.create(
        move_type=move_type, date=timezone.now().date(),
        journal=journal, company=company)
    AccountMoveLine.objects.create(move=move, account=receivable, debit=amount)
    AccountMoveLine.objects.create(move=move, account=income, credit=amount)
    return move


@pytest.mark.django_db
class TestAccountMoveSequence:
    def test_first_invoice_gets_sequence(self, setup):
        move = _balanced(*setup)
        move.post()
        move.refresh_from_db()
        assert move.name == f'INV/VEN/{move.date.year}/00001'

    def test_sequence_increments_per_journal(self, setup):
        first = _balanced(*setup)
        first.post()
        second = _balanced(*setup)
        second.post()
        first.refresh_from_db()
        second.refresh_from_db()
        assert first.name.endswith('/00001')
        assert second.name.endswith('/00002')

    def test_refund_has_own_sequence(self, setup):
        invoice = _balanced(*setup)
        invoice.post()
        refund = _balanced(*setup, move_type='out_refund')
        refund.post()
        refund.refresh_from_db()
        assert refund.name == f'RINV/VEN/{refund.date.year}/00001'

    def test_existing_name_is_preserved(self, setup):
        move = _balanced(*setup)
        move.name = 'MANUAL-001'
        move.save()
        move.post()
        move.refresh_from_db()
        assert move.name == 'MANUAL-001'

    def test_post_guarda_el_nombre_partido(self, setup):
        """``name`` y sus dos mitades salen del mismo ``post()``.

        Si se desincronizan, el ``MAX`` del siguiente asiento mide otra cosa.
        """
        move = _balanced(*setup)
        move.post()
        move.refresh_from_db()
        assert move.sequence_prefix == f'INV/VEN/{move.date.year}/'
        assert move.sequence_number == 1


@pytest.mark.django_db
class TestLimiteDeCincoDigitos:
    """El punto exacto donde el orden de cadena rompía (:ref:`h-api-339`).

    ``_assign_sequence`` buscaba el último con ``order_by('-name').first()``.
    Con el relleno a cinco dígitos eso ordena bien hasta 99 999, y se rompe al
    llegar a 100 000: ``'/100000'`` es lexicográficamente **menor** que
    ``'/99999'``, así que el descendente sigue devolviendo el 99 999 y la
    secuencia propone 100 000 otra vez. Como ``name`` es único, la numeración
    de ese diario queda atascada con ``IntegrityError`` para siempre.

    No hace falta crear 100 000 asientos para ejercerlo: bastan las dos filas
    que lo disparan.
    """

    @staticmethod
    def _numerado(company, journal, name, numero):
        return AccountMove.objects.create(
            name=name,
            sequence_prefix=f'INV/{journal.code}/{timezone.now().year}/',
            sequence_number=numero,
            move_type='out_invoice', date=timezone.now().date(),
            journal=journal, company=company, state='posted',
        )

    def test_el_siguiente_de_100000_es_100001(self, setup):
        company, journal, receivable, income = setup
        anio = timezone.now().year
        self._numerado(company, journal, f'INV/VEN/{anio}/99999', 99999)
        self._numerado(company, journal, f'INV/VEN/{anio}/100000', 100000)
        siguiente = _balanced(*setup)
        assert siguiente._assign_sequence() == f'INV/VEN/{anio}/100001'

    def test_contraprueba_el_orden_de_cadena_se_equivoca(self, setup):
        """Sin esto, el test de arriba pasaría con cualquier implementación.

        Mide el instrumento **viejo** sobre las mismas filas y muestra que da
        el resultado equivocado — que es lo que demuestra que había defecto, no
        sólo que la versión actual funciona.
        """
        company, journal, receivable, income = setup
        anio = timezone.now().year
        self._numerado(company, journal, f'INV/VEN/{anio}/99999', 99999)
        self._numerado(company, journal, f'INV/VEN/{anio}/100000', 100000)
        por_cadena = (AccountMove.objects
                      .filter(name__startswith=f'INV/VEN/{anio}/')
                      .order_by('-name').first())
        por_entero = (AccountMove.objects
                      .filter(sequence_prefix=f'INV/VEN/{anio}/')
                      .order_by('-sequence_number').first())
        assert por_cadena.sequence_number == 99999    # el viejo se equivoca
        assert por_entero.sequence_number == 100000   # el nuevo acierta

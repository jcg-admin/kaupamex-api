"""El impuesto con fórmula Python — porte de ``test_formula`` de
``odoo19c: addons/account_tax_python/tests/test_taxes_computation.py``.

Todas las fórmulas pasan por el motor real de ``account``: ``compute_all``
para las de ``price_unit``/``quantity``/``base`` y las de ``product.*``, y
``_get_tax_details(product_uom=...)`` para las de ``uom.*``, porque
``compute_all`` no recibe unidad, en la fuente tampoco. Es la verificación de
que la extensión de ``_eval_tax_amount_fixed_amount`` y la de los ganchos de
campos despachan dentro de ese motor.

Referencia medida sobre
``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``.
"""

from decimal import Decimal

import pytest

from addons.account.models import AccountTax
from addons.account_tax_python.models.account_tax import AccountTaxFormula
from addons.base.models import ResCompany
from addons.uom.models.uom_uom import Uom
from exceptions import ValidationError
from tests.factories.product_factory import make_product

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


def _code_tax(company, formula, price_include=False, **kwargs):
    """Un impuesto ``amount_type='code'`` con su ``AccountTaxFormula``
    vinculada — el análogo de ``python_tax`` de la referencia.
    """
    tax = AccountTax.objects.create(
        name='Impuesto fórmula',
        company=company,
        amount_type='code',
        price_include=price_include,
        **kwargs,
    )
    AccountTaxFormula.objects.create(tax=tax, formula=formula)
    return tax


def _sobre(*taxes):
    """El QuerySet de esos impuestos — el análogo del recordset de la
    fuente (mismo helper que ``tests/unit/account/
    test_account_tax_compute_all.py``)."""
    return AccountTax.objects.filter(pk__in=[t.pk for t in taxes])


# -- vía compute_all() real: sólo price_unit/quantity/base ------------------


class TestViaComputeAllReal:
    """``odoo19c: :11-34`` — el mismo caso, tax_excluded y tax_included."""

    def test_max_de_dos_expresiones_tax_excluded(self, company):
        tax = _code_tax(
            company, 'max(quantity * price_unit * 0.21, quantity * 4.17)'
        )
        r = _sobre(tax).compute_all(Decimal('130'))
        assert r['total_excluded'] == Decimal('130.00')
        assert r['total_included'] == Decimal('157.30')
        assert r['taxes'][0]['amount'] == Decimal('27.30')

    def test_max_de_dos_expresiones_tax_included(self, company):
        tax = _code_tax(
            company,
            'max(quantity * price_unit * 0.21, quantity * 4.17)',
            price_include=True,
        )
        r = _sobre(tax).compute_all(Decimal('130'))
        assert r['total_excluded'] == Decimal('102.70')
        assert r['total_included'] == Decimal('130.00')
        assert r['taxes'][0]['amount'] == Decimal('27.30')

    def test_zero_division_da_cero(self, company):
        """``_eval_tax_amount_formula`` atrapa ``ZeroDivisionError`` y
        devuelve 0.0 — ≙ referencia (``models/account_tax.py:113-114``)."""
        tax = _code_tax(company, 'price_unit / 0')
        r = _sobre(tax).compute_all(Decimal('100'))
        assert r['taxes'][0]['amount'] == Decimal('0.00')

    def test_sin_formula_record_falla_alto_y_claro(self, company):
        """Un impuesto ``amount_type='code'`` sin ``AccountTaxFormula``
        vinculada no computa silencioso en 0 — levanta, con el impuesto
        nombrado en el mensaje."""
        tax = AccountTax.objects.create(
            name='Huérfano', company=company, amount_type='code'
        )
        with pytest.raises(ValidationError, match='Huérfano'):
            _sobre(tax).compute_all(Decimal('100'))


# -- fórmulas con product.*/uom.*, por el motor real -------------------------


def _amount(tax, price_unit, quantity=1.0, product=None):
    """El importe del impuesto que ``compute_all`` calcula."""
    result = AccountTax.objects.filter(pk=tax.pk).compute_all(
        price_unit, quantity=quantity, product=product)
    return result['taxes'][0]['amount']


class TestFormulasWithProductAndUom:
    """``odoo19c: account_tax_python/tests/test_taxes_computation.py:36-70,
    115-138``, por el motor real: ``compute_all`` lleva el producto a
    ``_get_tax_details``, que arma ``evaluation_context['product']`` con los
    campos que declara la fórmula. Hasta que ``account`` portó sus
    ``_eval_taxes_computation_*`` estos casos pasaban por un sustituto local
    del contexto."""

    def test_product_volume(self, company):
        tax = _code_tax(company, 'product.volume * quantity * 0.35')
        product = make_product(name='Volumen fórmula', volume=100.0)
        assert _amount(tax, 100.0, product=product) == pytest.approx(35.0)

    def test_product_volume_subscript_ternary(self, company):
        """``product["volume"] > 100 and 10 or 5`` — ≙ referencia :47-58."""
        tax = _code_tax(company, 'product["volume"] > 100 and 10 or 5')
        product = make_product(name='Volumen ternario', volume=105.0)
        assert _amount(tax, 100.0, product=product) == pytest.approx(10.0)

    def test_max_with_product_and_base(self, company):
        """≙ referencia :115-126: min/max anidados + rango de comparación
        encadenado sobre un campo de producto."""
        tax = _code_tax(
            company,
            "min(max(price_unit, quantity), base) * 0.10 + "
            "(5 < product['volume'] < 10 and 1.0 or 0.0)",
        )
        product = make_product(name='Volumen rango', volume=7.0)
        assert _amount(tax, 20.0, product=product) == pytest.approx(3.0)

    def test_uom_relative_factor(self, company):
        """≙ referencia :127-138.

        ``compute_all`` no recibe unidad, en la fuente tampoco: la unidad
        llega por ``_get_tax_details(product_uom=...)``, que es donde la
        fuente la toma de la base-line. Un factor relativo distinto de 1
        exige unidad de referencia (``uom_uom.py:169-170``, ≙
        ``_check_factor`` de la referencia).
        """
        tax = _code_tax(company, 'uom.relative_factor')
        reference = Uom.objects.create(name='Base', relative_factor=1.0)
        unit = Uom.objects.create(
            name='Prueba', relative_factor=42.0, relative_uom_id=reference
        )
        details = AccountTax.objects.filter(pk=tax.pk)._get_tax_details(
            100.0, quantity=1.0, product_uom=unit)
        assert details['taxes_data'][0]['tax_amount'] == pytest.approx(42.0)

    def test_context_without_product_raises_keyerror_not_assertion(
        self, company
    ):
        """
        Sin producto en el contexto, el fallo llega del ``eval``, no del guard.

        La primera versión de este test afirmaba
        ``pytest.raises(AssertionError)``
        creyendo el docstring de ``account_tax.py``, que presenta el
        ``assert accessed_fields['product'] <= …`` como la red de seguridad.
        **Ese assert está muerto**, aquí y en la referencia:
        ``accessed_fields``
        es un ``defaultdict`` con claves ``'product.product'``/``'uom.uom'``
        (``formula_utils.py:60,64``) y el guard lee ``['product']``, así que
        siempre compara el conjunto vacío — y ``set() <= cualquier_cosa`` es
        cierto. Idéntico en ``odoo19c: account_tax.py:62-63`` (escribe
        ``'product.product'``) vs ``:105-106`` (lee ``'product'``).

        El puerto es fiel; lo que era falso es la afirmación del docstring.
        Ver :ref:`h-api-365`.
        """
        tax = _code_tax(company, 'product.volume * 0.35')
        formula_record = tax.formula_record
        with pytest.raises(KeyError, match='volume'):
            formula_record._eval_tax_amount_formula(
                100.0, {'price_unit': 100.0, 'quantity': 1.0}
            )


# -- formula_decoded_info / clean() -----------------------------------------


class TestFormulaDecodedInfoANDValidation:

    def test_formula_decoded_info_none_si_no_es_code(self, company):
        tax = AccountTax.objects.create(
            name='Percent',
            company=company,
            amount_type='percent',
            amount=Decimal('16'),
        )
        formula_record = AccountTaxFormula.objects.create(
            tax=tax, formula='product.field_que_no_existe'
        )
        # amount_type != 'code': la fórmula queda dormida, sin validar.
        assert formula_record.formula_decoded_info is None

    def test_clean_valida_solo_cuando_amount_type_es_code(self, company):
        tax = AccountTax.objects.create(
            name='Percent con basura',
            company=company,
            amount_type='percent',
            amount=Decimal('16'),
        )
        formula_record = AccountTaxFormula(
            tax=tax, formula='esto no es una fórmula válida (('
        )
        formula_record.clean()  # no levanta: dormida.

        tax.amount_type = 'code'
        tax.save()
        with pytest.raises(ValidationError):
            formula_record.clean()

    def test_formula_decoded_info_lista_campos_accedidos(self, company):
        tax = _code_tax(company, 'product.volume + uom.relative_factor')
        info = tax.formula_record.formula_decoded_info
        assert info['product_fields'] == ['volume']
        assert info['product_uom_fields'] == ['relative_factor']
        assert (
            info['py_formula'] == "product['volume'] + uom['relative_factor']"
        )


# -- hooks de AccountTaxQuerySet (monkeypatch de account_tax_extensions.py) --


class TestHooksOfQuerySet:

    def test_prepare_product_fields_agrega_solo_de_impuestos_code(
        self, company
    ):
        code_tax = _code_tax(company, 'product.volume * 0.1')
        percent_tax = AccountTax.objects.create(
            name='IVA',
            company=company,
            amount_type='percent',
            amount=Decimal('16'),
        )
        campos = _sobre(
            code_tax, percent_tax
        )._eval_taxes_computation_prepare_product_fields()
        assert campos == {'volume'}

    def test_prepare_product_uom_fields(self, company):
        tax = _code_tax(company, 'uom.relative_factor * 2')
        campos = _sobre(
            tax
        )._eval_taxes_computation_prepare_product_uom_fields()
        assert campos == {'relative_factor'}


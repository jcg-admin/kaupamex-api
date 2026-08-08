"""El motor de cálculo de impuestos — ``compute_all`` (H-API-340, tarea #141).

Los casos no son inventados: **son los ejemplos de la referencia**, tomados de
su propio ``help`` y de los comentarios que justifican cada pasada. Eso es lo
que hace a estos tests una verificación del porte y no de mi lectura de él:

- ``odoo19c: account_tax.py:88-95`` — el ``help`` de ``amount_type``, con los
  cuatro ejemplos numéricos de ``percent`` y ``division``.
- ``odoo19c: account_tax.py:1254-1260`` — el contraejemplo del fijo con
  ``include_base_amount`` delante de un porcentual incluido.
- ``odoo19c: account_tax.py:1055-1062`` — la cascada de dos porcentuales donde
  el primero afecta la base del segundo.

Referencia medida sobre ``odoo-tools@622ddc2a``.
"""
from decimal import Decimal

import pytest

from addons.account.models import AccountTax
from addons.base.models import ResCompany

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


def _tax(company, nombre, amount, **kwargs):
    return AccountTax.objects.create(
        name=nombre, amount=Decimal(str(amount)), company=company, **kwargs)


def _sobre(*taxes):
    """El QuerySet de esos impuestos — el análogo del recordset de la fuente."""
    return AccountTax.objects.filter(pk__in=[t.pk for t in taxes])


class TestLosCuatroEjemplosDelHelp:
    """``odoo19c: account_tax.py:88-95``, uno por línea del ``help``."""

    def test_percent_no_incluido_100_mas_10_es_110(self, company):
        iva = _tax(company, 'IVA 10', 10, amount_type='percent')
        r = _sobre(iva).compute_all(Decimal('100'))
        assert r['total_excluded'] == Decimal('100.00')
        assert r['total_included'] == Decimal('110.00')

    def test_percent_incluido_110_entre_1_10_es_100(self, company):
        iva = _tax(company, 'IVA 10 incl', 10, amount_type='percent',
                   price_include=True)
        r = _sobre(iva).compute_all(Decimal('110'))
        assert r['total_excluded'] == Decimal('100.00')
        assert r['total_included'] == Decimal('110.00')

    def test_division_no_incluido_180_entre_0_90_es_200(self, company):
        """``e.g 180 / (1 - 10%) = 200 (not price included)``."""
        t = _tax(company, 'Div 10', 10, amount_type='division')
        r = _sobre(t).compute_all(Decimal('180'))
        assert r['total_excluded'] == Decimal('180.00')
        assert r['total_included'] == Decimal('200.00')

    def test_division_incluido_200_por_0_90_es_180(self, company):
        """``e.g 200 * (1 - 10%) = 180 (price included)``."""
        t = _tax(company, 'Div 10 incl', 10, amount_type='division',
                 price_include=True)
        r = _sobre(t).compute_all(Decimal('200'))
        assert r['total_excluded'] == Decimal('180.00')
        assert r['total_included'] == Decimal('200.00')


class TestLote:
    """Por qué el motor agrupa en vez de recorrer impuesto a impuesto."""

    def test_dos_porcentuales_incluidos_se_extraen_juntos(self, company):
        """116 con 10 % y 6 % incluidos da base 100, no 99,45.

        Ésta es la razón de ser de ``_batch_for_taxes_computation``: extraer
        uno tras otro (116/1.1/1.06) daría 99,49. La referencia divide entre
        ``1 + Σ tasas del lote``.
        """
        a = _tax(company, 'A 10', 10, amount_type='percent',
                 price_include=True, sequence=1)
        b = _tax(company, 'B 6', 6, amount_type='percent',
                 price_include=True, sequence=2)
        r = _sobre(a, b).compute_all(Decimal('116'))
        assert r['total_excluded'] == Decimal('100.00')
        assert r['total_included'] == Decimal('116.00')

    def test_contraprueba_uno_tras_otro_daria_otra_cosa(self, company):
        """Sin esto, el test de arriba pasaría con la implementación ingenua.

        Se calcula a mano lo que daría extraer en cascada y se comprueba que
        **no** es lo que el motor devuelve — que es lo que demuestra que el
        lote hace algo, no que el número coincida por suerte.
        """
        a = _tax(company, 'A 10', 10, amount_type='percent',
                 price_include=True, sequence=1)
        b = _tax(company, 'B 6', 6, amount_type='percent',
                 price_include=True, sequence=2)
        ingenuo = (Decimal('116') / Decimal('1.10') / Decimal('1.06'))
        r = _sobre(a, b).compute_all(Decimal('116'))
        assert ingenuo.quantize(Decimal('0.01')) == Decimal('99.49')
        assert r['total_excluded'] != ingenuo.quantize(Decimal('0.01'))


class TestCascadaDeBase:
    """``include_base_amount`` — un impuesto que engorda la base del siguiente."""

    def test_el_primero_afecta_la_base_del_segundo(self, company):
        """``odoo19c: :1055-1062``: 100 → t1 10 % → base de t2 es 110.

        t1 = 10, t2 = 11 (10 % de 110), total 121.
        """
        t1 = _tax(company, 'T1 10', 10, amount_type='percent',
                  sequence=1, include_base_amount=True)
        t2 = _tax(company, 'T2 10', 10, amount_type='percent', sequence=2)
        r = _sobre(t1, t2).compute_all(Decimal('100'))
        assert r['total_excluded'] == Decimal('100.00')
        assert r['total_included'] == Decimal('121.00')
        por_nombre = {d['name']: d['amount'] for d in r['taxes']}
        assert por_nombre['T1 10'] == Decimal('10.00')
        assert por_nombre['T2 10'] == Decimal('11.00')

    def test_sin_include_base_amount_ambos_van_sobre_la_misma_base(self, company):
        """La contraparte: sin la marca, 10 % + 10 % sobre 100 son 20, no 21."""
        t1 = _tax(company, 'T1 10', 10, amount_type='percent', sequence=1)
        t2 = _tax(company, 'T2 10', 10, amount_type='percent', sequence=2)
        r = _sobre(t1, t2).compute_all(Decimal('100'))
        assert r['total_included'] == Decimal('120.00')

    def test_is_base_affected_false_rechaza_la_cascada(self, company):
        """``include_base_amount`` propone; ``is_base_affected`` acepta.

        Son dos marcas y hacen falta las dos: si el segundo declara que su
        base no se deja afectar, la cascada no ocurre aunque el primero la
        ofrezca.
        """
        t1 = _tax(company, 'T1 10', 10, amount_type='percent',
                  sequence=1, include_base_amount=True)
        t2 = _tax(company, 'T2 10', 10, amount_type='percent',
                  sequence=2, is_base_affected=False)
        r = _sobre(t1, t2).compute_all(Decimal('100'))
        assert r['total_included'] == Decimal('120.00')


class TestFijoAntesDeIncluido:
    """El contraejemplo que obliga a que los fijos vayan en la PRIMERA pasada.

    ``odoo19c: :1254-1260``: t1 fijo de 1 con ``include_base_amount``, t2 al
    21 % incluido. El importe de t1 debe conocerse antes de extraer t2.
    """

    def test_el_fijo_se_evalua_antes_que_el_incluido(self, company):
        """El fijo entra en la base del incluido, y luego sale por encima.

        ``odoo19c: :1013-1017`` describe los dos movimientos, y hay que
        distinguirlos porque el resultado no es intuitivo:

        1. t1 se evalúa PRIMERO (pasada 1) porque su importe engorda la base
           sobre la que t2 se extrae: 121 + 1 = 122, de donde el 21 %
           incluido son 122 × 0,21/1,21 = 21,17.
        2. Pero t1 **no** es price-included, así que su propia base se calcula
           quitando antes el importe de t2: 121 − 21,17 = 99,83, y su 1 se
           suma **encima** del precio dado.

        Por eso el total es 122, no 121: el precio incluía el 21 %, no la
        cuota fija.
        """
        t1 = _tax(company, 'Fijo 1', 1, amount_type='fixed',
                  sequence=1, include_base_amount=True)
        t2 = _tax(company, 'IVA 21 incl', 21, amount_type='percent',
                  sequence=2, price_include=True)
        r = _sobre(t1, t2).compute_all(Decimal('121'))
        por_nombre = {d['name']: d['amount'] for d in r['taxes']}
        assert por_nombre['Fijo 1'] == Decimal('1.00')
        assert por_nombre['IVA 21 incl'] == Decimal('21.17')
        assert r['total_excluded'] == Decimal('99.83')
        assert r['total_included'] == Decimal('122.00')

    def test_sin_include_base_amount_el_fijo_no_engorda_la_base(self, company):
        """La contraprueba del anterior: sin la marca, t2 se extrae de 121.

        Lo que cambia es el **reparto**, no el total: 121 × 0,21/1,21 = 21,00
        (no 21,17) y la base sube a 100,00 (no 99,83). El total sigue siendo
        122 porque la cuota fija va encima del precio en ambos casos — es la
        base la que absorbe la diferencia.

        Vale la pena fijarlo: un test que sólo mirara el total daría verde con
        y sin ``include_base_amount``, y no diría nada sobre la cascada.
        """
        t1 = _tax(company, 'Fijo 1', 1, amount_type='fixed', sequence=1)
        t2 = _tax(company, 'IVA 21 incl', 21, amount_type='percent',
                  sequence=2, price_include=True)
        r = _sobre(t1, t2).compute_all(Decimal('121'))
        por_nombre = {d['name']: d['amount'] for d in r['taxes']}
        assert por_nombre['IVA 21 incl'] == Decimal('21.00')
        assert r['total_excluded'] == Decimal('100.00')
        assert r['total_included'] == Decimal('122.00')

    def test_el_fijo_multiplica_por_cantidad_no_por_precio(self, company):
        """``sign * quantity * amount`` (``odoo19c: :1096``) — no por la base."""
        t = _tax(company, 'Cuota 5', 5, amount_type='fixed')
        r = _sobre(t).compute_all(Decimal('100'), quantity=3)
        assert r['taxes'][0]['amount'] == Decimal('15.00')

    def test_precio_negativo_invierte_el_signo_del_fijo(self, company):
        """Una nota de crédito lleva el fijo con signo opuesto (``:1095``)."""
        t = _tax(company, 'Cuota 5', 5, amount_type='fixed')
        r = _sobre(t).compute_all(Decimal('-100'))
        assert r['taxes'][0]['amount'] == Decimal('-5.00')


class TestGrupo:
    def test_un_grupo_se_sustituye_por_sus_hijos(self, company):
        """``amount_type='group'`` no calcula: aporta sus hijos (``:897``)."""
        hijo_a = _tax(company, 'A 10', 10, amount_type='percent', sequence=1)
        hijo_b = _tax(company, 'B 6', 6, amount_type='percent', sequence=2)
        grupo = _tax(company, 'Grupo', 0, amount_type='group', sequence=5)
        grupo.children.set([hijo_a, hijo_b])

        r = _sobre(grupo).compute_all(Decimal('100'))
        assert r['total_included'] == Decimal('116.00')
        assert {d['name'] for d in r['taxes']} == {'A 10', 'B 6'}


class TestBordes:
    def test_sin_impuestos_el_total_es_la_base(self, company):
        vacio = AccountTax.objects.none()
        r = vacio.compute_all(Decimal('100'))
        assert r['total_excluded'] == Decimal('100.00')
        assert r['total_included'] == Decimal('100.00')

    def test_handle_price_include_false_ignora_el_incluido(self, company):
        """``handle_price_include=False`` trata el precio como base pura.

        Es el ``special_mode='total_excluded'`` de la referencia (``:5015``):
        el 10 % incluido pasa a sumarse encima en vez de extraerse.
        """
        t = _tax(company, 'IVA 10 incl', 10, amount_type='percent',
                 price_include=True)
        r = _sobre(t).compute_all(Decimal('100'), handle_price_include=False)
        assert r['total_excluded'] == Decimal('100.00')
        assert r['total_included'] == Decimal('110.00')

    def test_la_cantidad_multiplica_la_base(self, company):
        t = _tax(company, 'IVA 16', 16, amount_type='percent')
        r = _sobre(t).compute_all(Decimal('50'), quantity=4)
        assert r['total_excluded'] == Decimal('200.00')
        assert r['total_included'] == Decimal('232.00')

    def test_el_resultado_es_decimal_no_float(self, company):
        """La divergencia declarada del porte, fijada como contrato.

        Si alguien reintroduce ``float`` en el motor, este test lo dice antes
        de que el descuadre aparezca sumando líneas de una factura.
        """
        t = _tax(company, 'IVA 16', 16, amount_type='percent')
        r = _sobre(t).compute_all(Decimal('100'))
        assert isinstance(r['total_included'], Decimal)
        assert isinstance(r['taxes'][0]['amount'], Decimal)

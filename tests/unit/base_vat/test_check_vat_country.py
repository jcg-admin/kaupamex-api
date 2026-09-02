"""Los validadores por país de ``base_vat`` y su despachador.

Cada caso ejerce un símbolo portado de
``odoo19c: addons/base_vat/models/res_partner.py``. Todo caso lleva su **par**
válido/inválido: un caso que sólo afirma «válido» pasa igual con un validador
que devuelve ``True`` siempre, y entonces no mide la guarda sino su ausencia
(sub-patrón D de ``metrica-decide-la-conclusion.md``).

Los pares no se eligieron de memoria: se midieron contra el porte antes de
escribirlos. El de México es el ejemplo de por qué — la fuente valida
**formato y fecha**, no el dígito verificador (``odoo19c: :533-553``), así que
un par que cambiara el último carácter habría pasado en los dos lados.
"""
import pytest

from addons.base_vat.models import res_partner as vat

pytestmark = pytest.mark.django_db


# --- Los validadores propios: ganan sobre stdnum -------------------------

@pytest.mark.parametrize('checker, valid, invalid, reason', [
    (vat.check_vat_mx, 'AAA010101AAA', 'AAA011301AAA', 'mes 13 no es fecha'),
    (vat.check_vat_ie, '1234567FA', '1234567FB', 'carácter de control'),
    (vat.check_vat_ru, '7830002293', '783000229', 'longitud del INN'),
    (vat.check_vat_gr, '123456783', '123456780', 'dígito verificador'),
    (vat.check_vat_de, '136695976', '136695970', 'dígito verificador'),
])
def test_country_checker_discriminates(checker, valid, invalid, reason):
    """El validador acepta el bien formado y rechaza el corrupto."""
    assert checker(None, valid), f'{valid} debía ser válido ({reason})'
    assert not checker(None, invalid), f'{invalid} debía fallar por {reason}'


@pytest.mark.parametrize('numero', [
    'AAA011301AAA',   # mes 13
    'AAA010230AAA',   # 30 de febrero
    'AA010101AAA',    # tres letras de persona moral, no dos
])
def test_check_vat_mx_rejects_impossible_dates_and_shapes(numero):
    """≙ ``check_vat_mx`` (``odoo19c: :533-553``) — formato **y** fecha.

    La fuente construye un ``datetime.date`` con el año, mes y día que el RFC
    codifica y rechaza el ``ValueError``. Es lo que este caso mide: los tres
    números tienen la longitud correcta y aun así no son RFC.
    """
    assert not vat.check_vat_mx(None, numero)


def test_check_vat_mx_maps_two_digit_year_across_the_century():
    """``ano > 30`` cae a 19xx; el resto a 20xx (``odoo19c: :542-546``).

    ``99`` es 1999 y ``01`` es 2001: los dos son fechas reales, así que los dos
    pasan. Si el porte hubiera fijado un solo siglo, uno de los dos caería.
    """
    assert vat.check_vat_mx(None, 'AAA991231AAA')
    assert vat.check_vat_mx(None, 'AAA010101AAA')


# --- El despachador ------------------------------------------------------

def test_dispatcher_prefers_our_own_checker_over_stdnum():
    """≙ ``_check_vat_number`` (``odoo19c: :927-934``).

    La fuente da prioridad al ``check_vat_xx`` propio y sólo cae a ``stdnum``
    cuando no hay ninguno. El receptor de este caso declara un ``check_vat_mx``
    que responde ``False`` **siempre**: si el despachador consultara ``stdnum``
    primero, el RFC bien formado saldría válido y el caso fallaría.
    """
    class PartnerWithAlwaysFalse:
        @staticmethod
        def check_vat_mx(number):
            return False

    assert not vat._check_vat_number(PartnerWithAlwaysFalse(), 'MX', 'AAA010101AAA')
    # y sin el propio, el mismo número lo resuelve la ruta de stdnum
    assert vat._check_vat_number(object(), 'MX', 'AAA010101AAA')


def test_dispatcher_falls_back_to_stdnum_when_no_own_checker():
    """Sin ``check_vat_xx`` propio, la validación la resuelve ``stdnum``.

    ``es`` no tiene método propio en este archivo, así que quien decide es
    ``stdnum.es.nif`` — y discrimina: sólo cambia el dígito de control.
    """
    assert vat._check_vat_number(object(), 'ES', 'A12345674')
    assert not vat._check_vat_number(object(), 'ES', 'A12345670')


def test_dispatcher_returns_true_for_country_without_rules():
    """≙ ``return check_func(vat_number) if check_func else True``.

    Sin validador propio ni módulo en ``stdnum``, la fuente **no** rechaza.
    Un país sin reglas no invalida a su socio.
    """
    assert vat._check_vat_number(object(), 'ZZ', 'lo-que-sea') is True


# --- _split_vat ----------------------------------------------------------

@pytest.mark.parametrize('value, expected', [
    ('MXAAA010101AAA', ('MX', 'AAA010101AAA')),
    ('be0477472701', ('BE', '0477472701')),   # normaliza el prefijo a mayúscula
    ('BE 0477 472 701', ('BE', '0477472701')),   # y quita los espacios
    ('12345678', ('', '12345678')),           # prefijo no alfabético: sin país
])
def test_split_vat(value, expected):
    """≙ ``_split_vat`` (``odoo19c: :214-219``)."""
    assert vat._split_vat(object(), value) == expected

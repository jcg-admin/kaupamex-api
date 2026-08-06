"""``res.partner.bank`` — el saneado del número es lo que hace única la cuenta.

Sin el saneado, ``ES91 2100 0418 45`` y ``es9121000418-45`` son dos filas
distintas para la base y la misma cuenta para el banco. Ese es el defecto que
la referencia evita poniendo el ``UNIQUE`` sobre la columna saneada y no sobre
la que escribe el usuario (``odoo19c: odoo/addons/base/models/res_bank.py``,
``_unique_number``), y es lo que estos tests fijan.
"""
import pytest
from django.db import IntegrityError, transaction

from addons.base.models import ResPartner, ResPartnerBank, sanitize_account_number

pytestmark = pytest.mark.django_db


@pytest.fixture
def titular():
    return ResPartner.objects.create(name='Ferretería del Norte', is_company=True)


class TestSanitizado:

    @pytest.mark.parametrize('escrito, esperado', [
        ('ES91 2100 0418 45', 'ES912100041845'),
        ('es9121000418-45', 'ES912100041845'),
        ('  MX02 0018 ', 'MX020018'),
        ('', ''),
        (None, ''),
    ])
    def test_deja_solo_alfanumericos_en_mayusculas(self, escrito, esperado):
        assert sanitize_account_number(escrito) == esperado

    def test_save_deriva_la_columna_saneada(self, titular):
        cuenta = ResPartnerBank.objects.create(
            acc_number='ES91 2100 0418 45', partner=titular,
        )
        assert cuenta.sanitized_acc_number == 'ES912100041845'


class TestUnicidad:

    def test_el_mismo_numero_escrito_distinto_choca(self, titular):
        """El UNIQUE va sobre el saneado — ese es el punto del campo."""
        ResPartnerBank.objects.create(
            acc_number='ES91 2100 0418 45', partner=titular,
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            ResPartnerBank.objects.create(
                acc_number='es9121000418-45', partner=titular,
            )

    def test_dos_titulares_pueden_tener_el_mismo_numero(self, titular):
        """La unicidad es (numero, titular), no del numero solo."""
        otro = ResPartner.objects.create(name='Aceros del Bajío', is_company=True)
        ResPartnerBank.objects.create(acc_number='ES91 2100 0418 45', partner=titular)
        ResPartnerBank.objects.create(acc_number='ES91 2100 0418 45', partner=otro)
        assert ResPartnerBank.objects.count() == 2


class TestTipoDeCuenta:

    def test_el_nucleo_infiere_bank(self, titular):
        cuenta = ResPartnerBank.objects.create(acc_number='0018 0001', partner=titular)
        assert cuenta.acc_type == 'bank'

    def test_retrieve_acc_type_es_el_punto_de_extension(self):
        """base_iban (Ola 0 · T-06) lo sobreescribe para devolver 'iban'.

        Se afirma sobre el método, no sobre el valor: lo que este porte promete
        es que el punto de extensión existe con la misma forma que en la
        referencia, no que ya haya alguien extendiéndolo.
        """
        assert ResPartnerBank.retrieve_acc_type('ES9121000418') == 'bank'
        assert callable(ResPartnerBank.retrieve_acc_type)


class TestDefaultsFieles:

    def test_allow_out_payment_nace_en_falso(self, titular):
        """Habilitar una cuenta para enviar dinero es un acto deliberado."""
        cuenta = ResPartnerBank.objects.create(acc_number='0018', partner=titular)
        assert cuenta.allow_out_payment is False

    def test_borrar_al_titular_borra_sus_cuentas(self, titular):
        """ondelete='cascade' en la referencia: la cuenta no sobrevive a su dueño."""
        ResPartnerBank.objects.create(acc_number='0018', partner=titular)
        titular.delete()
        assert ResPartnerBank.objects.count() == 0

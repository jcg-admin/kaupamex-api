"""``base_iban`` — validación, formato y derivación de tramos del IBAN.

Los vectores no son inventados: son los que la propia referencia usa en el
docstring de ``get_iban_part`` (``odoo19c: base_iban/models/res_partner_bank.py
:33-37``) más IBAN de ejemplo publicados por los registros nacionales.

Las funciones de módulo no tocan la base de datos; los métodos colgados sobre
``ResPartnerBank`` sí necesitan el registro de modelos poblado, que es lo que
``django_db`` garantiza.
"""
import pytest

from addons.base.models.res_partner import ResPartner
from addons.base.models.res_partner_bank import ResPartnerBank
from addons.base_iban.models.res_partner_bank import (
    check_iban,
    get_bban_from_iban,
    get_iban_part,
    normalize_iban,
    pretty_iban,
    validate_iban,
)
from exceptions import UserError, ValidationError

# IBAN español real de ejemplo (BBVA), con y sin separadores.
SPANISH_IBAN = 'ES9121000418450200051332'
SPANISH_IBAN_PRETTY = 'ES91 2100 0418 4502 0005 1332'
# El vector del docstring de la referencia.
ITALIAN_IBAN = 'IT60X0542811101000000123456'


def test_normalize_strips_every_separator():
    assert normalize_iban('ES91-2100 0418_4502 0005 1332') == SPANISH_IBAN
    assert normalize_iban(None) == ''
    assert normalize_iban('') == ''


def test_validate_accepts_a_real_iban():
    validate_iban(SPANISH_IBAN)
    validate_iban(SPANISH_IBAN_PRETTY)
    validate_iban(ITALIAN_IBAN)


def test_validate_rejects_an_empty_number():
    with pytest.raises(ValidationError) as excinfo:
        validate_iban('')
    assert excinfo.value.code == 'iban_empty'


def test_validate_rejects_an_unknown_country():
    with pytest.raises(ValidationError) as excinfo:
        validate_iban('ZZ9121000418450200051332')
    assert excinfo.value.code == 'iban_unknown_country'


def test_validate_rejects_a_wrong_length():
    with pytest.raises(ValidationError) as excinfo:
        validate_iban('ES912100041845020005')
    assert excinfo.value.code == 'iban_malformed'


def test_validate_rejects_a_broken_checksum():
    """Un dígito cambiado: la longitud y el país siguen bien, el mod-97 no."""
    with pytest.raises(ValidationError) as excinfo:
        validate_iban('ES9121000418450200051333')
    assert excinfo.value.code == 'iban_checksum'


def test_pretty_groups_by_four_and_leaves_a_bad_number_alone():
    assert pretty_iban(SPANISH_IBAN) == SPANISH_IBAN_PRETTY
    assert pretty_iban('no-es-un-iban') == 'no-es-un-iban'


def test_bban_drops_the_first_four_characters():
    assert get_bban_from_iban(SPANISH_IBAN) == '21000418450200051332'
    assert get_bban_from_iban(SPANISH_IBAN_PRETTY) == '21000418450200051332'


def test_iban_part_matches_the_reference_docstring():
    """Los dos valores que la referencia documenta, verbatim."""
    assert get_iban_part(ITALIAN_IBAN, 'bank') == '05428'
    assert get_iban_part(ITALIAN_IBAN, 'account') == '000000123456'


def test_iban_part_returns_false_for_an_unknown_kind():
    assert get_iban_part(ITALIAN_IBAN, 'no-such-part') is False


def test_iban_part_is_empty_for_a_country_outside_the_map():
    assert get_iban_part('ZZ60X05428111010000', 'bank') == ''


def test_check_iban_is_the_boolean_form():
    bank_account = ResPartnerBank()
    assert check_iban(bank_account, SPANISH_IBAN) is True
    assert check_iban(bank_account, 'ES9121000418450200051333') is False
    assert check_iban(bank_account) is False


@pytest.mark.django_db
class TestResPartnerBankExtension:
    """Los métodos que ``base_iban`` cuelga sobre el modelo."""

    def test_supported_types_accumulate(self):
        assert ResPartnerBank.get_supported_account_types() == [
            ('bank', 'Normal'), ('iban', 'IBAN'),
        ]

    def test_retrieve_acc_type_relays_to_base(self):
        assert ResPartnerBank.retrieve_acc_type(SPANISH_IBAN) == 'iban'
        assert ResPartnerBank.retrieve_acc_type(SPANISH_IBAN_PRETTY) == 'iban'
        # Una CLABE mexicana no es IBAN: cae al terminal de ``base``.
        assert ResPartnerBank.retrieve_acc_type('012180001234567895') == 'bank'
        assert ResPartnerBank.retrieve_acc_type('') == 'bank'

    def test_get_bban_refuses_a_non_iban_account(self):
        bank_account = ResPartnerBank(acc_number='0001234567', acc_type='bank')
        with pytest.raises(UserError):
            bank_account.get_bban()

    def test_get_bban_on_an_iban_account(self):
        bank_account = ResPartnerBank(acc_number=SPANISH_IBAN, acc_type='iban')
        assert bank_account.get_bban() == '21000418450200051332'

    def test_clean_rejects_an_account_marked_iban_with_a_broken_number(self):
        """La columna dice ``iban`` y el número ya no valida — el caso que la
        forma almacenada permite y la ``compute`` de la referencia no."""
        bank_account = ResPartnerBank(
            acc_number='ES9121000418450200051333', acc_type='iban')
        with pytest.raises(ValidationError):
            bank_account.clean()

    def test_clean_leaves_a_plain_bank_account_alone(self):
        bank_account = ResPartnerBank(acc_number='0001234567', acc_type='bank')
        bank_account.clean()

    def test_save_stores_the_iban_pretty_and_marks_the_type(self):
        """El porte de ``create``/``write``: formatea y deja que ``base``
        derive ``sanitized_acc_number`` y ``acc_type``."""
        partner = ResPartner.objects.create(name='Panadería El Águila Dorado')
        bank_account = ResPartnerBank(partner=partner, acc_number=SPANISH_IBAN)
        bank_account.save()

        bank_account.refresh_from_db()
        assert bank_account.acc_number == SPANISH_IBAN_PRETTY
        assert bank_account.acc_type == 'iban'
        # El saneado sigue sin separadores: es la columna por la que se busca.
        assert bank_account.sanitized_acc_number == SPANISH_IBAN

    def test_save_leaves_a_domestic_account_untouched(self):
        partner = ResPartner.objects.create(name='Tortillería La Esquina')
        bank_account = ResPartnerBank(partner=partner,
                                      acc_number='0012 3456 78')
        bank_account.save()

        bank_account.refresh_from_db()
        assert bank_account.acc_number == '0012 3456 78'
        assert bank_account.acc_type == 'bank'
        assert bank_account.sanitized_acc_number == '0012345678'

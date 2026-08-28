"""Contrato de ``account_qr_code_sepa`` — los cinco métodos QR SEPA colgados
sobre ``base.ResPartnerBank``.

Portación fiel del addon ``account_qr_code_sepa`` de Odoo 19
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:
addons/account_qr_code_sepa/models/res_bank.py``). Cada test verifica un
comportamiento del original o de la divergencia declarada que lo porta (ver
el docstring de ``src/addons/account_qr_code_sepa/models/res_bank.py``):

- ``_get_qr_vals`` — los 12 valores EPC; el caso de comunicación
  estructurada/libre reproduce ``test_get_qr_vals_communication`` de la
  referencia con los mismos dos vectores.
- ``_get_qr_code_generation_params`` — envoltorio de barcode.
- ``_get_error_messages_for_qr`` — elegibilidad (divisa, tipo de cuenta,
  zona SEPA).
- ``_check_for_qr_code_errors`` — consistencia de titular.
- ``_get_available_qr_methods`` — registro de ``sct_qr``.

Esta suite invoca ``apply_account_qr_code_sepa_extensions()`` explícitamente
en cada módulo de test — mismo criterio que la nota de wiring del propio
addon (``apps.py``): sin ``'addons.account_qr_code_sepa'`` en
``INSTALLED_APPS`` (fuera de este alcance), ``AccountQrCodeSepaConfig.
ready()`` no se dispara solo. La función es idempotente porque
``chain_method`` recorre la cadena antes de instalar
(``_already_in_chain``), así que llamarla en cada módulo no reinstala ni
duplica si el wiring real ya la corrió.

``base_iban`` **sí** está en ``INSTALLED_APPS``, así que su extensión de
``retrieve_acc_type`` está viva en estos tests sin invocarla: por eso una
cuenta con IBAN válido resuelve ``acc_type='iban'`` y sólo la cuenta nacional
recorre la rama del segundo check.
"""
import pytest

from addons.account_qr_code_sepa.models.res_bank import (
    apply_account_qr_code_sepa_extensions,
)
from addons.base.models import ResBank, ResCurrency, ResPartner
from addons.base.models.res_partner_bank import ResPartnerBank

pytestmark = pytest.mark.django_db

apply_account_qr_code_sepa_extensions()


@pytest.fixture
def titular():
    return ResPartner.objects.create(name='Ferretería del Norte', is_company=True)


@pytest.fixture
def eur():
    return ResCurrency.objects.create(name='EUR', symbol='€')


@pytest.fixture
def usd():
    return ResCurrency.objects.create(name='USD', symbol='$')


@pytest.fixture
def account_sepa(titular):
    # BE15001559627230 — mismo IBAN belga que usa el test de la referencia
    # (odoo19c: account_qr_code_sepa/tests/test_sepa_qr.py, acc_sepa_iban).
    return ResPartnerBank.objects.create(
        acc_number='BE15001559627230', partner=titular,
        allow_out_payment=True,
    )


@pytest.fixture
def cuenta_no_sepa(titular):
    # SA4420000001234567891234 — IBAN saudí, fuera de la zona SEPA (mismo
    # vector que acc_non_sepa_iban en la referencia).
    return ResPartnerBank.objects.create(
        acc_number='SA4420000001234567891234', partner=titular,
    )


@pytest.fixture
def domestic_account(titular):
    """Cuenta nacional que NO es IBAN — vector propio, no de la referencia.

    La referencia no ejercita la rama ``acc_type != 'iban'`` porque allí
    ``acc_type`` es un ``compute`` y sus dos vectores son IBAN. Aquí la rama sí
    es alcanzable desde que ``base_iban`` distingue los dos tipos, así que
    necesita un vector que la recorra.
    """
    return ResPartnerBank.objects.create(
        acc_number='0012345678', partner=titular,
    )


class TestExtensionWiring:
    def test_los_cinco_metodos_quedan_colgados(self):
        for nombre in (
            '_get_qr_vals', '_get_qr_code_generation_params',
            '_get_error_messages_for_qr', '_check_for_qr_code_errors',
            '_get_available_qr_methods',
        ):
            assert hasattr(ResPartnerBank, nombre), nombre

    def test_es_idempotente(self):
        # Segunda llamada: no debe alzar ni reemplazar los métodos ya
        # colgados (mismo criterio que account/l10n_mx: ready() puede correr
        # dos veces bajo el autoreloader).
        antes = ResPartnerBank._get_qr_vals
        apply_account_qr_code_sepa_extensions()
        assert ResPartnerBank._get_qr_vals is antes


class TestGetQrVals:
    """≙ ``_get_qr_vals`` (``odoo19c: res_bank.py:11-36``)."""

    def test_devuelve_none_para_metodo_no_soportado(self, account_sepa, eur):
        assert account_sepa._get_qr_vals(
            'otro_metodo', amount=100.0, currency=eur, debtor_partner=None,
            free_communication='', structured_communication='',
        ) is None

    def test_comunicacion_no_estructurada_va_en_comentario_libre(
            self, account_sepa, eur):
        """≙ primer vector de ``test_get_qr_vals_communication``: una
        comunicación de texto libre no valida como referencia estructurada,
        así que viaja en el campo de comunicación libre."""
        result = account_sepa._get_qr_vals(
            qr_method='sct_qr', amount=100.0, currency=eur,
            debtor_partner=None,
            free_communication='A free communication',
            structured_communication='A free communication',
        )
        assert result == [
            'BCD', '002', '1', 'SCT',
            '',
            'Ferretería del Norte',
            'BE15001559627230',
            'EUR100.00',
            '',
            '',
            'A free communication',
            '',
        ]

    def test_comunicacion_estructurada_valida_se_saniza(
            self, account_sepa, eur):
        """≙ segundo vector: la referencia NL válida se saniza y viaja en
        el campo estructurado; el comentario libre queda vacío."""
        result = account_sepa._get_qr_vals(
            qr_method='sct_qr', amount=100.0, currency=eur,
            debtor_partner=None,
            free_communication=' 5 000 0567 89012345 ',
            structured_communication=' 5 000 0567 89012345 ',
        )
        assert result == [
            'BCD', '002', '1', 'SCT',
            '',
            'Ferretería del Norte',
            'BE15001559627230',
            'EUR100.00',
            '',
            '5000056789012345',
            '',
            '',
        ]

    def test_bic_viene_del_banco_relacionado(self, account_sepa, eur):
        banco = ResBank.objects.create(name='BNP Paribas Fortis', bic='GEBABEBB')
        account_sepa.bank = banco
        account_sepa.save(update_fields=['bank'])
        result = account_sepa._get_qr_vals(
            qr_method='sct_qr', amount=100.0, currency=eur,
            debtor_partner=None, free_communication='',
            structured_communication='',
        )
        assert result[4] == 'GEBABEBB'

    def test_sin_banco_relacionado_el_bic_es_vacio(self, account_sepa, eur):
        result = account_sepa._get_qr_vals(
            qr_method='sct_qr', amount=100.0, currency=eur,
            debtor_partner=None, free_communication='',
            structured_communication='',
        )
        assert result[4] == ''

    def test_prefiere_acc_holder_name_sobre_el_nombre_del_partner(
            self, account_sepa, eur):
        account_sepa.acc_holder_name = 'Titular Distinto'
        account_sepa.save(update_fields=['acc_holder_name'])
        result = account_sepa._get_qr_vals(
            qr_method='sct_qr', amount=100.0, currency=eur,
            debtor_partner=None, free_communication='',
            structured_communication='',
        )
        assert result[5] == 'Titular Distinto'

    def test_holder_name_se_trunca_a_71_caracteres(self, titular, eur):
        titular.name = 'X' * 100
        titular.save(update_fields=['name'])
        cuenta = ResPartnerBank.objects.create(
            acc_number='BE15001559627230', partner=titular)
        result = cuenta._get_qr_vals(
            qr_method='sct_qr', amount=100.0, currency=eur,
            debtor_partner=None, free_communication='',
            structured_communication='',
        )
        assert len(result[5]) == 71

    def test_comentario_libre_se_trunca_a_141_caracteres(
            self, account_sepa, eur):
        result = account_sepa._get_qr_vals(
            qr_method='sct_qr', amount=100.0, currency=eur,
            debtor_partner=None,
            free_communication='Y' * 200,
            structured_communication='',
        )
        assert len(result[10]) == 141


class TestGetQrCodeGenerationParams:
    """≙ ``_get_qr_code_generation_params`` (``odoo19c: res_bank.py:38-48``)."""

    def test_devuelve_parametros_barcode_para_sct_qr(self, account_sepa, eur):
        params = account_sepa._get_qr_code_generation_params(
            qr_method='sct_qr', amount=100.0, currency=eur,
            debtor_partner=None, free_communication='',
            structured_communication='',
        )
        assert params['barcode_type'] == 'QR'
        assert params['width'] == 128
        assert params['height'] == 128
        assert params['quiet'] == 0
        assert params['humanreadable'] == 1
        assert 'BCD\n002\n1\nSCT' in params['value']

    def test_alza_notimplementederror_para_otro_metodo(
            self, account_sepa, eur):
        with pytest.raises(NotImplementedError):
            account_sepa._get_qr_code_generation_params(
                qr_method='otro_metodo', amount=100.0, currency=eur,
                debtor_partner=None, free_communication='',
                structured_communication='',
            )


class TestGetErrorMessagesForQr:
    """≙ ``_get_error_messages_for_qr`` (``odoo19c: res_bank.py:50-67``)."""

    def test_devuelve_none_para_metodo_no_soportado(self, account_sepa, eur):
        assert account_sepa._get_error_messages_for_qr(
            'otro_metodo', debtor_partner=None, currency=eur) is None

    def test_rechaza_divisa_distinta_de_eur(self, account_sepa, usd):
        mensaje = account_sepa._get_error_messages_for_qr(
            'sct_qr', debtor_partner=None, currency=usd)
        assert mensaje is not None
        assert 'USD' in mensaje

    def test_rechaza_cuenta_no_iban(self, domestic_account, eur):
        """La rama ``acc_type != 'iban'``, con una cuenta nacional.

        Hasta que ``base_iban`` existió, este test afirmaba lo contrario —que
        ``acc_type`` era ``'bank'`` **para toda** cuenta, IBAN incluida— y
        fijaba ese estado como conocido. Portado ``base_iban``, la afirmación
        quedó falsa y el test la delató: ahora sólo rechaza aquí la cuenta que
        de verdad no es IBAN.
        """
        assert domestic_account.acc_type == 'bank'
        mensaje = domestic_account._get_error_messages_for_qr(
            'sct_qr', debtor_partner=None, currency=eur)
        assert mensaje is not None
        assert "isn't IBAN" in mensaje

    def test_acepta_el_tipo_de_cuenta_de_un_iban_sepa(self, account_sepa, eur):
        """El contrapunto: un IBAN de la zona SEPA no dispara ningún mensaje.

        Es la prueba de que ``base_iban`` está cableado — sin él, ``acc_type``
        sería ``'bank'`` y esta cuenta rechazaría por el segundo check.
        """
        assert account_sepa.acc_type == 'iban'
        assert account_sepa._get_error_messages_for_qr(
            'sct_qr', debtor_partner=None, currency=eur) is None

    def test_rechaza_iban_fuera_de_zona_sepa(self, cuenta_no_sepa, eur):
        mensaje = cuenta_no_sepa._get_error_messages_for_qr(
            'sct_qr', debtor_partner=None, currency=eur)
        assert mensaje is not None
        assert 'non SEPA iban' in mensaje

    def test_acumula_varios_mensajes_separados_por_crlf(
            self, domestic_account, usd):
        """Divisa mal Y tipo de cuenta mal Y fuera de zona SEPA: los tres
        mensajes se acumulan, separados por ``\\r\\n`` (fiel a la referencia).

        Requiere la cuenta **nacional**: un IBAN saudí sólo dispara dos de los
        tres checks, porque su ``acc_type`` sí es ``'iban'`` desde que
        ``base_iban`` lo deriva.
        """
        mensaje = domestic_account._get_error_messages_for_qr(
            'sct_qr', debtor_partner=None, currency=usd)
        assert mensaje.count('\r\n') == 2


class TestCheckForQrCodeErrors:
    """≙ ``_check_for_qr_code_errors`` (``odoo19c: res_bank.py:69-74``)."""

    def test_devuelve_none_para_metodo_no_soportado(self, account_sepa, eur):
        assert account_sepa._check_for_qr_code_errors(
            'otro_metodo', amount=100.0, currency=eur, debtor_partner=None,
            free_communication='', structured_communication='',
        ) is None

    def test_rechaza_sin_titular_ni_nombre_de_partner(self, eur):
        partner = ResPartner.objects.create(name='', is_company=True)
        cuenta = ResPartnerBank.objects.create(
            acc_number='BE15001559627230', partner=partner)
        mensaje = cuenta._check_for_qr_code_errors(
            'sct_qr', amount=100.0, currency=eur, debtor_partner=None,
            free_communication='', structured_communication='',
        )
        assert mensaje is not None
        assert 'account holder name' in mensaje

    def test_acepta_con_acc_holder_name_propio(self, eur):
        partner = ResPartner.objects.create(name='', is_company=True)
        cuenta = ResPartnerBank.objects.create(
            acc_number='BE15001559627230', partner=partner,
            acc_holder_name='Titular explícito',
        )
        assert cuenta._check_for_qr_code_errors(
            'sct_qr', amount=100.0, currency=eur, debtor_partner=None,
            free_communication='', structured_communication='',
        ) is None

    def test_acepta_con_nombre_del_partner(self, account_sepa, eur):
        assert account_sepa._check_for_qr_code_errors(
            'sct_qr', amount=100.0, currency=eur, debtor_partner=None,
            free_communication='', structured_communication='',
        ) is None


class TestGetAvailableQrMethods:
    """≙ ``_get_available_qr_methods`` (``odoo19c: res_bank.py:76-80``)."""

    def test_incluye_sct_qr_con_secuencia_20(self, account_sepa):
        metodos = account_sepa._get_available_qr_methods()
        codigos = {codigo: secuencia for codigo, _name, secuencia in metodos}
        assert codigos.get('sct_qr') == 20

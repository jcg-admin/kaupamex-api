"""``account_qr_code_emv`` — el puente QR EMV que cuelga de ``res.partner.bank``.

Portación de ``odoo19c: account_qr_code_emv/models/res_bank.py``
(addon ``account_qr_code_emv``, LGPL-3, ``odoo-tools@622ddc2a``).

Todos los oráculos de este archivo se computaron de forma independiente
(Python puro, sin importar el módulo bajo prueba) antes de escribirlo —
``metrica-decide-la-conclusion.md``: una prueba que re-deriva su propio
oráculo con el mismo código que prueba no prueba nada. El CRC16 se contrasta
contra el vector de verificación estándar de CRC-16/CCITT-FALSE
(``"123456789"`` → ``0x29B1``), no contra un valor inventado.

Wiring pendiente (ver ``models/res_bank.py``, divergencia 4): este addon NO
está en ``INSTALLED_APPS`` todavía (fuera del alcance de quien lo portó —
prohibido tocar ``config/settings/base.py``), así que
``AccountQrCodeEmvConfig.ready()`` no se dispara solo. Este archivo llama
``apply_account_qr_code_emv_extensions()`` explícitamente — es idempotente
(``hasattr``/``_add_if_absent``), así que no rompe nada el día que el
wiring exista y ``ready()`` ya la haya llamado.

Todas las instancias de ``ResPartnerBank``/``ResPartner``/``ResCurrency``/
``ResCountry`` de este archivo son **NO guardadas** (nunca ``.save()`` ni
``.objects.create()``): los tres campos con columna que este addon cuelga
(``include_reference``, ``proxy_type``, ``proxy_value``) no tienen migración
todavía en ``base`` (misma divergencia 4) — escribirlos a la base fallaría
por columna inexistente. La instanciación pura de Django no toca la base.
"""
from decimal import Decimal

import pytest

from addons.account_qr_code_emv.const import CURRENCY_MAPPING
from addons.account_qr_code_emv.models.res_bank import (
    apply_account_qr_code_emv_extensions,
    strip_accents,
)
from addons.account_qr_code_emv.models.res_bank import (
    _get_error_messages_for_qr as raw_get_error_messages_for_qr,
)
from addons.base.models import ResCountry, ResCurrency, ResPartner, ResPartnerBank

pytestmark = pytest.mark.unit

# Aplicar la extensión una vez al importar el módulo — mismo efecto que
# ``AccountQrCodeEmvConfig.ready()``, sin depender de que el addon esté en
# ``INSTALLED_APPS`` (ver docstring de arriba).
apply_account_qr_code_emv_extensions()


# -- fixtures — todo NO guardado (sin tocar la base) ------------------------


@pytest.fixture
def country_mx():
    return ResCountry(name='México', code='MX')


@pytest.fixture
def partner(country_mx):
    return ResPartner(
        name='Panadería El Águila Dorado S.A. de C.V.',
        city='Ciudad de México',
        country=country_mx,
    )


@pytest.fixture
def currency_mxn():
    return ResCurrency(
        name='MXN', full_name='Peso mexicano', symbol='$',
        rounding=Decimal('0.01'), decimal_places=2,
    )


@pytest.fixture
def bank(partner):
    return ResPartnerBank(partner=partner, acc_number='0123456789012345')


# -- const.py -----------------------------------------------------------


class TestCurrencyMapping:
    def test_tiene_48_entradas(self):
        """``odoo19c: const.py`` — conteo verificado con Python puro sobre
        el archivo de la referencia (``exec`` + ``len(dict)`` → 48)."""
        assert len(CURRENCY_MAPPING) == 48

    def test_mxn_y_usd(self):
        assert CURRENCY_MAPPING['MXN'] == '484'
        assert CURRENCY_MAPPING['USD'] == '840'


# -- strip_accents / _remove_accents -------------------------------------


class TestAcentos:
    def test_strip_accents_nfkd(self):
        assert strip_accents('café') == 'cafe'
        assert strip_accents('MÉXICO Ñandú') == 'MEXICO Nandu'

    def test_strip_accents_cadena_vacia_o_none(self):
        assert strip_accents('') == ''
        assert strip_accents(None) is None

    def test_remove_accents_conserva_d_con_trazo_vietnamita(self, bank):
        """``đ``/``Đ`` no son diacríticos combinantes — NFKD no los toca;
        la referencia los reemplaza a mano y este puerto también."""
        assert bank._remove_accents('đồng') == 'dong'
        assert bank._remove_accents('café') == 'cafe'


# -- campos colgados por apply_account_qr_code_emv_extensions() ----------


class TestCamposColgados:
    def test_defaults_de_una_instancia_nueva(self):
        nueva = ResPartnerBank()
        assert nueva.display_qr_setting is False
        assert nueva.country_proxy_keys == ''
        assert nueva.include_reference is False
        assert nueva.proxy_type == 'none'
        assert nueva.proxy_value == ''

    def test_display_qr_setting_y_country_proxy_keys_son_nonstored(self):
        """No aparecen en ``_meta.get_fields()`` — es la propiedad que
        distingue un campo ``store=False`` de uno con columna real."""
        nombres = {f.name for f in ResPartnerBank._meta.get_fields()}
        assert 'display_qr_setting' not in nombres
        assert 'country_proxy_keys' not in nombres
        assert 'include_reference' in nombres
        assert 'proxy_type' in nombres
        assert 'proxy_value' in nombres

    def test_apply_extensions_es_idempotente(self):
        """Llamar dos veces no duplica el campo ``proxy_type`` en
        ``_meta`` — ``ready()`` puede correr más de una vez por proceso
        (recarga del autoreloader)."""
        apply_account_qr_code_emv_extensions()
        apply_account_qr_code_emv_extensions()
        nombres = [f.name for f in ResPartnerBank._meta.get_fields()]
        assert nombres.count('proxy_type') == 1
        assert nombres.count('include_reference') == 1
        assert nombres.count('proxy_value') == 1


# -- _serialize -----------------------------------------------------------


class TestSerialize:
    def test_valor_presente(self, bank):
        # header=0 -> '00'; len('01')=2 -> '02'; + '01' == '000201'
        assert bank._serialize(0, '01') == '000201'

    def test_valor_none_o_vacio_serializa_a_cadena_vacia(self, bank):
        assert bank._serialize(5, None) == ''
        assert bank._serialize(5, '') == ''


# -- _get_crc16 — contra el vector de verificación estándar --------------


class TestCrc16:
    def test_vector_de_verificacion_ccitt_false(self, bank):
        """CRC-16/CCITT-FALSE del ASCII "123456789" es ``0x29B1`` — valor
        de verificación publicado del algoritmo (poly 0x1021, init
        0xFFFF, sin reflejar), independiente de esta implementación."""
        assert bank._get_crc16(b'123456789') == 0x29B1

    def test_determinista(self, bank):
        assert bank._get_crc16(b'hola') == bank._get_crc16(b'hola')


# -- los 4 hooks de extensión (terminal del puente, sin localización) ----


class TestHooksDeExtension:
    def test_get_merchant_account_info(self, bank):
        assert bank._get_merchant_account_info() == (None, None)

    def test_get_additional_data_field(self, bank):
        assert bank._get_additional_data_field('cualquier comentario') is None

    def test_get_merchant_category_code(self, bank):
        assert bank._get_merchant_category_code() == '0000'

    def test_available_qr_methods_registers_emv_qr(self, bank):
        """El addon aporta ``emv_qr`` **sin desplazar** lo que ya estaba.

        La versión anterior afirmaba ``len(metodos) == 1``: codificaba la
        premisa "soy el único que contribuye a este hook", que era falsa desde
        que ``account_qr_code_sepa`` se instaló en la misma tanda. Con la
        guarda ``if not hasattr`` el que iba primero ganaba y el test pasaba
        **porque el otro addon estaba desactivado**. Ver :ref:`h-api-364`.
        """
        metodos = bank._get_available_qr_methods()
        por_codigo = {codigo: (nombre, secuencia)
                      for codigo, nombre, secuencia in metodos}

        assert 'emv_qr' in por_codigo
        nombre, secuencia = por_codigo['emv_qr']
        assert secuencia == 30
        assert 'EMV' in nombre

        # El hermano sigue vivo: la cadena acumula, no reemplaza.
        assert 'sct_qr' in por_codigo


# -- _get_qr_code_vals_list / _get_qr_vals / _get_qr_code_generation_params


class TestQrCodeValsList:
    def test_estructura_completa(self, bank, currency_mxn, partner):
        vals = bank._get_qr_code_vals_list(
            'emv_qr', Decimal('150.50'), currency_mxn, partner, None, None)

        assert vals == [
            (0, '01'),
            (1, '12'),
            (None, None),                          # sin localización EMV
            (52, '0000'),
            (53, '484'),
            (54, Decimal('150.50')),
            (58, 'MX'),
            (59, 'Panaderia El Aguila Dorad'),      # sin acentos, 25 chars
            (60, 'Ciudad de Mexic'),                # sin acentos, 15 chars
            (62, None),                             # include_reference=False
        ]

    def test_monto_entero_se_convierte_a_int(self, bank, currency_mxn, partner):
        vals = bank._get_qr_code_vals_list(
            'emv_qr', Decimal('100.00'), currency_mxn, partner, None, None)
        monto = next(v for tag, v in vals if tag == 54)
        assert monto == 100
        assert isinstance(monto, int)

    def test_monto_cero_es_none(self, bank, currency_mxn, partner):
        vals = bank._get_qr_code_vals_list(
            'emv_qr', Decimal('0.00'), currency_mxn, partner, None, None)
        monto = next(v for tag, v in vals if tag == 54)
        assert monto is None

    def test_sin_partner_no_revienta(self, currency_mxn):
        """``self.partner`` puede ser ``None`` — a diferencia de la
        referencia (recordset vacío ≙ falsy), este ORM necesita la guarda
        explícita (divergencia declarada en el docstring del módulo)."""
        bank_sin_partner = ResPartnerBank(acc_number='000')
        vals = bank_sin_partner._get_qr_code_vals_list(
            'emv_qr', Decimal('1'), currency_mxn, None, None, None)
        merchant_name = next(v for tag, v in vals if tag == 59)
        merchant_city = next(v for tag, v in vals if tag == 60)
        country_code = next(v for tag, v in vals if tag == 58)
        assert merchant_name == 'NA'
        assert merchant_city == ''
        assert country_code is None


class TestGetQrVals:
    # Oráculo verificado por dos vías independientes: (a) un script Python
    # que reimplementa TLV+CRC16 sin importar este módulo, y (b) el propio
    # módulo ejecutado directamente en el intérprete del proyecto
    # (.venv, Python 3.12.3) — ambos coinciden en este valor exacto.
    QR_ESPERADO = (
        '0002010102125204000053034845406150.50'
        '5802MX5925Panaderia El Aguila Dorad'
        '6015Ciudad de Mexic6304D1DA'
    )

    def test_emv_qr_serializa_y_agrega_crc(self, bank, currency_mxn, partner):
        qr = bank._get_qr_vals(
            'emv_qr', Decimal('150.50'), currency_mxn, partner, None, None)
        assert qr == self.QR_ESPERADO
        assert qr.endswith('6304D1DA')

    def test_otro_metodo_es_none(self, bank, currency_mxn, partner):
        """Terminal del ``super()`` ausente (divergencia 3 del módulo)."""
        assert bank._get_qr_vals(
            'pix_qr', Decimal('1'), currency_mxn, partner, None, None
        ) is None


class TestGetQrCodeGenerationParams:
    def test_emv_qr_arma_los_parametros_del_barcode(
            self, bank, currency_mxn, partner):
        params = bank._get_qr_code_generation_params(
            'emv_qr', Decimal('150.50'), currency_mxn, partner, None, None)
        assert params['barcode_type'] == 'QR'
        assert params['width'] == 128
        assert params['height'] == 128
        assert params['value'] == bank._get_qr_vals(
            'emv_qr', Decimal('150.50'), currency_mxn, partner, None, None)

    def test_otro_metodo_lanza_not_implemented(self, bank, currency_mxn, partner):
        """Terminal del ``super()`` ausente (divergencia 3)."""
        with pytest.raises(NotImplementedError):
            bank._get_qr_code_generation_params(
                'pix_qr', Decimal('1'), currency_mxn, partner, None, None)


# -- _check_for_qr_code_errors --------------------------------------------


class TestCheckForQrCodeErrors:
    def test_sin_ciudad(self, currency_mxn, country_mx, partner):
        sin_ciudad = ResPartner(name='X', city='', country=country_mx)
        b = ResPartnerBank(partner=sin_ciudad, proxy_type='none',
                            proxy_value='5551234567')
        assert b._check_for_qr_code_errors(
            'emv_qr', Decimal('1'), currency_mxn, partner, None, None
        ) == 'Falta la ciudad del comercio.'

    def test_sin_proxy_value(self, bank, currency_mxn, partner):
        bank.proxy_type = 'none'
        bank.proxy_value = ''
        assert bank._check_for_qr_code_errors(
            'emv_qr', Decimal('1'), currency_mxn, partner, None, None
        ) == 'Falta el valor del proxy.'

    def test_sin_proxy_type(self, bank, currency_mxn, partner):
        bank.proxy_type = ''
        bank.proxy_value = '5551234567'
        assert bank._check_for_qr_code_errors(
            'emv_qr', Decimal('1'), currency_mxn, partner, None, None
        ) == 'Falta el tipo de proxy.'

    def test_todo_presente_no_hay_error(self, bank, currency_mxn, partner):
        bank.proxy_type = 'none'
        bank.proxy_value = '5551234567'
        assert bank._check_for_qr_code_errors(
            'emv_qr', Decimal('1'), currency_mxn, partner, None, None
        ) is None

    def test_otro_metodo_no_valida_nada(self, bank, currency_mxn, partner):
        """``proxy_value``/``proxy_type`` vacíos, pero ``qr_method`` no es
        ``'emv_qr'`` — la validación ni se ejecuta."""
        bank.proxy_type = ''
        bank.proxy_value = ''
        assert bank._check_for_qr_code_errors(
            'pix_qr', Decimal('1'), currency_mxn, partner, None, None
        ) is None

    def test_merchant_account_info_ausente_nunca_dispara_en_el_puente(
            self, bank, currency_mxn, partner):
        """``_get_merchant_account_info()`` devuelve ``(None, None)`` — una
        tupla de longitud 2, truthy en Python. El primer chequeo de la
        referencia (pensado para cuando SÍ hay localización) no puede
        disparar en el puente puro; lo prueba indirectamente el hecho de
        que, con todo lo demás en orden, el resultado es ``None`` y no el
        mensaje "Falta la información de cuenta del comercio."."""
        bank.proxy_type = 'none'
        bank.proxy_value = '5551234567'
        resultado = bank._check_for_qr_code_errors(
            'emv_qr', Decimal('1'), currency_mxn, partner, None, None)
        assert resultado != 'Falta la información de cuenta del comercio.'
        assert resultado is None


# -- _get_error_messages_for_qr -------------------------------------------


class TestGetErrorMessagesForQr:
    def test_emv_qr_siempre_rechaza_en_el_puente_puro(self, bank, currency_mxn):
        mensaje = bank._get_error_messages_for_qr('emv_qr', None, currency_mxn)
        assert mensaje is not None
        assert '0123456789012345' in mensaje

    def test_otro_metodo_es_elegible(self, bank, currency_mxn):
        assert bank._get_error_messages_for_qr(
            'pix_qr', None, currency_mxn) is None

    def test_self_none_devuelve_el_mensaje_de_cuenta_requerida(
            self, currency_mxn):
        """Traduce el ``if not self:`` de la referencia (recordset vacío).
        Código muerto bajo la convención de llamada de Django (todo método
        de instancia recibe un ``self`` real) — se ejerce llamando la
        función cruda importada del módulo, no el método atado a una
        instancia, para no dejar el símbolo sin cubrir."""
        mensaje = raw_get_error_messages_for_qr(None, 'emv_qr', None, currency_mxn)
        assert mensaje == (
            'Se requiere una cuenta bancaria para generar el código QR EMV.')

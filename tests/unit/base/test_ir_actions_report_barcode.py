"""``barcode`` y ``get_available_barcode_masks`` de ``ir.actions.report``.

Los dos símbolos que quedaban del bloque D en la tarea #170. La declaración
anterior los daba por fuera «porque el motor es nuestro»; medido, eso mezclaba
dos contratos distintos: el **PDF** lo dibujan los helpers de libharu
(ADR-017), pero el **raster de un código de barras a PNG** no toca ese motor.
Es ``python-barcode`` + ``qrcode`` + Pillow, que es el camino de
reimplementación fiel y no el de declarar divergencia.

Cada caso mide una rama que la fuente declara, no el resultado agregado: los
validadores de ``defaults``, la guarda de tamaño, la promoción de ``UPCA``, la
adivinanza de ``auto``, el trato de ``quiet`` en ``QR``, el respaldo a
``Code128`` cuando la codificación no cuadra, el gancho de máscara y las tres
salidas del ``except``.
"""
import inspect

import pytest

from addons.base.models.ir_actions_report import IrActionsReport

pytestmark = pytest.mark.django_db

PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


class TestTheDefaultsAreValidatedLikeTheSource:
    """``defaults`` — cada clave con su validador, no un ``kwargs.get``."""

    def test_without_arguments_it_draws_with_the_declared_defaults(self):
        output = IrActionsReport.barcode('Code128', 'KX-0001')
        assert output.startswith(PNG_MAGIC)

    def test_the_size_arrives_as_a_string_and_is_read_as_an_integer(self):
        # La fuente valida con ``int``: el llamador es una URL, y ahí todo
        # llega como texto.
        output = IrActionsReport.barcode(
            'Code128', 'KX-0001', width='300', height='80')
        assert output.startswith(PNG_MAGIC)

    def test_humanreadable_arrives_as_a_digit_and_is_read_as_a_boolean(self):
        # ``lambda x: bool(int(x))`` — '0' es falso, no verdadero.
        without_text = IrActionsReport.barcode(
            'Code128', 'KX-0001', humanreadable='0')
        with_text = IrActionsReport.barcode(
            'Code128', 'KX-0001', humanreadable='1')
        assert without_text != with_text

    def test_an_unknown_correction_level_falls_back_to_l(self):
        # ``x in ('L','M','Q','H') and x or 'L'`` — el validador de la fuente.
        assert (IrActionsReport.barcode('QR', 'KX', barLevel='Z')
                == IrActionsReport.barcode('QR', 'KX', barLevel='L'))


class TestTheSizeGuardRejectsBeforeDrawing:
    """``width * height > 1200000`` o ``max(...) > 10000`` → ``ValueError``."""

    def test_the_area_over_the_limit_is_rejected(self):
        with pytest.raises(ValueError, match='Barcode too large'):
            IrActionsReport.barcode('Code128', 'KX', width=2000, height=2000)

    def test_a_side_over_ten_thousand_is_rejected(self):
        # El área cabe (10001 x 1 = 10001) y el lado no: son dos guardas.
        with pytest.raises(ValueError, match='Barcode too large'):
            IrActionsReport.barcode('Code128', 'KX', width=10001, height=1)

    def test_the_limit_itself_is_not_rejected(self):
        # ``>`` y no ``>=``: 1200 x 1000 = 1 200 000 exacto pasa.
        assert IrActionsReport.barcode(
            'Code128', 'KX-0001', width=1200, height=1000)


class TestUpcaIsPromotedToEan13:
    """Las tres longitudes que la fuente admite, con su relleno de cero."""

    @pytest.mark.parametrize('value', ['01234567890', '012345678905'])
    def test_eleven_and_twelve_digits_get_a_leading_zero(self, value):
        promoted = IrActionsReport.barcode('UPCA', value)
        assert promoted == IrActionsReport.barcode('EAN13', '0' + value)

    def test_thirteen_digits_are_promoted_without_padding(self):
        value = '0012345678905'
        assert (IrActionsReport.barcode('UPCA', value)
                == IrActionsReport.barcode('EAN13', value))

    def test_another_length_stays_upca(self):
        # Fuera de (11, 12, 13) la fuente no promueve: el tipo sigue siendo
        # UPCA y cae al respaldo del ``except``, que da Code128.
        assert IrActionsReport.barcode('UPCA', 'KX-0001')


class TestAutoGuessesTheSymbologyByLength:
    """``symbology_guess = {8: 'EAN8', 13: 'EAN13'}``, si no ``Code128``."""

    def test_eight_digits_guess_ean8(self):
        assert (IrActionsReport.barcode('auto', '96385074')
                == IrActionsReport.barcode('EAN8', '96385074'))

    def test_thirteen_digits_guess_ean13(self):
        assert (IrActionsReport.barcode('auto', '5901234123457')
                == IrActionsReport.barcode('EAN13', '5901234123457'))

    def test_any_other_length_guesses_code128(self):
        assert (IrActionsReport.barcode('auto', 'KX-0001')
                == IrActionsReport.barcode('Code128', 'KX-0001'))


class TestQrTradesQuietForBorder:
    """``quiet`` no existe en QR; la fuente lo traduce a ``barBorder``."""

    def test_quiet_false_removes_the_border(self):
        assert (IrActionsReport.barcode('QR', 'KX', quiet=0)
                == IrActionsReport.barcode('QR', 'KX', barBorder=0))

    def test_quiet_true_keeps_the_default_border(self):
        assert (IrActionsReport.barcode('QR', 'KX', quiet=1)
                == IrActionsReport.barcode('QR', 'KX', barBorder=4))


class TestABadEncodingFallsBackToCode128:
    """El motivo que la fuente escribe: EAN8 de 11111111 dibujaría 11111115."""

    def test_an_ean8_with_a_wrong_check_digit_becomes_code128(self):
        assert (IrActionsReport.barcode('EAN8', '11111111')
                == IrActionsReport.barcode('Code128', '11111111'))

    def test_an_ean8_with_the_right_check_digit_stays_ean8(self):
        right = IrActionsReport.barcode('EAN8', '96385074')
        assert right != IrActionsReport.barcode('Code128', '96385074')


class TestTheFailurePathHasThreeOutcomes:
    """``except (ValueError, AttributeError)`` — dos alzan y uno reintenta."""

    def test_code128_that_cannot_be_drawn_raises_its_own_message(self):
        with pytest.raises(ValueError, match='Cannot convert into barcode'):
            IrActionsReport.barcode('Code128', '')

    def test_qr_that_cannot_be_drawn_raises_its_own_message(self):
        # Un value que no cabe ni en la versión 40, la mayor que hay.
        with pytest.raises(ValueError, match='Cannot convert into QR code'):
            IrActionsReport.barcode('QR', 'x' * 3000)

    def test_any_other_type_retries_as_code128(self):
        # 'ITF' sólo admite dígitos; con letras falla y la fuente reintenta.
        assert (IrActionsReport.barcode('ITF', 'ABC')
                == IrActionsReport.barcode('Code128', 'ABC'))


class TestTheMaskHookIsCalledAndIsEmptyByDefault:
    """``get_available_barcode_masks`` — gancho de extensión, ``{}``."""

    def test_the_hook_returns_an_empty_mapping(self):
        assert IrActionsReport.get_available_barcode_masks() == {}

    def test_a_registered_mask_post_processes_the_image(self, monkeypatch):
        seen = {}

        def apply_mask(width, height, barcode):
            seen['args'] = (width, height, type(barcode).__name__)
            return barcode

        monkeypatch.setattr(
            IrActionsReport, 'get_available_barcode_masks',
            classmethod(lambda cls: {'kx': apply_mask}))
        IrActionsReport.barcode('QR', 'KX', mask='kx', width=120, height=120)
        assert seen['args'][:2] == (120, 120)

    def test_an_unknown_mask_is_ignored(self):
        assert (IrActionsReport.barcode('QR', 'KX', mask='no-existe')
                == IrActionsReport.barcode('QR', 'KX'))


class TestTheSignaturesMatchTheSource:
    """El contrato: mismo nombre, mismos parámetros, mismo orden."""

    def test_barcode_takes_the_type_the_value_and_free_keywords(self):
        signature = inspect.signature(IrActionsReport.barcode)
        assert list(signature.parameters) == ['barcode_type', 'value', 'kwargs']

    def test_the_mask_hook_takes_no_arguments(self):
        signature = inspect.signature(IrActionsReport.get_available_barcode_masks)
        assert list(signature.parameters) == []

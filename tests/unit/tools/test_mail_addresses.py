"""Tests — normalización y formato de direcciones de correo.

Contrato adaptado de ``odoo19c: odoo/tools/mail.py``: ``email_normalize``
(``:812``), ``email_normalize_all`` (``:848``) y ``formataddr`` (``:961``).

Por qué la normalización no es ``.strip().lower()``
====================================================

Un correo capturado por una persona llega con ruido —espacios, mayúsculas, el
nombre pegado delante— y el mismo buzón escrito de dos formas tiene que
comparar igual, o el sistema manda dos veces o no manda ninguna. La fuente
extrae la dirección de dentro del formato ``Nombre <buzon@dominio>`` y baja
el dominio siempre.

**La parte local se baja sólo si es ASCII**, y la razón está escrita en el
docstring de la fuente: el RFC 5322 §3.4.1 la declara sensible a mayúsculas,
*"however most main providers do consider the local-part as case
insensitive"*. Con SMTP-UTF8 esa suposición deja de valer para una parte local
internacional, así que la fuente baja la ASCII y **deja intacta** la que no lo
es. No es una inconsistencia: es la única regla que no rompe ninguno de los
dos mundos.

Qué haría fallar a cada control
--------------------------------

``TestNormalize.test_a_non_ascii_local_part_is_left_alone``
    El eje. Lo haría fallar un ``.lower()`` sobre la cadena entera — que es
    lo que uno escribe si no lee el docstring de la fuente.

``TestFormatAddr.test_a_non_ascii_name_is_encoded_when_the_charset_is_ascii``
    CONTROL: sólo con ``charset='ascii'`` la fuente codifica en base64. Con
    el ``utf-8`` por defecto el nombre pasa tal cual, y afirmar lo contrario
    describe una función que no existe.
"""
import pytest

from tools.mail import email_normalize, email_normalize_all, formataddr

pytestmark = pytest.mark.unit


class TestNormalize:
    """≙ ``email_normalize`` — una dirección, o cadena vacía."""

    def test_it_extracts_the_address_from_a_formatted_one(self):
        assert email_normalize('Ana Ruiz <ana@kaupamex.mx>') == 'ana@kaupamex.mx'

    def test_it_trims_and_lowercases_the_domain(self):
        assert email_normalize('  ana@KAUPAMEX.MX ') == 'ana@kaupamex.mx'

    def test_an_ascii_local_part_is_lowered(self):
        """La fuente la baja a propósito: los proveedores la tratan así."""
        assert email_normalize('Ana.Ruiz@kaupamex.mx') == 'ana.ruiz@kaupamex.mx'

    def test_a_non_ascii_local_part_is_left_alone(self):
        """El eje — SMTP-UTF8 la admite tal cual; bajarla fusiona buzones."""
        assert email_normalize('Añez@KAUPAMEX.MX') == 'Añez@kaupamex.mx'

    def test_something_that_is_not_an_address_is_false(self):
        """La fuente devuelve ``False``, no cadena vacía."""
        assert email_normalize('no soy un correo') is False

    def test_none_is_false(self):
        assert email_normalize(None) is False

    def test_two_addresses_are_refused_when_strict(self):
        """CONTROL — en modo estricto una cadena con dos buzones no es UNA
        dirección; devolverla mezclada es lo que rompe el envío."""
        assert email_normalize('a@kaupamex.mx, b@kaupamex.mx') is False

    def test_without_strict_the_first_one_wins(self):
        """CONTROL del argumento — sin él ``strict`` sería decorativo."""
        assert email_normalize('a@kaupamex.mx, b@kaupamex.mx',
                               strict=False) == 'a@kaupamex.mx'


class TestNormalizeAll:
    """≙ ``email_normalize_all`` — la lista, para el campo multi-correo."""

    def test_it_returns_every_address(self):
        assert email_normalize_all('a@kaupamex.mx, b@kaupamex.mx') == [
            'a@kaupamex.mx', 'b@kaupamex.mx']

    def test_one_address_is_a_list_of_one(self):
        assert email_normalize_all('ana@kaupamex.mx') == ['ana@kaupamex.mx']

    def test_nothing_usable_is_an_empty_list(self):
        assert email_normalize_all('no soy un correo') == []

    def test_none_is_an_empty_list(self):
        assert email_normalize_all(None) == []


class TestFormatAddr:
    """≙ ``formataddr`` — ``Nombre <buzon@dominio>`` para una cabecera."""

    def test_it_joins_name_and_address(self):
        """El nombre va **entre comillas** — RFC 2822 §3.4."""
        assert formataddr(('Ana Ruiz', 'ana@kaupamex.mx')) == (
            '"Ana Ruiz" <ana@kaupamex.mx>')

    def test_without_a_name_it_is_the_bare_address(self):
        assert formataddr(('', 'ana@kaupamex.mx')) == 'ana@kaupamex.mx'

    def test_a_non_ascii_name_is_encoded_when_the_charset_is_ascii(self):
        """CONTROL — sólo con ``charset='ascii'``. La fuente codifica en
        base64 (RFC 2047) cuando el nombre no cabe en el charset pedido."""
        salida = formataddr(('Ana Muñoz', 'ana@kaupamex.mx'), charset='ascii')
        assert salida.startswith('=?utf-8?b?')
        assert salida.endswith('<ana@kaupamex.mx>')
        assert salida.isascii()

    def test_with_the_default_utf8_charset_it_passes_through(self):
        """CONTROL de la otra rama — el default es ``utf-8``, y ahí cabe."""
        assert formataddr(('Ana Muñoz', 'ana@kaupamex.mx')) == (
            '"Ana Muñoz" <ana@kaupamex.mx>')

    def test_a_quote_in_the_name_is_escaped(self):
        """CONTROL — una comilla sin escapar rompe la cabecera entera."""
        assert formataddr(('Ana "La Jefa"', 'ana@kaupamex.mx')) == (
            r'"Ana \"La Jefa\"" <ana@kaupamex.mx>')

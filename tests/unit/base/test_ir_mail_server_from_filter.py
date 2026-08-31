"""``_match_from_filter`` y ``_find_mail_server`` — el enrutado por remitente.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_mail_server.py``
(``_match_from_filter`` ``:956-973``, ``_find_mail_server`` ``:900-954``).

Por qué estos casos existen ahora
=================================

El archivo implementaba sus tres normalizadores como funciones **privadas**
propias, con el argumento de que ``tools/mail.py`` no estaba portado. Ese
archivo ya existe, así que las tres se retiran y se importan de allá. El
cambio no es cosmético: las privadas devolvían ``''`` al fallar y las
públicas de la fuente devuelven ``False``, y la comparación de dominios se
hace **entre dos resultados de esas funciones**.

Sin estos casos, el intercambio se hace a ciegas: no había ni un test que
ejerciera ``match_from_filter`` ni ``find_mail_server``.

Qué haría fallar a cada control
--------------------------------

``TestMatchFromFilter.test_an_invalid_sender_does_not_match_a_domain_filter``
    El eje del cambio de valor falso. Lo haría fallar una implementación en
    que el dominio del remitente inválido y el del filtro colapsen al mismo
    valor falso — dos ``False`` comparan iguales, y el servidor equivocado se
    declararía válido para cualquier basura.

``TestFindMailServer.test_the_domain_step_keeps_the_requested_sender``
    CONTROL de la segunda mitad del contrato: el método devuelve **par**
    (servidor, remitente), y el remitente cambia según el paso. Un puerto que
    devolviera sólo el servidor pasaría los demás casos.
"""
import pytest

from addons.base.models.ir_mail_server import IrMailServer

pytestmark = pytest.mark.django_db


def _server(from_filter='', sequence=10, active=True):
    """Un servidor **sin guardar**: la cascada acepta la lista por argumento."""
    return IrMailServer(name=f'smtp-{sequence}', smtp_host='localhost',
                        from_filter=from_filter, sequence=sequence,
                        active=active)


class TestMatchFromFilter:
    """≙ ``_match_from_filter`` — ¿este servidor puede enviar por ese buzón?"""

    def test_an_empty_filter_always_matches(self):
        """Sin filtro es «sin restricción», no «no casa nada»."""
        assert IrMailServer.match_from_filter('ana@kaupamex.mx', '') is True
        assert IrMailServer.match_from_filter('ana@kaupamex.mx', None) is True

    def test_a_full_address_matches_itself(self):
        assert IrMailServer.match_from_filter(
            'Ana <ANA@Kaupamex.MX>', 'ana@kaupamex.mx') is True

    def test_a_domain_filter_matches_any_address_of_that_domain(self):
        assert IrMailServer.match_from_filter(
            'quien.sea@kaupamex.mx', 'KAUPAMEX.MX') is True

    def test_another_domain_does_not_match(self):
        assert IrMailServer.match_from_filter(
            'ana@otra.mx', 'kaupamex.mx') is False

    def test_a_comma_separated_filter_matches_any_of_its_parts(self):
        assert IrMailServer.match_from_filter(
            'ana@otra.mx', 'kaupamex.mx, otra.mx') is True

    def test_an_invalid_sender_does_not_match_a_domain_filter(self):
        """El eje: dos valores falsos NO se declaran iguales.

        ``email_normalize`` rehúsa el texto, así que el dominio del remitente
        es falso; el del filtro es una cadena real. Si el puerto dejara ambos
        lados en el mismo valor falso, este servidor aceptaría cualquier
        remitente irreconocible.
        """
        assert IrMailServer.match_from_filter(
            'no soy un correo', 'kaupamex.mx') is False

    def test_an_invalid_sender_does_not_match_an_address_filter(self):
        assert IrMailServer.match_from_filter(
            'no soy un correo', 'ana@kaupamex.mx') is False


class TestFindMailServer:
    """≙ ``_find_mail_server`` — la cascada de cinco pasos, con su remitente."""

    def test_the_exact_address_wins_over_the_domain(self):
        by_domain = _server(from_filter='kaupamex.mx', sequence=1)
        exact = _server(from_filter='ana@kaupamex.mx', sequence=2)
        server, sender = IrMailServer.find_mail_server(
            'ana@kaupamex.mx', servers=[by_domain, exact],
            notifications_email='')
        assert server is exact
        assert sender == 'ana@kaupamex.mx'

    def test_the_domain_step_keeps_the_requested_sender(self):
        """CONTROL — el par: en los pasos 1 y 2 el remitente NO se suplanta."""
        by_domain = _server(from_filter='kaupamex.mx')
        server, sender = IrMailServer.find_mail_server(
            'Ana <ana@KAUPAMEX.mx>', servers=[by_domain],
            notifications_email='')
        assert server is by_domain
        assert sender == 'Ana <ana@KAUPAMEX.mx>'

    def test_the_notifications_step_replaces_the_sender(self):
        """El paso 3 SÍ suplanta: se envía como el buzón de notificaciones."""
        operator_server = _server(from_filter='avisos@kaupamex.mx')
        server, sender = IrMailServer.find_mail_server(
            'ana@otra.mx', servers=[operator_server],
            notifications_email='avisos@kaupamex.mx')
        assert server is operator_server
        assert sender == 'avisos@kaupamex.mx'

    def test_an_unfiltered_server_is_the_fourth_step(self):
        unfiltered = _server(from_filter='')
        server, sender = IrMailServer.find_mail_server(
            'ana@otra.mx', servers=[unfiltered],
            notifications_email='avisos@kaupamex.mx')
        assert server is unfiltered
        assert sender == 'avisos@kaupamex.mx'

    def test_the_last_step_uses_any_server_even_if_it_does_not_match(self):
        foreign = _server(from_filter='tercera.mx')
        server, sender = IrMailServer.find_mail_server(
            'ana@otra.mx', servers=[foreign], notifications_email='')
        assert server is foreign
        assert sender == 'ana@otra.mx'

    def test_an_archived_server_is_never_used(self):
        """CONTROL — el paso 0. Sin él, el archivado ganaría por el paso 1."""
        archived = _server(from_filter='ana@kaupamex.mx', active=False)
        server, _sender = IrMailServer.find_mail_server(
            'ana@kaupamex.mx', servers=[archived], notifications_email='')
        assert server is None

    def test_without_rows_it_falls_back_to_the_global_config(self):
        """Sin servidores, ``None`` significa «usa la configuración global»."""
        server, sender = IrMailServer.find_mail_server(
            'ana@kaupamex.mx', servers=[], notifications_email='')
        assert server is None
        assert sender == 'ana@kaupamex.mx'

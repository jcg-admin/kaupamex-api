"""Integration — los emisores del bus (T-079, H-API-70).

T-077 portó la cola y el punto de extensión, pero **nada emitía**: un ``grep``
de ``BusListenerMixin`` fuera del addon devolvía una sola línea, y era un
docstring. Sin emisores, ``/bus/poll`` devuelve lista vacía para siempre y la
UI que dependiera de él quedaría muerta en silencio.

Estos casos fijan los dos emisores que los tres sondeos de la UI necesitan:

- crear una ``Notification`` deja el evento en el canal de su destinatario;
- un ``Payment`` que alcanza estado terminal deja el evento en el canal del
  comprador de la orden.
"""
import pytest
from addons.bus.models import BusMessage
from addons.bus.services import user_channel
from addons.mail.models import Notification, NotificationType
from addons.payment.models import Payment
from addons.sale.models import SaleOrder
from django.contrib.auth import get_user_model

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

User = get_user_model()


@pytest.fixture
def comprador(db):
    return User.objects.create_user(login='emisor@e.com', password='BusPass123!')


# --- Notificación ----------------------------------------------------------

def test_crear_notificacion_emite_al_canal_del_destinatario(comprador):
    Notification.objects.create(
        user=comprador,
        type=NotificationType.ORDER_UPDATE,
        subject='Orden confirmada #A-1',
        body='Tu orden fue recibida.',
    )

    mensaje = BusMessage.objects.get()
    assert mensaje.channel == user_channel(comprador)
    assert mensaje.payload()['type'] == 'notificacion'
    assert mensaje.payload()['payload']['subject'] == 'Orden confirmada #A-1'


def test_marcar_leida_no_vuelve_a_emitir(comprador):
    """Sólo la creación es un evento; actualizar la fila no lo es."""
    n = Notification.objects.create(
        user=comprador, type=NotificationType.SYSTEM,
        subject='Hola', body='Cuerpo',
    )
    n.read = True
    n.save()

    assert BusMessage.objects.count() == 1


# --- Pago ------------------------------------------------------------------

@pytest.fixture
def pago_pendiente(comprador):
    orden = SaleOrder.objects.create(partner=comprador)
    return Payment.objects.create(
        sale_order=orden, gateway=Payment.GATEWAYS[0][0],
        amount='100.00', status=Payment.STATUS_PENDING,
    )


def test_pago_pendiente_no_emite(pago_pendiente):
    """PENDING no es noticia: el comprador ya está mirando esa pantalla."""
    assert BusMessage.objects.count() == 0


def test_pago_aprobado_emite_al_canal_del_comprador(pago_pendiente, comprador):
    pago_pendiente.status = Payment.STATUS_APPROVED
    pago_pendiente.save()

    mensaje = BusMessage.objects.get()
    assert mensaje.channel == user_channel(comprador)
    assert mensaje.payload()['type'] == 'pago.estado'
    assert mensaje.payload()['payload']['status'] == Payment.STATUS_APPROVED


def test_pago_fallido_tambien_emite(pago_pendiente):
    """El comprador necesita enterarse del rechazo tanto como de la aprobación."""
    pago_pendiente.status = Payment.STATUS_FAILED
    pago_pendiente.save()

    assert BusMessage.objects.get().payload()['payload']['status'] == \
        Payment.STATUS_FAILED


def test_guardar_sin_cambiar_estado_no_reemite(pago_pendiente):
    """Sin transición no hay evento — evita inundar la cola en cada save."""
    pago_pendiente.status = Payment.STATUS_APPROVED
    pago_pendiente.save()
    pago_pendiente.save()

    assert BusMessage.objects.count() == 1


def test_orden_sin_comprador_no_rompe_el_guardado(comprador):
    """Carrito anónimo: sin destinatario no hay canal, y guardar no falla."""
    orden = SaleOrder.objects.create(partner=None)
    pago = Payment.objects.create(
        sale_order=orden, gateway=Payment.GATEWAYS[0][0],
        amount='50.00', status=Payment.STATUS_PENDING,
    )
    pago.status = Payment.STATUS_APPROVED
    pago.save()

    assert BusMessage.objects.count() == 0

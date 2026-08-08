"""Contrato de ``bus`` — puerto de la cola y el mixin (T-077, DEC-AF-06).

Se porta el **concepto** (cola persistida + punto de extensión + lectura por
consulta) y se deja fuera el **transporte** de la referencia, que está atado a
``pg_notify`` de PostgreSQL — mecanismo que MariaDB no tiene. El detalle de por
qué, en ``analisis-transporte-tiempo-real.rst``.

Los casos siguen ``bus/models/bus.py`` de la referencia: ``_sendone`` (``:110``),
``_poll`` (``:170``), ``_gc_messages`` (``:98``) y ``_bus_send`` del mixin
(``bus_listener_mixin.py:16``).

Toca DB → django_db.
"""
import datetime

import pytest
from django.utils import timezone

from addons.base.models import SystemParameter
from addons.bus.models import BusMessage
from addons.bus.mixins import BusListenerMixin

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


# --- sendone: la cola persiste canal + mensaje -----------------------------

def test_sendone_persiste_tipo_y_carga(_):
    BusMessage.sendone('canal-a', 'pago.aprobado', {'order': 7})

    fila = BusMessage.objects.get()
    assert fila.channel == 'canal-a'
    assert fila.payload() == {'type': 'pago.aprobado', 'payload': {'order': 7}}


@pytest.fixture(name='_')
def _seed():
    """Sin datos previos; existe para nombrar la precondición en cada caso."""
    return None


# --- poll: lectura por consulta (la vía que la referencia ya contempla) ----

def test_poll_devuelve_solo_lo_posterior_a_last(_):
    BusMessage.sendone('c1', 't', {'n': 1})
    corte = BusMessage.last_id()
    BusMessage.sendone('c1', 't', {'n': 2})

    salida = BusMessage.poll(['c1'], last=corte)

    assert [m['message']['payload']['n'] for m in salida] == [2]


def test_poll_filtra_por_canal(_):
    BusMessage.sendone('c1', 't', {'n': 1})
    BusMessage.sendone('c2', 't', {'n': 2})

    salida = BusMessage.poll(['c1'], last=0)

    assert [m['message']['payload']['n'] for m in salida] == [1]


def test_poll_sin_last_solo_ve_la_ventana_reciente(_):
    """``last=0`` devuelve el búfer reciente, no la cola entera.

    Es la rama ``if last == 0`` de la referencia (``bus.py:172-174``): una
    pestaña que abre no debe recibir la historia completa del canal.
    """
    viejo = BusMessage.sendone('c1', 't', {'n': 'viejo'})
    BusMessage.objects.filter(pk=viejo.pk).update(
        created_at=timezone.now() - datetime.timedelta(seconds=BusMessage.BUFFER_SECONDS + 10),
    )
    BusMessage.sendone('c1', 't', {'n': 'nuevo'})

    salida = BusMessage.poll(['c1'], last=0)

    assert [m['message']['payload']['n'] for m in salida] == ['nuevo']


def test_poll_respeta_ignore_ids(_):
    a = BusMessage.sendone('c1', 't', {'n': 1})
    BusMessage.sendone('c1', 't', {'n': 2})

    salida = BusMessage.poll(['c1'], last=0, ignore_ids=[a.pk])

    assert [m['message']['payload']['n'] for m in salida] == [2]


def test_last_id_sin_mensajes_es_cero(_):
    assert BusMessage.last_id() == 0


# --- Recolección de basura (bus.py:98-108) ---------------------------------

def test_gc_borra_lo_viejo_y_conserva_lo_reciente(_):
    viejo = BusMessage.sendone('c1', 't', {'n': 'viejo'})
    BusMessage.objects.filter(pk=viejo.pk).update(
        created_at=timezone.now() - datetime.timedelta(days=2),
    )
    BusMessage.sendone('c1', 't', {'n': 'nuevo'})

    borrados = BusMessage._gc_messages()

    assert borrados == 1
    assert [m.payload()['payload']['n'] for m in BusMessage.objects.all()] == ['nuevo']


def test_gc_lee_la_retencion_de_system_parameter(_):
    SystemParameter.objects.update_or_create(
        key='bus.gc_retention_seconds', defaults={'value': '60'},
    )
    reciente = BusMessage.sendone('c1', 't', {'n': 1})
    BusMessage.objects.filter(pk=reciente.pk).update(
        created_at=timezone.now() - datetime.timedelta(seconds=120),
    )

    assert BusMessage._gc_messages() == 1


# --- El mixin: punto de extensión (bus_listener_mixin.py) ------------------

class _Emisor(BusListenerMixin):
    """Modelo ficticio que emite en su propio canal."""

    def __init__(self, clave):
        self.clave = clave

    def _bus_channel(self):
        return self

    def bus_channel_key(self):
        return f'emisor:{self.clave}'


class _Delegado(BusListenerMixin):
    """Delega su canal en otro objeto — la referencia recorre hasta el fijo."""

    def __init__(self, destino):
        self.destino = destino

    def _bus_channel(self):
        return self.destino


def test_bus_send_publica_en_el_canal_propio(_):
    _Emisor('u7')._bus_send('notificacion', {'texto': 'hola'})

    fila = BusMessage.objects.get()
    assert fila.channel == 'emisor:u7'
    assert fila.payload()['type'] == 'notificacion'


def test_bus_send_recorre_la_delegacion_hasta_el_punto_fijo(_):
    """``_bus_channel()`` puede delegar; se emite en el canal del final."""
    _Delegado(_Delegado(_Emisor('u9')))._bus_send('notificacion', {})

    assert BusMessage.objects.get().channel == 'emisor:u9'


def test_bus_send_admite_subcanal(_):
    _Emisor('u7')._bus_send('notificacion', {}, subchannel='pagos')

    assert BusMessage.objects.get().channel == 'emisor:u7/pagos'

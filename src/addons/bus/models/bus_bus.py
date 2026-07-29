"""Modelo ``BusMessage`` — la cola persistida del addon ``bus``.

Adaptación de ``bus.bus`` (``bus/models/bus.py:89-94``). La referencia tiene una
tabla de dos campos —canal y mensaje— y dos formas de leerla: **empuje** por
WebSocket y **consulta** por ``_poll`` (``:170``). DEC-AF-06 adopta la cola y la
consulta, y deja fuera el empuje.

Por qué se corta ahí
====================

El despertar de la referencia es ``pg_notify`` (``bus.py:29``), es decir
``LISTEN``/``NOTIFY`` de PostgreSQL. **MariaDB no tiene equivalente**, así que
no es una omisión por conveniencia: el mecanismo no existe en nuestro motor. Y
la entrega es un bucle ``select()`` que empuja a WebSockets, lo que exigiría
ASGI — incompatible con CNST-ARQ-001 (Apache + mod_wsgi, 30 peticiones
concurrentes).

La referencia **ya contempla** leer por consulta; estamos eligiendo una de sus
dos vías, no inventando una tercera. Si mañana se adopta ASGI, el cambio es de
transporte: la cola y el mixin no se tocan.
"""
import datetime
import json

import fields
import models
from addons.base.models import SystemParameter, TimeStampedModel
from django.utils import timezone

#: Retención por defecto de la cola: 24 h, igual que
#: ``DEFAULT_GC_RETENTION_SECONDS`` (``bus/models/bus.py:26``).
DEFAULT_GC_RETENTION_SECONDS = 60 * 60 * 24

#: Clave de configuración que permite ajustar la retención sin tocar código
#: (la referencia la lee de ``ir.config_parameter``, aquí ``SystemParameter``).
GC_RETENTION_PARAM = 'bus.gc_retention_seconds'


class BusMessage(TimeStampedModel):
    """``bus.bus`` — una notificación encolada para un canal."""

    #: Ventana del primer sondeo. La referencia usa el ``TIMEOUT`` de su
    #: despachador (``bus.py:25``) para acotar qué ve una pestaña que abre:
    #: el búfer reciente, no la historia completa del canal.
    BUFFER_SECONDS = 50

    channel = fields.Char(
        max_length=255, db_index=True,
        help_text='Canal destino (Odoo bus.bus.channel).',
    )
    message = fields.Text(
        help_text='Carga JSON {type, payload} (Odoo bus.bus.message).',
    )

    class Meta:
        db_table = 'bus_bus'
        ordering = ['id']
        verbose_name = 'Mensaje del bus'
        verbose_name_plural = 'Mensajes del bus'

    def __str__(self) -> str:
        return f'{self.channel}#{self.pk}'

    def payload(self) -> dict:
        """Devuelve el mensaje decodificado."""
        return json.loads(self.message)

    # === ESCRITURA =========================================================

    @classmethod
    def sendone(cls, target: str, notification_type: str, message) -> 'BusMessage':
        """Encola ``message`` para ``target`` (Odoo ``_sendone``, ``:110``).

        Usar ``BusListenerMixin._bus_send()`` en vez de esto: el mixin deriva el
        canal del propio registro, de modo que un atacante no puede adivinarlo
        — la misma advertencia que la referencia hace sobre ``_sendone``.
        """
        return cls.objects.create(
            channel=target,
            message=json.dumps({'type': notification_type, 'payload': message}),
        )

    # === LECTURA ===========================================================

    @classmethod
    def poll(cls, channels, last: int = 0, ignore_ids=None) -> list[dict]:
        """Lee los mensajes pendientes de ``channels`` (Odoo ``_poll``, ``:170``).

        Con ``last=0`` devuelve la **ventana reciente**; con ``last=N``, todo lo
        posterior a ese id. Es la rama que la referencia usa para el primer
        sondeo de una pestaña que abre.
        """
        qs = cls.objects.filter(channel__in=list(channels))
        if last == 0:
            qs = qs.filter(
                created_at__gt=timezone.now() - datetime.timedelta(
                    seconds=cls.BUFFER_SECONDS,
                ),
            )
        else:
            qs = qs.filter(pk__gt=last)
        if ignore_ids:
            qs = qs.exclude(pk__in=list(ignore_ids))
        return [
            {'id': fila.pk, 'message': fila.payload()}
            for fila in qs.order_by('id')
        ]

    @classmethod
    def last_id(cls) -> int:
        """Id del último mensaje encolado, o 0 si la cola está vacía."""
        ultimo = cls.objects.order_by('-id').values_list('pk', flat=True).first()
        return ultimo or 0

    # === MANTENIMIENTO =====================================================

    @classmethod
    def gc_messages(cls) -> int:
        """Purga los mensajes vencidos (Odoo ``_gc_messages``, ``:98``).

        La referencia lo cuelga de su ``autovacuum``; aquí es una llamada
        explícita para que el planificador la invoque.

        :return: número de filas borradas.
        """
        retencion = int(
            SystemParameter.get_param(
                GC_RETENTION_PARAM, default=DEFAULT_GC_RETENTION_SECONDS,
            )
        )
        corte = timezone.now() - datetime.timedelta(seconds=retencion)
        borradas, _ = cls.objects.filter(created_at__lt=corte).delete()
        return borradas

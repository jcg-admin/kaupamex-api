"""Caché de idempotencia de request — ``base.CheckoutAttempt``.

Vivía en ``orders.CheckoutAttempt``. Su redomiciliación la dicta
``analisis-estructura-destino-comercial.rst`` (tabla 5, fila
``orders.CheckoutAttempt``): *"Sin análogo — idempotencia de request HTTP, no
dato de dominio comercial. Redomiciliar fuera de ``orders``. Candidatos:
``base`` (utilidad de idempotencia genérica) … pero **no** como parte del grafo
de datos comerciales"*. Se toma el primer candidato.

**Sin análogo en la referencia, y por qué.** El e-commerce de Odoo no necesita
esta caché: su carrito **es** el ``sale.order`` en ``state='draft'``, así que un
reintento del comprador reencuentra el mismo documento en vez de crear otro.
Nuestro checkout expone un endpoint con clave de idempotencia, de modo que este
modelo es **propio, no un puerto** — se declara para que nadie lo lea como
adaptación de algo que allá no existe.

Conserva su nombre y su forma: generalizarlo a una utilidad de idempotencia
sin apellido comercial es una decisión aparte, no parte de este movimiento.
"""
from django.conf import settings
from django.db import models


class CheckoutAttempt(models.Model):
    """Respuesta cacheada de un checkout, por clave de idempotencia. DEC-BC-03."""

    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='checkout_attempts',
    )
    idempotency_key = models.CharField(max_length=100)
    response_json   = models.TextField(default='')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'base_checkout_attempt'
        constraints  = [
            models.UniqueConstraint(
                fields=['user', 'idempotency_key'],
                name='unique_checkout_attempt',
            )
        ]
        verbose_name = 'Intento de checkout'

    def __str__(self):
        return f'{self.user_id}/{self.idempotency_key}'

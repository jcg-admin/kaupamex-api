"""Lo que ``sale`` añade a la pasarela de pago — ≙ ``_inherit``.

Origen: ``odoo19c: sale/models/payment_provider.py`` (LGPL-3 según su
``__manifest__.py``: copia + adaptación con atribución).

Un solo símbolo, y es un campo: ``so_reference_type`` (``:9-14``). Gobierna
**qué referencia viaja al banco** cuando el cliente paga un pedido — el nombre
del documento, o el identificador del cliente. Es configuración de la pasarela,
no del pedido, y por eso vive aquí y no en ``sale.order``.

El destino es :class:`~addons.payment.models.payment_provider.PaymentGateway`,
que es nuestra contraparte de ``payment.provider``.
"""
import fields

from orm.model_classes import extend_model

#: ≙ ``('so_name', 'Based on Document Reference')`` (``odoo19c: :11``). El
#: **valor** es idéntico al de la referencia —es lo que se guarda y se compara—;
#: la etiqueta va en español por ``redaccion-tecnica-es.md``.
SO_REFERENCE_SO_NAME = 'so_name'

#: ≙ ``('partner', 'Based on Customer ID')`` (``odoo19c: :12``).
SO_REFERENCE_PARTNER = 'partner'

#: ≙ el ``selection`` completo (``odoo19c: :10-12``).
SO_REFERENCE_TYPES = [
    (SO_REFERENCE_SO_NAME, 'Según la referencia del documento'),
    (SO_REFERENCE_PARTNER, 'Según el identificador del cliente'),
]

#: ≙ ``string='Communication'`` (``odoo19c: :9``) — el rótulo del campo en la
#: fuente. Se conserva su sentido: es el texto que el cliente ve en su estado de
#: cuenta, no un nombre interno.
SO_REFERENCE_TYPE_VERBOSE_NAME = 'Comunicación'


def apply_sale_payment_provider_extensions():
    """Cuelga ``so_reference_type`` sobre ``payment.provider``.

    La invoca ``SaleConfig.ready()``. Su DDL lo emite
    ``payment/migrations/0002`` — la columna la aporta ``sale``, pero el modelo
    es de la app ``payment`` y ahí es donde Django la escribe.
    """
    extend_model(
        'payment', 'PaymentGateway',
        campos={
            'so_reference_type': fields.Selection(
                max_length=16, choices=SO_REFERENCE_TYPES,
                default=SO_REFERENCE_SO_NAME,
                verbose_name=SO_REFERENCE_TYPE_VERBOSE_NAME,
                help_text='Odoo so_reference_type ("Communication"). Fija el '
                          'tipo de comunicación que aparecerá en los pedidos '
                          'de venta; se le entrega al cliente al elegir el '
                          'método de pago.',
            ),
        },
    )

"""Serializers del backoffice de ventas — UC-ORD-07/09.

``sale_management`` es, en la referencia, el addon del **backoffice**: no
tiene controller propio salvo un ayudante de línea, porque Odoo actúa ahí por
vistas XML y acciones. Nosotros exponemos API, así que la superficie
equivalente es un par de endpoints admin; lo que se conserva es la frontera —
el recorrido del comprador es de ``sale``, la gestión es de aquí.
"""
from rest_framework import serializers

from addons.sale.controllers.serializers import OrderSerializer


class AdminOrderSerializer(OrderSerializer):
    """Detalle de orden para el panel admin.

    Sobre el del comprador añade el correo y el nombre del cliente resueltos
    del FK: el panel los muestra en la lista y, sin ellos, tendría que pedir
    cada usuario por separado. El serializer del comprador no los lleva porque
    ahí el cliente es siempre quien pregunta.
    """
    user_email    = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ['user_email', 'user_username']

    def get_user_email(self, obj) -> str | None:
        return obj.partner.email if obj.partner_id else None

    def get_user_username(self, obj) -> str | None:
        return obj.partner.email if obj.partner_id else None

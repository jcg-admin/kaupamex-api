"""Serializers — addons.authz.

Superficie pública para el cliente admin: las capacidades del usuario
autenticado y el árbol de menú podado por esas capacidades (DEC-08/09).

Los modelos del árbol son ``base.IrUiMenu`` (backoffice) y
``website.WebsiteMenu`` (cuenta del comprador) — la referencia mantiene los dos
separados, ``ir.ui.menu`` y ``website.menu``, en vez de un campo de audiencia.
Por eso el nodo se serializa con un ``Serializer`` plano y no con un
``ModelSerializer``: la forma del payload es una, los modelos son dos.

El **payload no cambia** con la mudanza: los nombres públicos ``label`` /
``icon`` / ``order`` se mapean con ``source=`` a los campos fieles ``name`` /
``web_icon`` / ``sequence``. Renombrar el contrato que consume el SPA es una
decisión aparte de adaptar el modelo, y no se toma de rebote.
"""
from rest_framework import serializers


class MenuNodeSerializer(serializers.Serializer):
    """Nodo del árbol de menú. ``children`` lo fija el manager (ya podado).

    Sirve por igual a ``base.IrUiMenu`` y a ``website.WebsiteMenu``: ambos
    exponen los mismos atributos de nodo.
    """

    key = serializers.CharField(read_only=True)
    label = serializers.CharField(source='name', read_only=True)
    route = serializers.CharField(read_only=True)
    icon = serializers.CharField(source='web_icon', read_only=True)
    order = serializers.IntegerField(source='sequence', read_only=True)
    capability = serializers.CharField(
        source='group.code', default=None, read_only=True,
    )
    children = serializers.SerializerMethodField()

    def get_children(self, obj):
        # ``obj._visible_children`` lo fija ``load_menus_tree`` con el subárbol
        # ya filtrado.
        kids = getattr(obj, '_visible_children', [])
        return MenuNodeSerializer(kids, many=True).data

"""Retira ``WishlistItem`` del estado de ``wishlist`` (movido a website_sale_wishlist).

State-only (``SeparateDatabaseAndState``): la tabla ``wishlist_item`` NO se toca
— la adopta ``website_sale_wishlist.0001_initial``. Aquí sólo se elimina el
modelo del estado de ``wishlist`` para que ``wishlist`` quede como paquete
controlador sin modelos propios. Depende de la migración de
``website_sale_wishlist`` que crea el modelo en su estado, para que el grafo no
quede con el modelo huérfano.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("wishlist", "0001_initial"),
        ("website_sale_wishlist", "0001_initial"),
    ]

    state_operations = [
        migrations.DeleteModel(name="WishlistItem"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=state_operations,
            database_operations=[],
        ),
    ]

"""Señales del núcleo ``base`` — punto de extensión para los addons que
reaccionan a la creación de una credencial.

En Odoo un addon extiende ``res.users`` con ``_inherit`` y sobreescribe
``create()``: ``digest`` auto-suscribe al usuario recién creado
(``digest/models/res_users.py``) sin que ``base`` sepa que ``digest`` existe.
Django no tiene ``_inherit``; su punto de extensión nativo son las señales.
Mismo patrón e idéntica motivación que ``sale/signals.py``: el núcleo
**emite**, el satélite **escucha**, y ``base`` no importa a nadie.
"""
import django.dispatch


# Emitida por ``ResUsersManager._create_user`` **después** de guardar la
# credencial y de aplicar sus grupos.
#
# El momento importa y no es negociable: replica lo que en la referencia ve
# el override de ``create()``. Ahí ``super().create(vals_list)`` devuelve los
# usuarios **con su M2M ``group_ids`` ya escrito** —``group_ids`` es un campo
# de ``res.users`` (``odoo19c: odoo/addons/base/models/res_users.py:257``) y
# viaja dentro de ``vals``—, y por eso el propio ``create`` de la referencia
# puede leer ``user._is_internal()`` (``:583``) y ``user.share`` (``:590``)
# sobre lo que acaba de crear.
#
# ``post_save`` de Django **no** sirve para esto: dispara antes de que el M2M
# pueda existir (sólo se escribe una vez que la fila tiene PK), así que todo
# usuario se ve ``share=True`` ahí y cualquier guard por tipo de usuario corta
# siempre. Ver H-API-304.
#
#   :param sender: la clase ``ResUsers``
#   :param user: la credencial ya creada, con sus grupos aplicados
res_users_created = django.dispatch.Signal()

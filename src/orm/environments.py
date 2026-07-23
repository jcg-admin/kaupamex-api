"""``Environment`` — fiel a ``odoo/orm/environments.py`` (Odoo 19).

En Odoo el ``Environment`` (``self.env``) es el contexto de ejecución que ata
tres cosas a cada recordset: el **cursor** de la transacción (``env.cr``), el
**usuario** actual (``env.uid`` / ``env.user`` / ``env.su`` para sudo) y el
**contexto** (``env.context``, dict de solo lectura). Además indexa los modelos
por nombre (``env['res.partner']``) y cachea registros dentro de la transacción.

Mapeo a Django — **cada pieza del Environment ya existe en Django**, dispersa en
distintos lugares en vez de un único objeto:

=====================  =========================================================
Odoo ``env.*``         Equivalente Django
=====================  =========================================================
``env.cr`` (cursor)    ``django.db.connection`` / ``connections[alias]``;
                       la transacción se maneja con ``transaction.atomic``
``env.uid`` / ``.user``  ``request.user`` (autenticación DRF/Django)
``env.su`` (sudo)      ``user.is_superuser`` / correr sin filtros de permiso
``env.context``        ``request`` + ``get_language()`` (i18n) + kwargs de vista
``env['model.name']``  ``apps.get_model(...)`` / import directo del modelo
cache por transacción  el ORM de Django gestiona su propio caché de queries
=====================  =========================================================

Por eso este archivo es un **stub delgado y documentado, no una
reimplementación**: recrear ``Environment`` sobre Django duplicaría el registro
de apps, el manejo de conexiones y la autenticación que Django ya provee. Un
addon portado que en Odoo escribía ``self.env.user`` se adapta a
``request.user``; ``self.env['res.partner']`` a ``apps.get_model('base',
'ResPartner')`` o al import directo del modelo. Cuando un flujo concreto necesite
azúcar de acceso (p. ej. un helper ``env(request)`` que exponga ``user`` +
``lang`` + ``company``), se añade aquí como conveniencia sobre las piezas
nativas, sin reintroducir el motor.
"""
from django.apps import apps
from django.db import connection, connections

__all__ = ['apps', 'connection', 'connections']

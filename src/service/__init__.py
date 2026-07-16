"""Capa de servicio de infraestructura (hermano de ``orm`` y ``apps``).

Fiel a ``odoo/service/`` de Odoo 19 (hermano de ``odoo/orm/``): aquí vive el
servicio de administración de bases DB-per-company (``db.py`` == ``odoo/service/db.py``),
separado de la máquina ORM (``orm/``, que sólo tiene el binding ORM↔base:
``routers.py``) y del dominio (``apps/``).
"""

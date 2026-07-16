"""Infraestructura ORM multi-DB de la plataforma (hermano de apps).

Sigue la estructura ``orm/`` de Odoo 19 (``odoo/orm/``): aquí vive la maquina
multi-DB DB-per-company (router, y mas adelante el registro L0 + loader +
provisioning), separada del dominio (``apps.*``). Fiel a ``odoo/orm/`` de Odoo 19
(hermano de ``addons``).
"""

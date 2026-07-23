"""Utilidades de infraestructura (hermano de ``service`` y ``orm``).

Fiel a ``odoo/tools/`` de Odoo 19 (hermano de ``odoo/service/`` y ``odoo/orm/``):
utilidades transversales sin dependencia de dominio. El subconjunto que sirve al
multi-DB DB-per-company (SOL-091):

- ``config`` — accesores de las settings ``MULTIDB_*`` (== ``odoo.tools.config``).
- ``sql`` — introspección sobre ``information_schema`` (== ``odoo.tools.sql``).

Coexiste con ``pdf/`` (tooling nativo en C para reportes/recibos, invocado como
binario por subprocess — no es un subpaquete Python importable).
"""

"""Utilidades de infraestructura (hermano de ``service`` y ``orm``).

Fiel a ``odoo/tools/`` de Odoo 19 (hermano de ``odoo/service/`` y ``odoo/orm/``):
utilidades transversales sin dependencia de dominio. El subconjunto que sirve al
multi-DB DB-per-company (SOL-091):

- ``config`` — accesores de las settings ``MULTIDB_*`` (== ``odoo.tools.config``).
- ``sql`` — introspección sobre ``information_schema`` (== ``odoo.tools.sql``).
- ``set_expression`` — álgebra de conjuntos con nombre
  (== ``odoo.tools.set_expression``), con la que ``res.groups`` expresa quién
  tiene un permiso: unión, intersección y complemento sobre grupos declarados.

Los símbolos se importan por su submódulo (``from tools.set_expression import
SetDefinitions``), no por este paquete. La fuente los re-exporta aquí —su
``__init__`` es una fachada— y este árbol no: ninguno de los otros módulos de
``tools/`` se re-exporta tampoco, así que la fachada sería una segunda forma
de nombrar lo mismo.

Coexiste con ``pdf/`` (tooling nativo en C para reportes/recibos, invocado como
binario por subprocess — no es un subpaquete Python importable).
"""

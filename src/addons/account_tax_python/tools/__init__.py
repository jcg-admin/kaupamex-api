"""``tools/`` de ``account_tax_python`` — paquete espejo de la referencia.

La referencia declara ``tools/formula_utils.py`` sin ``__init__.py`` propio
(namespace package implícito, PEP 420 — válido en Python 3 sin marcador).
Aquí se agrega este archivo explícito por consistencia con el resto del
árbol (``no-lazy-imports`` y la convención del proyecto prefieren paquetes
declarados, no implícitos).
"""
from . import formula_utils  # noqa: F401

"""
slos.py — umbrales de Service Level Objective (P95) por grupo de endpoint.

Anclados a los RNF de performance del proyecto:
- RNF-PERF-001 (lectura): catálogo, detalle, carrito → P95 <= 400 ms;
  búsqueda con filtros → P95 <= 600 ms.
- RNF-PERF-002 (escritura): add-to-cart, checkout, crear orden → P95 <= 500 ms.
- RNF-PERF-003 (paginación / agregaciones): listados paginados grandes,
  reportes → P95 <= 1200 ms.

Estos umbrales cierran los 153 AC-07 (performance/concurrencia) a nivel
de NFR: cada grupo de endpoint se valida contra su P95, no AC por AC.

NOTA: confirmar los valores exactos contra
``docs/source/requisitos/requisitos-no-funcionales/rnf-perf-00*.rst``
al implementar; aquí están los SLO declarados a 2026-06-02.
"""
from __future__ import annotations

# Grupo de endpoint -> P95 máximo permitido (milisegundos).
SLO_P95_MS: dict[str, int] = {
    "read_simple": 400,    # RNF-PERF-001: catálogo, detalle, carrito-ver
    "search": 600,         # RNF-PERF-001: búsqueda con filtros
    "write": 500,          # RNF-PERF-002: add-cart, checkout, crear orden
    "pagination": 1200,    # RNF-PERF-003: listados grandes / reportes
}

# Mapeo grupo -> RNF de origen (trazabilidad a los AC-07).
SLO_SOURCE: dict[str, str] = {
    "read_simple": "RNF-PERF-001",
    "search": "RNF-PERF-001",
    "write": "RNF-PERF-002",
    "pagination": "RNF-PERF-003",
}

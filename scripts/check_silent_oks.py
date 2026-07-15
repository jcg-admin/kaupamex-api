#!/usr/bin/env python3
"""
check_silent_oks — gate para silencios de excepción justificados.

Implementa el AC uc-sys-06 (T-021): todo silencio de excepción
(``except ...:`` cuyo cuerpo es SOLO ``pass`` o ``...``) debe llevar una
justificación inline ``# silent OK because <razon>`` en el rango del
handler. Un ``except`` que registra/loguea o re-lanza NO es silencioso y
no se reporta.

Uso:

    # Validar el repo entero (CI):
    python3 scripts/check_silent_oks.py

    # Validar archivos especificos (pre-commit hook con staged files):
    python3 scripts/check_silent_oks.py path/to/a.py path/to/b.py

Exit codes:
    0  -- todo silencio esta justificado (o no hay silencios).
    1  -- hay 1+ silencios sin ``# silent OK because``.
    2  -- error de parseo (algun archivo no es Python valido).

Alcance: ``src/apps/**`` excluyendo ``migrations/``.
NO requiere dependencias externas — solo stdlib.

Equivalente JS/bash (uc-sys-06 menciona "o equivalente en JS/bash"):
pendiente como checker hermano en ui/ y server/ (ver tareas T-021).
"""
from __future__ import annotations

import ast
import pathlib
import sys

JUSTIF = "# silent OK because"


def _is_silent_body(body: list[ast.stmt]) -> bool:
    """True si el cuerpo del handler es solo pass o una constante (... / str)."""
    if len(body) != 1:
        return False
    stmt = body[0]
    if isinstance(stmt, ast.Pass):
        return True
    # ``...`` o un string suelto (docstring-like) también es swallow silencioso
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return True
    return False


def check_file(path: pathlib.Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as exc:  # pragma: no cover
        print(f"PARSE-ERROR {path}: {exc}", file=sys.stderr)
        raise
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if not _is_silent_body(node.body):
            continue
        # rango de lineas del handler (1-based, inclusivo)
        start = node.lineno
        end = getattr(node, "end_lineno", node.lineno) or node.lineno
        block = "\n".join(lines[start - 1:end])
        if JUSTIF.lower() not in block.lower():
            violations.append(f"{path}:{start}: silencio sin '{JUSTIF} <razon>'")
    return violations


def iter_targets(argv: list[str]) -> list[pathlib.Path]:
    if argv:
        return [pathlib.Path(a) for a in argv if a.endswith(".py")]
    root = pathlib.Path(__file__).resolve().parent.parent / "src" / "apps"
    return [p for p in root.rglob("*.py") if "migrations" not in p.parts]


def main(argv: list[str]) -> int:
    targets = iter_targets(argv)
    all_violations: list[str] = []
    for path in targets:
        try:
            all_violations.extend(check_file(path))
        except SyntaxError:
            return 2
    if all_violations:
        print("Silencios de excepción SIN justificación (AC uc-sys-06):")
        for v in all_violations:
            print(f"  {v}")
        print(f"\nTotal: {len(all_violations)}. "
              f"Añade '# silent OK because <razon>' o maneja la excepción.")
        return 1
    print("OK: todo silencio de excepción está justificado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""PreToolUse gate — invocar backend-drf / backend-drf-spectacular.

Convierte en GATE mecanico la prosa del CLAUDE.md de api ("invocarlo al
implementar/modificar endpoints en src/addons/**"). Dispara en CADA
Edit/Write/MultiEdit cuyo objetivo sea codigo Python del monolito modular
(``src/**/*.py``) o sus tests DRF (``tests/**/*.py``), e inyecta un
``additionalContext`` recordando invocar los skills obligatorios ANTES de
escribir. No depende de la memoria del agente.

Alcance (directiva ejecutor 2026-07-24): no solo ``src/addons/**`` — todo lo
que vive en ``src/`` (monolito modular), y todo lo que involucre Django REST
Framework / Python / drf-spectacular. Los tests de integracion tambien, porque
ejercen el contrato DRF (``force_login`` + ``format='json'`` contra MariaDB).

Surfacing NO bloqueante: sale 0 SIEMPRE (nunca rompe el flujo). Es un gate por
ser automatico y disparado en el momento de la accion, no por bloquear —
mismo patron que ``coherence-audit-gate`` / ``flow-selection-agile``.
"""
import json
import os
import sys

DRF_LAYER = {"views.py", "serializers.py", "urls.py", "permissions.py",
             "schema.py"}


def _read_stdin():
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def _target_path(data):
    ti = data.get("tool_input", {}) or {}
    return (ti.get("file_path") or ti.get("path") or "").replace("\\", "/")


def _in_app_python(p):
    if not p.endswith(".py"):
        return False
    return ("/src/" in p or p.startswith("src/")
            or "/tests/" in p or p.startswith("tests/"))


def _is_drf_layer(p):
    base = os.path.basename(p)
    return base in DRF_LAYER or "/views/" in p or "/serializers/" in p


def _message(p):
    if _is_drf_layer(p):
        return (
            "[GATE DRF] Vas a tocar la capa DRF ({0}). ANTES de escribir, "
            "invoca los DOS skills obligatorios:\n"
            "  - `backend-drf`: estilo de vista (FBV vs ViewSet+router, nunca "
            ".as_view({{...}}) manual), autorizacion por CAPACIDAD "
            "(HasCapability fail-closed, NUNCA IsAuthenticated a secas; "
            "permission_map por accion; capacidad nueva -> seed_authz), "
            "canon `codigo_error`, ModelSerializer con Meta.fields explicito, "
            "no-lazy-imports, testing pytest contra MariaDB real.\n"
            "  - `backend-drf-spectacular`: @extend_schema por endpoint "
            "(summary + tags=['<app>'] + responses con codigo_error), "
            "schema.py por app con SPECTACULAR_TAGS (Open/Closed; NO tocar "
            "base.py). Un endpoint sin @extend_schema degrada el OpenAPI "
            "publicado."
        ).format(p)
    return (
        "[GATE monolito modular] Vas a tocar Python del monolito modular "
        "({0}). Invoca `backend-drf` — gobierna las DOS capas: el MODELO usa "
        "el vocabulario de primitivos Odoo (import fields; from "
        "addons.base.models import TimeStampedModel; DEC-FW-01), la capa API "
        "usa DRF. Respeta no-lazy-imports (imports al top del modulo). Si el "
        "cambio toca endpoints/serializers/urls/permisos, invoca ADEMAS "
        "`backend-drf-spectacular`."
    ).format(p)


def main():
    data = _read_stdin()
    p = _target_path(data)
    if not _in_app_python(p):
        print("{}")
        return
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": _message(p),
        }
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Nunca romper el flujo: gate surfacing, no bloqueante.
        print("{}")
    sys.exit(0)

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
ejercen el contrato DRF (``force_login`` + ``format='json'`` contra PostgreSQL).

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


def _huella_de_agente(data):
    """Registra las CLAVES del payload para medir si trae ``agent_id``.

    La documentacion del Agent SDK dice que los hooks **programaticos**
    reciben ``agent_id`` y ``agent_type`` — *"identify which agent fired the
    hook"*. De los hooks de **filesystem** (este) solo dice que disparan *"in
    the main agent and any subagents it spawns"*: donde, no con que campos.

    Sin ``agent_id`` un ``PreToolUse`` no puede expresar "denegar cuando hay
    mas de un agente vivo", que es lo que ``bash-background-tasks.md`` pide y
    hoy es prosa. Medirlo exige que dispare un SUBAGENTE, no la sesion
    principal, asi que el instrumento se instala ahora y el dato llega en la
    proxima tanda. Ver tarea #177 y el analisis del Agent SDK.

    Solo se guardan las claves y los valores de identidad — nunca el
    ``tool_input``, que lleva contenido de archivo. El log es local y
    git-ignored; el hook sale 0 pase lo que pase.
    """
    try:
        registro = {
            "claves": sorted(data.keys()),
            "agent_id": data.get("agent_id"),
            "agent_type": data.get("agent_type"),
            "hook_event_name": data.get("hook_event_name"),
            "session_id": data.get("session_id"),
        }
        destino = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "agent-results", "huella-payload-hook.jsonl")
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except Exception:
        pass


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
            "no-lazy-imports, testing pytest contra PostgreSQL real.\n"
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
    _huella_de_agente(data)   # instrumento de #177; nunca altera el flujo
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

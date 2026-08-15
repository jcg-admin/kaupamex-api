#!/usr/bin/env python3
"""agent_store.py — SQLite embebido local para el manejo de tareas de agentes.

Implementa DEC-03 de la iniciativa ``implementar-base-datos-agentes``
(kaupamex-docs): dos piezas, dos archivos SQLite locales, ninguna toca
``kaupamex_core`` (esa base es de la aplicación, no de tooling).

- Pieza (a) — coordinación en vivo: roster de sesiones de agente dentro
  del contenedor actual. Archivo: agent-results/sesiones.sqlite3.
- Pieza (b) — historial cross-sesión: hallazgos/tareas correlacionables
  entre sesiones, consumidos por la iniciativa KNN. Archivo:
  agent-results/historial.sqlite3.

Ambos archivos viven bajo ``.claude/agent-results/`` — ya gitignored
(``.gitignore:27``) y ya tratado como telemetría local no versionada por
``agent-results-to-docs.md``. Solo stdlib (``sqlite3``): cero
dependencias externas, mismo criterio que D-05 de la iniciativa KNN.
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

STORE_DIR = Path(__file__).resolve().parent.parent / "agent-results"
SESIONES_DB = STORE_DIR / "sesiones.sqlite3"
HISTORIAL_DB = STORE_DIR / "historial.sqlite3"

SESIONES_SCHEMA = """
CREATE TABLE IF NOT EXISTS sesiones_agentes (
    agent_id      TEXT PRIMARY KEY,
    subagent_type TEXT NOT NULL,
    session_id    TEXT NOT NULL,
    status        TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')),
    output_key    TEXT,
    started_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    timeout_at    TEXT
);
"""

HISTORIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS hallazgos_historial (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    hallazgo_id TEXT NOT NULL UNIQUE,
    submodulo   TEXT NOT NULL,
    iniciativa  TEXT NOT NULL,
    resumen     TEXT NOT NULL,
    contenido   TEXT NOT NULL,
    fecha       TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def connect(db_path: Path) -> sqlite3.Connection:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def cmd_init(_args: argparse.Namespace) -> None:
    with connect(SESIONES_DB) as conn:
        conn.execute(SESIONES_SCHEMA)
    with connect(HISTORIAL_DB) as conn:
        conn.execute(HISTORIAL_SCHEMA)
    print(f"OK: {SESIONES_DB} y {HISTORIAL_DB} listos")


def cmd_registrar_sesion(args: argparse.Namespace) -> None:
    ts = now_iso()
    with connect(SESIONES_DB) as conn:
        conn.execute(SESIONES_SCHEMA)
        conn.execute(
            """
            INSERT INTO sesiones_agentes
                (agent_id, subagent_type, session_id, status,
                 output_key, started_at, updated_at, timeout_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                subagent_type = excluded.subagent_type,
                session_id    = excluded.session_id,
                status        = excluded.status,
                output_key    = excluded.output_key,
                updated_at    = excluded.updated_at,
                timeout_at    = excluded.timeout_at
            """,
            (
                args.agent_id,
                args.subagent_type,
                args.session_id,
                args.status,
                args.output_key,
                ts,
                ts,
                args.timeout_at,
            ),
        )
    print(f"OK: sesion {args.agent_id} registrada ({args.status})")


def cmd_actualizar_sesion(args: argparse.Namespace) -> None:
    with connect(SESIONES_DB) as conn:
        conn.execute(SESIONES_SCHEMA)
        cur = conn.execute(
            "UPDATE sesiones_agentes SET status = ?, updated_at = ?, "
            "output_key = COALESCE(?, output_key) WHERE agent_id = ?",
            (args.status, now_iso(), args.output_key, args.agent_id),
        )
        if cur.rowcount == 0:
            print(f"ERROR: agent_id {args.agent_id} no existe", file=sys.stderr)
            sys.exit(1)
    print(f"OK: sesion {args.agent_id} -> {args.status}")


def cmd_listar_sesiones(args: argparse.Namespace) -> None:
    with connect(SESIONES_DB) as conn:
        conn.execute(SESIONES_SCHEMA)
        if args.status:
            rows = conn.execute(
                "SELECT * FROM sesiones_agentes WHERE status = ? ORDER BY started_at",
                (args.status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sesiones_agentes ORDER BY started_at"
            ).fetchall()
    for row in rows:
        print(
            f"{row['agent_id']}  {row['subagent_type']}  {row['status']}  "
            f"started={row['started_at']}  updated={row['updated_at']}"
        )
    print(f"Total: {len(rows)}")


def cmd_agregar_hallazgo(args: argparse.Namespace) -> None:
    with connect(HISTORIAL_DB) as conn:
        conn.execute(HISTORIAL_SCHEMA)
        conn.execute(
            """
            INSERT INTO hallazgos_historial
                (hallazgo_id, submodulo, iniciativa, resumen, contenido, fecha)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(hallazgo_id) DO UPDATE SET
                submodulo  = excluded.submodulo,
                iniciativa = excluded.iniciativa,
                resumen    = excluded.resumen,
                contenido  = excluded.contenido,
                fecha      = excluded.fecha
            """,
            (
                args.hallazgo_id,
                args.submodulo,
                args.iniciativa,
                args.resumen,
                args.contenido,
                args.fecha or now_iso(),
            ),
        )
    print(f"OK: hallazgo {args.hallazgo_id} registrado")


def cmd_buscar_hallazgos(args: argparse.Namespace) -> None:
    like = f"%{args.query}%"
    with connect(HISTORIAL_DB) as conn:
        conn.execute(HISTORIAL_SCHEMA)
        rows = conn.execute(
            "SELECT hallazgo_id, submodulo, iniciativa, resumen FROM hallazgos_historial "
            "WHERE resumen LIKE ? OR contenido LIKE ? ORDER BY fecha DESC",
            (like, like),
        ).fetchall()
    for row in rows:
        print(f"{row['hallazgo_id']}  [{row['submodulo']}/{row['iniciativa']}]  {row['resumen']}")
    print(f"Total: {len(rows)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("init", help="crear ambos archivos SQLite si no existen").set_defaults(
        func=cmd_init
    )

    p = sub.add_parser("registrar-sesion", help="pieza (a): registrar/actualizar una sesion de agente")
    p.add_argument("--agent-id", required=True)
    p.add_argument("--subagent-type", required=True)
    p.add_argument("--session-id", required=True)
    p.add_argument("--status", required=True, choices=["running", "completed", "failed"])
    p.add_argument("--output-key", default=None)
    p.add_argument("--timeout-at", default=None)
    p.set_defaults(func=cmd_registrar_sesion)

    p = sub.add_parser("actualizar-sesion", help="pieza (a): cambiar el status de una sesion existente")
    p.add_argument("--agent-id", required=True)
    p.add_argument("--status", required=True, choices=["running", "completed", "failed"])
    p.add_argument("--output-key", default=None)
    p.set_defaults(func=cmd_actualizar_sesion)

    p = sub.add_parser("listar-sesiones", help="pieza (a): listar sesiones registradas")
    p.add_argument("--status", default=None, choices=["running", "completed", "failed"])
    p.set_defaults(func=cmd_listar_sesiones)

    p = sub.add_parser("agregar-hallazgo", help="pieza (b): registrar un hallazgo/tarea en el historial")
    p.add_argument("--hallazgo-id", required=True)
    p.add_argument("--submodulo", required=True)
    p.add_argument("--iniciativa", required=True)
    p.add_argument("--resumen", required=True)
    p.add_argument("--contenido", required=True)
    p.add_argument("--fecha", default=None)
    p.set_defaults(func=cmd_agregar_hallazgo)

    p = sub.add_parser("buscar-hallazgos", help="pieza (b): buscar hallazgos por texto (LIKE)")
    p.add_argument("--query", required=True)
    p.set_defaults(func=cmd_buscar_hallazgos)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

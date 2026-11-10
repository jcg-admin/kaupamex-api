# Diferencia del store de Thyrox escrita desde VM-x2hokp (2026-11-10)

Fecha: 2026-11-10T04:15:11Z. Para la autoridad de integración de Thyrox (VM-A), por el canal
ya establecido: **TASK-API-0498** (coordinación pendiente con VM-A,
H-API-1186). VM-x2hokp **no** commitea ni retira nada de
`thyrox/agent-results/agent_store.sqlite3` (directiva del ejecutor
2026-11-10).

## Archivo

- Ruta: `thyrox/agent-results/agent_store.sqlite3` (versionado).
- Revisión Git de partida: `5dfeb7fe24` (*Index H-API-1191 in the store*).
- sha256 de la versión de `HEAD`: `82f91b24973358d99cc8c6fed91da0092b6d9c9e220fe4f90240d6f14b922515`.
- sha256 del archivo de trabajo: `71c1e57fce191261c6eaab3e623ac06380996c46541f3a64424ccfcb5631af9e`.
- WAL vacío al medir (0 bytes); el archivo contiene todas las escrituras.
- Método: copia de las dos versiones al scratchpad y comparación por tabla,
  abriendo las copias en sólo lectura. Ninguna escritura sobre el original.

## Contenido de la diferencia — sólo filas añadidas, ninguna retirada

| Tabla | Filas | Procedencia |
|---|---|---|
| `tasks` | +13, −0 | sesión `0390150a-c498-513f-9c46-273b863ccf3b` (VM-x2hokp), `source='task_ids ingest-board'`, citas **TASK-API-0504** … **TASK-API-0516**, ordinales del board 47–60 |
| `findings_history` | +3, −0 | `agent_store agregar-hallazgo` sin `--repo`, 2026-11-10T02:51:41: **H-API-1209**, **H-API-1210**, **H-API-1211** |
| `findings_fts` y sus tablas sombra | índice de texto de las 3 filas anteriores | derivado de `findings_history` |

Ninguna otra tabla difiere. La clave de `tasks` es `(task_id, session_id)`:
las 13 filas conviven con las de otras sesiones que comparten `task_id`
(p. ej. `task_id='27'` tiene 7 filas previas de 7 sesiones) y no
reemplazan ninguna.

## Por qué cayeron en el store del Provider

1. **Tareas.** `task_ids ingest-board` no tiene selector de store: escribe
   siempre en el hogar del Provider. Es también donde viven las citas
   `TASK-API-NNNN` de sesiones anteriores, así que el destino es el
   canónico para tareas; lo que falta es su integración por VM-A.
2. **Hallazgos.** `agent_store agregar-hallazgo` resuelve el destino con
   `resolve_store_dir` (`thyrox: src/agents/agent_store.py:461-505`):
   `--claude-dir` › `--repo` › **hogar de Thyrox**. La ejecución del
   2026-11-10 no declaró `--repo`, y cayó en el hogar. Las de bloques
   anteriores de esta iniciativa declararon `--repo api`: el store de
   `kaupamex-api/.claude/agent-results/agent_store.sqlite3` (no versionado)
   tiene 27 hallazgos de `completar-raiz-orm`, H-API-1209 y H-API-1210
   incluidos (2026-11-09T23:38:38).

Consecuencia: **H-API-1209 y H-API-1210 quedan duplicados** (store de API y
store de Thyrox); **H-API-1211 sólo está en el de Thyrox**. Su autoridad
documental es el `.rst` en `kaupamex-docs` (publicado en
`3600e4ef0`).

## Lo que se pide a VM-A, y lo que no se hace desde aquí

- Integrar las 13 filas `tasks` (identidad canónica `TASK-API-0504…0516`).
- Decidir sobre las 3 filas `findings_history`: su hogar en esta
  iniciativa es el store de API; retirarlas del de Thyrox, o conservarlas,
  es decisión de VM-A.
- Desde VM-x2hokp: ninguna escritura más sobre ese store; sin fusiones por
  identificador numérico; sin copia de filas entre bases.

## Pendiente de autorización en este nodo

El índice de H-API-1211 en el store de API (`agent_store agregar-hallazgo
--repo api`) fue rehusado por el clasificador de permisos al intentarlo; no
se reintentó ni se rodeó. Queda pendiente de autorización del ejecutor.

## Brecha del Provider, para VM-A

`agent_store agregar-hallazgo` sin `--repo` escribe en el hogar del
Provider aunque el hallazgo sea de un consumidor con store propio: el
destino depende de que quien llama se acuerde del parámetro. La regla de
`.claude/CLAUDE.md` (paso 5) no menciona `--repo`. No se corrige desde
esta VM.

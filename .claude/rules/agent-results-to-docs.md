```yml
type: Convención de Proyecto
category: Captura de resultados de subagentes
version: 1.0.0
created_at: 2026-06-02T07:00:34
applies_to: e-comerce v1.0.0+
```

# Resultados de subagentes — captura automática (hook SubagentStop)

> Cargado automáticamente. Origen: directiva del ejecutor 2026-06-02
> ("ya no sé qué hizo cada agente"). Implementado como **hook**, no como
> memoria — solo un hook dispara en respuesta a un evento.

## Qué hace

Cada vez que termina un subagente (tool `Agent`/`Task`), el hook
`SubagentStop` ejecuta `node .claude/hooks/save-agent-result.mjs`, que:

1. Lee el payload del subagente por stdin (campo `transcript_path`).
2. Extrae el **último mensaje del asistente** (el reporte final del agente)
   de ese transcript JSONL.
3. Lo apende, con timestamp ISO real (`new Date()`, no de memoria), a
   `.claude/agent-results/registro-de-agentes.md` (append-only).

El script **nunca rompe el flujo**: traga todo error y sale 0.

## Dónde está cada pieza

| Pieza | Ruta | Versionado |
|---|---|---|
| Hook | `.claude/settings.json` → `hooks.SubagentStop` | sí |
| Script | `.claude/hooks/save-agent-result.mjs` | sí |
| Regla (este doc) | `.claude/rules/agent-results-to-docs.md` | sí |
| Log raw | `.claude/agent-results/registro-de-agentes.md` | **NO** (gitignored) |

El **mecanismo** se versiona; el **log raw** no (telemetría local
append-only — evitar churn de commits).

## Relación con `registro-reportes-agentes.md`

Son complementarios, distinto nivel:

- **Este hook (raw):** captura automática y de bajo nivel del reporte final
  de TODO subagente. Telemetría local; no se pierde dentro de la sesión.
- **`registro-reportes-agentes.md` (curado):** reportes analíticos
  deliberados (inventarios, audits) que el propio subagente persiste como
  `reporte-<slug>.rst` en `docs/` con cabecera de procedencia.

El raw es la red para "no perder nada"; el curado es el artefacto de
gobierno. Si un análisis importa, va a docs como `reporte-*.rst`, no se
queda solo en el log raw.

## Verificación

```bash
# El hook está en settings.json y el JSON es válido:
jq -e '.hooks.SubagentStop[].hooks[].command' .claude/settings.json
# Pipe-test del script (sin esperar a un subagente real):
printf '{"session_id":"t","transcript_path":"/tmp/t.jsonl"}' \
  > /dev/null  # (ver el pipe-test del commit de implementación)
```

## Activación (caveat del watcher)

El watcher de Claude Code solo vigila `.claude/` si había un `settings.json`
al **arranque** de la sesión. Como ya existía, el hook debería tomarse en la
próxima sesión; para forzar la recarga ahora: abrir `/hooks` una vez o
reiniciar. Los subagentes de la sesión en que se creó el hook pueden no
auto-registrarse hasta esa recarga.

## Severidad

**MEDIA** — sin el hook, el reporte final de cada subagente vive solo en su
transcript y se pierde de vista; con él, queda en un log consultable. No es
bloqueante (el script nunca rompe el flujo), pero su ausencia reintroduce el
problema "no sé qué hizo cada agente".

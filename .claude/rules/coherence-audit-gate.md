```yml
type: Convención de Proyecto
category: Auditoría de coherencia — gate automático (hook SessionStart)
version: 1.0.0
created_at: 2026-06-03T01:05:00
applies_to: e-comerce v1.0.0+
origen: directiva ejecutor 2026-06-03 ("audit como gate automático")
```

# Auditoría de coherencia — gate automático

> Cargado automáticamente. Origen: tras adaptar `thyrox-audit` de
> NestorMonroy/thyrox, el ejecutor pidió que el audit fuera **gate
> automático**, no un comando que hay que recordar. Mismo patrón que
> `flow-selection-agile.md` y `agent-results-to-docs.md`: comportamiento
> automático = hook, no memoria.

## Qué hace

Un hook `SessionStart` (`.claude/hooks/inject-coherence-audit.sh`) corre la
auditoría mecánica (`.claude/scripts/thyrox-audit.sh --fast`) e **inyecta el
score** de coherencia del repo al inicio de **cada sesión**. Así el tool
`/thyrox:audit-coherence` se **usa siempre** (no queda como capacidad muerta
— el problema que `flow-selection-agile.md` describe).

Surfacing **no bloqueante**: el hook sale 0 siempre. El modo `--fast` omite el
gate lento de referencias (lo corre el comando completo).

## Piezas

| Pieza | Ruta | Qué hace |
|---|---|---|
| Script | `.claude/scripts/thyrox-audit.sh` | motor mecánico (6 gates) |
| Hook | `.claude/hooks/inject-coherence-audit.sh` | corre `--fast`, inyecta score |
| Wiring | `.claude/settings.json` → `hooks.SessionStart` (4º command) | dispara al inicio |
| Comando | `.claude/commands/audit-coherence.md` → `/thyrox:audit-coherence` | run full + triage + reporte a docs |
| Reporte | `docs/source/gestion/pm/docs/audits/reporte-auditoria-coherencia-<fecha>.rst` | salida persistida (NO audit-report.md suelto) |

## Gates del script

1. Referencias (markdown links rotos) — omitido en `--fast`.
2a. Lenguaje muerto **duro** (tokens ``arc42``, ``.claude``-prds,
    ``.claude``-epics, ``task``-create) → FAIL.
2b. **Candidatos a deriva** (tokens ``pm``-thyrox, ``.thyrox``-context,
    ``ROADMAP``, ``now`` md, ``type``-scope) → WARN + triage cualitativo
    (muchas son notas de adaptación legítimas).
3. SMD anti-staleness (`:commit_referencia:` vs docs HEAD; fecha > 7 días).
4. Anatomía del skill `thyrox`.
5. Coherencia parent ↔ submódulos (gitlink vs clon hermano; `gitlink-bump-gate`).
6. Fechas fabricadas (THH:00:00) en canónicos.

## Por qué surfacing y no pre-push bloqueante (todavía)

Un gate **bloqueante** (`--strict` en pre-push/CI) marcaría rojo el día 1 por
deuda **pre-existente** (F-COH-01: 15 broken links de 892, ver el reporte de
auditoría). Bloquear todo push por deuda heredada es contraproducente. Por eso
hoy el gate es **surfacing automático** (visibilidad cada sesión). Graduar a
`--strict` en un githook `pre-push` o workflow CI **cuando F-COH-01 esté en 0**.

## Verificación

```bash
# El hook está en settings.json y emite JSON válido:
jq -e '.hooks.SessionStart[].hooks[] | select(.command|test("inject-coherence-audit")) | .command' .claude/settings.json
echo '{}' | bash .claude/hooks/inject-coherence-audit.sh | jq -e '.hookSpecificOutput.additionalContext' >/dev/null && echo OK
# Auditoría completa manual:
bash .claude/scripts/thyrox-audit.sh          # reporte
bash .claude/scripts/thyrox-audit.sh --strict # exit 1 si FAIL
```

## Activación (caveat del watcher)

El watcher de Claude Code solo recarga `settings.json` si existía al arranque
de la sesión (ya existía). El nuevo command del SessionStart puede no tomarse
hasta la próxima sesión o tras abrir `/hooks` una vez.

## Severidad

**MEDIA** — sin el hook, el audit depende de que alguien recuerde correr
`/thyrox:audit-coherence`; con el hook, la coherencia se reporta en cada
sesión. No bloqueante (el hook sale 0 siempre).

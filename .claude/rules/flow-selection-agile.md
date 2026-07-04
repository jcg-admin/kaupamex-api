```yml
type: Convención de Proyecto
category: Selección de metodología (flow) — adopción de skills ágiles
version: 1.0.0
created_at: 2026-06-02T18:50:29
applies_to: e-comerce v1.0.0+
origen: directiva ejecutor 2026-06-02 ("¿cómo aseguras que se usen estas metodologías? NO QUEREMOS NADA PENDIENTE")
```

# Selección de flow — adopción automática de Scrum/Kanban

> Cargado automáticamente en cada sesión. Origen: tras crear los
> namespaces `scrum:` y `kanban:` (iniciativa
> `agregar-metodologias-agiles-thyrox`), el ejecutor señaló que crear
> los skills no garantiza que se usen — un skill registrado pero nunca
> seleccionado es deuda, no capacidad.

## El problema que esta regla resuelve

Un methodology skill se invoca cuando un work package declara un `flow:`
y THYROX activa los skills anclados a ese flow+stage. Si nadie
**selecciona** `flow: scrum` o `flow: kanban`, los 10 skills nuevos
quedan muertos. La documentación pasiva (tabla + guía) no dispara nada
por sí sola.

## Mecanismo de adopción (tres capas)

1. **Registro** — `scrum:`/`kanban:` están en la tabla de namespaces de
   `.claude/skills/thyrox/SKILL.md` (13 namespaces) con sus stages de
   anclaje. THYROX sabe que existen.
2. **Selección** — la lista "Selección por necesidad" de
   `thyrox/SKILL.md` incluye los criterios:
   - desarrollo ágil iterativo en Sprints → `scrum-*`
   - flujo continuo / mantenimiento sin iteraciones → `kanban-*`
   Más las "Entradas rápidas por namespace" (menú de acceso).
3. **Activación automática (hook)** — un hook `SessionStart`
   (`.claude/hooks/inject-flow-selection.sh`) inyecta en CADA sesión un
   `additionalContext` recordando consultar la selección de flow,
   nombrando explícitamente `scrum-*` y `kanban-*`. Esto es lo que
   convierte la capacidad en comportamiento: no depende de que el
   agente "recuerde" que existen.

## Piezas

| Pieza | Ruta | Qué hace |
|---|---|---|
| Hook | `.claude/settings.json` → `hooks.SessionStart` (3er command) | dispara al inicio de sesión |
| Script | `.claude/hooks/inject-flow-selection.sh` | emite JSON con `additionalContext`; sale 0 siempre |
| Registro+selección | `.claude/skills/thyrox/SKILL.md` | tabla de namespaces + "Selección por necesidad" + entradas rápidas |
| Guía | `docs/source/gestion/pm/guias/metodologias-agiles.rst` | criterios Scrum vs Kanban vs PMBOK + anclaje a 12 stages |

## Verificación

```bash
# El hook está en settings.json y el JSON es válido:
jq -e '.hooks.SessionStart[].hooks[] | select(.command|test("inject-flow-selection")) | .command' .claude/settings.json
# El script emite additionalContext y sale 0:
echo '{}' | bash .claude/hooks/inject-flow-selection.sh | jq -e '.hookSpecificOutput.additionalContext' >/dev/null && echo OK
```

## Activación (caveat del watcher)

El watcher de Claude Code solo recarga `.claude/settings.json` si existía
al arranque de la sesión (ya existía). El nuevo command del SessionStart
puede no tomarse hasta la próxima sesión o tras abrir `/hooks` una vez.

## Severidad

**MEDIA** — sin la capa 3 (hook), las metodologías ágiles dependerían de
que el agente recuerde consultarlas; con el hook, se ofrecen en cada
sesión. No es bloqueante (el command sale 0 ante cualquier error), pero
su ausencia reintroduce el problema "skills creados pero nunca usados".

## Relación con otras reglas

- `agent-results-to-docs.md`: mismo patrón (comportamiento automático =
  hook, no memoria).
- `principio-rector-rup-arquitectura.md`: la selección de flow es parte
  del análisis previo a ejecutar, no un paso opcional.

---
name: Loop THYROX
description: Ejecución continua de Phase 10 EXECUTE — continúa automáticamente el work package activo sin intervención. Usar con /loop para auto-avanzar tareas T-NNN. STOP automático ante gates humanos.
---

# /thyrox:loop — Ejecución continua THYROX

Ejecuta la siguiente tarea pendiente del work package activo. Diseñado para usarse con `/loop`:

```
/loop 10m /thyrox:loop
```

---

## Instrucciones de ejecución

### 1. Verificar contexto

Identificar la iniciativa activa (en kaupamex el estado **no** vive en
`.thyrox/`): el `progreso-<slug>.rst` más reciente bajo
`docs/source/gestion/pm/<submodulo>/iniciativas/`, situado con el SMD
(`docs/source/gestion/pm/siguiente-mejor-decision.rst`).
- Si la fase activa ≠ EXECUTE/IMPLEMENT (Phase 10) → STOP: reportar "Loop
  detenido: la iniciativa activa no está en EXECUTE. Usar `/thyrox:execute`
  para avanzar manualmente."
- Si no hay iniciativa activa → STOP: reportar "Loop detenido: sin
  iniciativa activa. Usar `/thyrox:discover` para iniciar."

### 2. Encontrar la siguiente tarea

Leer el `tareas-<slug>.rst` de la iniciativa activa:
- Encontrar la primera tarea pendiente `[ ] T-NNN`
- Si no hay tareas pendientes → STOP: reportar "EXECUTE completa — todas las
  tareas `[x]`. Usar `/thyrox:track`."
- Si la próxima tarea tiene `[GATE]` → STOP: reportar "Gate humano detectado
  en `{T-NNN}`. Revisar y aprobar manualmente antes de continuar el loop."

### 3. Ejecutar la tarea

1. Leer la descripción de la tarea y el UC/spec referenciado
2. Verificar que las dependencias anteriores estén `[x]`
3. Implementar el cambio (respetar tech skills activos + `.claude/rules/`)
4. Si falla → registrar el episodio según
   `.claude/rules/memoria-episodica-fallos.md` (en
   `lecciones-aprendidas/`) y STOP: reportar el error

### 4. Commit y actualizar

1. Commit estilo **Tim Pope** (subject imperativo ≤50 ch, sin punto; body
   QUÉ/POR QUÉ; `Refs: T-NNN`) — ver `.claude/rules/commit-conventions.md`.
   **NO** Conventional Commits (`type(scope):` está prohibido desde ÉPICA 4).
2. Actualizar el checkbox de la tarea en `tareas-<slug>.rst`: `[ ]` → `[x]`
3. Anotar el avance en `progreso-<slug>.rst` con timestamp real
   (`date -u +"%Y-%m-%dT%H:%M:%S"`)
4. Si el commit fue en un submódulo, **bumpear el gitlink** del superproyecto
   (`.claude/rules/gitlink-bump-gate.md`)

### 5. Reportar

Reportar en una línea: `[T-NNN] ✓ {descripción} — {N} tareas restantes`

Si quedan tareas → el loop continuará en el próximo ciclo.
Si no quedan tareas → reportar compleción y proponer `/thyrox:track`.

---

## Reglas de STOP

El loop se detiene automáticamente cuando:

| Condición | Mensaje |
|-----------|---------|
| `phase` ≠ `Phase 10` | "Fase `{phase}` no es ejecutable con loop" |
| Sin WP activo | "Sin WP activo" |
| Tarea con `[GATE]` | "Gate humano en `{T-NNN}`" |
| Error en implementación | "ERR: `{descripción del error}`" |
| Todas las tareas `[x]` | "Phase 10 completa" |
| Tarea `irreversible` | "Tarea irreversible requiere aprobación manual" |

> Ausencia de respuesta ≠ aprobación. Si el usuario no responde, esperar — no auto-continuar.

---

## Uso recomendado

```bash
# Auto-continuar Phase 10 cada 10 minutos
/loop 10m /thyrox:loop

# Para WPs grandes con muchas tareas
/loop 5m /thyrox:loop

# Para sesiones nocturnas (ejecutar cada 30 min)
/loop 30m /thyrox:loop
```

> Requiere que el task-plan no tenga gates humanos en las tareas pendientes.
> Para WPs con gates obligatorios, usar solo para el batch de tareas entre gates.

Ver [scheduling](../skills/workflow-implement/references/scheduling.md) para patrones avanzados.

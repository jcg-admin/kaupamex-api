```yml
type: Regla de Proyecto
category: Operación del agente — gate de skills DRF/spectacular (hook PreToolUse)
version: 1.0.0
created_at: 2026-07-24T20:39:22
applies_to: kaupamex v1.0.0+ (api)
origen: directiva ejecutor 2026-07-24 ("El CLAUDE.md de api ya ordena
  'invocarlo al implementar/modificar endpoints en src/addons/**', pero es
  prosa, no un gate. Haz que sea un gate y que no solo sea en src/addons/**,
  sino a todo lo que vive en src/ o cosas que involucren Django REST Framework,
  o Python, o drf_spectacular, monolito modular, etc.")
```

# Gate de skills DRF / drf-spectacular — hook PreToolUse

> Cargado automáticamente en cada sesión. Convierte en **gate mecánico** la
> prosa del CLAUDE.md de api ("invocarlo al implementar/modificar endpoints en
> `src/addons/**`"). Mismo patrón que `coherence-audit-gate` /
> `flow-selection-agile` / `agent-results-to-docs`: **comportamiento automático
> = hook, no memoria**.

## El problema que esta regla resuelve

El CLAUDE.md de api pedía "invocar el skill `backend-drf` al tocar endpoints"
en **prosa**. La prosa depende de que el agente lo recuerde — y el propio
ejecutor observó que no se cumplía (los endpoints de billing slice 3 se
escribieron sin `@extend_schema`, difiriendo la parte spectacular). Un skill
que "hay que acordarse de invocar" es deuda, no capacidad. Sólo un gate
integrado en el flujo lo hace fiable.

## Qué hace

Un hook **`PreToolUse`** (`.claude/hooks/inject-drf-skill-gate.py`, matcher
`Edit|Write|MultiEdit`) inspecciona el `file_path` del objetivo. Si es Python
del **monolito modular** — `src/**/*.py` o `tests/**/*.py` — inyecta un
`additionalContext` que recuerda invocar los skills obligatorios **ANTES** de
escribir:

- **Capa DRF** (`views.py` / `serializers.py` / `urls.py` / `permissions.py` /
  `schema.py`, o rutas `/views/` `/serializers/`) → recuerda invocar **ambos**
  `backend-drf` **y** `backend-drf-spectacular`.
- **Resto de Python del monolito** (modelos, servicios, etc.) → recuerda
  invocar `backend-drf` (cubre la separación de dos capas: modelo con
  vocabulario de primitivos Odoo DEC-FW-01, API con DRF) + no-lazy-imports; y
  `backend-drf-spectacular` si el cambio toca la capa DRF.

**Surfacing NO bloqueante:** el hook sale 0 SIEMPRE (nunca rompe el flujo). Es
un *gate* por ser **automático y disparado en el momento de la acción**, no por
bloquear — el hook es stateless y no puede saber si el skill ya se invocó en la
sesión, así que un bloqueo duro sería inviable. El disparo per-edit es más
fuerte que un recordatorio `SessionStart` (que se dispara una vez y se olvida).

## Alcance (por directiva del ejecutor)

No sólo `src/addons/**`: **todo lo que vive en `src/`** (monolito modular) y
**todo lo que involucre Django REST Framework / Python / drf-spectacular**. El
matcher cubre `src/**/*.py` (los addons: modelos, vistas, serializers, urls,
permisos, esquema, servicios) y `tests/**/*.py` (los tests de integración
ejercen el contrato DRF: `force_login` + `format='json'` contra MariaDB). Queda
fuera el tooling de `.claude/` y los `.rst` de docs (no son código de app).

## Piezas

| Pieza | Ruta | Qué hace |
|---|---|---|
| Hook | `.claude/settings.json` → `hooks.PreToolUse` (matcher `Edit\|Write\|MultiEdit`) | dispara antes de cada edición |
| Script | `.claude/hooks/inject-drf-skill-gate.py` | parsea `tool_input.file_path`; emite `additionalContext` o `{}`; sale 0 siempre |
| Skills | `.claude/skills/backend-drf/` · `.claude/skills/backend-drf-spectacular/` | el contenido que el gate recuerda invocar |
| Regla (este doc) | `.claude/rules/drf-skill-gate.md` | documenta el gate |

## Verificación

```bash
# El hook está en settings.json y el JSON es válido:
python3 -c "import json;d=json.load(open('.claude/settings.json'));\
print(d['hooks']['PreToolUse'][0]['hooks'][0]['command'])"

# Dispara sobre capa DRF (views.py) — additionalContext presente:
printf '{"tool_input":{"file_path":"src/addons/company/views.py"}}' \
  | python3 .claude/hooks/inject-drf-skill-gate.py

# Silencioso sobre no-código de app (docs .rst) → {}:
printf '{"tool_input":{"file_path":"source/foo.rst"}}' \
  | python3 .claude/hooks/inject-drf-skill-gate.py

# Nunca rompe el flujo (stdin vacío → {} exit 0):
printf '' | python3 .claude/hooks/inject-drf-skill-gate.py; echo "exit=$?"
```

## Activación (caveat del watcher)

El watcher de Claude Code sólo recarga `.claude/settings.json` si existía al
arranque de la sesión (ya existía). El nuevo `PreToolUse` puede no tomarse
hasta la próxima sesión o tras abrir `/hooks` una vez. Hasta entonces, la
obligación sigue vigente por prosa (este doc + CLAUDE.md).

## Severidad

**MEDIA** — sin el gate, la invocación de `backend-drf`/`backend-drf-spectacular`
depende de que el agente la recuerde; con él, se recuerda automáticamente en
cada edición de código de app. No bloqueante (sale 0 siempre), pero su ausencia
reintroduce el defecto observado (endpoints sin `@extend_schema`).

## Relación con otras reglas

- `coherence-audit-gate.md` / `flow-selection-agile.md` / `agent-results-to-docs.md`:
  mismo patrón (comportamiento automático = hook).
- `no-lazy-imports.md`: uno de los invariantes que el gate recuerda.
- Skills `backend-drf` y `backend-drf-spectacular`: el contenido invocado.

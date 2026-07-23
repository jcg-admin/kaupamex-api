```yml
type: Reference (lazy-load on-demand)
applies_when: Se evalúa generar un cliente desde el schema, o se ajustan settings de componentes/enums/tipos que afectan a un generador
created_at: 2026-07-18 03:48:19
status: Aprobado
version: 1.0.0
source: drf-spectacular client generation
```

# Client generation — settings de compatibilidad (el proyecto NO genera cliente)

> drf-spectacular prioriza un schema **preciso**; algunos settings sacrifican
> precisión para contentar a un **generador de clientes**. Contexto del proyecto:
> **no se genera cliente** desde el schema — la UI usa un `apiService.js`
> escrito a mano (PROVEN 2026-07-18: 0 openapi-codegen en `ui/package.json`). El
> schema es para **documentación** (Swagger/Redoc). Por eso los knobs de
> compatibilidad se dejan en su **default preciso**.

## El único ajuste pro-cliente que sí está — `COMPONENT_SPLIT_REQUEST`

El TL;DR del doc ("`COMPONENT_SPLIT_REQUEST: True` da el mejor cliente") **ya está
activo** (`base.py:382`, PROVEN) — pero aquí se adopta por su **beneficio de
precisión**, no por un generador: separa request/response, resolviendo los
problemas de `required`/`readOnly`/`writeOnly` (p.ej. un `id` `readOnly` que no
debe pedirse en el `POST`). `COMPONENT_SPLIT_PATCH: True` (`base.py:384`) es
default y también está — `PATCH` y `POST` chocan en `required` y no se modelan con
un solo componente. Ver `spectacular-settings.md`.

## Los knobs de compatibilidad que se dejan en default (0 overrides)

PROVEN 2026-07-18 (0 override en `base.py` → default de drf-spectacular):

| Setting | Default (activo) | Qué haría cambiarlo | Por qué NO se toca |
|---|---|---|---|
| `COMPONENT_NO_READ_ONLY_REQUIRED` | `False` | quitar `required` de campos `readOnly` **sin** split | `COMPONENT_SPLIT_REQUEST` ya resuelve el problema con mayor precisión — el doc lo prefiere |
| `ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE` | `True` | quitar las choices `blank`/`null` explícitas (schema menos preciso) | sin generador que "se ofenda", conviene el schema correcto |
| `GENERIC_ADDITIONAL_PROPERTIES` | `'dict'` | emitir `additionalProperties` como `bool`/`None` | idem — es sensibilidad de generadores, no aplica |

**Regla:** no activar estos "por si acaso". Bajan la precisión del schema y solo
tienen sentido si aparece un **generador concreto** que tropiece. Hoy no lo hay.

## Si en el futuro se genera un cliente

1. **Primero** `COMPONENT_SPLIT_REQUEST` (ya está) — cubre casi todo.
2. Solo si el generador **concreto** falla, activar el knob mínimo necesario
   (`ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE=False` o `GENERIC_ADDITIONAL_PROPERTIES`)
   — documentando qué generador lo exige.
3. **Arreglar todos los warnings** de generación primero (un warning suele ser un
   cliente incorrecto).

## Gap conocido — el gate `--validate --fail-on-warn` NO está cableado

El doc recomienda para CI::

    ./manage.py spectacular --file schema.yaml --validate --fail-on-warn

PROVEN 2026-07-18: **0** en `Makefile`/`.githooks`/CI. Hoy la generación se
verifica vía `check --deploy` (default-ON, ver `spectacular-settings.md`), que
emite los warnings pero **no** falla el build por ellos. Graduar a
`--validate --fail-on-warn` en CI es la mejora natural **cuando** los warnings
estén en 0 (mismo criterio de graduación surfacing→bloqueante que otros gates del
proyecto). No cablearlo con deuda de warnings pendiente (marcaría rojo por deuda
heredada).

## Referencias cruzadas

- `spectacular-settings.md` — `COMPONENT_SPLIT_REQUEST/PATCH` (fijados) + defaults
  heredados + el gate `check --deploy`.
- `customization.md` — arreglar los warnings antes de confiar en el schema/cliente.
- `enum-overrides` (por pieza) — los enums, la otra fuente de fricción de cliente.
- Código: `config/settings/base.py:382,384` (`COMPONENT_SPLIT_REQUEST/PATCH`).
```

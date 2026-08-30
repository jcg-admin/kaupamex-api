# `scripts/workbench/` — el trabajo instrumentado de api

Un directorio por pieza de trabajo, con su instrumento, su evidencia y el
destino de lo que produce. Fechado, reproducible, y **no se borra**: la
evidencia de una medición vale tanto como su conclusión.

```
scripts/workbench/<slug>-<ISO>/
├── README.md            la pregunta, la premisa y su corrección, el veredicto
├── manifest.json        el mismo contenido en forma verificable
├── <instrument>.py      lo que mide o transforma
├── tests/               escritos ANTES del instrumento (TDD)
├── probes/              sondas de una pregunta suelta, no del camino principal
└── outputs/             las salidas fechadas — el registro de la secuencia
```

`<ISO>` es `date -u +%Y%m%dT%H%M%S`, obtenido en el mismo turno en que se usa
(`timestamps-iso8601-obligatorios.md`). El slug describe el trabajo, no su
resultado: al empezar todavía no se sabe cuál es.

## De dónde sale esto, y por qué no se llama «eventos»

El mecanismo lo estrenó `kaupamex-docs` en `.claude/eventos/`, y **su
convención sigue siendo la fuente**: `docs: .claude/eventos/README.md` (dos
formas —generador de corpus y medición con TDD—, la anatomía completa y las
prohibiciones). Este archivo no la repite: declara lo que cambia para api.

Los 99 trabajos de docs **se quedan donde están**, con sus rutas citadas
intactas. Esto no es una migración: es el mismo mecanismo con hogar propio.

Lo que sí cambia es el nombre, porque «evento» ya significa **otras dos cosas
en este mismo árbol**, y las dos están documentadas:

| Sentido | Dónde vive | Tamaño |
|---|---|---|
| **el de Claude Code** | `docs: source/base-cognitiva/hooks-claude-code/` — *«los 31 eventos que el binario declara»* | 33 documentos `hook-*.rst`: `SessionStart`, `PreToolUse`, `SubagentStop`, `TaskCompleted`, `PreCompact`… |
| **el telemétrico** | los `tengu_*` del ejecutable | 2025 nombres reales |
| **la pieza de trabajo** | `docs: .claude/eventos/` | 99 directorios |

El primero es el dueño legítimo del nombre: es el término del propio cliente.
Y la colisión no es teórica — tres directorios de docs la encarnan:

- `hooks-claude-code-20260819T201332` — el evento que **genera** el documento
  sobre los eventos de Claude. Su índice lo cita en la línea 31.
- `hooks-binario-20260821T063349` — el evento que **mide** esos eventos en el
  ejecutable.
- `extraer-eventos-telemetricos-20260824T053003` — un evento sobre eventos.

**Workbench** nombra lo que esto es: el banco donde se construye el
instrumento, se usa, y el producto sale hacia su destino mientras la
herramienta se queda. Medido contra colisión antes de elegirlo — 0 hits en el
ejecutable, en Django, en DRF y en `src/`; `operations` da 93 en Django y 329
aquí (migrations), `jobs` 53 en el ejecutable (`ir.cron`), `campaign` 14 en el
ejecutable, `generators` choca con el generador de Python y `workshops` con la
skill `workshop` del harness.

*Métrica:* ocurrencias del literal entrecomillado en el ejecutable, archivos
que lo nombran en `django/` y `rest_framework/`, y archivos de `src/`+`addons/`.
*Ciega a:* un sentido que el cliente use sin literal, y a la documentación web
de Anthropic, que no se midió.

## Qué es una pieza de trabajo, y qué no

La triple que la define es **instrumento → medición → destino**. No es un
estudio: de aquí salen cosas, y el manifiesto declara cuáles.

Es una pieza de trabajo cuando: hay una pregunta que exige construir algo para
responderla, la respuesta se publica en algún sitio, y alguien tendrá que
poder re-correrla.

**No** lo es: un gate estable (va a `scripts/check_*.py`), un instrumento
reusable (va a `scripts/`), un documento (va a `kaupamex-docs/source/**`), ni
un comando de una línea cuya salida cabe en el turno.

## La frontera con `scripts/`

| Vive en | Qué es |
|---|---|
| `scripts/*.py` | instrumento **estable y reusable** — los gates, `reference_roots.py`, los censos que se vuelven a correr |
| `scripts/workbench/<slug>-<ISO>/` | una pieza de trabajo **fechada**, con su instrumento propio y su evidencia |

El camino entre las dos es de una sola dirección: un instrumento que nace en
el banco y resulta reusable **se promueve** a `scripts/`. Nunca al revés — un
gate estable no se copia a un directorio fechado, porque entonces hay dos
copias y ninguna autoridad (`calibration-verified-numbers.md`).

## Dónde aterriza lo que sale

El banco guarda el instrumento y la evidencia. **El documento publicable no
vive aquí**: va a `kaupamex-docs/source/**`, que es su hogar.

| Sale | Destino |
|---|---|
| hallazgo | `docs: source/gestion/pm/api/iniciativas/<slug>/hallazgos/` |
| análisis, censo, reporte | `docs: source/gestion/pm/...` o `source/normativa/...` |
| decisión de arquitectura | `docs: source/backend/adr/adr-NNN-<tema>.rst` |
| cambio de código | el commit en `api`, citado por el hallazgo como `api@<hash>` |
| instrumento reusable | promovido a `scripts/` |

El manifiesto declara el destino **antes** de que exista, en la clave
`destination`. Un trabajo sin destino declarado produce algo que nadie
encuentra.

## El manifiesto

`manifest.json`, con el esquema de `manifest_schema.json`. Cinco claves son
obligatorias y las verifica `scripts/check_workbench.py`:

| Clave | Qué declara |
|---|---|
| `question` | qué se quería saber, en una frase |
| `instrument` | con qué se midió — archivo, comando, o ambos |
| `metric` | qué cuenta exactamente la cifra que se publica |
| `blind_to` | qué NO puede ver ese instrumento |
| `destination` | dónde aterriza lo que produce |

`metric` y `blind_to` no son ceremonia: son
`metrica-decide-la-conclusion.md` hecho campo obligatorio. Si `blind_to`
incluye el fenómeno sobre el que se iba a concluir, la conclusión no se emite.

Las opcionales que la experiencia de docs mostró útiles: `corrected_premise`
(cuando la pregunta venía con una cifra que resultó ser otra cosa),
`findings`, `tasks`, `reproducible`, `outputs`.

## Reglas que no se relajan aquí

- **Sin deuda congelada.** Un instrumento que nace en el banco no trae
  baseline. Directiva del ejecutor 2026-08-30; ver la tarea #219.
- **Los nombres de archivo `.py` en inglés**, `snake_case`; los comentarios y
  docstrings en español (`identificadores-en-ingles.md`).
- **TDD**: el test existe y se observa en rojo antes del instrumento. Las
  salidas fechadas de `outputs/` son el registro de esa secuencia, no copias
  redundantes.
- **Todo control declara qué lo haría fallar**, y se prueba contra eso. Un
  verde que no discrimina no es evidencia (sub-patrón D).

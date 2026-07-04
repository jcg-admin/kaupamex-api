```yml
type: Convención de Proyecto
category: Operación del agente — comandos de larga duración
version: 1.1.0
created_at: 2026-05-06 00:42:00
updated_at: 2026-05-06 19:35:00
applies_to: e-comerce v1.0.0+
origin_wp: 2026-05-06-00-31-12-api-socket-error-investigation
```

# Long-running commands — patrones de invocación

> Cargado automáticamente. Aplica a TODA invocación de comandos
> shell estimados >5 minutos de duración.

> **Adaptacion e-comerce (2026-05-19):** Las referencias a
> `.thyrox/context/work/<WP>/` en los patrones (R-4, etc.) son del
> template. En e-comerce los logs persisten en `docs/build-logs/<slug>/`
> (git-ignored). Ver `.claude/rules/build-logs.md` para la politica
> completa.

## Por qué existe esta regla

El cliente Claude Code se comunica con el backend Anthropic vía
**SSE (Server-Sent Events)** con liveness timeout (~5 min en
sesiones normales). Cuando un `tool_exec` foreground se ejecuta
sin producir mensajes durante esa ventana, el stream cae con:

```
API Error: The socket connection was closed unexpectedly.
```

Wrapper user-facing del evento interno `cli_sse_liveness_timeout`.

Causa raíz documentada en
`.thyrox/context/work/2026-05-06-00-31-12-api-socket-error-investigation/`.

## Reglas operacionales

### R-1 — Comandos >5 min siempre en background

Cualquier comando con duración estimada >5 minutos (build
completo, tests E2E, prerender masivo, batch generation) se lanza
detached. **NUNCA** esperar foreground.

#### Patrón preferido — `nohup … & disown` dentro de Bash foreground

```bash
# CORRECTO — Bash retorna inmediato tras lanzar el nohup;
# no crea shell entry trackeada en Claude Code.
nohup bash -c "long_command ..." > "$LOG" 2>&1 &
PID=$!
disown $PID
echo "$PID" > /tmp/<wp>_pid.txt   # si se necesitará para Monitor R-2.1
```

#### Patrón evitado — `Bash run_in_background=true`

```python
Bash(command="long_command ...", run_in_background=true)  # ⚠
```

Este patrón crea una **shell trackeada por Claude Code** que
persiste en el state del agente aunque el proceso PID muera.
Solo se elimina con `KillBash` (no siempre disponible) o al
cerrar la sesión. En sesiones largas se acumulan: 10-20 shells
fantasma que el ejecutor humano debe cancelar manualmente desde
el UI.

Usar `Bash run_in_background=true` solo si:

- Se va a llamar `KillBash` explícitamente al terminar.
- El comando es muy corto (<1 min) y no merece el setup de
  `nohup`.
- Se necesita `BashOutput` para leer el output stream.

En cualquier otro caso, preferir el patrón `nohup … & disown`.

```bash
# INCORRECTO — foreground >5 min, dispara SSE timeout
sphinx-build -W -j auto -b html source build/html
```

### R-2 — Patrón según duración esperada

**Árbol de decisión (aplicar SIEMPRE en este orden):**

| Duración esperada | Patrón | Razón |
|---|---|---|
| <5 min | **R-2.0** (Bash + `until`) | Sin task entry persistente |
| 5–30 min | **R-2.1** (Monitor + `tail -f --pid`) | Necesita progress mid-stream |
| Sin fin | **R-2.2** (Monitor `persistent: true`) | Stream eterno; cleanup vía TaskStop |
| Silencioso, no observable | `Bash run_in_background=true` directo | Fire-and-forget |

#### R-2.0 — Builds <5 min: Bash + `until`, NO Monitor

Para builds locales con duración esperada <5 min (Sphinx
strict, npm build, pytest suite corto, etc.), usar
`Bash run_in_background=true` con un `until` loop que espere
la condición de salida. Esto **NO crea task entry persistente**
en la UI del agent harness, a diferencia de `Monitor`.

**Patrón canónico R-2.0:**

```bash
# Lanzar el build en background detached
nohup bash -c "make html SPHINXOPTS='-W -j auto' 2>&1; echo EXIT=\$?" \
    > "$LOG" 2>&1 &
PID=$!
disown $PID

# Esperar la condición de salida — emite UNA notificación final
Bash(
  command='until grep -qE "^EXIT=" "'$LOG'"; do sleep 2; done && tail -5 "'$LOG'"',
  run_in_background=true,
  description="esperar build"
)
```

**Por qué R-2.0 es la opción default:**

- `Bash run_in_background=true` con un comando que termina
  por condición no genera un task entry visual persistente.
- El ejecutor recibe 1 sola notificación al completarse.
- Si hay 11 builds en el WP, hay 0 entries acumuladas (vs 11
  con Monitor).
- `TaskStop` no está disponible en el runtime del agent —
  Monitor entries solo se cierran al finalizar la sesión o
  por cancelación manual del ejecutor.

**Cuándo NO usar R-2.0 (escalar a R-2.1):**

- Si necesitas observar progreso intermedio (logs streaming).
- Si el comando puede colgarse y necesitás detección temprana.
- Si el comando no tiene marcador `EXIT=` o equivalente.

**Origen:** WP `2026-05-06-00-31-12-api-socket-error-investigation`
(followup analysis Phase 3, 2026-05-06). Detectado tras 4 WPs
encadenados con ~31 task entries acumuladas que el ejecutor
canceló manualmente.

#### R-2.1 — Builds 5–30 min: Monitor con grep line-buffered

Para comandos en background con duración 5–30 min y outcome
conocido (success/failure markers), usar `Monitor` con
`tail -f LOG | grep --line-buffered "PATTERN"`. Cada línea
emitida es un evento que mantiene el stream SSE vivo.

**Cobertura del filtro**: incluir TODOS los estados terminales
(success, failure, error). Un filtro que sólo matchea success
deja al monitor silencioso ante un crash → indistinguible de
"sigue corriendo".

##### R-2.1.1 — El monitor DEBE auto-cerrarse al completar el work

`tail -f` solo nunca termina, así que el monitor queda activo hasta
el timeout aunque el comando observado ya haya terminado. Eso
genera notificaciones "Monitor timed out — re-arm if needed" que
son ruido y obligan a cancelar manualmente. Usar uno de estos
patrones para que el monitor se cierre cuando el work termina.

##### Patrón canónico — `tail -f --pid=$PID` (GNU tail)

```bash
# Lanzar el comando capturando PID
nohup bash -c "long_command; echo EXIT=\$?" > "$LOG" 2>&1 &
PID=$!
disown $PID

# Monitor: tail termina automáticamente cuando $PID muere
Monitor(
  command='tail -f --pid='"$PID"' "$LOG" | grep -E --line-buffered "^EXIT=|build succeeded|FAIL|Error"',
  description="...",
  timeout_ms=1800000
)
```

`tail -f --pid=PID` (extensión GNU) hace exit cuando el proceso
PID termina. El monitor recibe EOF, emite los eventos finales y
se cierra limpiamente.

##### Patrón alternativo — `awk` con exit en marker terminal

Útil si no se tiene acceso al PID (e.g. observando un log que
escribe otro agente):

```bash
tail -f "$LOG" | awk '
  /^EXIT=|build succeeded|build finished with problems|FAILED|Traceback/ {
    print; fflush(); exit
  }
  /pattern/ { print; fflush() }
'
```

Riesgo: si el comando crashea sin escribir un marker terminal en
el log, el `awk` nunca hace exit. Por eso preferir `--pid` cuando
sea posible.

##### Anti-patrón

```bash
# ❌ Monitor queda activo hasta el timeout aunque el comando termine
tail -f "$LOG" | grep --line-buffered "PATTERN"
```

#### R-2.2 — Cada Monitor crea un task entry; minimizar el número

Cada llamada a `Monitor(...)` crea un task entry persistente en
el UI del usuario. Estos entries:

- No se eliminan al expirar (timeout) — quedan visibles como
  "Monitor timed out".
- No se eliminan al completar limpiamente — quedan visibles como
  "completed".
- Solo se descartan con `TaskStop` (no siempre disponible) o al
  cerrar la sesión.

Reglas:

- **Reusar el mismo Monitor** si se sigue observando el mismo
  log/proceso, en lugar de cancelar y rearmar.
- **No rearmar tras timeout** salvo que el comando aún esté vivo
  (usar el patrón `--pid=$PID` para que esto sea improbable).
- **Un solo Monitor por work**, no uno por iteración.

Sesiones con 10+ entries Monitor son señal de que se rearmó
varias veces o se observó por separado lo que se podía observar
con uno solo.

### R-3 — Probes periódicos cuando no hay output natural

Si la operación no tiene markers para grep (p.ej., proceso
silencioso con outcome sólo al final), emitir tool_uses cortos
cada 3-4 min:

```bash
ls -la <path>      # 0.1s, suficiente para mantener SSE vivo
git status --short
```

### R-4 — Persistir logs en el WP activo

Logs siempre redirigidos a archivo dentro de
`{wp}/execute/build-logs/{contexto}-{ISO}.log`. Cumple
`.claude/rules/build-logs.md` y permite recovery tras timeouts.

```bash
WP=.thyrox/context/work/{wp-activo}
ISO=$(date -u +%Y-%m-%dT%H-%M-%S)
LOG="$WP/execute/build-logs/{contexto}-$ISO.log"
mkdir -p "$(dirname "$LOG")"
nohup bash -c "long_command ..." > "$LOG" 2>&1 &
```

### R-5 — Atacar la causa de fondo, no sólo el síntoma

Si los builds son lentos por causas resolubles (cache stale,
deps mal configuradas), priorizar resolverlo antes de aceptar
"el build dura 20 min y hay que esperarlo".

**Ejemplo en este proyecto:** el cache PlantUML al 83% provocaba
builds de ~20 min. WP `plantuml-cache-prerender-update` lleva el
cache a ~100%, reduciendo el build a <5 min y eliminando la
condición que dispara el timeout.

## Tabla de decisión

| Duración estimada | Patrón | Genera task entry? |
|---|---|---|
| ≤30 s | `Bash` foreground normal | No |
| 30 s – 5 min | `Bash` foreground con `timeout_ms` | No |
| 5 min – 30 min, **silencioso** (no necesitás progreso) | `Bash run_in_background=true` + `until` loop (**R-2.0**) | **No** ← preferido |
| 5 min – 30 min, **con progreso visible** | `Bash run_in_background=true` + `Monitor` (R-2.1) | Sí (1 entry) |
| >30 min | Background detached + `Monitor` con timeout extendido + checks periódicos (R-3) | Sí (1 entry) |
| Stream sin fin (tail eterno) | `Monitor persistent: true` + `TaskStop` final | Sí (manual cleanup) |

**Default para builds locales del submodulo docs de e-comerce
(Sphinx strict 1-3 min):** R-2.0 — sin Monitor, sin task entry
persistente.

## Anti-patrones prohibidos

### AP-1 — Foreground con timeout >5 min

```python
Bash(command="sphinx-build -W ...", timeout=600000)  # ❌ 10 min foreground
```

El parámetro `timeout` evita el kill local pero **no** previene
el SSE liveness timeout del transporte. El tool_exec puede
completar localmente pero la conexión al servidor ya cayó.

### AP-2 — Esperar pasivamente "que termine"

```
Usuario: "espera a que termine el build"
Agente: <silencio durante 15 min>     ← el stream cae
```

Reemplazar con: lanzar background + Monitor + comunicar progreso
al usuario cuando el monitor emita.

### AP-3 — `sleep` largos

```bash
sleep 600  # ❌ 10 min sin output → SSE timeout
```

El harness bloquea sleeps largos. Para esperar una condición,
usar `Monitor` con `until` loop o polling con intervalos cortos.

### AP-4 — `tail -f` sin límite ni filtro

```python
Monitor(command="tail -f /var/log/app.log", ...)  # ❌
```

Sin filtro:
- Genera demasiados eventos → harness los suprime.
- Sin estado terminal claro → ambiguo si crashea.

Siempre incluir `grep --line-buffered "PATRÓN_ESTADO_TERMINAL"`.

### AP-5 — `tail -f` sin `--line-buffered` en grep

```bash
tail -f log | grep "ERROR"  # ❌ buffering retrasa eventos 60+ s
```

El buffer de pipe acumula líneas hasta llenarse. Para flujo
inmediato:

```bash
tail -f log | grep --line-buffered "ERROR"
```

### AP-6 — Monitor para builds locales <5 min

```python
Monitor(command="tail -f --pid=$PID build.log | grep ...",
        timeout_ms=300000)  # ❌ build de 2 min
```

`Monitor` crea un task entry persistente en la UI del agent
harness que **no se cierra automáticamente al completar** —
solo via `TaskStop` (no siempre disponible) o cierre de sesión.
Para builds <5 min esto satura la UI con entries innecesarias
que el ejecutor debe cancelar manualmente.

**Solución:** R-2.0 (Bash + `until`). El task entry
persistente solo está justificado cuando la duración hace
inviable otro patrón (5+ min, progreso mid-stream, stream
eterno).

**Evidencia:** sesión 2026-05-06 acumuló ~31 task entries en
4 WPs encadenados aplicando Monitor a builds Sphinx de 1-3 min.

## Relación con otras reglas

- **`build-logs.md`**: define dónde van los logs (R-4 invoca
  esa regla). Compatible y complementaria.
- **`thyrox-invariants.md`**: I-013 sobre context pruning entre
  stages. Si un comando largo cruza un cierre de stage, marcar
  como "pendiente:re-verificar".
- **`commit-conventions.md`**: Tim Pope; aplicable a commits que
  registren ejecución de comandos largos.

## Referencias

- WP de origen: `2026-05-06-00-31-12-api-socket-error-investigation/`.
  - `analyze/socket-error-root-cause.md` — evidencia textual del
    error y mecanismo.
  - `track/recommendations.md` — origen de R-1..R-5 y AP-1..AP-3.
- Logs evidencia: `/tmp/claude-code-*.diag.log`
  (`cli_sse_liveness_timeout`, `cli_sse_reconnect_attempt`).

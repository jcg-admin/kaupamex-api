```yml
type: Convención de Proyecto
category: Operación del agente — tareas background del bug sweep
version: 1.3.0
created_at: 2026-05-27
applies_to: e-comerce v1.0.0+
extends: long-running-commands.md (R-2.1)
```

# Background tasks — Bug sweep ciclos

> Este documento extiende `long-running-commands.md` con el patrón
> específico para lanzar y esperar ciclos del loop autónomo de bug
> sweep. La regla general AP-3 (no `sleep` largo, usar Monitor) y
> R-2.1 (`tail -f --pid` para 5-30 min) aplican directamente.

## Contexto

Cada ciclo del loop autónomo de bug sweep:

- Dura entre 5 y 15 minutos en un agente background.
- Produce exactamente una señal de completación: commit RST en
  `e-comerce-docs` con el archivo `hallazgos-cicloN-api.rst`.
- No tiene output natural en un log local del executor (el agente
  background escribe a los repos directamente).

El executor principal **NUNCA** debe:

- Leer archivos `.jsonl` internos del harness para monitorear
  el progreso del agente (`/root/.claude/.../*.jsonl`).
- Usar `sleep 30` o cualquier `sleep` aislado para esperar.
- Usar `tail` sobre logs internos del subagente.

Estos patrones violan **AP-3** de `long-running-commands.md` y
están explícitamente bloqueados por el harness. El executor ha
incurrido en este antipatrón desde el inicio del loop; la señal
de bloqueo es: `"Blocked: sleep 30 followed by: tail ..."`.

## Secuencia obligatoria — sin trabajo entre lanzar y recibir señal

**Regla:** entre el `Agent(run_in_background=True)` y la recepción
de la señal de completación, el executor NO hace ningún otro trabajo.

```
# CORRECTO
1. Agent(run_in_background=True)   ← lanzar ciclo N
2. Monitor(until grep cicloN)      ← activar espera inmediatamente
3. <recibir señal>
4. Verificar commits + actualizar SMD
5. Agent(run_in_background=True)   ← lanzar ciclo N+1

# INCORRECTO (patrón observado en el historial del loop)
1. Agent(run_in_background=True)   ← lanzar ciclo N
2. "While ciclo N completes, I'll pre-scan areas for ciclo N+1"
   ← consume contexto del executor; la <task-notification>
     puede llegar mientras el executor está ocupado y no
     procesarse; en sesiones largas, el contexto se compacta
     y la notificación se pierde definitivamente
3. Intentar leer JSONL interno      ← bloqueado
4. Verificar manualmente con git log ← trabajo no previsto
5. Actualizar SMD
6. Agent(run_in_background=True)   ← lanzar ciclo N+1
```

**Por qué el trabajo durante la espera es un problema:**

El harness emite `<task-notification>` cuando el agente termina.
Si el executor está procesando otra cosa en ese momento, la
notificación compite con ese trabajo por atención. En sesiones
largas donde el contexto se compacta entre turnos, la notificación
puede quedar en el historial compactado y nunca procesarse —
produciendo exactamente el patrón de "verificación manual con
shells ad-hoc" que se observó en ciclos 57-109.

El Monitor es la solución: el executor activa el Monitor
inmediatamente después de lanzar el agente, y la sesión queda
en estado de espera activa. Cuando llega la señal, el Monitor
la emite como evento y el executor la procesa sin ambigüedad.

**Anti-patrón específico prohibido:**

```
# PROHIBIDO — pre-scan durante la espera
Agent(description="Ciclo N ...", run_in_background=True)
# [executor]: "While the agent runs, I'll scan these new areas..."
# [executor]: grep, Read, Bash sobre el codebase
# → contexto consumido, notificación potencialmente perdida
```

## Patrón correcto — R-2.1 adaptado para ciclos

### Lanzar un ciclo

Los ciclos se lanzan con `Agent(run_in_background=True)`. El
harness asigna un task-id y emite `<task-notification>` cuando
termina. No lanzar con `nohup bash -c "claude ..."` porque el
agente background necesita acceso a las herramientas del harness.

```python
Agent(
  description="Ciclo N autonomous bug sweep",
  prompt="...",  # ver template en SMD
  run_in_background=True
)
```

### Esperar la completación vía Monitor

La señal de completación es el commit del RST en docs:
`hallazgos-cicloN-api.rst` en la rama `claude/great-fermat-N01N4`.

```python
Monitor(
  description="Esperar senal ciclo N en docs",
  command=(
    "until "
    "git -C /home/user/e-comerce-docs fetch origin "
    "claude/great-fermat-N01N4 --quiet 2>/dev/null && "
    "git -C /home/user/e-comerce-docs log --oneline "
    "origin/claude/great-fermat-N01N4 "
    "| grep -q 'cicloN'; "
    "do sleep 2; done && echo 'Ciclo N completado'"
  ),
  timeout_ms=600000  # 10 minutos; ciclos normales ~5-15 min
)
```

**Sustituir** `cicloN` por el número concreto (ej. `ciclo110`).
El subject del commit del agente tiene la forma:
`"Add ciclo N audit hallazgos"`.

### Si la `<task-notification>` llega antes que el Monitor

El harness emite `<task-notification>` cuando el agente termina.
Si esa notificación llega mientras el executor no está esperando
activamente (sesión compactada, fin de turno), el Monitor
confirmará el estado leyendo el remote — no hay pérdida de señal.

### Si el Monitor expira sin evento

El agente probablemente no hizo push. Verificar manualmente:

```bash
git -C /home/user/e-comerce-docs log --oneline \
  origin/claude/great-fermat-N01N4 | head -5
```

Si el RST no aparece pero los commits de código están:

```bash
cd /home/user/e-comerce-api && git log --oneline -3
cd /home/user/e-comerce-ui && git log --oneline -3
```

Si los commits están locales pero sin push, hacer push manualmente.
Si el agente no produjo cambios, relanzar el ciclo.

## Calibración epistémica del agente — tres requisitos

El loop genera hallazgos PROVEN por definición (cada fix tiene un
diff de commit). Pero tres dimensiones del procedimiento de
calibración del proyecto (`auto-audit-before-writing.md` +
`agentic-calibration-workflow-example.md`) no se aplicaban. Los
tres cambios siguientes los incorporan al template del ciclo.

### Cambio 1 — Premisa verificada por hallazgo (Premise Gate nivel 0a)

Cada hallazgo en el RST DEBE incluir una sección
`**Premisa verificada:**` con la cita `file:line` exacta del
código que sustenta el claim, marcada `[PROVEN]`. Sin esta cita
el hallazgo no cumple el estándar del proyecto aunque el fix sea
correcto.

**Formato obligatorio por hallazgo:**

```rst
H-CICLON-NN — Descripcion corta
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Severidad:** Alta.

**Premisa verificada:**
``apps/voucher/views.py:47`` — ``self.get_object()`` sin
``select_for_update()``.  [PROVEN]

**Descripcion:**
...

**Correccion:**
...

**Commit:** api@hash
```

La cita PROVEN es el `file:line` leído con `Read` o `grep`
durante la investigación, no reconstruido de memoria.

### Cambio 2 — Check de cobertura previa antes de investigar un área

Antes de investigar cada área del ciclo, el agente debe ejecutar:

```bash
git -C /home/user/e-comerce-docs log --oneline \
  origin/claude/great-fermat-N01N4 \
  | grep -i "<keyword-del-area>"
```

Si el log muestra un hallazgo previo del mismo archivo o módulo,
reportar como `YA CUBIERTO en cicloN (docs@hash)` en lugar de
reinvestigar. Esto implementa el **red flag 7** de
`auto-audit-before-writing.md`: sucesoras hijas previas que
cierran items sin que el audit fuente lo registre.

**Ejemplo en el prompt del agente:**

```
Para cada area antes de investigar:
1. git -C /home/user/e-comerce-docs log --oneline \
     origin/claude/great-fermat-N01N4 | grep -i "voucher"
2. Si aparece hallazgo reciente (< 10 ciclos) del mismo modulo:
   reportar YA CUBIERTO, no re-auditar.
3. Si limpio o el hallazgo es mas antiguo: proceder con la
   investigacion normal.
```

### Cambio 3 — Métrica de calibración al cierre del RST

Al final de cada RST agregar la sección de métrica. Esta sección
permite calcular el ratio PROVEN sobre el espacio auditado —
sin ella el ejecutor solo ve "N hallazgos" sin poder detectar
el **Patrón CAD** (Calibración Asintótica por Dominio): el
promedio global oculta zonas con cobertura cero.

**Formato obligatorio al final del RST:**

```rst
Metrica de calibracion del ciclo
----------------------------------

:hallazgos_nuevos: N
:areas_limpias: M
:ratio_proven: N/(N+M)  (fraccion de areas con evidencia PROVEN)
:dominios_sin_cobertura: <lista de repos/modulos no auditados>
:patron_cad_activo: si|no  (si algun dominio lleva >5 ciclos sin cobertura)
```

**Ejemplo:**

```rst
Metrica de calibracion del ciclo
----------------------------------

:hallazgos_nuevos: 3
:areas_limpias: 7
:ratio_proven: 3/10 = 0.30
:dominios_sin_cobertura: db (scripts/), server (vhosts/)
:patron_cad_activo: si (db y server sin sweep sistematico en >20 ciclos)
```

### Cambio 4 — Especificidad de áreas db y server + evidencia CLEAN obligatoria

**Origen:** auditoría empírica ciclos 79-112 (2026-05-27). De 34
ciclos ejecutados: api 68% cobertura activa, ui 44%, db 3% (1 commit),
server 3% (1 commit). Causa raíz: las áreas de db y server se asignaban
de forma vaga ("scripts de BD", "configuración Apache") sin archivo
concreto, y los agentes las declaraban CLEAN sin `file:line` verificable.

**Regla:** las áreas de db y server en el prompt del ciclo DEBEN:

1. Referenciar un archivo **concreto** con su path absoluto, igual que
   las áreas de api (`apps/orders/admin_services.py`) y ui
   (`src/pages/admin/AdminOrderDetailPage.jsx`).
2. Describir qué verificar en ese archivo (idempotencia, `set -euo pipefail`,
   passwords hardcodeados, manejo de errores, etc.).

**Inventario de archivos auditables en db y server:**

```
db (e-comerce-db):
  /home/user/e-comerce-db/provisioners/mariadb/db_setup.sh
  /home/user/e-comerce-db/provisioners/mariadb/db_qa_setup.sh
  /home/user/e-comerce-db/provisioners/mariadb/install.sh
  /home/user/e-comerce-db/provisioners/mariadb/deploy_objetos.sh
  /home/user/e-comerce-db/provisioners/mariadb/objetos/funciones/fn_price_with_tax.sql
  /home/user/e-comerce-db/provisioners/mariadb/objetos/funciones/fn_qualifies_free_shipping.sql
  /home/user/e-comerce-db/provisioners/mariadb/objetos/funciones/fn_stock_status.sql
  /home/user/e-comerce-db/provisioners/mariadb/objetos/sps/sp_rpt_catalog_by_category.sql
  /home/user/e-comerce-db/provisioners/mariadb/objetos/sps/sp_rpt_catalog_summary.sql
  /home/user/e-comerce-db/provisioners/mariadb/objetos/sps/sp_rpt_low_stock.sql
  /home/user/e-comerce-db/provisioners/mariadb/objetos/vistas/v_featured_products.sql
  /home/user/e-comerce-db/provisioners/mariadb/objetos/vistas/v_low_stock.sql
  /home/user/e-comerce-db/provisioners/mariadb/objetos/vistas/v_published_catalog.sql
  /home/user/e-comerce-db/provisioners/mariadb/seed_catalogo.sql
  /home/user/e-comerce-db/scripts/backup_db.sh
  /home/user/e-comerce-db/scripts/check_db.py

server (e-comerce-server):
  /home/user/e-comerce-server/config/apache/practicayoruba-https.conf
  /home/user/e-comerce-server/config/apache/practicayoruba-http.conf
  /home/user/e-comerce-server/provisioners/apache/install.sh
  /home/user/e-comerce-server/provisioners/apache/setup_vhost.sh
  /home/user/e-comerce-server/provisioners/ssl/setup_ssl.sh
  /home/user/e-comerce-server/provisioners/firewall/setup_firewall.sh
  /home/user/e-comerce-server/provisioners/security/setup_fail2ban.sh
  /home/user/e-comerce-server/provisioners/security/setup_ssh_hardening.sh
  /home/user/e-comerce-server/scripts/healthcheck.sh
  /home/user/e-comerce-server/utils/core.sh
  /home/user/e-comerce-server/utils/validation.sh
  /home/user/e-comerce-server/tests/test_apache_ssl_provisioning.sh
```

**Ejemplo correcto de área db en el prompt:**

```
/home/user/e-comerce-db/provisioners/mariadb/db_setup.sh —
verificar: set -euo pipefail presente, idempotencia en CREATE USER
y GRANT, ausencia de passwords hardcodeados en texto plano,
manejo de errores en cada sección crítica, GRANT mínimo privilegio
(no GRANT ALL).
```

**Ejemplo incorrecto (NO usar):**

```
scripts de BD — revisar scripts de configuración    ← demasiado vago
```

**Evidencia CLEAN obligatoria para db y server:**

Las áreas de db y server declaradas como CLEAN en la sección
"Áreas limpias" del RST DEBEN citar al menos un `file:line` leído
con `Read`, igual que los hallazgos. Sin cita, la declaración
CLEAN no tiene evidencia verificable.

**Formato obligatorio para área CLEAN de db/server:**

```rst
- **db/provisioners/mariadb/db_setup.sh**: ``set -euo pipefail``
  presente en línea 3. ``CREATE USER IF NOT EXISTS`` con password
  leído de variable de entorno (línea 47, sin hardcode). ``GRANT``
  a ``django_user`` solo sobre la BD específica (línea 52, no
  ``GRANT ALL ON *.*``). Idempotente: guards ``IF NOT EXISTS``
  en CREATE DATABASE (línea 31). Sin hallazgos.
```

**Contraste con el anti-patrón observado:**

```rst
# INCORRECTO — sin file:line, no verificable
- **scripts/provisioners/mysql/db_setup.sh**: idempotente,
  ``set -euo pipefail``, validación de root al inicio, socket/TCP
  fallback, charset utf8mb4. Sin hallazgos.

# CORRECTO — con file:line PROVEN
- **db/provisioners/mariadb/db_setup.sh**: ``set -euo pipefail``
  (línea 3). ``CREATE DATABASE IF NOT EXISTS`` (línea 31). Password
  leído de ``$DB_PASSWORD`` no hardcodeado (línea 47). ``GRANT``
  mínimo a ``django_user`` solo sobre practicayoruba_db (línea 52).
  Sin hallazgos.
```

### Relación con `auto-audit-before-writing.md`

Los cuatro cambios implementan las exigencias del Premise Gate
nivel 0a aplicadas al contexto específico del loop:

| Exigencia del Premise Gate | Implementación en el ciclo |
|---|---|
| `file:line` PROVEN por claim | Sección "Premisa verificada" por hallazgo (Cambio 1) |
| Red flag 7: sucesoras previas | Check `git log grep` por área antes de investigar (Cambio 2) |
| Calibración por dominio | Sección de métrica al cierre del RST (Cambio 3) |
| Evidencia verificable para CLEAN db/server | Áreas concretas + `file:line` en sección "Áreas limpias" (Cambio 4) |

## Criterio de terminación formal

El loop termina **SOLO** cuando el ejecutor lo ordena explícitamente
(I-011 de `thyrox-invariants.md`). Las condiciones observables que
pueden fundamentar esa decisión son:

1. **N ciclos consecutivos con 0 hallazgos** — ciclos 85 y 96
   fueron limpios; no son suficientes solos para cerrar.
2. **Agotamiento estático de áreas** — db y server nunca han sido
   auditados sistemáticamente; hay superficie no cubierta.
3. **Densidad < 1 hallazgo/ciclo en 5 ciclos consecutivos** —
   indicador de saturación del dominio estático.
4. **Decisión explícita del ejecutor** — única condición formal.

Sin instrucción explícita del ejecutor, el loop continúa.

## Regla de commit — esperar suite verde antes de commitear

**No commitear cambios de producción o test mientras el suite está corriendo.**

El commit debe hacerse DESPUÉS de recibir el resultado del Monitor y
confirmar que el suite está verde (o que los fallos son pre-existentes
documentados). Commitear al 57% del suite viola este principio: si el
suite descubre regresiones en el 43% restante, el commit queda en el
historial con código que rompe tests.

```
# CORRECTO
1. Editar archivos de producción o tests
2. Lanzar suite: nohup pytest ... > LOG 2>&1 & PID=$!
3. Monitor(tail -f --pid=$PID LOG | grep --line-buffered "passed|failed|error")
4. <recibir resultado del Monitor>
5. Si verde → git commit
   Si hay fallos → corregir, volver al paso 2

# INCORRECTO (violación observada 2026-05-27 — commit api@0666cab al 57%)
1. Editar archivos
2. Lanzar suite en background
3. git commit  ← suite aún corriendo; fallos en el 43% restante invisibles
4. Monitor detecta 3 fallos adicionales → segundo commit de fix necesario
```

**Por qué importa:** el historial de git debe reflejar estados conocidos.
Un commit "verde" que en realidad tenía fallos pendientes corrompe la
trazabilidad. El segundo commit de fix (`api@52764b4`) corrigió lo que
`api@0666cab` debió haber incluido.

**Origen:** defecto observado en la sesión 2026-05-27 al reconciliar el
baseline E2E. Documentado para evitar repetición.

## Aislamiento de working tree entre agentes paralelos

**Regla:** en una tanda paralela, cada agente commitea SOLO su propio
repo, y NINGÚN agente escribe en el working tree de un repo que otro
agente está commiteando. Si el agente A hace `git add -A && commit` en
`<repo>` mientras el agente B dejó un archivo sin commitear en ese mismo
working tree, el commit de A **barre** el archivo de B → atribución
incorrecta, refs `:Commits:` sin resolver, y posible commit de estado
parcial.

**Gate previo a lanzar una tanda paralela:** los repos de **escritura**
de los agentes deben ser **disjuntos**. Un repo = un agente con permiso
de commit por tanda. Si dos tareas escriben el mismo repo → **serializar
ese par** (no paralelizar).

**Hallazgos cross-repo** (p. ej. un agente que trabaja en `api` y debe
documentar en `docs`): el agente NO escribe en el working tree de `docs`
si hay otro agente commiteándolo. En su lugar **devuelve el contenido en
su resumen** y el orquestador lo persiste en `docs` cuando no haya otro
agente activo en ese repo; o escribe a una ruta staging fuera del
working tree compartido.

**Origen (2026-06-03):** tanda 1 del loop Fase-1 — el agente de `api`
(canon-idioma) creó su archivo de hallazgos en el working tree de `docs`
mientras otro agente commiteaba `docs` con `git add -A`. Agravante: el
orquestador afirmó "lección anotada" sin persistirla — over-claim del
`react-verification-gate.md` (afirmación de estado sin la Observation de
haberla escrito). Esta regla cierra ambos: el aislamiento y la
persistencia real de la lección.

## Reconciliación tras resume — el "agent running" del summary NO es estado

**Regla:** tras reanudar una sesión desde un summary de compactación, un
"agente X sigue corriendo / no reconciliado" leído del summary es una
**creencia heredada**, NO un estado verificado. Antes de actuar sobre
ella (relanzar, esperar, o reportar "en ejecución"), **verificar con una
Observation del turno actual** y reconciliar el working tree.

**Por qué:** los agentes background son asíncronos; su
`<task-notification>` de completación puede caer **dentro** de la ventana
que la compactación resume y perderse. El summary congela "running" como
si fuera verdad presente. En realidad el agente pudo: (a) completar y
pushear, (b) completar dejando trabajo **sin commitear**, o (c) morir.
Las tres se ven igual desde el summary. Es un caso del
`react-verification-gate.md`: estado heredado ≠ Observation.

**Procedimiento de reconciliación (en este orden):**

```bash
# 1. ¿Hay procesos reales del agente vivos? (no el claude de la sesión)
ps -eo pid,etime,stat,cmd | grep -E "pytest|jest|[n]ode |npx|until " | grep -v grep
#    vacío → ningún work del agente corre.

# 2. ¿El registro de tareas del harness lo conoce?
#    TaskOutput/TaskStop <id> → "No task found" = tarea ya destruida.

# 3. ¿Qué dejó en el working tree de cada repo de la tanda?
cd /home/user/e-comerce-<repo> && git status --short && \
  git log --oneline origin/<rama>..HEAD     # commits locales sin push
```

- **Trabajo sin commitear** → inspeccionar diffs, correr los gates
  (DB por socket + pytest para api; Node v20 + jest + lazy/canon para ui),
  completar lo que falte (p. ej. test ausente de un `lib/` nuevo),
  commitear, pushear, bumpear gitlink.
- **Commits locales sin push** → pushear y bumpear gitlink.
- **Nada** → relanzar el work si todavía se necesita.

**Higiene de cards fantasma:** un Monitor/agente background **no se
auto-limpia** del UI al completar/morir (R-2.2 / AP-6 de
`long-running-commands.md`). Lo que el ejecutor ve como "en ejecución"
puede ser una **card persistente** cuyo backend ya murió. Cerrar los
Monitors completados con `TaskStop`; si el id da "No task found", el
backend ya lo destruyó (la card es solo visual).

**Origen (ERR-12, 2026-06-03):** sesión reanudada con summary que decía
"two agents currently RUNNING (not reconciled)". `ps` mostró 0 procesos
de agente; `TaskStop` sobre los 4 ids → "No task found"; ambas tandas
habían terminado dejando trabajo **sin commitear** (api nunca commiteó;
ui dejó `lib/dateMath.js`+edit de Calendar). Reconciliado a
`develop@b71074f`. Ver
`docs/source/gestion/pm/docs/audits/registro-errores-falsos-positivos.rst`
(ERR-12).

## Relación con otras reglas

- `long-running-commands.md`: R-2.1 y AP-3 son las reglas base; R-2.2/AP-6
  explican por qué las cards persisten (higiene de fantasmas).
- `react-verification-gate.md`: el "agent running" del summary es estado
  heredado — requiere Observation del turno antes de propagarse.
- `thyrox-invariants.md`: I-011 define el cierre formal de WPs.
- SMD (`siguiente-mejor-decision.rst`): contiene la sección
  "Criterio de terminación formal del loop autónomo" con el
  estado actual y el historial de ciclos.

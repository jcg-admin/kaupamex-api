```yml
created_at: 2026-05-20 00:00:00
updated_at: 2026-05-21 08:00:00
status: Aprobado
project: kaupamex
author: claude
version: 1.2.0
```

# Auto-Auditar Antes de Escribir

> Cargado automáticamente en cada sesión.
> Regla NO NEGOCIABLE sobre creación y edición de artefactos.

## Regla principal

**Antes de cada Write o Edit, ejecutar checklist de
auto-auditoría.** Antes de cada batch potencial de Write/Edit,
detenerse, auto-cuestionarse y aplicar el checklist.

Esto aplica a:

- Artefactos RST de iniciativas (alcance, analisis, decisiones,
  tareas, progreso, index).
- Archivos de código nuevos.
- Documentos de decisión (DEC-DOC-NN, ADRs).
- Audits, hallazgos, FUs.
- Cualquier archivo donde la calidad del razonamiento importa
  más que la velocidad de salida.

## Stage 0 — Premise Gate (OBLIGATORIO antes del checklist)

**Cuando aplica:** ANTES de scaffolding de cualquier iniciativa
sucesora (los 6 artefactos), antes de aceptar un stub como base de
trabajo, antes de generar `alcance-<slug>.rst` que cite un audit
fuente.

**Por qué existe:** la auto-auditoría per-artefacto (Stage 1
abajo) atrapa premisa falsa entre artefactos, pero no antes del
primero. Si el primer `alcance-*.rst` ya nace sobre premisa
incompleta, los 6 artefactos se contaminan en cascada. El Premise
Gate corre ANTES del primer `Write`.

**Precedente concreto:** iniciativa
``fix-ui-auth-logout-y-refresh-wiring`` (stub T-102). Premisa del
stub: "UI envía body vacío en logout, falta `{refresh}`". Premisa
real (descubierta DURANTE el alcance, no antes): la UI no
almacena tokens en ningún storage accesible; `loginUser.fulfilled`
no llama `setAuthToken`; comentarios mienten sobre httpOnly
cookies. Scope explotó de ~10 líneas a ~200 líneas. El gate
upfront habría detectado esto sin scaffold abortado.

### Gate de 3 niveles con promoción

**Nivel 0a — grep + cita PROVEN + sucesoras hijas previas** (siempre, ~2 min)

- Localizar el `file:line` citado en el audit/stub.
- Confirmar que el código en esa línea coincide con la
  descripción del hallazgo.
- **Verificar metadata del audit fuente:** si dice
  ``:estado: parcialmente_cerrado``, leer ``:hallazgos_cerrados:``
  para excluir items ya resueltos.
- **`git log --grep` + `ls iniciativas/`** en el cluster afectado
  para detectar sucesoras hijas previas que pudieron cerrar
  hallazgos sin actualizar el audit (ver red flag #7 abajo).
- Si no coincide o el item ya esta cerrado: audit stale →
  reordenar el item al final del backlog hasta refresh.
  Actualizar metadata del audit (red flag #7). NO scaffolding.

**Nivel 0b — lectura completa del audit fuente** (siempre que
severidad ≥ MEDIA, ~5 min)

- Leer el audit RST completo, no solo la cita del bombazo.
- Identificar patrones sistemicos, "Drift loud" mentions sin
  fix, cross-links a otros UCs/hallazgos.
- Si emerge una señal de scope mayor que el stub describe →
  promover a 0c.

**Nivel 0c — micro-investigación cross-capa** (~15-30 min,
OBLIGATORIO si red flags activas)

- Trazar el flujo afectado end-to-end (data, token, state,
  schema, signal).
- Grep siblings/dependents en otros submódulos.
- Verificar suposiciones del audit contra código real, no solo
  cita aislada.
- Budget máximo 30 min. Si después no hay claridad, el item se
  convierte en **iniciativa de investigación separada** antes
  de scaffolding el fix.

### Red flags que OBLIGAN promoción a 0c

Estas señales fuerzan escalar al nivel 0c sin importar cuán
"chico" parezca el bombazo:

1. **"Drift loud" sin fix** en el audit o UC fuente — indica
   deuda técnica abierta que el audit reconoció pero no
   resolvió.
2. **Palabras-clave en el hallazgo:** ``lifecycle``, ``state``,
   ``storage``, ``schema``, ``migration``, ``interceptor``,
   ``middleware``, ``signal``, ``transaction``, ``concurrent``,
   ``cache``, ``webhook``, ``scheduler``, ``cron``, ``Celery``.
3. **Cross-submodulo** — el fix toca más de un submodulo (api +
   ui, api + db, api + server, etc.) entre los 5: api, db, docs,
   server, ui.
4. **Stub o audit anterior a refactor relevante** — si el audit
   fuente es de fecha X y hubo commits en el área afectada
   posterior a X, la premisa puede haber shifted. Verificar con
   ``git log -1 --format=%cd <archivo>`` del área tocada.
5. **"Comentarios obsoletos" sospechados** — comentarios del
   código contradicen el comportamiento observado (caso #6 con
   httpOnly cookies).
6. **El audit fuente fue producido por un solo agent** con
   alcance focal, pero la fix tocaría infraestructura
   compartida (alcance ancho). Asimetría = riesgo.
7. **Sucesoras hijas previas pudieron cerrar items del audit
   sin actualizar el audit fuente** — leccion T-102 (2026-05-21):
   los 3 hallazgos ALTA top D-17/D-23/D-26 fueron cerrados por
   la sucesora ``fix-ui-auth-logout-y-refresh-wiring`` (``ui@ca66946``,
   2026-05-20T23:39 UTC) pero el audit metadata seguia diciendo
   ``estado: completado`` con 28 hallazgos vivos. Sin verificar
   esto upfront, T-102 hubiera sido scaffolded sobre premisa stale
   completa.

   **Check obligatorio (sumar a Nivel 0a):**

   .. code-block:: bash

      # Para cada sucesora candidato T-NNN, antes de scaffold:
      # 1. git log --grep en el cluster afectado (apps modificadas)
      cd /home/user/kaupamex/<submodulo> \
          && git log --all --oneline --grep="<tema-cluster>" | head -20

      # 2. Listar iniciativas hijas previas que pudieron tocar el area
      ls /home/user/kaupamex/docs/source/gestion/pm/<submodulo>/iniciativas/ \
          | grep -i "<tema-cluster>"

      # 3. Si hay iniciativas cerradas <30 dias previas, leer su
      #    progreso para ver que hallazgos del audit cubrieron.

   **Si el check revela items cerrados**, actualizar el audit
   fuente:

   - Metadata ``:estado: completado`` -> ``parcialmente_cerrado``.
   - Nuevos campos ``:hallazgos_cerrados:`` +
     ``:hallazgos_abiertos:``.
   - Nota inline ``[CERRADO <repo>@<hash>]`` en cada hallazgo
     ya resuelto con cross-link al commit.

   Documentar la accion en el ``progreso-`` del meta-initiative
   (analogo a T-102 2026-05-21T07:58:10).

### Sección obligatoria en `alcance-<slug>.rst`

Cada `alcance-<slug>.rst` de sucesora DEBE empezar con una
sección "Premisa verificada" que documente el resultado del
Premise Gate. Sin esa sección, el alcance se considera
incompleto y el resto de artefactos no debe generarse.

Formato canonico:

```rst
Premisa verificada
==================

:nivel_evidencia: 0a | 0b | 0c
:duracion: ~N min
:fecha: <YYYY-MM-DDTHH:MM:SS de date>
:red_flags_activas: <lista de numeros 1-6 o "ninguna">

Citas PROVEN:

- ``<file>:<line>`` — <claim verbatim>.
- ``<file>:<line>`` — <claim verbatim>.

Sintesis de la investigacion (si nivel 0c):

- <hallazgo del walk cross-capa que NO estaba en el audit fuente>.
- <decision sobre scope: confirmar / expandir / colapsar / reordenar>.
```

Ver template completo en
``docs/source/normativa/estandares/plantillas/tpl-iniciativa-alcance.rst``.

### Costos vs ROI

Sobre un backlog típico de 18 sucesoras pendientes:

| Nivel | Items estimados | Tiempo |
|---|---|---|
| 0a sólo (hotfixes triviales) | ~4 | ~4 min |
| 0a + 0b (medios) | ~8 | ~48 min |
| 0a + 0b + 0c (heavy) | ~6 | ~150 min |

Total upfront: ~3.5 horas sobre 18 items. Alternativa rígida
("scaffold + descubrir mid-flight") observada con caso #6: ~1
hora de scaffold abortado × 6 cat-3 mal escalados = ~6 horas
perdidas + commits rework. ROI estimado 1:2.

## Checklist de auto-auditoría

Antes de escribir cualquier artefacto sustantivo:

### 1. Premisa

- ¿La premisa fundamental está verificada con datos PROVEN?
- ¿He leído la normativa / canon vigente que aplica a este
  artefacto, **completa**, no solo el título o el primer
  párrafo?
- ¿He cruzado la premisa con DEC-DOC existentes, ADRs,
  iniciativas hermanas?
- Si la premisa cambia a mitad de la redacción, **paro**, **no
  parcheo** — vuelvo al inicio.

### 2. Scope del artefacto

- ¿Este artefacto es alcance, análisis, decisiones, tareas o
  progreso? Cada uno tiene un job distinto.
- ¿Estoy filtrando decisiones a un alcance? ¿Estoy filtrando
  tareas atómicas a decisiones? Esos leaks contaminan el
  flujo.
- Alcance: QUÉ + POR QUÉ + CRITERIO + FUERA DE SCOPE.
- Análisis: hallazgos calibrados PROVEN/INFERRED, sin
  decisiones.
- Decisiones: DEC-NN con alternativas evaluadas, sin tareas.
- Tareas: T-NNN atómicas con entregable verificable, sin
  decisiones.
- Progreso: bitácora + cobertura + lecciones aprendidas.
- Index: toctree + intro corta + metadata canónico.

### 3. Bundle

- ¿Estoy a punto de crear N archivos en una sola pasada sin
  verificar el primero? **Eso es bundle, prohibido.**
- Crear de a uno, verificar template + premisa, luego seguir.

### 4. Template y convención

- ¿Estoy usando el template correcto para el directorio?

  - `pm/docs/iniciativas/` → Template A (IACT verbose con
    `:artefacto:`, `:tipo:`, `:dominio:`, `:subdominio:`,
    `:estado:`, `:version:`, `:fecha_creacion:` ISO 8601,
    `:autor: Equipo kaupamex`, `:clasificacion:`).
  - `pm/{api,ui,db}/iniciativas/` → Template B (THYROX simple
    con `:fecha_creacion: YYYY-MM-DD`, `:autor: claude`,
    `:estado:`, `:submodulo:`, `:iniciativa:`).
  - `.claude/rules/` → markdown con yaml frontmatter
    (estilo de este archivo).
  - Decisiones: `decisiones/index.rst` para DEC-DOC; ADRs
    en `backend/adr/` o `frontend/adr/`.

- ¿Estoy nombrando los artefactos según convención (kebab-case,
  sin prefijos numéricos en archivos, `<tipo>-<slug>.rst`)?

### 5. Inconsistencias propagables

- Si edito un artefacto, ¿los otros 4-5 artefactos de la misma
  iniciativa siguen coherentes con el cambio? Premisa propaga.
- Si reescribo una decisión, ¿hay tareas que la asumen mal?
- Si descubro un canon vigente que contradice mi propuesta,
  ¿reformulo desde el alcance hacia abajo?

### 6. Lo que no escribo

- ¿Estoy añadiendo contenido que no aporta? Sin relleno,
  sin "según expertos del campo", sin párrafos de
  introducción genéricos.
- ¿Estoy duplicando información que ya está en otro artefacto
  de la misma iniciativa? Cross-link en su lugar.

## Después de escribir: auto-audit

Inmediatamente después de un Write o Edit grande:

1. **Releer** el output (especialmente las primeras y últimas
   secciones).
2. Identificar **leaks**: ¿decisiones en alcance? ¿tareas en
   decisiones? ¿análisis en tareas?
3. Identificar **contradicciones internas**: el documento dice
   X en línea 50 y no-X en línea 200.
4. Identificar **premisa equivocada**: si la premisa cambió o
   se demostró falsa, **revertir o reescribir**, no parchear.

## Aplicabilidad cuando el usuario interrumpe

Si el usuario interrumpe con una corrección sustantiva
(p. ej. "ya existe una normativa que no leíste", "esto viola
otra norma", "lo creaste por bundle"), **NO continuar el flujo
actual**. Detenerse:

1. Auto-audit profunda sobre la directiva del usuario.
2. Validar la premisa contra el código/docs PROVEN.
3. Si la premisa estaba mal: revertir o reescribir desde el
   artefacto fundacional. **No parchear** el output existente
   superficialmente.
4. Solo después continuar con el siguiente artefacto.

## Casos donde la regla ya falló (lecciones)

Documentadas en
``docs/source/gestion/pm/api/iniciativas/canon-idioma-enums-error-codes/progreso-canon-idioma-enums-error-codes.rst``,
sección "Lecciones aprendidas durante el planning":

1. **Auto-auditar antes de escribir.** Primera versión del
   alcance leakeó "Decisiones de scope ya tomadas" — premisa
   mezcló alcance + decisiones. Detectado al re-leer.
2. **Leer la normativa antes de inventarla.** Primer borrador
   asumió contradicción entre DEC-DOC-005 y DEC-DOC-006 sin
   leer los documentos. Tras leer, premisa real: DEC-DOC-006
   viola la norma maestra.
3. **Premisa propaga.** Premisa falsa contaminó 4 artefactos
   antes de detectarse. Auto-audit entre cada artefacto ayuda
   a contener pero no a prevenir.

## Severidad

**CRÍTICA** — Saltarse esta regla genera:

- Artefactos con premisa equivocada que propagan a otros.
- Bundles que producen 7+ archivos con el mismo error.
- Pérdida de tiempo del operador en correcciones repetidas.
- Pérdida de confianza en la calidad del agent.

## Excepción

Operaciones triviales sin contenido sustantivo:

- Bump de versión metadata.
- Fix de typo.
- Reemplazar string específico por otro string específico
  (rename mecánico).

Estas no requieren el checklist completo, pero sí auto-audit
ligera ("¿esto rompe algo más?").

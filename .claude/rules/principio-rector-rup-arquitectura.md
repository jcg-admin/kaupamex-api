```yml
type: Principio Rector de Proyecto
category: Gobierno — analisis antes de ejecucion
version: 1.1.0
created_at: 2026-05-21 14:40:00
updated_at: 2026-07-05 01:23:35
applies_to: kaupamex v1.0.0+
source_canonical: docs/source/normativa/principios/principio-rector-rup-arquitectura.rst
```

# Principio Rector — Analisis antes de ejecucion (RUP + arquitectura)

> Cargado automaticamente en cada sesion. **Anterior y superior** a
> las demas reglas en `.claude/rules/`. Si una regla operativa
> contradice este principio, prevalece el principio.

> Origen: directiva del ejecutor 2026-05-21T14:40:00 tras corregir
> el anti-patron "PARCIAL JUSTIFICADO" en los artefactos de la
> sucesora `completar-cobertura-rup-iters-parciales`.

## Enunciado

Antes de proceder con cualquier caso, tarea o decision sucesoria,
se realiza un analisis que considera simultaneamente el marco RUP y
el estado arquitectonico actual. La decision que resulte de ese
analisis es la que gobierna, **sin excepcion**.

## Clausulas operativas

### Clausula 1 — Regla base

El camino a seguir es siempre el que resulte del mejor analisis
RUP-arquitectonico disponible, no el que preserve decisiones
anteriores ni el que sea mas conveniente ejecutar.

**Implicacion para agentes:** si una iter previa, un audit o un
comentario heredado proponen un camino, y el analisis actual
arroja un camino distinto, **prevalece el analisis actual**. No se
"respeta" la decision previa por ser previa.

### Clausula 2 — Estado heredado

- Estado correcto + analisis lo confirma → se procede sobre esa
  base.
- Estado incorrecto → el analisis lo expone, documenta la
  correccion, y el caso sucesorio parte del estado **ya
  corregido**.
- **NUNCA** continuar con estado incorrecto conocido bajo
  justificativos de conveniencia, naturaleza del scope, o deuda
  diferida.

**Implicacion para agentes:** la primera responsabilidad del
analisis al abrir un caso es PROVEN del estado heredado. Si hay
divergencia entre lo declarado y lo real, la correccion entra en
el alcance del caso actual.

### Clausula 3 — Artefactos UCS

Los UCS (casos de uso) **no son inmutables**. Si el analisis
detecta que un UCS:

- Esta mal especificado → **actualizar** el UCS existente.
- Es incompleto → **completar** el UCS existente.
- Falta del todo → **crear** el UCS faltante.

**NUNCA** continuar con un UCS incorrecto o ausente como si fuera
valido.

La autoridad para corregir o crear UCS es **parte del analisis**,
no un paso separado que requiere decision externa. El agente NO
pide permiso para corregir un UCS detectado como incorrecto — lo
corrige como parte del mismo cambio.

### Clausula 4 — Verificacion de cobertura: regla de las 8 capas

Ningun hallazgo, tarea ni caso se cierra sin verificacion PROVEN
de las 8 capas arquitectonicas:

| Capa | Path | Contenido |
|------|------|-----------|
| 1 | `docs/source/requisitos/casos-uso/` | UC narrativa |
| 2 | `docs/source/requisitos/requisitos-funcionales/` | FRs derivados |
| 3 | `docs/source/arquitectura-tecnica/` | Vistas Kruchten + modelos + modulos |
| 4 | `docs/source/backend/` | Convenciones HTTP + OpenAPI + ADRs |
| 5 | `docs/source/frontend/` | Arquitectura UI + design-system |
| 6 | `docs/source/normativa/` | Estandares + procedimientos |
| 7 | `docs/source/quality/` | Tests-implementados + TDD |
| 8 | `docs/source/risks-technical-debt/` | Registro deuda + riesgos |

El sweep **no es opcional ni abreviable** por consideraciones de
scope, tiempo o aparente irrelevancia de las capas restantes.

**Desenlaces validos del sweep:**

1. **0 hits PROVEN en capa N** → documentar con cita del comando +
   conteo. Evidencia positiva, no exencion ex-ante.
2. **Hits en capa N** → alinear en el mismo commit/iter, o crear
   sub-iniciativa explicita.

**Si el scope real excede el iter en curso:**

- Crear sub-iniciativa explicita ANTES del cierre del caso actual.
- Anotar slug de la sub-iniciativa en el `progreso-` correspondiente.
- Solo entonces marcar el caso actual como cerrado.

**NUNCA diferir** cobertura faltante para "despues" sin crear la
sub-iniciativa.

### Clausula 5 — Anti-patron prohibido: "PARCIAL JUSTIFICADO"

El estado "PARCIAL JUSTIFICADO" **no existe** como estado terminal
valido de cierre.

Declarar algo como "parcial por naturaleza", "parcial por diseno"
o "parcial por limitacion de scope" sin haber verificado las 8
capas es **exactamente el anti-patron** que perpetua deuda
invisible.

Cualquier cierre que no tenga verificacion completa de las 8
capas es un **cierre invalido**, independientemente de la
justificacion narrativa que lo acompane.

**Unica excepcion reconocida:** scope genuinamente amplio detectado
durante la verificacion → sub-iniciativa explicita (Clausula 4).

No hay un tercer desenlace "esa capa no aplica por naturaleza".

### Clausula 6 — Ejecucion paralela

Cuando el analisis identifica tareas **independientes** entre si,
se despachan **agentes en paralelo**. El criterio para paralelizar
es la **independencia arquitectonica** de las tareas, no la
comodidad de ejecucion secuencial.

Si las tareas tienen dependencia → serializar en el orden que el
analisis determine correcto.

**Patron operativo de invocacion paralela:**

```python
# CORRECTO — un solo mensaje con N Agent calls independientes
Agent(description="sweep capa 4 backend", ...)
Agent(description="sweep capa 5 frontend", ...)
Agent(description="sweep capa 7 quality", ...)

# INCORRECTO — N llamadas secuenciales sin razon de dependencia
```

### Clausula 7 — Coexistencia y fronteras de marcos

El proyecto es multi-metodologia: cada iniciativa declara su `flow:`
(rup, scrum, kanban, pm, pdca, tdd, o sin metodologia anclada) en la
metadata de su `alcance`. Los marcos **se componen, no se sustituyen**: el
`flow:` declarado gobierna DENTRO de la iniciativa; los ejes transversales
(medicion COSMIC donde hay FUR, agenda por sprint/Milestone, codigo TDD) la
envuelven sin gobernarla.

Fronteras de aplicacion (cuando un marco deja de aplicar):

- **RUP** es rector para el trabajo *design-heavy* (Elaboration: UC + vistas
  Kruchten antes de construir; ver `docs-design-first-rup.md`).
- **Scrum/Kanban** gobiernan solo el flow de ejecucion iterativa/continua;
  una iniciativa con otro `flow:` declarado NO queda sujeta a sus ceremonias.
- **COSMIC** aplica solo donde hay FUR medible; fuera de FSM (bugs, db,
  server) la salida es una talla alterna (S/M/L), no forzar CFP.
- **PMBOK** no se "sale": queda subsumido en los 12 stages THYROX.

**Accion al salirse de un marco:** re-analizar (Clausula 1 — prevalece el
analisis actual), re-declarar el `flow:` de la iniciativa, o abrir una
sub-iniciativa explicita (Clausula 4). Forzar un marco fuera de su frontera
—o declarar una iniciativa "bajo marco X" cuando sus artefactos no lo
reflejan— es una variante del anti-patron de la Clausula 5 y esta prohibido.
Si una iniciativa se pide bajo un `flow:` (ej. RUP para la pasarela de
pagos) pero sus artefactos no lo reflejan, la divergencia es estado
incorrecto heredado (Clausula 2): se corrige antes de continuar.

### Condicion necesaria

El analisis RUP-arquitectonico **no es un paso opcional previo** a
la ejecucion. Es la **condicion necesaria** para que cualquier
ejecucion sea valida.

**Sin analisis previo confirmado, no hay ejecucion.**

Se aplica en:

- Cada caso sucesorio: `alcance-<slug>.rst` con seccion "Premisa
  verificada" nivel 0a/0b/0c + citas PROVEN.
- Cada tarea T-NNN: entregable incluye verificacion PROVEN de 8
  capas.
- Cada cierre de hallazgo D-NN: `:hallazgos_cerrados:` cita PROVEN
  del sweep o de los commits que cierran drift en cada capa.

## Jerarquia con otras reglas

Este principio precede a:

- `.claude/rules/auto-audit-before-writing.md` — Premise Gate
  sigue obligatorio; alimenta al analisis RUP, no lo reemplaza.
- `.claude/rules/test-execution-protocol.md` — pytest + jest
  siguen obligatorios; ademas se verifica capa 7 y capa 8.
- `.claude/rules/thyrox-invariants.md` — I-001 (DISCOVER antes de
  planificar) es compatible y se subsume aqui.
- Todos los demas `.claude/rules/*.md` — son operativos; este es
  rector.

## Severidad

**CRITICA** — violacion de este principio causa:

- Cierres invalidos que acumulan deuda invisible (iters 22-30
  parciales como caso documentado).
- Reapertura forzada por agentes futuros que detectan los mismos
  drifts.
- Perdida de confianza del ejecutor en el cierre del agente.
- Necesidad de iniciativas dedicadas a re-cerrar lo "ya cerrado"
  (sucesora `completar-cobertura-rup-iters-parciales` como
  precedente).

## Excepciones

**Ninguna.** La unica adaptacion contemplada es la sub-iniciativa
explicita de la Clausula 4 cuando el scope detectado excede el
iter en curso.

## Canon en el proyecto

Fuente canonica del principio (RST publicable):
`docs/source/normativa/principios/principio-rector-rup-arquitectura.rst`.

Este archivo (`.claude/rules/principio-rector-rup-arquitectura.md`)
es la **proyeccion del canon al espacio de configuracion del
agente**, para que cargue en cada sesion sin requerir lectura
explicita del RST. Ambos archivos se sincronizan via los commits
del proyecto.

Si el RST se actualiza (bump version, nueva clausula), este `.md`
debe actualizarse en el mismo commit.

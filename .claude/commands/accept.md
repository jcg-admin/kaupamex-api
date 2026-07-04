---
name: Accept
description: Gate de aceptación del incremento (THYROX 6→7, EXECUTE→TRACK). Verifica el incremento/tarea contra la Definition of Done con evidencia real (no compliance). Emite ACEPTADO o RECHAZADO con gaps accionables. Delega en el agente increment-acceptor.
argument-hint: "[iniciativa/WP o T-NNN] [nivel: AC|incremento|release]"
---

# /thyrox:accept — Aceptar el incremento (gate 6→7)

Verifica la **Definition of Done** antes de cerrar una tarea o fase.

Delega en el subagente **`increment-acceptor`** vía la herramienta Agent.

El agente debe:

1. Localizar la DoD aplicable en `docs/source/quality/definition-of-done.rst`
   y los criterios de aceptación del UC / `tareas-<slug>.rst`.
2. Exigir **evidencia real** por criterio (test verde citado, commit, salida
   de comando), no compliance superficial — la carga de la prueba recae sobre
   el incremento (`react-verification-gate.md`).
3. Aplicar el sweep de **8 capas** al UC tocado (cláusula 4 del principio
   rector); un test verde con capa 5 ausente es deuda, no cierre.
4. Emitir veredicto **ACEPTADO** (pasa el gate) o **RECHAZADO** (vuelve a
   EXECUTE con gaps concretos citados).

**Argumentos:** `$ARGUMENTS` = la iniciativa/WP (o T-NNN) y, opcional, el
nivel de DoD (AC | incremento | release; default AC + incremento).

**Salida:** veredicto con evidencia por criterio. Si ACEPTADO → siguiente
`/thyrox:track`. Si RECHAZADO → volver a `/thyrox:execute` con las observaciones.

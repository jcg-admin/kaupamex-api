---
name: Status
description: Estado rápido del proyecto sin invocar agentes. Lee la fuente canónica de "qué sigue" (siguiente-mejor-decision.rst), el progreso de la iniciativa activa y git, y resume en 3-5 líneas. Adaptado a kaupamex (no usa ROADMAP.md ni .thyrox/).
---

# /thyrox:status — Estado rápido

Muestra una foto del proyecto **sin invocar agentes**. Ejecuta y resume:

1. **Fuente canónica de prioridad (SMD)** — leer la cabecera + "Snapshot
   estado actual" + "Siguiente paso recomendado":
   !`sed -n '1,12p' docs/source/gestion/pm/siguiente-mejor-decision.rst 2>/dev/null`

   Anti-staleness: si `:fecha_actualizacion:` > 7 días o `:commit_referencia:`
   no coincide con `git -C docs rev-parse --short HEAD`, advertirlo.

2. **Iniciativa activa** — el `progreso-<slug>.rst` más reciente bajo
   `docs/source/gestion/pm/<submodulo>/iniciativas/` (último modificado).

3. **Commits recientes (super + submódulos):**
   !`git log --oneline -8`

4. **Cambios sin commitear / gitlinks pendientes:**
   !`git status --short`

5. **Coherencia develop ↔ submódulos** (si aplica): los 5 gitlinks de
   `develop` deben igualar los tips de `develop` de cada submódulo.

Resume en 3-5 líneas: en qué iniciativa/fase está el proyecto, qué hay en
progreso, qué sigue (del SMD), y si hay trabajo sin commitear o gitlinks sin
bumpear que deban cerrarse (`gitlink-bump-gate.md`).

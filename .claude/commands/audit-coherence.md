---
name: Audit Coherence
description: Auditoría crítica de COHERENCIA del repo / multi-repo (no de completitud de un WP — eso es /thyrox:audit→workflow-audit). Patrón Command → Script + Agente: corre los gates mecánicos (.claude/scripts/thyrox-audit.sh) y delega el juicio cualitativo en increment-acceptor. No corrige — documenta. El reporte va a docs/source/**.
argument-hint: "[repo | submodulos]"
---

# /thyrox:audit-coherence — Auditor crítico de coherencia

Verifica que el repo sea **coherente** (no que un WP esté completo — para eso
está `/thyrox:audit` → `workflow-audit`). Patrón **Command → Script + Agente**.

## Contrato de ejecución

1. **Gates mecánicos** — corre el motor verificable y captura su salida:
   ```bash
   bash .claude/scripts/thyrox-audit.sh
   ```
   Cubre: referencias (markdown links rotos), lenguaje muerto (duro +
   candidatos a triage), coherencia del **SMD** (anti-staleness:
   `:commit_referencia:` vs docs HEAD), anatomía del skill `thyrox`,
   **coherencia parent↔submódulos** (gitlink vs clon hermano; regla
   `gitlink-bump-gate`), y heurística de **fechas fabricadas** (THH:00:00,
   regla `timestamps-iso8601`).

2. **Juicio cualitativo** — delega en el subagente **`increment-acceptor`**
   vía la herramienta Agent. Triage de los WARN "candidatos a deriva"
   (distinguir uso-real de mención-documental legítima), evidencia real
   sobre compliance. Si una decisión contradice una instrucción literal,
   gana el mejor análisis (principio rector) y se **registra como decisión
   trazable** (ADR/finding), no solo en el chat.

3. **Reporte → `docs/source/**`** (NO un `audit-report.md` suelto). Según
   `registro-reportes-agentes.md`:
   - Cross-cutting / repo → `docs/source/gestion/pm/docs/audits/reporte-auditoria-coherencia-<YYYY-MM-DD>.rst`.
   - Específico de un submódulo → `docs/source/gestion/pm/<submodulo>/audits/`.

   El reporte abre con la cabecera de procedencia (`:agente: :tarea: :fecha:
   :herramientas: :basado-en:`), tabla de chequeos (PASS/FAIL/WARN), hallazgos
   `F-NNN`, y un **action plan ordenado**. Timestamps con
   `date -u +"%Y-%m-%dT%H:%M:%S"`. Verificar aterrizaje con
   `git ls-files --error-unmatch <ruta>` antes de declarar hecho.

## Alcance según `$ARGUMENTS`

- `repo` (default) — coherencia global (los 6 gates).
- `submodulos` — foco en 5/5 gitlinks parent == tips de cada clon hermano.

**Salida:** reporte RST en `docs/source/**` con score + action plan. **No
modifica** el trabajo auditado. Complementa `/thyrox:audit` (WP) y
`/thyrox:accept` (DoD del incremento).

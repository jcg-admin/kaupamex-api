# Hallazgos — documentación obligatoria — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/hallazgos-documentacion-obligatoria.md` — se carga en sesiones con
`docs` en scope. Aquí solo el invariante operativo (Opción B, iniciativa
`consolidar-reglas-fuente-unica`, DEC-01/02):

Cada hallazgo de implementación se documenta en docs antes del commit final; secuencia de
2 commits (código + docs). **Ubicación (2026-08-03): un archivo por hallazgo** en
`pm/<submodulo>/iniciativas/<slug>/hallazgos/hallazgo-<ID>-<slug-corto>.rst` + su
`index.rst`. Los `audits/hallazgos-<slug>.rst` existentes se congelan (prospectivo, sin
retrofit): un hallazgo nuevo NUNCA se apenda a ellos.

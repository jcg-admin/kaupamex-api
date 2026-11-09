# Conciliación de asentamientos del 2026-11-09 (sección 6 de la directiva)

Fuente canónica: `outputs/continuation.jsonl` (filas `attempt` y `accepted`).
Se informaron «ocho unidades» y se enumeraron «siete hallazgos». La fuente
canónica tiene **8 unidades** con `attempt success` + `accepted`, y el
almacén de docs tiene **8 hallazgos** (H-API-1196 a H-API-1203). La
discrepancia era del reporte: contó los hallazgos a partir de H-API-1197 y
dejó fuera H-API-1196, que se asentó en la misma ventana.

| Unidad (TASK) | Hallazgo | Implementación | Asentamiento (claim) | `verifyExit` | RED / control |
|---|---|---|---|---|---|
| orm-related-implicit-access-message-0182 (TASK-API-0182) | H-API-1196 | `1993f7f4` | `3d6eb641` → `7e6e42ea` | 0 (7 passed) | `red/related-traversal-access.txt`; control en el mensaje de `1993f7f4` |
| orm-x2many-sudo-commands-0485 (TASK-API-0485) | H-API-1197 | `235f9e7d` | `40dd80f2` → `aae30cd0` | 0 (8 passed) | `red/sudo-commands.txt` |
| orm-parent-path-check-0485 | H-API-1198 | `6ce6d05c` | `bed3b121` → `17757856` | 0 (5 passed) | `red/parent-path-check.txt` |
| orm-field-index-btree-0485 | H-API-1199 | `0eeab536` | `156f70ea` → `1b01cf01` | 0 (8 passed) | `red/field-index-to-db-index.txt` |
| orm-company-dependent-index-0485 | H-API-1200 | `35b14737` | `a6b5bf74` → `ff8b282c` | 0 (2 passed) | `red/company-dependent-partial-index.txt` |
| orm-new-django-comodel-0485 | H-API-1201 | `f78e62e3` | `9966218b` → `599a9e35` | 0 (2 passed) | `red/update-cache-django-comodel.txt` |
| orm-one2many-new-records-0485 | H-API-1202 | `bb4fba46` | `055bbbe6` → `3f14bb5b` | 0 (2 passed) | `red/one2many-on-new-records.txt` |
| orm-many2one-write-inverses-0485 | H-API-1203 | `a2fb50d6` | `f87e5004` → `2dfb5be0` | 0 (4 passed) | `red/many2one-write-inverses.txt` |

Comprobaciones:

- Los 8 commits de reclamo son ancestros de `HEAD` (`git merge-base --is-ancestor`).
- Una sola fila `attempt` por unidad. El falso «Record … settlement» `7041c372`
  de la unidad de sudo no dejó fila en `continuation.jsonl`; el reclamo
  válido es `40dd80f2`.
- Desde aquel episodio, `settle_unit` aborta con el árbol sucio o sin
  `verify=0` antes de escribir el veredicto.
- Integración y aceptación: `plan_coverage.json` declara
  `acceptance: requires executor authority (I-011)`. Ninguna unidad está
  aceptada globalmente.

*Métrica:* filas de `continuation.jsonl`, hallazgos `.rst` y ascendencia de
los commits.
*Ciega a:* que la suite completa y multidb se hayan ejecutado sobre cada
revisión de implementación. `continuation.jsonl` registra sólo el `verify` de
la unidad; la regresión de impacto vive en cada archivo `red/` cuando se
anotó.

# Corte 4.4.1-A — unidad 3 asentada, bloque D en F2

Fecha: 2026-11-18T00:23:55Z. Rama `feature/vm-x2hokp-orm-root`. Desde
`9833ba83` hasta `a58ac65d`: 24 commits publicados (`git log --oneline
9833ba83..HEAD | wc -l`). La ejecución no se detiene por este registro.

## Hecho y verificado

| Unidad | Commits | Evidencia |
|---|---|---|
| `SET`/`CLEAR` de un One2many acotados al dominio del campo | `32da44b9`, `6319d0b4`, `67688172` | 3 casos; anulado el filtro caen los 2 de dominio y los 2 del diario |
| `account-journal-payment-method-lines-0515` | `29285b00` | F2 verde en `4033a0ae`: 13698 passed, 66 skipped, 79 xfailed, `EXIT=0`. Asentada en `f42ae3d5` (verify: 737 passed) |
| veredicto de tres estados en `persist_gate_evidence.py` | `7994ec00` | 6 casos; anulado el conteo de errores cae 1 |
| resiembra bajo entorno de superusuario | `6c124bbd`, `a72e109f` | reproduce el `ValueError` de la F2 al anular la asignación |
| preflight: base a medio resembrar | `9630445e` | 3 casos; el preflight real rehusó `gw1` |
| alias de base que una prueba dejaba registrado | `4033a0ae` | anulado el borrado cae 1 |
| bloque D: 44 filas `set null` | `0f31b25a`, `a58ac65d` | contrato 74 passed, 28 xfailed; anulada una fila caen 2. **F2 en curso sobre `a58ac65d`** |

## Sin cerrar (se conserva)

- Contrato de política de borrado: 27 filas siguen `xfail` (25 `restrict`,
  2 `set null`). Investigación de nivel 3 en
  `outputs/orm-fk-delete-policy-contract-0515/research/`.
- `account-payment-method-line-field-0515`: diseñada
  (`designs/payment-method-line-field.md`), sin implementar.
- `account-journal-mixins-0515`: sin empezar; el mixin de alias depende de
  TASK-GEN-0413.
- Eje de prosa heredada en `check_reference_flow.py`: sin empezar.
- `tests/unit/tools/test_convert.py:98`: tautología sin corregir.
- Por qué `test_database_exists_catalog` pasó en las F2 de `9f23b2fc` y
  `73d845ac` y falló desde `29285b00`: UNVERIFIED.
- Una fila de `ir_model_data` de diferencia en `gw1`
  (`account.model_account_invoice_report`): sin medir su origen; la F2 de
  `4033a0ae` pasó con ella ausente.
- `plan_coverage.json` tras asentar: 71 tareas abiertas, frontera 1, 1448
  obligaciones sin unidad. El objetivo no está cumplido.

## Desperdicio medido

| Ejecución | Segundos | Qué compró |
|---|---|---|
| subconjunto derivado (21 directorios) antes de la F2 | 691 | 9493 passed; contenido entero en la F2 que vino después |
| F2 `29285b00` | 975 | primer fallo de resiembra |
| F2 de diagnóstico ×2 sobre `7994ec00` | 867 + 882 | la traza del volcado; la primera se leyó mal (era el alias) |
| F2 `a72e109f` | 455 | nada del cambio: base `gw1` rota por el corte anterior |
| F2 `9630445e` | 875 | el alias `orm_a` |
| F2 `4033a0ae` | 906 | el verde |

Cinco F2 falladas por dos defectos de infraestructura de pruebas y un
residuo; `--maxfail=1` deja ver un solo fallo por ejecución. Cambios de
método ya aplicados: el preflight detecta la base a medio resembrar; el
subconjunto derivado no se repite cuando el cambio es ancho y la F2 va a
correr igual (bloque D fue directo a F2 tras sus dos archivos de prueba).

*Métrica:* segundos que publica pytest en su resumen.
*Ciega a:* el tiempo de preparación y de preflight de cada ejecución.

## Subagentes

Tres investigaciones de sólo lectura (`sonnet`): 503 417, 486 596 y 531 001
tokens según el titular del arnés, que excluye la caché leída y por tanto no
es su costo. Informes en el Workbench, nivel 3; dos conteos reproducidos
por el coordinador (71 filas; 8 sitios de creación de pagos).

## Reclamo del contenedor (2026-11-18T01:16Z)

Durante el subconjunto derivado de la fila `project.ProjectTask.project` el
contenedor se reclamó: `boot_id` pasó de `a0af12c0…` a `432be89e…`
(`uptime -s`: 01:16:26) y el proceso de espera terminó con salida 137.

| Qué | Estado tras el reclamo |
|---|---|
| árbol de trabajo (3 archivos modificados, migración `0009` y pruebas nuevas, sin commitear) | intacto |
| `HEAD` | `ca836c02`, igual que el remoto |
| scratchpad de la sesión | intacto |
| PostgreSQL | parado; arrancado con `probes/gate-procedure/ensure-postgres.sh` |
| bases de los cuatro workers | `PREFLIGHT OK` |
| subconjunto en curso | muerto al 93 % sin fallos; relanzado entero |

Nada de lo publicado se perdió. Lo no publicado sobrevivió esta vez porque
el disco se conservó; no es una garantía.

## Bloque C en curso (2026-11-18T02:50Z)

Unidad `orm-fk-delete-policy-contract-0515`, las dos filas de
`account.AccountPartialReconcile` que siguen `xfail`. Diseño:
`designs/restrict-ondelete-partial-reconcile.md`.

| Paso | Revisión | Qué | Verificación derivada |
|---|---|---|---|
| C1 | `2611ef87` | `unlink` de la conciliación parcial y total con el orden de la fuente; `delete_and_update_matching` retirado | 866 pasan, 2 xfailed |
| C2a | `07d92374` | `move_name` y `date` del apunte, relacionados almacenados; migración `0046` | 5681 pasan, 40 omitidas, 8 xfailed |
| ORM | `1b45bb0c` | lectura de un x2many sobre varios registros (`designs/x2many-multi-record-read.md`) | 8378 pasan, 66 omitidas, 8 xfailed (mismo árbol que C2) |
| C2 | `e60f5b88` | `AccountMoveLine` adopta `BaseModel`; `remove_move_reconcile` y `unlink`; nombres inversos cruzados corregidos, migración `0047` | la misma ejecución |
| C3 | — | `AccountMove` adopta `BaseModel`; `unlink` | medición de la adopción en curso |
| C4 | — | `PROTECT` en `debit_move` y `credit_move`; migración `0048` | pendiente de C3 |

Tres cosas que el plan no preveía y que salieron de medir, no de leer:

1. La adopción de `BaseModel` en el apunte dejó 14 fallos, 13 por
   `Invalid field 'date'`: `_order` citaba dos campos sin portar que nadie
   leía mientras el modelo ordenaba por `Meta.ordering`. De ahí C2a.
2. El inverso de un Many2one sólo se leía sobre un registro. La fuente
   devuelve la unión (`_Relational.__get__`); el `Many2one` ya tenía esa
   rama y las tres rutas x2many no. De ahí la pieza del ORM.
3. `matched_debit_ids` y `matched_credit_ids` estaban cruzados respecto de
   la fuente. Ningún lector vivo cambiaba de resultado (los dos toman la
   unión), así que ninguna prueba lo delataba; lo delató leer la
   declaración de la fuente para escribir `remove_move_reconcile`.

Sin F2 todavía sobre estas revisiones: el bloque toca `src/orm`, que es
mecanismo transversal, así que la F2 completa es obligatoria antes de
asentar y se lanza al cerrar C4. Las cifras de arriba son regresiones
derivadas, no aceptación.

*Métrica:* resumen de pytest de cada regresión derivada, con `-n 4` y
`test_multidb_isolation` excluido.
*Ciega a:* los directorios fuera del derivado y la F3.

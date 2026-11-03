# Bootstrap ORM y contrato compute — lote incremental

Continúa API b1b6f59b, Docs fdc991771 y Provider9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f. Referencia abe4040ec1a45beee90fb694e4eae4453e46b389, sin cambio a main. No reinventa los dos AS IS, sus60TASK,33descriptores/66grupos ni las78consultas históricas GitHub.

## Cambios y alcance

- d2001199: migración inicial nativa de los DOS modelos Django actualmente registrados de test_orm. swappable_dependency(AUTH_USER_MODEL) ordena res_users antes de las FK. Un único enlace desde apps no migradas apunta a una migrada; evidencia unmigrated-relations.json. No declara completo el corpus Odoo test_orm ni cierra GEN0312. No SQL permanente manual, nuevo motor, FK deshabilitada o cambio de workflow.
- 8b6ea823: ResGroups.full_name asigna, declara dependencias y short_display_name. FieldDescriptor usa identidad técnica al informar falta de asignación y no el __str__ que recursa. El bucket contextual con id estable gana sobre el almacén Django de otro contexto. Environment.cache_key lee el mapa derivado existente, no sólo field._depends_context. No nueva caché o infraestructura virtual.
- Dos contratos de14elementos en outputs; procedencia de ocho símbolos exactos mediante reference_roots.require y counterpart_body.declarations_of en pinned-source-contracts.json. No inventario Odoo nuevo.

## Verificación y fallos conservados

Bootstrap-before exit1 reprodujo sync_apps→FK→res_users ausente sobre una base nueva. Bootstrap-after exit0 aplicó todas las migraciones existentes, comprobó tablas/FK validada y repitió migrate. Sin la migración, el control negativo vuelve al mismo fallo (exit1). Compatibilidad legacy exit0: native sync tras base, adopción inicial Django --fake-initial; columnas/restricciones/fila testigo permanecen y makemigrations test_orm no detecta cambios. Ninguna base compartida migrada. La adopción legacy exige verificar el esquema existente y aprobación de su flujo de despliegue, no un fake general.

Segunda preparación mediante pytest-Django completada:41cuerpos PASS (incluidas las dos pruebas antes bloqueadas),1ERROR de teardown, exit1 agregado. Transaction.flush no encuentra base.public_user; luego falla autocommit. No res_users/prepare-schema failure. Flush no se modificó, pero el origen/fixture interaction todavía requiere control independiente; no se declara heredado automáticamente ni se arregla bajo bootstrap.

Compute: rojo7FAIL/1PASS; corrección acotada y regresión126PASS. Cuatro controles en memoria: Consumer2FAIL, diagnóstico1FAIL, almacén de instancia1FAIL, clave de contexto1FAIL. Se exige fallo de test real, no sólo exit1. Los primeros intentos negativos fallaron por orden de import (logs invalid-startup); NO acreditan discriminación. Hubo además un intento Consumer con self.env no disponible y metadata derivada retenida entre mocks; ambos se corrigieron, con logs intermedios conservados.

Regresión estructural independiente214PASS/1XFAIL heredado. GEN0559 vuelve a pasar16PG por cambios materiales de lectura/caché; no se repiten su admisión ni controles anteriores. preserved-contracts.json demuestra sus dos cuerpos AST sin cambios y fuentes/pruebas0419/0420 idénticas. No se reejecutan sus pruebas PG históricas válidas sin motivo.

Fallo residual real: virtual-context-limitation.log exit1. Un objeto Django con pkNone reutilizado entre contextos conserva la etiqueta previa. Está relacionado con GEN0579/NewId; no se implementa identidad virtual ni se declara todo compute aceptado. El caso con id estable sí discrimina y pasa. Seguridad sudo/acceso del Consumer y restantes ramas de cache_key no quedan aceptadas por estos probes.

CI anterior39669997683 terminó FAILURE,10674errores de setup (10636res_users,38transacción abortada),26skips/1xfail. Cuerpos funcionales bloqueados no aceptados. Log íntegro comprimido, SHA y comando en ci-before.json. CI posterior a publicación se verifica en PR109; desaparecer res_users no implica CI global PASS. Sphinx NOT_EVALUATED.

## Autoridades, admisión y continuidad

admission-and-provenance.json conserva cinco identidades nativas, revisión Provider, estado/owner/dependencias raw y claims. Identidad estable verificada con mapping_from_store/lookup. Lectura mediante resolve_store_dir(create=False)/connect_readonly; ningún estado oficial escrito. GEN0312 pending/ownerNULL no fue considerado disponible por eso: es una corrección limitada de bootstrap expresamente autorizada y reclamada.0415 completed y0417 in_progress permanecen;0576 completed se conserva junto con su corrección y alcance exacto. No se reabre ni asigna ninguna TASK automáticamente.

Usados session.job_runs.jobs_dir/scaffold_run/settle y workbench.manifest.declare_workbench/checkWorkbench, CLI claimsCommand para claims y releases. El reader task_source defectuoso/1072 y la cualificación del runtime local permanecen según evidencia válida de la misma revisión. Ninguna TASK fue ejecutada por inferencia local Thyrox; esto es ingeniería de Codex autorizada. Sin segundo selector/planner/runner/TaskStore. No merges ni modelos externos.

Los AS IS de orm-as-is-substantive-20261021T194156 se actualizan sólo para0415/0417/0416/0559 y grupos contextuales afectados, conservando conclusiones históricas identificadas y hashes de entrada. Se enlazan0312/0576 como relaciones existentes; no se regenera todo el expediente ni las78consultas. Los ocho ordinales ambiguos permanecen sin inventar identidad.

## Reproducción portable

Desde la raíz Git de API, con uv frozen y Docker/PostgreSQL disponibles, declarar ORM_QA_CONTAINER, ORM_QA_HOST y ORM_QA_BRIDGE según el entorno verificado. Ejecutar:

```sh
uv run --frozen python scripts/evidence/orm-bootstrap-compute-20261021T210528/probes/qa_context.py uv run --frozen python scripts/evidence/orm-bootstrap-compute-20261021T210528/probes/bootstrap_contract.py
```

La fixture declara settings y crea una base/rol impredecibles exclusivamente propios; cleanup finally los elimina junto a su regla SCRAM. No depende de /workspace, archivos .env, credenciales versionadas ni otro transcript. Se puede invocar el verificador pytest o los controles compute_negative.py con la misma fixture. El wrapper temporal usado para pruebas sin DB sólo aportó variables de settings y no es una dependencia de reanudación. No recrear QA compartida.

Continuar revisando CI/publicación y la unidad acotada; GEN0579 requiere admisión propia y representación virtual verificada. La corrección de bootstrap no acepta el corpus completo test_orm. Las demás condiciones del AS IS siguen vigentes; no seleccionar TASK ajenas o sin owner por defecto. Evidencia y decisiones se publican en API109/Docs154, sin merge.

# TASK-API-0478 — validación local y CI al primer fallo

Solicitud directa del usuario: validar localmente antes de depender del resultado
de GitHub, detener las etapas al detectar un error, implementar las mejoras y
registrar la TASK. Baseline API: `12f8eee5218c69c316b67a80bc0c409dbe6f6c74`.
No se modifican contratos funcionales ORM, estados de TASK históricas, hooks,
`.env`, protecciones ni otros productos. No hay inferencia local de Thyrox.

## Registro y autoridades existentes

Thyrox `9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f`: búsqueda de tareas mediante
`agent_store buscar-tareas` y su conexión readonly. `related-tasks.json` conserva
las coincidencias de CI API y sus identidades. TASK-API-0136 trata PDF/CI histórico;
TASK-API-0093 conserva el drift de migraciones; ninguna declara el contrato
compartido local/CI al primer fallo. Las búsquedas de fail/preflight del Provider
no encontraron una TASK equivalente para este Consumer.

La solicitud autoriza explícitamente registrar esta TASK nueva. `TaskCreate`
existente devuelve ordinal local1441 en sesión
`168b0fdf-bfe4-590b-b6c0-b6be124c124a`. `assign_missing_ids/persist_to_store` asignan
**TASK-API-0478** sólo a esa fila; `correct_layer` declara API con razón y conserva
la identidad. `TaskGet` confirma propietario `codex-ci-local`, estado `pending`.
Cero aristas declaradas no se interpreta como independencia o cualificación
automática: el alcance es el CI Consumer expresamente solicitado y requiere
dependencias nativas y recurso PG propio. No se cambian estados para dar por
aceptada la implementación. La exportación de esa TASK, no del store, queda en
`task-created.json` y `task-registered.json`; el store nativo del Provider queda
actualizado localmente, sin afirmar su sincronización remota.

Los mecanismos genéricos permanecen en Thyrox: TaskCreate/Get, identidad, claims,
jobs_dir/scaffold_run, manifiesto y settle. Sus interfaces, revisión, comandos,
resultados y limitaciones están en `interfaces-and-provenance.json`. El runner
Provider se probó con su gate real `provider-evidence`: 1PASS/1, exit0. No tiene
un contrato registrado para ejecutar esta suite API ni una opción fail-fast.
El hook `stop_tests` es informativo por diseño; no se lo presenta como gate.
Se amplía únicamente el Makefile existente del Consumer, sin otro runner,
TaskStore, scheduler, selección ni sistema de evidencia.

## Cambio y comprobaciones

`make ci-verify` es la orden compartida: perfil Python3.12, uv frozen, validación
del destino efectivo Django, compilación PDF, suite completa PostgreSQL con
`--create-db --maxfail=1` y JUnit. Una sola receta preserva secuencia incluso
con `make -j`. Actions conserva nombre de workflow/job, condiciones del PR y
protecciones; usa DB por ejecución, instala dependencias nativas, limita el job
a60min e intenta subir resultados con `always()`. No se usa continue-on-error,
reintento, baseline nuevo ni eliminación de pruebas para publicar verde.

18PASS en `mechanism-tests.log`: rechaza producción/QA compartida incluso con
autorización por nombre; rechaza motor, módulo, TEST.NAME o consentimiento
inconsistentes; fallos inyectados en cada etapa impiden las siguientes aun con
`make -j4`; tanto una aserción fallida como un error de fixture interrumpen
pytest antes de la segunda prueba y producen JUnit. Make sale no cero y muestra
el exit7 original de la etapa de control. `actionlint1.7.12` aprueba el workflow
(`workflow-lint.json`); los archivos Consumer tienen hashes en
`verified-files.json`. La prueba negativa directa del guard contra la QA de la
configuración de test terminó exit2, sin abrir ni recrear esa base.

## Ejecución real y límites

`local-ci.log`: exit2, falta `png.h`; no se ejecuta pytest y el harness elimina
su DB/rol/HBA. `local-ci-provisioned.log`: PDF PASS, pytest rehúsa antes de la
suite por `pg_isready` ausente (pytest1, Make2); limpieza propia completada.
Ambos son fallos reales de precondiciones locales, no fallos funcionales ORM.
No se los convierte en pruebas aprobadas.

El usuario del entorno no tiene privilegios de apt ni sudo. Se extrajo el paquete
libpng-dev exactamente correspondiente al runtime instalado y se obtuvo el
cliente pg_isready del contenedor PG existente, sin modificar el sistema ni los
checkers. Fuente, versiones y hashes en `interfaces-and-provenance.json`.
CPATH/LIBRARY_PATH/PATH sólo se declaran para esa invocación. El harness existente
`orm-bootstrap-compute-20261021T210528/probes/qa_context.py` crea rol/DB aleatorios;
se concede CREATEDB únicamente a su rol para que pytest pueda recrear su DB.
No se recrea QA compartida ni se siembra un actor para esconder errores.

La ejecución con precondiciones completas terminó **FAIL**: 77PASS, 1SKIP,
1ERROR, 489.48s. pytest1, Make/harness2; se detiene tras el primer error. Los
logs completos están en `local-ci-complete-prerequisites.log`, JUnit en
`local-ci-junit.xml` y resultado estructurado en `verification-result.json`.
El harness eliminó su base, rol y regla HBA: recuentos restantes DB0/rol0.
El job nativo se liquida con exit2, no como aprobado porque el mecanismo detectó
el fallo. No se suman los 18 tests del mecanismo a los77 de la suite como
cobertura global, pues pertenecen a ejecuciones y alcances distintos.

Primer error: preparación de
`TestCartSnapshotsV2.test_saves_cart_and_returns_200`. `cart_with_item` llama
`add_item_to_draft` → `_line_snapshot_name` → `str(product)` → `display_name`.
`ProductProduct._compute_display_name` devuelve texto sin asignar el campo;
el descriptor exige asignación y rechaza `product.ProductProduct(1,).display_name`.
Las cinco fuentes del recorrido son idénticas al baseline12f8eee5, comprobado
por hashes, sin cambio funcional en este lote. Esto demuestra la contradicción
del código existente; no se repitió una suite global del baseline ni se atribuye
el resultado remoto a esta causa sin sus logs.

`compute-related-tasks.json` conserva las coincidencias nativas. GEN0386 está
completed para display_name universal;0415 completed para despacho compute;
0417 in_progress sin propietario. Son autoridades para reconciliar el caso,
no autorización para declarar elegibilidad, reabrirlas, agregar una TASK duplicada
o debilitar la asignación estricta. No se corrige ProductProduct como efecto
secundario de implementar el contrato CI. La nueva0478 conserva owner y pending,
con aceptación remota e integración pendientes.

Las pruebas no alcanzadas permanecen no evaluadas. Un CI anterior o un
subconjunto local aprobado no acreditan este head ni completan el ORM.
El protocolo y sus dependencias están en `docs/ci-local.md`; AGENTS.md incorpora
la obligación de ejecutar el contrato local antes de publicar para aceptación,
sin instalar ni modificar hooks. Publicar evidencia/correcciones en un PR
pendiente no convierte la suite en PASS.

# Continuación: estado de módulos por base

Se continúa el expediente `orm-module-lifecycle-20261022T023817` y la iniciativa `completar-raiz-orm`, sin nuevo plan rector. Referencia Odoo Community fijada: `abe4040ec1a45beee90fb694e4eae4453e46b389`; Provider: `9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f`. No se utiliza el texto de las cabeceras como prueba de implementación.

## Cambios funcionales

- `d34c0aaf`: `update_module_list --database <alias>` conserva estados operativos persistidos, crea entradas disponibles como no instaladas, reconcilia disponibilidad no operativa y dependencias, y revierte una actualización incompleta. No deriva instalación de INSTALLED_APPS.
- `e9211d51`: IrModule.button_install/button_upgrade/button_uninstall programan estados transitorios con autorización administrativa, bloqueo ordenado, dependencias, auto_install, requisitos externos, exclusiones individuales y protección de base. Reutilizan ModuleGraph, el recorrido de dependencias y transaction.atomic. Dependencias y exclusiones ligadas conservan su base; lotes con IDs iguales entre bases se rechazan. La migración0087 sólo altera metadata/choices de IrModule.state; se excluyó deriva no relacionada de zonas horarias.

TASK-API-0382/session168b0fdf-bfe4-590b-b6c0-b6be124c124a/local737 conserva pending y owner codex-module-lifecycle. Se consultó TaskGet nativo, sin nuevas escrituras de propietario ni de estado en este lote. Las claims se adquirieron/liberan con claimsCommand de Thyrox. Las interfaces reales, revisión y parámetros se registran en outputs/native-task-0382.json y admission-continuation.json. No se implementó otro TaskStore, planificador o coordinador; no hubo inferencia local ni remota atribuida a Thyrox.

## Validación y experimentos

Baseline congelado del catálogo: 5FAIL/1PASS en452.96s (`catalog-baseline.log` y fuente histórica no ejecutable). Demuestra sobrescritura de estado, instalación por importación, parcialidad y ausencia de alias explícito.

Primera verificación:84PASS/1FAIL en449.59s. La prueba histórica esperaba coherencia contra la lista global aun con catálogo vacío. Se conservó el fallo, se corrigió el fixture para declarar módulos instalados y se añadió el control de catálogo vacío con código importado. No se restauró la inferencia global para hacerla pasar.

Segunda verificación:86PASS en469.78s, con PostgreSQL exclusivo y las migraciones reales (`module-state.junit.xml`, verification-batch.log). La última refinación del lote/alias y exclusiones se verifica además por la sonda final de dos bases sobre el código final. La suite global ci-verify conserva por separado su resultado y nunca se sustituye por el subconjunto.

`database-module-states.json` verifica dos bases físicas propias con fixtures de estado derivados de manifiestos reales base/uom/product, no instalaciones realizadas: catálogo A base instalado, B base/uom/product instalados; solicitudes divergentes; dependientes de upgrade/retirada; rollback; peticiones concurrentes en dos conexiones; estados de dependencias diferentes; rechazo de lote mixto con PKs iguales; lote ligado en una consulta y exclusión ligada a su base. Usa los servicios create_empty_database/drop_database existentes y SchemaEditor para preparar únicamente tablas del fixture. No se copian tablas de producción ni se presenta bulk_create de fixtures como instalación.

El refresco de las dos bases usa metadata ya coincidente. El primer experimento (`database-module-states-signal-boundary.*`) demuestra que una actualización efectiva de metadata en el runtime con todos los addons puede entrar en signals globales de base_automation que consultan sin alias. Ese fallo sigue abierto; no se desactivaron signals ni se declara completo el comando bajo todos los Consumers. El fallo posterior del gestor de relaciones (`*-related-manager-boundary.*`) se corrigió usando el manager explícito antes de evaluar relaciones. `dependency-state-before.log` demuestra otra pérdida de alias antes de corregir el lote. Las variantes y sus límites se conservan; no se mezclan intentos de instrumentación con PASS definitivos.

## Registro efectivo: capacidad y frontera

La sonda registry_process.py usa procesos frescos y el Apps nativo, nunca set_installed_apps por solicitud. Dos rosters componen modelos diferentes; base_address_extended añade city_id sobre ResPartner y base solo no lo expone. Importación exitosa no equivale a aceptación: las comprobaciones de modelos detectan E300/E307 por base.IrUiMenu.group→authz.Capability cuando authz no está instalado.

El cierre real de auto_install del grafo incorpora authz/authz_passkey y supera las comprobaciones de modelos. Es una capacidad verificada del stack para futura integración; no hay binding productivo por base, cargador persistente ni recarga de workers cualificados. Los resultados separados están en registry-process*.log/json. La fuente base/migrations/0001_initial.py depende de authz0001 y contiene la FK; no se infirió de sus comentarios. TaskGet322 resuelve TASK-API-0173, pending/owner null, sobre el ciclo base↔authz. No se declaró automáticamente elegible ni se movieron identidades de capacidades o migraciones históricas.

## Clasificación de compute/CI

`compute-boundary.json` demuestra el mismo fallo de asignación en DisplayNameMixin genérico y ProductProduct._compute_display_name. Ambos devuelven cadenas; el descriptor real exige asignación. Dos controles que conservan el cálculo y asignan pasan. No es prueba de un defecto aislado de product; no se cambia el descriptor para aceptar retornos ni se inicia una campaña de modelos de negocio. La sonda modifica clases sólo dentro de patch controlado y no ejecuta SQL de negocio. TaskGet1192 confirma TASK-API-0417 in_progress/owner null; no se asume disponible ni se altera su estado.

El run remoto39715997899/head d25042fd terminóFAILURE en Verify API; se preservó metadata del run y su upload de resultados fue exitoso. No se inventa causa de un log remoto vacío. La causa local y la nueva prueba discriminante se documentan por separado.

## Obligaciones que no se declaran resueltas

Programar to install/to upgrade/to remove NO ejecuta instalación, actualización ni desinstalación. Registry.new aún no consume de forma funcional todos los argumentos de módulo. Permanecen loader de esquema/datos/hooks, composición efectiva por base en runtime, separación de versiones, semántica de países/categorías, invalidación/recarga multiworker, metadata compartida y retirada de esquema. La migración company auth/contenttypes sigue ligada a DEC-AISL-05 y al fallo documentado del lote anterior. No se cierra por llamarla divergencia: continúa siendo implementación obligatoria dentro de TASK-API-0382 y sus dependencias.

No se declara completo el documento, la TASK, la autoimplementación local ni completar-raiz-orm. No merges.

## Continuidad y reproducción

Las sondas nuevas y la transformación AS IS están en probes/, nunca exclusivamente en /tmp. El adaptador de imports /tmp/orm_batch_env.py ya tiene copia histórica publicada en el expediente anterior; no se usa para pruebas DB. Dos intentos rápidos fallaron por configuración de prueba (pg_isready ausente, después credenciales sintéticas en un fixture autouse que sí usa DB); routing-graph-regression.log conserva el segundo, y no cuenta como fallo funcional ni PASS. Se corrigió la invocación usando el harness propio, no las credenciales ni .env compartidos.

Resolver raíz por Git; usar uv congelado. El comando de dos bases es: uv run --frozen python scripts/evidence/orm-bootstrap-compute-20261021T210528/probes/qa_context.py uv run --frozen python <este-run>/probes/database_module_states.py, con ORM_QA_CONTAINER/HOST/BRIDGE explícitos y CREATEDB sólo para el rol recién creado por el harness. El log registra las operaciones y cleanup. Los rosters experimentales usan DJANGO_SETTINGS_MODULE=settings_module_roster y PYTHONPATH apuntando a probes más src; ORM_PROBE_MODULES configura sólo la sonda, ORM_PROBE_RESOLVE_DEPENDENCIES=1 activa el mecanismo existente de cierre del grafo. No son interfaces productivas.

El AS IS se actualiza mediante probes/reconcile_state_as_is.py: añade un registro nativo0382, enlaza el grupo de composición existente y corrige sólo la observación0417 afectada. No regenera las60TASK/66caracterizaciones ni las usa como denominador. Ver outputs/module-state-contracts.json para14dimensiones y condiciones de aceptación. No reejecutar escrituras de TASK por conservación.

## Resultado global final

make ci-verify terminóFAIL, exit2 (pytest1):77PASS,1SKIP,1ERROR en487.20s por ProductProduct.display_name. El harness confirmó DROP DATABASE y DROP ROLE. La suite se detuvo al primer error; lo posterior no está evaluado. Mismo primer fallo previo a d34c0aaf/e9211d51; no se presenta como PASS. JUnit final: outputs/ci-final.junit.xml. Las86pruebas focalizadas no sustituyen este resultado.

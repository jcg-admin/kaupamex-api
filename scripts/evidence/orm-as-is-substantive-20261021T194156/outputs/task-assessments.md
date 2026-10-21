# Revisión individual TASK AS IS

Head 99f4a0445c163b8a5228e3df68121ce27905559b; develop observado ed55e6d5ff4879f0e7170ed1daf5fb90eff6154f. La pertenencia de commits no sustituye verificación de conducta.

## TASK-API-0216 — Gate: orm.fields.__all__ sólo contiene clases de campo

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '383'}.

El criterio clases-only contradice factories Selection/Char/Json exportadas: comprobar el vocabulario consumido, no imponer herencia a las factories.

Siguiente condición: Reconciliar H-API-616 y criterio del gate con FIELD_TYPES; no ejecutar un guard que rechace exports legítimos.

Fuente: src/orm/fields.py:__all__, src/addons/base/models/ir_model.py:FIELD_TYPES.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_field_type_vocabulary.py (Executed named cases; see phase/outcome)

## TASK-API-0283 — field_description sin translate= mientras la referencia lo declara translate=True

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '487'}.

La declaración actual aún carece de translate=True. Etiquetas y almacenamiento multilingüe son obligaciones distintas; la flag no prueba jsonb/PO.

Siguiente condición: Comprobar solapamiento con PR110 antes de reservar el cambio; GEN0060/0062 no quedan satisfechas por metadatos.

Fuente: src/addons/base/models/ir_model.py:field_description.
Commits con cita explícita: 1; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-API-0397 — Construir BaseModel propio desde el contrato medido de la referencia

Estado nativo: in_progress; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1167'}.

El núcleo ya construye recordsets con ids/entorno, cardinalidad y protocolos de conjunto; las pruebas existentes ejecutadas cubren ese núcleo. mapped aún contiene el bloqueo fetch.

Siguiente condición: Conservar núcleo; continuar por contratos faltantes de fetch/new/acceso, no portar de nuevo BaseModel ni declarar sus194métodos aceptados.

Fuente: src/orm/models.py:BaseModel.
Commits con cita explícita: 5; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_base_model_recordset.py (Executed named cases; see phase/outcome)

## TASK-API-0398 — Verificar contrato por contrato los 21 del cubo TRAE de BaseModel

Estado nativo: in_progress; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1168'}.

El censo histórico por nombre no resuelve los21contratos. create/exists/update y operadores tienen semántica distinta de QuerySet; la nueva ejecución verifica el núcleo propio, no convierte los21en delegables.

Siguiente condición: Usar veredictos históricos por cuerpo; delimitar los contratos de persistencia aún sin conformidad, especialmente exists/new.

Fuente: scripts/workbench/basemodel-contract-20260911T030334/census_class.py:ast.parse, src/orm/models.py:BaseModel.
Commits con cita explícita: 1; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_base_model_recordset.py (Executed named cases; see phase/outcome)

## TASK-API-0399 — Portar BaseModel.fetch — mapped por ruta de campo sobre PREFETCH_MAX lo exige

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1170'}.

mapped por ruta sobre PREFETCH_MAX lanza NotImplementedError y cita0399. No hay implementación de fetch/_fetch_query en BaseModel; el camino pequeño no acepta prefetch grande.

Siguiente condición: Admisión requiere unidad fetch y consultas/cache/acceso verificables; no sustituir fetch por construcción de filas ni convertir ausencia en nueva TASK.

Fuente: src/orm/models.py:mapped.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_base_model_recordset.py (Executed named cases; see phase/outcome)

## TASK-API-0400 — Portar _sorted_order_to_function — sorted() por cadena y por _order lo exige

Estado nativo: completed; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1171'}.

La implementación existe y las pruebas ejecutadas ejercitan callable/cadena/order/nulls y validación. Conserva un xfail heredado que debe leerse por nodeid, no contarlo como PASS.

Siguiente condición: Conservar helper; revisar el caso xfail antes de aceptar todo sorted; integración histórica se mide por commits, no por completed.

Fuente: src/orm/models.py:_sorted_order_to_function.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_sorted_order_to_function.py (Executed named cases; see phase/outcome)

## TASK-API-0401 — Extender la guarda de tamaño al acceso llano rs.label

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1172'}.

La guarda por __getitem__ y mapped no demuestra la misma guarda por descriptor Django ordinario. Cambiar todos los descriptores afecta el coste de lectura medido históricamente.

Siguiente condición: Decisión arquitectónica/coste y prueba de rs.label vacío/múltiple preceden a la ampliación; no admitida por ownerNULL.

Fuente: src/orm/models.py:_read_field, src/orm/fields.py:FieldDescriptor.
Commits con cita explícita: 1; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_base_model_recordset.py (Executed named cases; see phase/outcome)

## TASK-API-0402 — Hacer que las filas que Django construye lleven la terna del recordset

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1173'}.

__init__,from_db y save ya instalan la terna. El xfail de sorted aún cita su ausencia, pero ejecutado con --runxfail falla al solicitar DB por ForeignKeyDeferredAttribute; no prueba que falte la terna. Estado pending e implementación se contradicen en presencia, no se cierra su aceptación.

Siguiente condición: Conservar implementación, verificar construcción/recarga persistente de sus consumidores antes de aceptación completa; historial de símbolo separado de identidad TASK.

Fuente: src/orm/models.py:_install_singleton_triple.
Commits con cita explícita: 1; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_base_model_recordset.py (Executed named cases; see phase/outcome)

## TASK-API-0406 — Censar las aserciones negativas que el barrido invirtió en los cinco clones

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1181'}.

Es un censo de aserciones negativas sobre cinco Consumers, no un sucesor web_tour ni una unidad funcional de src/orm. Este lote no inspecciona los otros repositorios.

Siguiente condición: Mantener alcance transversal pendiente; no usar esta identidad para UI/test_orm y no afirmar censo completado.

Fuente: tests/integration/auto_backup/test_backups.py:kaupamex.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-API-0412 — Despachar el inverse declarado al escribir el campo

Estado nativo: completed; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1187'}.

Descripción nativa cita775c674e y sonda de cuatro vías por contenido. save y descriptor conservan la marca/despacho; eso es evidencia histórica concreta, no prueba nueva de atomicidad.

Siguiente condición: Revalidar si cambian save/descriptores; GEN0507 cubre atomicidad y no se cierra por este despacho.

Fuente: src/orm/models.py:PENDING_INVERSE_FIELDS, src/orm/fields.py:determine_inverse.
Commits con cita explícita: 8; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-API-0417 — Retirar el enrutado de las fachadas: la costura decide, no el constructor

Estado nativo: in_progress; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1192'}.

Las factories ya no eligen NonStored por store. La derivación central existe; siguen tres fallos heredados que esperan claves antiguas en apply_source_defaults.

Siguiente condición: Reconciliar criterio residual y pruebas de vocabulario con autoridad; no retirar aserciones ni llamar verde a la suite completa.

Fuente: src/orm/fields_nonstored.py:apply_source_defaults.
Commits con cita explícita: 8; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_field_type_vocabulary.py (Executed named cases; see phase/outcome)

## TASK-API-0418 — Retirar NonStored como clase: el eje es store, no el tipo

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1193'}.

NonStored sigue siendo clase y export; su eliminación general no está terminada. La MRO real0419 prueba fusión alcanzable sin eliminarla.

Siguiente condición: Separar adopción general de reparación0419; revisar consumidores isinstance y búsqueda antes de migrar representación.

Fuente: src/orm/fields_nonstored.py:NonStored.
Commits con cita explícita: 2; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_field_type_vocabulary.py (Executed named cases; see phase/outcome)

## TASK-API-0419 — Reconstruir un campo relacional desde _args__: to y on_delete no llegan a Field.__init__

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1194'}.

6c11ddde conserva to/on_delete/relación nueva. Ocho pruebas de reconstrucción y cinco PostgreSQL previas son evidencia válida; no se reimplementa.

Siguiente condición: CI global aún bloquea aceptación; M2M/O2O persistencia completa y concurrencia no se deducen de FK.

Fuente: src/orm/fields.py:_merge_field_definitions.
Commits con cita explícita: 4; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_relational_field_reconstruction.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.), tests/unit/orm/test_relational_reconstruction_persistence.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-API-0420 — El default literal de fields.Json dispara E010: la fuente lo copia por registro

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1195'}.

8aca3900 preserva literal y usa partial(deepcopy,...). Siete casos y PostgreSQL JSONB/serialización previos acreditan aislamiento acotado; CI no ejecuta sus cuerpos.

Siguiente condición: Mantener corrección; aceptación global de migraciones/CI sigue pendiente; no cambiar literal a dict ni repetir admisión.

Fuente: src/orm/fields_misc.py:Json.
Commits con cita explícita: 5; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_json_defaults.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-API-0421 — Portar BaseModel.create por contenido: lista de dicts → recordset, dict → singleton

Estado nativo: completed; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1196'}.

El estado completed cita aceptación de contenido dict/list/defaults/M2M. BaseModel.create y model_create_multi existen; no se valida todo el recorrido por la mera existencia.

Siguiente condición: Conservar porte; ejecutar flujos de create con fixtures y adopción de overrides antes de aceptar todos los consumidores.

Fuente: src/orm/models.py:create.
Commits con cita explícita: 2; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_create.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-API-0424 — El campo sin columna de una cadena related no es buscable: el recompute no puede hallar las filas

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1199'}.

Las suites actuales reproducen warnings de country→company_country_code/group_codes y prueban el grafo. El aviso exige searchabilidad; no prueba defecto frente a referencia.

Siguiente condición: Re-medir borrado con declaración en clase y decidir search/simplificación/divergencia; no confundirlo con pérdida de pendientes0559.

Fuente: src/orm/fields.py:resolve_depends.
Commits con cita explícita: 1; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_field_resolve_depends.py (Executed named cases; see phase/outcome), tests/unit/orm/test_field_triggers.py (Executed named cases; see phase/outcome)

## TASK-API-0427 — La suite completa de api se cuelga en espera de lock: una conexión queda idle in transaction

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1207'}.

El histórico documenta contención con clientes no identificados. CI actual falla al crear FK a res_users, firma distinta y sin evidencia de lock actual.

Siguiente condición: No aplicar fix de lock a CI por asociación; identificar backends si reaparece y usar timeout dentro de su unidad autorizada.

Fuente: tests/conftest.py:_pg_probe.
Commits con cita explícita: 1; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0060 — Construir el almacenamiento jsonb de translate=True

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '333'}.

La anotación translate no convierte varchar en jsonb. El contrato exige idioma activo y consulta/orden por idioma además de almacenamiento y migración.

Siguiente condición: No elegible para migración sin autoridad/plan de preservación; mantener divergencia de almacenamiento demostrada históricamente.

Fuente: src/orm/fields_textual.py:Char.
Commits con cita explícita: 1; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0062 — Construir el motor de traducción: import/export de .po

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '400'}.

La dependencia raw333 corresponde a GEN0060; los destinos etiquetas y arch_db son distintos de valores jsonb. Proyección vacía no elimina esas obligaciones.

Siguiente condición: Reconciliar destinos y dependencia API0283; no admitir un motor PO sólo con la flag o con catálogo de traducciones.

Fuente: src/tools/translate.py:_translate_and_format.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0461 — Censar odoo/orm/ entero: que falta de cada archivo, y su veredicto TRAE/CONSTRUYE

Estado nativo: in_progress; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '209'}.

Hay inventarios/contrapartes y cobertura histórica completa del módulo test_orm; no son un denominador funcional global ni autorización para repetir censo AST.

Siguiente condición: Usar33descriptores/66grupos ya fijados y resolver brechas por contrato; tarea de inventario no equivale a ORM terminado.

Fuente: scripts/counterpart_body.py:pair_declarations.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0462 — Barrer los 181 Selection que no declaran required contra la fuente

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '210'}.

Selection distingue choices del tipo y required declarado; no hay en este lote comparación por consumidor de las181declaraciones históricas.

Siguiente condición: Conservar cuenta como histórica; verificar consumidores concretos y defaults contra fuente antes de afirmar barrido o exigir required.

Fuente: src/orm/fields_selection.py:Selection.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_field_type_vocabulary.py (Executed named cases; see phase/outcome)

## TASK-GEN-0463 — Portar Field, el contrato de campo del que cuelga todo el ORM

Estado nativo: in_progress; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '211'}.

Field integra atributos, cache, metadatos y recálculo. Las pruebas ejecutadas cubren vocabulario/cache/dependencias; One2many no participa de todo ese contrato.

Siguiente condición: No reimplementar Field; separar setup/cache/schema/relaciones y registrar propiedades aún sin prueba persistente.

Fuente: src/orm/fields.py:_field_get_attrs.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_field_type_vocabulary.py (Executed named cases; see phase/outcome), tests/unit/orm/test_field_cache.py (Executed named cases; see phase/outcome), tests/unit/orm/test_field_resolve_depends.py (Executed named cases; see phase/outcome)

## TASK-GEN-0464 — Recrear las bases limpias al cerrar el porte de src/orm entero

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '212'}.

Recrear bases depende del cierre del porte y es provisioning. CI actual no dispone de res_users al aplicarFK; no autoriza destruir QA ni afirmar causa raíz resuelta.

Siguiente condición: Bloqueo por cierre ORM/provisioning no destructivo y causa CI; este lote sólo usa tablas TEMP en QA.

Fuente: src/config/settings/testing.py:DATABASES.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0465 — Medir cada tipo de campo por CONDUCTA, no por nombre

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '213'}.

La suite mide tipos/choices y HTML, y las pruebas JSON previas cubren default; no cubre por sí sola conversión/persistencia de todos los tipos.

Siguiente condición: Mantener medición por comportamiento específico: temporal,binario,reference,numeric precisan sus consumidores y verificadores, no otro conteo de nombres.

Fuente: tests/unit/orm/test_field_type_vocabulary.py:TestEveryFamilyPublishesItsType.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_field_type_vocabulary.py (Executed named cases; see phase/outcome), tests/unit/orm/test_fields_html.py (Executed named cases; see phase/outcome)

## TASK-GEN-0470 — Extender orden_de_porte a las otras raices espejadas

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '218'}.

El instrumento conserva REFERENCE_SUBPATH=(odoo,orm) y OUR_SUBPATH=(src,orm); no demuestra extensión a todas las raíces espejadas.

Siguiente condición: Preparar parametrización sólo bajo esta TASK si sigue necesaria; no reemplazar selección/planificación genérica de Thyrox.

Fuente: scripts/orden_de_porte.py:REFERENCE_SUBPATH.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0476 — Recorrer _table_object_definitions hacia Meta al construir la clase

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '224'}.

TableObject acumula definiciones y ofrece to_django; búsqueda de consumidores no localiza lectura de _table_object_definitions fuera de su registro. Meta no se completa sólo por registrar.

Siguiente condición: Verificar integración en construcción y SQL de Constraint/Index con modelo real; no aceptar por lista de definiciones existente.

Fuente: src/orm/table_objects.py:__set_name__.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_table_objects.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0477 — Portar los 33 optimizadores de dominio que el registro ya admite

Estado nativo: in_progress; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '225'}.

Los optimizadores registrados tienen cuerpos y las suites actuales ejercitan normalización/tipos/operadores. Registro no demuestra cada camino relacional o SQL.

Siguiente condición: Conservar optimizadores verificados y completar tests DB/hierarquía/rights por contrato; no portar33nombres de nuevo.

Fuente: src/orm/domains.py:_OPTIMIZATIONS.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_domain_optimizer_registry.py (Executed named cases; see phase/outcome), tests/unit/orm/test_domain_operator_optimizers.py (Executed named cases; see phase/outcome), tests/unit/orm/test_domain_type_optimizers.py (Executed named cases; see phase/outcome)

## TASK-GEN-0478 — Gate contra una quinta copia de la tupla estrecha de colecciones

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '226'}.

COLLECTION_TYPES central existe y lo importa Field. No se identificó un gate dedicado contra nuevas copias en el conjunto de scripts consultado.

Siguiente condición: Distinguir centralización actual de prevención futura; verificar copias/consumidores y checker vigente antes de crear gate duplicado.

Fuente: src/orm/utils.py:COLLECTION_TYPES.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0479 — Censar por consumidor los 64 atributos de clase de campo que quedan

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '227'}.

Hay mapa por familia y check_field_class_attributes; un valor en la clase no demuestra cada uno de64atributos consumidos en producción.

Siguiente condición: Usar checker e inventario existentes por consumidor; no declarar64cerrados ni fabricar un nuevo inventario global.

Fuente: src/orm/fields.py:REFERENCE_CLASS_TO_DJANGO.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_field_type_vocabulary.py (Executed named cases; see phase/outcome)

## TASK-GEN-0482 — Renombrar TRUE_DOMAIN y FALSE_DOMAIN: son Q, no Domain

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '230'}.

TRUE_DOMAIN/FALSE_DOMAIN siguen siendo Q; Domain.TRUE/FALSE son AST separados. El comentario describe la fachada Q usada por consumidores.

Siguiente condición: Renombrar exige compatibilidad y adopción de callers, no reemplazo mecánico por Domain ni aprobación inferida de pending.

Fuente: src/orm/domains.py:TRUE_DOMAIN.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0483 — Sonda de conducta para el contrato de un simbolo con N implementaciones

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '231'}.

El comparador existente conserva owner,funciones,clases y asignaciones; methods_of pierde esos ejes. El correctivo estructural no prueba conducta de Nimplementaciones.

Siguiente condición: Reutilizar declarations_of con cuerpos/controles por símbolo; no construir otro analizador ni declarar equivalencia por firma.

Fuente: scripts/counterpart_body.py:declarations_of.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0484 — Barrer los operadores que el compilador de hoja no conoce

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '232'}.

La compilación reconoce operadores del vocabulario central. Los tests de optimización no cubren todas sus combinaciones relacionales SQL.

Siguiente condición: Relacionar operadores registrados con compilador y pruebas DB; no convertir cada operador no ejecutado en TASK nueva.

Fuente: src/orm/domains.py:condition_to_q.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_domain_operator_optimizers.py (Executed named cases; see phase/outcome)

## TASK-GEN-0485 — Hacer que el caso de campo no relacional discrimine su guarda

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '233'}.

La guarda escalar debe rechazar jerarquía en campo no relacional. La prueba existe en suite con DB, no se ejecutó en el lote sin fixtures; no se cuenta como PASS por presencia.

Siguiente condición: Ejecutar guarda y control de relación con fixture PG acotado; conservar el control negativo, no quitarlo para aprobar.

Fuente: src/orm/domains.py:_operator_hierarchy.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_domain_hierarchy.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0487 — Dar a child_of y parent_of un predicado en memoria propio

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '235'}.

Hay constructores Domain para jerarquía y camino que recorre IDs. Eso no demuestra predicado en memoria ni ciclos,parent_path o jerarquía real.

Siguiente condición: Separar SQL,recorrido y evaluación en memoria; suite DB y comparación Odoo delimitan lo pendiente.

Fuente: src/orm/domains.py:_operator_child_of_domain, src/orm/domains.py:_operator_parent_of_domain.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_domain_hierarchy.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0492 — Cerrar la rama polimorfica de One2many._additional_domain

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '240'}.

La rama polimórfica devuelve [] y declara que GenericForeignKey usa ct_field/fk_field y no model_field. No es equivalencia de predicado por discriminador.

Siguiente condición: Reconciliar Many2oneReference y un consumidor polimórfico; no declarar no aplicable sin decisión autorizada.

Fuente: src/orm/fields_relational.py:_additional_domain.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_one2many.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0493 — Devolver Domain en get_comodel_domain, tras separar fachada de definidor

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '241'}.

El método devuelve lista compuesta y la suite existente exige lista. La referencia devuelve Domain; equivalencia de composición no resuelve tipo público.

Siguiente condición: Depende de separar definidor/fachada y resolver ciclo0512; cambiar tests/API por autoridad, no unilateralmente.

Fuente: src/orm/fields_relational.py:get_comodel_domain.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_one2many.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0494 — Validar el inverso de One2many al arrancar, no al leerlo

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '242'}.

La prueba de inverso inexistente accede al descriptor después de crear fila; no verifica rechazo al arrancar. Distinguir diagnóstico tardío de validación de registro.

Siguiente condición: Añadir verificador de arranque compatible con registro Django antes de portar una validación prematura.

Fuente: src/orm/fields_relational.py:_inverse_field.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_one2many.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0495 — Portar el lado SQL de One2many: la condicion relacional y su subconsulta

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '243'}.

One2many usa manager inverso y no recibe métodos SQL/caché de Field; _get_query_for_condition_value figura como pendiente en el propio contrato.

Siguiente condición: Preparar semántica any/subconsulta sobre FK existente y verificación SQL, sin crear columna para One2many.

Fuente: src/orm/fields_relational.py:One2many.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_one2many.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0496 — Medir si setup_inverses tiene receptor en este arbol

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '244'}.

La navegación inversa de Django existe, pero One2many plano no hereda actualización/cache de _RelationalMulti. La infraestructura no demuestra receptor completo de setup_inverses.

Siguiente condición: Determinar consumidores y contratos de inversas/caché con0495; no implementar un segundo registro por nombre idéntico.

Fuente: src/orm/fields_relational.py:_many2one_update_inverse.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_fields_relational_update_inverse.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0503 — Derivar required de null en el campo persistido

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '251'}.

El contrato actual documenta required explícito independiente de null; tests ya prueban required=False con columna NOTNULL. Derivarlo de null contradice esa arquitectura.

Siguiente condición: Reconciliar criterio histórico mediante autoridad antes de cambiarlo; no implementar esta TASK tal como está redactada.

Fuente: tests/unit/orm/test_field_required_declared.py:TestTheDeclaredIntent.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_field_required_declared.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0507 — Transaccionar la escritura del inverso con la del origen

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '255'}.

save despacha el inverso tras super.save. Un despacho correcto no demuestra atomicidad conjunta ante fallo del inverso.

Siguiente condición: Prueba PG de fallo/rollback de origen e inverso y delimitación atomic preceden al cambio; no usar0412como aceptación.

Fuente: src/orm/models.py:save.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_determine_inverse.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0508 — Construir la señalizacion de cache entre procesos, que hoy es media

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '256'}.

Hay tablas/secuencias y comparación de lectores, no sólo flags locales. La tarea pendiente que decía media señalización quedó desactualizada en presencia estructural.

Siguiente condición: Verificar tablas y dos lectores reales/commit/rollback con fixtures PG; no reconstruir el eje porque siga pending.

Fuente: src/orm/registry.py:signal_changes, src/orm/registry.py:check_signaling.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_registry_signaling_axis.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0512 — Enderezar la direccion del import entre fields_properties, domains y models

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '260'}.

El ciclo fields_properties→domains→fields se reprodujo en el probe inicial del lote anterior y queda documentado en get_comodel_domain. Importar orm.models primero funciona, pero no prueba resolver direcciones.

Siguiente condición: Reconciliar fachada/definidor y consumidores __all__ antes de retirar imports; no esconderlo con lazy imports.

Fuente: src/orm/fields.py:Properties, src/orm/fields_properties.py:Properties, src/orm/domains.py:Domain.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0525 — Construir modified(): el motor de recálculo de campos calculados sobre registro virtual

Estado nativo: in_progress; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '273'}.

El motor marca dependencias y recompone/flush reales en pruebas PG0559. Los triggers actuales pasan; el registro virtual completo y todas las relaciones no se deducen de esos casos.

Siguiente condición: Conservar motor y completar contratos virtual/relacional por sus unidades; no volver a construir modified.

Fuente: src/orm/models.py:modified, src/orm/models.py:_recompute_field.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_field_triggers.py (Executed named cases; see phase/outcome), tests/unit/orm/test_missing_recompute.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0554 — Barrer los campos de la fuente declarados aqui como property pelada

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '302'}.

El porte por property no equivale a Field registrado: la cadena related consulta _meta. La evidencia histórica de ResCompany identifica consumidores que no se cubren por descriptor aislado.

Siguiente condición: Continuar por propiedades y consumidores concretos del inventario existente, no barrido global ni reemplazo automático de todas las properties.

Fuente: src/orm/models.py:FieldDescriptor.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0558 — Dar al computo un QuerySet en vez de una fila, y recuperar el lote de prelectura

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '306'}.

El bucle invoca determine sobre una fila. Retirar IDs ausentes y reintentar0559 no cambia ese reparto a QuerySet/PREFETCH_MAX.

Siguiente condición: Requiere contrato de lote/prefetch y adopción de métodos compute; no admitida por independencia supuesta del grafo vacío.

Fuente: src/orm/fields.py:_invoke_compute_method.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0559 — Portar apply_except_missing: desmarcar el computo de la fila que ya no existe

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '307'}.

Se demuestran consulta sin fila y desaparición durante compute. Delta actual reintenta una vez MissingError/ObjectDoesNotExist y conserva trabajo si persiste;16PGPASS y control anterior7fallos.

Siguiente condición: Publicar y verificar regresiones/CI; no confundir aceptación acotada con batching0558 o equivalencia de todo ORM.

Fuente: src/orm/fields.py:recompute, src/orm/models.py:_recompute_field.
Commits con cita explícita: 2; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_missing_recompute.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0562 — Portar internal_group a store=False + search, cuando el buscador sirva la travesia por FK

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '310'}.

El consumidor declara internal_group calculado store=True y lo usa en consulta account__internal_group. Pasarlo a store=False sin search rompe ese consumidor real.

Siguiente condición: Esperar buscador por FK y prueba del consumidor digest; la flag fuente no justifica quitar columna unilateralmente.

Fuente: addons/account/models/account_account.py:internal_group.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0570 — Reubicar los símbolos del ORM que aterrizaron en un addon consumidor

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '318'}.

La nota en save atribuye anotación de inverso a símbolos ajenos al núcleo. Hay infraestructura de campos/modelos ya extraída, pero no un mapa completo de símbolos reubicados para cerrar318.

Siguiente condición: Recuperar listado histórico de símbolos/consumidores y decidir ownership de cada uno antes de mover código.

Fuente: src/orm/models.py:PENDING_INVERSE_FIELDS.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0575 — Portar Cache (28 metodos) y Starred a src/orm/environments.py

Estado nativo: completed; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '323'}.

Cache y transacción comparten mapas; los tests de campo/Transaction pasan. El subconjunto Cache con DB no se confunde con todas28operaciones de su fachada.

Siguiente condición: Conservar implementación; ejecutar superficie completa de Cache y dos uid/contextos si se busca aceptación total.

Fuente: src/orm/environments.py:Cache.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_field_cache.py (Executed named cases; see phase/outcome), tests/unit/orm/test_environments_transaction.py (Executed named cases; see phase/outcome)

## TASK-GEN-0578 — Portar Field._filter_not_equal y _update_inverse, que Cache delega

Estado nativo: completed; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '326'}.

Los métodos están instalados y delegan a cachés/inversas. Los casos de inversas de relación necesitan su suite y persistencia, no sólo el test de cache básico.

Siguiente condición: No re-portar por nombre; relacionar comportamiento de cada tipo y controles de invalidación inversa.

Fuente: src/orm/fields.py:_filter_not_equal, src/orm/fields_relational.py:_many2one_update_inverse.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_fields_relational_update_inverse.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0579 — Construir BaseModel.new: el registro virtual con origin, que la rama dict de

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '327'}.

No se localiza BaseModel.new; hay NewId y _new_records pero no constituyen el protocolo new(values,origin) de registro virtual.

Siguiente condición: La representación/origin y caché de nuevo registro son dependencias reales; no reemplazarlo por Model(**vals) ni implementar por una ausencia nominal.

Fuente: src/orm/models.py:BaseModel.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-GEN-0581 — Hacer que los dos registrantes sin tabla hereden de AbstractModel

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '329'}.

AbstractModel existe como registrante sin tabla; su docstring dice que adopción de los dos registrantes sigue329. Existencia de base no prueba adopción.

Siguiente condición: Verificar las dos clases históricas y comportamiento de registro antes de cambiar herencia; distinguir de modelos Django abstractos.

Fuente: src/orm/models.py:AbstractModel.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_model_class_construction.py (Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.)

## TASK-GEN-0587 — Portar la mitad de change_default de onchange_methods

Estado nativo: pending; owner: None. Identidad {'session_id': '29a5e555-e34f-5a20-8c39-ad6cf2f19961', 'task_id': '335'}.

El colector agrupa decoradores; la mitad change_default sigue explícitamente ausente y condicionada a primer consumidor. No se construye por contar la flag en Field.

Siguiente condición: Verificar consumidor vigente y contrato ir.default antes de admitir; no imponer todas las fases de onchange.

Fuente: src/orm/registry.py:_OnchangeMethods.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-THYROX-1072 — Read the task universe from the store in task_source

Estado nativo: pending; owner: None. Identidad {'session_id': '844a0a13-9fd8-5607-beb0-74daab7018a3', 'task_id': '140'}.

La función fija blockedBy=[] y omite descripción pese al raw333 de0062. Existe claim vm-r y no se verificó progreso remoto; no admite grafo como completo.

Siguiente condición: Preservar claim y bloqueo de cualificación; usar filas/raw y contratos para investigación autorizada, no crear otro selector.

Fuente: ../thyrox/src/task/task_source.py:records_from_store.
Commits con cita explícita: 0; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.

## TASK-API-0415 — Despachar el compute declarado al leer un NonStored

Estado nativo: completed; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1190'}.

Completed documenta a95c11fb y9PASS históricos; ahora su suite da7FAIL/2PASS. Parte exige clase/directo __get__ obsoletos tras0417, pero lectura real ResGroups.full_name reproduce RecursionError sinSQL: compute retorna valor y FieldDescriptor exige asignación. Diagnóstico completed_with_contract_divergence, no siete defectos nuevos.

Siguiente condición: Reconciliar consumidor retornante y contrato actual compute con0417; no restaurar fábrica NonStored ni debilitar aserciones. ResCompany0634 es otra dependencia.

Fuente: src/orm/fields_nonstored.py:__get__.
Commits con cita explícita: 1; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_nonstored_compute_dispatch.py (Executed named cases; see phase/outcome)

## TASK-API-0405 — La rama is_transient() de ondelete no se simula: el momento del stack no la alcanza

Estado nativo: completed; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1180'}.

El código re-resuelve default transient en contribute/operación diferida y actualiza remote_field.on_delete;8casos de ondelete pasan, sin aceptar todas las combinaciones transient. La descripción completed conserva una pregunta previa al cambio.

Siguiente condición: Separar default de política explícita y wizard→wizard; verificar resultados del suite y no reconstruir el mecanismo porque el texto nativo quedó antiguo.

Fuente: src/orm/fields_relational.py:_setup_nonrelated, src/orm/fields_relational.py:_decide_transient_ondelete.
Commits con cita explícita: 1; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_many2one_ondelete.py (Executed named cases; see phase/outcome)

## TASK-API-0416 — Portar la fase que recoge las definiciones de campo por clase

Estado nativo: completed; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1191'}.

Recolección MRO y fusión existen:19casos de su suite pasan y2necesitan fixtures PG no admitidos por el rol mínimo. Native completed no acepta NonStored0418 ni reconstrucción0419; sus criterios son distintos.

Siguiente condición: Conservar colección y lecturas por cadena; no convertir la dependencia histórica MetaModel en bloqueo vigente sin conducta que lo pruebe.

Fuente: src/orm/fields.py:_collect_field_definitions, src/orm/fields.py:_field_get_attrs.
Commits con cita explícita: 5; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_field_definition_collection.py (Executed named cases; see phase/outcome)

## TASK-API-0404 — La guarda :289 de ondelete es ciega al segundo vocabulario

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1179'}.

La guarda IR_MODELS contempla vocabulario fuente y el caso de etiqueta Django queda histórico; model_by_key durante definición tiene límite de registry readiness.

Siguiente condición: Reconciliar si hay consumidor actual con segundo vocabulario antes de añadir puente manual; no declarar equivalencia por default de on_delete.

Fuente: src/orm/fields_relational.py:_apply_ondelete.
Commits con cita explícita: 1; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_many2one_ondelete.py (Executed named cases; see phase/outcome)

## TASK-GEN-0634 — Portar como campo los ocho @property de ResCompany que delegan al partner

Estado nativo: pending; owner: None. Identidad {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': '1204'}.

La autoridad es un Consumer de la raíz: delegaciones ResCompany al partner por property no viven en _meta y bloquean related. No es otra implementación de Field ni autorización para portar toda compañía.

Siguiente condición: Clasificar como dependencia de aceptación de related/compute; consultar sus ocho campos y ownership antes de cambiar el addon, sin ampliar esta unidad0559.

Fuente: src/addons/base/models/res_company.py:name.
Commits con cita explícita: 1; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.
Verificadores: tests/unit/orm/test_nonstored_compute_dispatch.py (Executed named cases; see phase/outcome)


## Incremento bootstrap/compute — 2026-10-21

Esta sección actualiza las conclusiones históricas afectadas sin regenerar la población. Detalle verificable: scripts/evidence/orm-bootstrap-compute-20261021T210528/README.md y outputs.

### TASK-API-0415

El despacho histórico completed se conserva. Incremento actual: ResGroups asigna full_name y declara dependencias como Odoo; el descriptor informa falta de asignación sin invocar __str__.126casos focalizados PASS y controles negativos Consumer/diagnóstico/bucket/clave discriminan por separado. No se restaura la fábrica NonStored.

Continuación: Aceptar sólo el delta acotado tras revisión/CI; subsiste reutilización entre contextos de un objeto Django sin pk (GEN0579), no equivalencia total.

### TASK-API-0417

in_progress oficial conservado. Corrección de composición Consumer/FieldDescriptor/Environment en8b6ea823: asignación explícita, diagnóstico estable, buckets de id estable y dependencias de contexto derivadas. Las nueve pruebas históricas se reconcilian por responsabilidad y contrato actual, sin exigir retorno de compute ni fábrica retirada.

Continuación: Revisión/CI e integración autorizada pendientes. GEN0576 completed tiene una divergencia de clave contextual corregida sin reabrir su estado. GEN0579 sigue dependencia para objetos virtuales entre contextos.

### TASK-GEN-0559

3ffa958e y2f01be1b preservados, sin modificar sus cuerpos de recompute/_recompute_field.16PostgreSQLPASS de regresión tras cambios materiales en lectura/caché. CI39669997683/headb1b6 terminóFAILURE por10636res_users+38transacción, sin otras firmas de setup.

Continuación: No reimplementar retry. No aceptación global ni integración por PR109 abierto. La migración nueva se verifica como unidad0312/H1120, no se atribuye su deuda a0559.

### TASK-API-0416

Estado histórico conservado.19casos de colección ya pasaban; los dos antes bloqueados requieren la segunda preparación pytest-Django de este lote. Resultado definitivo en native-pytest-bootstrap.log, no se declara PASS antes de terminar.

Continuación: Consultar el resultado de la prueba PG de bootstrap y aceptar separadamente del porte completo de las fachadas.

Relaciones nativas adicionales: GEN0312/session29a5e555-e34f-5a20-8c39-ad6cf2f19961/local60 (migración inicial de dos modelos registrados) y GEN0576/misma sesión/local324 (clave de contexto derivada). No nuevas TASK, estados o inventario. Los datos completos e identidad verificada están en admission-and-provenance.json. No se da por cerrado el porte de test_orm ni todas las13funciones de Environment.

Resultado final del segundo bootstrap nativo:41cuerposPASS,1ERRORteardown (exit1).21de colección incluyen los dos antes bloqueados. Transaction.flush→base.public_user ausente→autocommit es una falla pendiente de ciclo de fixture, no res_users. No se etiqueta heredada sin control.

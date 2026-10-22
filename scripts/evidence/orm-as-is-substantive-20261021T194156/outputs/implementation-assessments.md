# Implementation AS IS y reconciliación contractual

Se conserva la población y sus14elementos; aquí se distinguen comportamiento observado, candidato y condición de verificación.

## Obligaciones existentes

| Descriptor | Hallazgo individual |
|---|---|
| record_identity_singleton | __getitem__/cardinalidad y descriptor computado están presentes. Acceso ordinario rs.label por DeferredAttribute y frontera campos privados requiere prueba específica, no extender todos los descriptores por inferencia. Consumer ResGroups.full_name está demostrado divergent: retorna desde compute en vez de asignar y la lectura recursa; evidencia nonstored-consumer.json, relacionado0415/0417, no otro hallazgo por grupo. |
| exists_recordset_semantics | El caso vacío existe; la suite312 no observa existentes/nuevos/id0 con PG. QuerySet.exists devuelve bool y no puede sustituir recordset exists sin adaptación. BaseModel.new falta; no se acepta esa rama por browse. |
| cache_value_and_miss | La lectura/escritura de caché de campo y Transaction se ejecutó en suites seleccionadas; las28operaciones de Cache no están todas ejecutadas. CacheMiss se distingue de valorFalse, y prueba de facade requiere su suite específica. |
| cache_across_user_environments | Cache es transaccional, pero dos uid con campos name/ref set-overwrite-remove y contexto sensible requieren fixture explícito. No se presupone partición/compartición por compartir objeto Transaction. |
| selective_invalidation | Pruebas de cache/Transaction ejecutadas cubren borrado selectivo de entradas; composición exacta dos campos/dos registros y todos los contextos requiere escenario de referencia. No se sustituye por invalidación total. |
| row_rule_access | AccessQuerySet existe pero el fixture necesita usuarios/grupos/reglas y distinguir denegado de borrado. CI res_users no preparado impide aceptación de este flujo. |
| cursor_transaction_lifecycle | El probePG histórico de cursor/rollback se reutiliza; el batch312 verifica Transaction en memoria. Ownership/nesting/callbacks de cursor necesitan prueba real aislada; no se aceptan desde Cache.clear. |
| cursor_replica_selection | La comparación previa de seis escenarios del cuerpo detecta diferencias cooldown/thread/ProgrammingError. Sigue sin réplica real y sin TASK atómica reconciliada; fallback disponible no implica equivalencia. |
| inverse_dependency_navigation | Las suites actuales prueban resolución de cadenas y trigger tree; los avisos de searchabilidad no acreditan capacidad de descubrir dependientes para toda cadena relacionada. |
| domain_any_rights_optimization | La equivalencia del predicado any/rights fue acotada históricamente; joins/testigos existenciales sobre SQL y related bajo seguridad requieren dataset y permisos propios. |
| invalidate_all_flush_before_invalidate | Defecto previo demostrado: invalidate_all ignora flush. No se encontró identidad atómica equivalente en la consulta nativa documentada; GEN0575 completed no autoriza asignarle esta corrección. |
| flush_recompute_fixpoint | Flush de columnas y rollback se prueban en modelos temporales. Fixpoint que crea trabajo nuevo, hooks precommit y finalización de colas requieren caso por orquestación, no sólo una escritura. |
| relational_field_reconstruction | Se conserva6c11ddde y sus8casos más5PG históricos. Nuevo diff sólo modifica recompute/imports, no el algoritmo de reconstrucción; no repetir pruebas válidas ni aceptar M2M/O2O persistente por FK. |
| recompute_dependent_record_discovery | Se cerró la brecha acotada de0559 con16PGPASS, incluyendo filas ausentes al consultar/durantecompute, error persistente,related ausente,virtual,AccessError y managerpúblico.7de8casos nuevos fallan con Field.recompute99f restaurado; no acepta batching ni toda cadena0424. |
| translated_record_storage_query | Divergencia histórica varchar/jsonb conservada. GEN0060/0062 y flag0283 son obligaciones distintas; la migración permanece no autorizada. No se computa cobertura funcional desde presencia translate. |
| company_relation_consistency | _check_company existe; necesita dos compañías,relaciones permitidas/prohibidas y error/rollback. No convertir ausencia de warning en consistencia demostrada. Contexto company y allowed_company_ids deben afectar valor/fallback/caché conforme a permisos. Transacción o company_dependent aislados no aceptan todo ese flujo. |
| domain_null_boolean_partition | Optimizadores actuales ejercitan False/in/set; NULL,vacío,traducido y complementos relacionales deben contrastarse por partición de resultados, no por expresión parecida. |
| protected_compute_scope | Se prueban desmarcado/restauración ante error y transacción de cómputo. Protección recursiva/contexto/uid y valores precalculados del fixture completo necesitan casos adicionales. Consumer ResGroups.full_name está demostrado divergent: retorna desde compute en vez de asignar y la lectura recursa; evidencia nonstored-consumer.json, relacionado0415/0417, no otro hallazgo por grupo. |
| json_value_isolation_roundtrip | 0420 preserva literal e independencia de default,serialización y PGJSONB previos; actual regresión pasa7JSON. Json copy-on-read/normalización general no se declara aceptado. CI bloquea cuerpos por setup, no prueba fallos JSON. |
| relation_command_membership | Managers Django no garantizan por sí solos cache inversa después de Command.set/unlink. Ejecutar cambios de membresía y lecturas antes/después en ambos extremos. Borrado FK y constraints están probados; orden de Command.unlink/delete/set bajo constraints M2M/O2M requiere transacciones y colas de comandos, no aceptación de toda relación. |
| virtual_onchange_delta | Onchange debe producir delta virtual y origen; BaseModel.new falta y el camino web usa adaptaciones. No se copia TestCase nativo ni se admite el flujo sin resolver esa dependencia. |
| prefetch_batch_reuse | mapped grande tiene bloqueo0399; descartar MissingError0559 no implementa fetch seguro, campos por grupos ni prefetch de registros denegados. Cache local y protocolos de registro pasan; fetch0399 grande sigue bloqueado. Métricas de lote/contexto necesitan ejecutar el camino real y medir consultas, no contar helpers. |
| property_definition_authority | PropertiesDefinition es autoridad de nombres/tipos; distinguir definición y valores de instancia. Exige demostrar rechazo de definición inválida, no sólo JSON serializable. Conversión Properties requiere tipos,defaults,falsy y salida de lectura/escritura. JSONField genérico no sustituye la validación declarada por la definición. |
| field_storage_reflection | DDL por tipo/columna, reflexión y catalogación aún requiere PG real de schema axis. La FK temporal0419 o un field con store=True no satisface ese contrato completo. |
| relational_domain_query_semantics | La equivalencia del predicado any/rights fue acotada históricamente; joins/testigos existenciales sobre SQL y related bajo seguridad requieren dataset y permisos propios. Optimizadores actuales ejercitan False/in/set; NULL,vacío,traducido y complementos relacionales deben contrastarse por partición de resultados, no por expresión parecida. |
| recordset_sort_order | Sorted pasa sus casos salvo xfail de recursión many2one. Ejecutado sin xfail falla por acceso DB no permitido, no demuestra ausencia de terna0402; criterio histórico requiere reconciliación. |
| web_projection_access | web_read proyecta campos pero debe respetar ACL/row-rules/propiedades. La delegación declarada a DRF no es aceptación de seguridad para toda proyección. |
| record_attribute_boundary | Frontera de atributos privados/campos debe comprobar getattr/getitem/asignación y errores; el protocolo de conjunto ejecutado cubre otra parte, no da autoridad para exponer atributos. |
| autovacuum_expiration | Autovacuum necesita cron y marcadores de expiración,empresa/usuario y tiempo controlado. Existencia del modelo no acredita ejecución/limpieza ni justifica borrar datos reales. |
| index_method_reconciliation | check_indexes y TableObject aplican esquema, pero método/parcialidad/unicidad deben observarse en PG. Índices Odoo literales no son automáticamente requisitos de Django. |
| float_render_precision | El candidato previo src/addons/base/models/ir_qweb_fields.py no existe en este checkout; el addon html_editor no demuestra ese conversor de base. Render de float exige formato/localización/precisión frente al conversor de salida. El almacenamiento Float/Decimal o round() no demuestra HTML/string correcto. |
| browser_x2many_constraint_integration | Constraints de tours/formularios necesitan Consumer UI y recursos equivalentes; web_tour no recuperado en runtime. No imputar TASK0406 ni crear otra auditoría UI independiente. |
| default_view_field_projection | Metadatos de vista/default-form precisan tipo de vista/campos/acceso y Consumer de salida. No hay equivalencia demostrada por existencia de IrUiView o XML nativo. |

## Caracterizaciones completas de test_orm

### model_registry_extension_semantics

La composición MRO/registro es adaptación Django; el fixture de extensiones repetidas test_orm requiere orden de módulos y registro reconstruido, no sólo creación de una clase.

Consumer: src/orm/model_classes.py.
Verificadores: tests/unit/orm/test_model_class_construction.py — ver evidencia/condición individual, no PASS por existencia, tests/unit/orm/test_extend_model_selection_and_indexes.py — ver evidencia/condición individual, no PASS por existencia

### computed_fixture_dependency_graph

Grafo y limpieza/reintento están probados en sus casos; cascadas que crean nuevas filas, ciclos y compute contextuales requieren escenarios distintos de los16PG de ausencia. Consumer ResGroups.full_name está demostrado divergent: retorna desde compute en vez de asignar y la lectura recursa; evidencia nonstored-consumer.json, relacionado0415/0417, no otro hallazgo por grupo.

Consumer: src/orm/registry.py, src/orm/models.py, src/orm/fields.py.
Verificadores: tests/unit/orm/test_field_triggers.py — ejecutado (ver outcomes por nodeid), tests/unit/orm/test_field_resolve_depends.py — ejecutado (ver outcomes por nodeid), tests/unit/orm/test_missing_recompute.py — ver evidencia/condición individual, no PASS por existencia

### relational_fixture_integrity

La FK reconstruida tiene cinco pruebas PG históricas válidas; no equivalen al fixture íntegro de M2M/O2M/referencias, sus restricciones y comandos.

Consumer: src/orm/commands.py, src/orm/fields_relational.py.
Verificadores: tests/unit/orm/test_relational_reconstruction_persistence.py — ver evidencia/condición individual, no PASS por existencia

### custom_sql_model_identity

Cardinalidad/representación no acredita modelo SQL-view con id no entero. Requiere vista temporal, esquema de identidad, lectura/browse y persistencia explícitamente no aplicable cuando sea read-only.

Consumer: src/orm/models.py, src/orm/registry.py.
Verificadores: tests/unit/orm/test_base_model_recordset.py — ejecutado (ver outcomes por nodeid)

### fixture_access_matrix

AccessQuerySet existe pero el fixture necesita usuarios/grupos/reglas y distinguir denegado de borrado. CI res_users no preparado impide aceptación de este flujo.

Consumer: src/addons/base/models/ir_rule.py, src/orm/models.py.
Verificadores: tests/unit/orm/test_access_manager.py — ver evidencia/condición individual, no PASS por existencia

### xml_ui_fixture_contracts

El módulo Consumer no porta todos los XML/static/tours del fixture nativo. Adaptación DRF/web debe validar necesidad observable; no inventar obligación de copiar XML ni aceptar UI por pruebas ORM.

Consumer: src/addons/test_orm, addons/web.
Verificador Consumer de este comportamiento aún por delimitar con los fixtures y criterio descritos; no se excluye el contrato.

### catalog_constraint_message_identity

Mensaje SQL y clave traducible son contratos diferentes. Constraint conserva mensaje/callable; coincidencia de claves catálogo y traducción necesita fixture de idioma y violación real PG.

Consumer: src/orm/table_objects.py, src/tools/translate.py.
Verificadores: tests/unit/orm/test_table_objects.py — ver evidencia/condición individual, no PASS por existencia

### field_access_boundary

__getitem__/cardinalidad y descriptor computado están presentes. Acceso ordinario rs.label por DeferredAttribute y frontera campos privados requiere prueba específica, no extender todos los descriptores por inferencia. Consumer ResGroups.full_name está demostrado divergent: retorna desde compute en vez de asignar y la lectura recursa; evidencia nonstored-consumer.json, relacionado0415/0417, no otro hallazgo por grupo.

Consumer: src/orm/models.py, src/orm/fields.py.
Verificadores: tests/unit/orm/test_base_model_recordset.py — ejecutado (ver outcomes por nodeid)

### compute_definition_trigger_setup

Las suites actuales prueban resolución de cadenas y trigger tree; los avisos de searchabilidad no acreditan capacidad de descubrir dependientes para toda cadena relacionada.

Consumer: src/orm/registry.py, src/orm/fields.py.
Verificadores: tests/unit/orm/test_field_triggers.py — ejecutado (ver outcomes por nodeid), tests/unit/orm/test_field_resolve_depends.py — ejecutado (ver outcomes por nodeid)

### compute_recompute_protection

Se prueban desmarcado/restauración ante error y transacción de cómputo. Protección recursiva/contexto/uid y valores precalculados del fixture completo necesitan casos adicionales. Consumer ResGroups.full_name está demostrado divergent: retorna desde compute en vez de asignar y la lectura recursa; evidencia nonstored-consumer.json, relacionado0415/0417, no otro hallazgo por grupo.

Consumer: src/orm/environments.py, src/orm/fields.py.
Verificadores: tests/unit/orm/test_missing_recompute.py — ver evidencia/condición individual, no PASS por existencia, tests/unit/orm/test_environments_transaction.py — ejecutado (ver outcomes por nodeid)

### context_and_access_compute_cache

Mapas de caché y limpieza son verificables; compartir name/ref entre dos usuarios no demuestra partición por cada depends_context ni ausencia de fuga de permisos.

Consumer: src/orm/environments.py, src/orm/fields.py.
Verificadores: tests/unit/orm/test_field_cache.py — ejecutado (ver outcomes por nodeid), tests/unit/orm/test_environments_transaction.py — ejecutado (ver outcomes por nodeid)

### inverse_and_constraint_dispatch

La sonda histórica0412 verifica cuatro vías del inverso. Fallo de una constraint/inverso y rollback conjunto GEN0507 siguen siendo aceptación diferente.

Consumer: src/orm/models.py, src/orm/fields.py.
Verificadores: tests/unit/orm/test_determine_inverse.py — ver evidencia/condición individual, no PASS por existencia

### flush_precommit_completion

Flush de columnas y rollback se prueban en modelos temporales. Fixpoint que crea trabajo nuevo, hooks precommit y finalización de colas requieren caso por orquestación, no sólo una escritura.

Consumer: src/orm/environments.py, src/orm/models.py.
Verificadores: tests/unit/orm/test_missing_recompute.py — ver evidencia/condición individual, no PASS por existencia

### numeric_currency_conversion

Float/Monetary se adaptan a campos numéricos Django; equivalencia de conversión, moneda, redondeo y precisión exige valores/límites y consumidor de moneda, no tipo de columna.

Consumer: src/orm/fields_numeric.py.
Verificador Consumer de este comportamiento aún por delimitar con los fixtures y criterio descritos; no se excluye el contrato.

### scalar_temporal_selection_reference

El vocabulario distingue Selection/Date/Datetime; conversiones de zona horaria, falsy y referencia necesitan entradas y errores concretos del test nativo.

Consumer: src/orm/fields_temporal.py, src/orm/fields_selection.py, src/orm/fields_reference.py.
Verificadores: tests/unit/orm/test_field_type_vocabulary.py — ejecutado (ver outcomes por nodeid)

### related_read_write_metadata

La suite actual comprueba montaje compute/inverse/search y metadatos de cadena. Escritura persistente e invalidación de todos los related no se deducen de esa preparación. Consumer ResGroups.full_name está demostrado divergent: retorna desde compute en vez de asignar y la lectura recursa; evidencia nonstored-consumer.json, relacionado0415/0417, no otro hallazgo por grupo.

Consumer: src/orm/fields.py.
Verificadores: tests/unit/orm/test_related_field_setup.py — ejecutado (ver outcomes por nodeid)

### company_dependent_storage_fallback

CompanyDependent dispone mapa por empresa y fallback; falta aquí ejecutar dos empresas/defaults/rollback contra la columna real de cada tipo admitido.

Consumer: src/orm/fields_company_dependent.py.
Verificadores: tests/unit/orm/test_company_dependent.py — ver evidencia/condición individual, no PASS por existencia

### company_dependent_search

El almacenamiento por empresa no acredita filtrado/orden/agrupación por empresa activa; requiere SQL/índice y valores de dos empresas.

Consumer: src/orm/domains.py, src/orm/fields_company_dependent.py.
Verificadores: tests/unit/orm/test_company_dependent.py — ver evidencia/condición individual, no PASS por existencia

### prefetch_security_missing_and_groups

mapped grande tiene bloqueo0399; descartar MissingError0559 no implementa fetch seguro, campos por grupos ni prefetch de registros denegados.

Consumer: src/orm/models.py, src/orm/fields.py.
Verificadores: tests/unit/orm/test_base_model_recordset.py — ejecutado (ver outcomes por nodeid)

### virtual_record_origin_and_conversion

NewId existe pero no se localiza BaseModel.new con origin. Construcción Model(**vals) no implementa la vida virtual ni conversión/origen del fixture.

Consumer: src/orm/identifiers.py, src/orm/models.py.
Verificadores: tests/unit/orm/test_base_model_recordset.py — ejecutado (ver outcomes por nodeid)

### relational_search_context_order

Optimización de predicados no acepta orden/contexto de búsqueda relacional completa; requiere campos,comodelos,consulta y orden observables.

Consumer: src/orm/domains.py, src/orm/fields_relational.py.
Verificadores: tests/unit/orm/test_domain_operator_optimizers.py — ejecutado (ver outcomes por nodeid)

### relation_membership_inverse_cache

Managers Django no garantizan por sí solos cache inversa después de Command.set/unlink. Ejecutar cambios de membresía y lecturas antes/después en ambos extremos.

Consumer: src/orm/fields_relational.py, src/orm/commands.py.
Verificadores: tests/unit/orm/test_fields_relational_update_inverse.py — ver evidencia/condición individual, no PASS por existencia

### privilege_safe_relational_commands

Los comandos deben respetar privilegios del comodelo y propietarios; comprobar un resultado de membresía como superusuario no valida seguridad de la operación.

Consumer: src/orm/commands.py, src/orm/models.py.
Verificadores: tests/unit/orm/test_access_manager.py — ver evidencia/condición individual, no PASS por existencia

### binary_image_attachment_conversion

Binary/Image y conversión PIL existen. Se requieren tamaños,base64,adjuntos,resoluciones y errores; no equiparar BinaryField a todo contrato de attachment.

Consumer: src/orm/fields_binary.py.
Verificador Consumer de este comportamiento aún por delimitar con los fixtures y criterio descritos; no se excluye el contrato.

### html_sanitize_authority_and_cache

La suite HTML ejecutada prueba sanitización/declaración; autoridad de usuario y caché tras cambiar permisos/idioma requieren fixtures de acceso adicionales.

Consumer: src/orm/fields_textual.py.
Verificadores: tests/unit/orm/test_fields_html.py — ejecutado (ver outcomes por nodeid)

### parent_store_tree_and_cycles

Hay algoritmos child_of/parent_of. Cobertura de parent_path,ciclos y actualización del árbol precisa PG y modelo jerárquico; la guarda escalar no basta.

Consumer: src/orm/domains.py, src/orm/models.py.
Verificadores: tests/unit/orm/test_domain_hierarchy.py — ver evidencia/condición individual, no PASS por existencia

### relational_ondelete_and_reference

PROTECT/CASCADE y rechazo de huérfano verificados para FK. Polimorfismo y policies de referencias requieren discriminador modelo+id y comportamiento de borrado propio.

Consumer: src/orm/fields_relational.py, src/orm/fields_reference.py.
Verificadores: tests/unit/orm/test_relational_reconstruction_persistence.py — ver evidencia/condición individual, no PASS por existencia

### selection_registry_update_and_uninstall

Selection por choices y required está probado; añadir valores durante reconstrucción/desinstalación exige ondelete y registro de módulo, no sólo devolver selection.

Consumer: src/orm/model_classes.py, src/orm/fields_selection.py.
Verificadores: tests/unit/orm/test_field_type_vocabulary.py — ejecutado (ver outcomes por nodeid)

### create_precompute_batch_and_storage

Create dict/list y precompute tienen implementaciones y evidencia histórica; la aceptación conjunta de overrides,M2M/defaults/INSERT depende de sus fixtures PG, no del estado completed0421.

Consumer: src/orm/models.py, src/orm/decorators.py.
Verificadores: tests/unit/orm/test_create.py — ver evidencia/condición individual, no PASS por existencia, tests/unit/orm/test_precompute_before_insert.py — ver evidencia/condición individual, no PASS por existencia

### copy_translation_and_dynamic_field_lifecycle

Copy_data y lifecycle dinámico dependen de traducción por idioma y nuevos campos; varchar de translate=True sigue sin resolver el contrato multilingüe GEN0060.

Consumer: src/orm/models.py, src/orm/fields_textual.py.
Verificadores: tests/unit/orm/test_copy.py — ver evidencia/condición individual, no PASS por existencia

### company_consistency

_check_company existe; necesita dos compañías,relaciones permitidas/prohibidas y error/rollback. No convertir ausencia de warning en consistencia demostrada.

Consumer: src/orm/models.py.
Verificadores: tests/unit/orm/test_check_company.py — ver evidencia/condición individual, no PASS por existencia

### company_context

Contexto company y allowed_company_ids deben afectar valor/fallback/caché conforme a permisos. Transacción o company_dependent aislados no aceptan todo ese flujo.

Consumer: src/orm/environments.py, src/orm/fields_company_dependent.py.
Verificadores: tests/unit/orm/test_company_dependent.py — ver evidencia/condición individual, no PASS por existencia

### property_authority

PropertiesDefinition es autoridad de nombres/tipos; distinguir definición y valores de instancia. Exige demostrar rechazo de definición inválida, no sólo JSON serializable.

Consumer: src/orm/fields_properties.py.
Verificadores: tests/unit/orm/test_fields_properties.py — ver evidencia/condición individual, no PASS por existencia

### property_conversion

Conversión Properties requiere tipos,defaults,falsy y salida de lectura/escritura. JSONField genérico no sustituye la validación declarada por la definición.

Consumer: src/orm/fields_properties.py.
Verificadores: tests/unit/orm/test_fields_properties.py — ver evidencia/condición individual, no PASS por existencia

### property_relational

Valores relacionales de propiedades deben respetar modelo,destino,registros ausentes y acceso; una lista de IDs sintáctica no acredita esos efectos.

Consumer: src/orm/fields_properties.py, src/orm/fields_relational.py.
Verificadores: tests/unit/orm/test_fields_properties.py — ver evidencia/condición individual, no PASS por existencia

### property_search

Buscar una propiedad exige nombre/path y compilación de operador/fecha. La rama DomainCondition sin nombre tiene un pendiente histórico348, no aceptación por parser de JSON.

Consumer: src/orm/domains.py, src/orm/fields_properties.py.
Verificadores: tests/unit/orm/test_fields_properties.py — ver evidencia/condición individual, no PASS por existencia

### property_group

Agrupar por propiedad requiere claves/tipos/valores vacíos y consumidores de lectura agrupada; no se observó ejecución de ese flujo en312casos.

Consumer: src/orm/fields_properties.py, src/orm/models.py.
Verificadores: tests/unit/orm/test_fields_properties.py — ver evidencia/condición individual, no PASS por existencia

### property_onchange

Onchange de definiciones/valores necesita registro virtual y delta estable; la conversión persistente de Properties no prueba ese resultado UI.

Consumer: src/orm/fields_properties.py, addons/web/models/models.py.
Verificadores: tests/unit/orm/test_fields_properties.py — ver evidencia/condición individual, no PASS por existencia

### property_security

Definición/valor y comodelos deben filtrarse según usuario/grupos; no usar un valor almacenado correctamente como prueba de visibilidad autorizada.

Consumer: src/orm/fields_properties.py, src/addons/base/models/ir_rule.py.
Verificadores: tests/unit/orm/test_fields_properties.py — ver evidencia/condición individual, no PASS por existencia

### property_performance

Los contadores de consultas del fixture son observables de eficiencia. Requieren baseline comparable/dataset; no adoptar literalmente SQL Odoo ni proclamar complejidad desde presencia de caché.

Consumer: src/orm/fields_properties.py.
Verificadores: tests/unit/orm/test_fields_properties.py — ver evidencia/condición individual, no PASS por existencia

### property_fixture

El fixture incluye autoridad y datos relacionados; modelos declarados en API no garantizan filas,IDs externos o reglas necesarias para todos los tests de propiedades.

Consumer: src/orm/fields_properties.py, src/addons/base/models/properties_base_definition.py.
Verificadores: tests/unit/orm/test_fields_properties.py — ver evidencia/condición individual, no PASS por existencia

### Relational boolean search, related field security and existential witnesses

La equivalencia del predicado any/rights fue acotada históricamente; joins/testigos existenciales sobre SQL y related bajo seguridad requieren dataset y permisos propios.

Consumer: src/orm/domains.py, src/orm/fields_relational.py.
Verificadores: tests/unit/orm/test_domain_any_with_rights.py — ver evidencia/condición individual, no PASS por existencia

### Flush-before-search and selective search_fetch/cache visibility

Search debe ver escrituras pendientes y respetar invalidación selectiva. invalidate_all ignora flush en evidencia previa; no basta que QuerySet lea filas persistidas.

Consumer: src/orm/models.py, src/orm/environments.py.
Verificadores: tests/unit/orm/test_read_path_mechanism.py — ver evidencia/condición individual, no PASS por existencia

### Date-part relational search and noninteger SQL-view identity

Date parts y SQL-view con ID no entero requieren tipo de columna/consulta real y representación compatible; singleton test con int no acepta ese caso.

Consumer: src/orm/domains.py, src/orm/models.py.
Verificadores: tests/unit/orm/test_base_model_recordset.py — ejecutado (ver outcomes por nodeid)

### NULL/False/empty partitions, translation and relational any complements

Optimizadores actuales ejercitan False/in/set; NULL,vacío,traducido y complementos relacionales deben contrastarse por partición de resultados, no por expresión parecida.

Consumer: src/orm/domains.py, src/orm/fields_textual.py.
Verificadores: tests/unit/orm/test_domain_operator_optimizers.py — ejecutado (ver outcomes por nodeid)

### Domain optimizer normalization, type algebra, contextual dates and property expressions

Las suites actuales cubren registro,normalización y algebra por tipos. SQL sobre propiedades/fechas contextuales aún exige sus fixtures; no se declara entero el optimizador aceptado.

Consumer: src/orm/domains.py.
Verificadores: tests/unit/orm/test_domain_optimizer_registry.py — ejecutado (ver outcomes por nodeid), tests/unit/orm/test_domain_operator_optimizers.py — ejecutado (ver outcomes por nodeid), tests/unit/orm/test_domain_type_optimizers.py — ejecutado (ver outcomes por nodeid)

### Recordset stable ordering, nulls, collation, relational recursion and virtual IDs

Sorted pasa sus casos salvo xfail de recursión many2one. Ejecutado sin xfail falla por acceso DB no permitido, no demuestra ausencia de terna0402; criterio histórico requiere reconciliación.

Consumer: src/orm/models.py.
Verificadores: tests/unit/orm/test_sorted_order_to_function.py — ejecutado (ver outcomes por nodeid)

### Batch fetching, context-sensitive cache and mutation/recompute performance observables

Cache local y protocolos de registro pasan; fetch0399 grande sigue bloqueado. Métricas de lote/contexto necesitan ejecutar el camino real y medir consultas, no contar helpers.

Consumer: src/orm/models.py, src/orm/environments.py.
Verificadores: tests/unit/orm/test_read_path_mechanism.py — ver evidencia/condición individual, no PASS por existencia, tests/unit/orm/test_field_cache.py — ejecutado (ver outcomes por nodeid)

### Relational command membership and deletion ordering under constraints

Borrado FK y constraints están probados; orden de Command.unlink/delete/set bajo constraints M2M/O2M requiere transacciones y colas de comandos, no aceptación de toda relación.

Consumer: src/orm/commands.py, src/orm/fields_relational.py.
Verificadores: tests/unit/orm/test_relational_reconstruction_persistence.py — ver evidencia/condición individual, no PASS por existencia

### Company default field optimization and skip-locked raw SQL exception

Default por empresa y SKIP LOCKED son contratos distintos. El primero requiere contexto/permisos; el segundo concurrencia y versión PG, no equivalencia automática de sintaxis SQL.

Consumer: src/orm/models.py, src/orm/fields_company_dependent.py.
Verificadores: tests/unit/orm/test_check_company.py — ver evidencia/condición individual, no PASS por existencia

### Timing harness, large-domain stress and measured—not asserted—linearity

El harness temporal y estrés de dominio requieren datos/tamaño/mediciones comparables. No se transforma medición no asertada en requisito obligatorio de rendimiento.

Consumer: src/orm/domains.py, src/orm/models.py.
Verificador Consumer de este comportamiento aún por delimitar con los fixtures y criterio descritos; no se excluye el contrato.

### record_attribute_boundary

Frontera de atributos privados/campos debe comprobar getattr/getitem/asignación y errores; el protocolo de conjunto ejecutado cubre otra parte, no da autoridad para exponer atributos.

Consumer: src/orm/models.py, src/orm/fields.py.
Verificadores: tests/unit/orm/test_base_model_recordset.py — ejecutado (ver outcomes por nodeid)

### expiration_lifecycle

Autovacuum necesita cron y marcadores de expiración,empresa/usuario y tiempo controlado. Existencia del modelo no acredita ejecución/limpieza ni justifica borrar datos reales.

Consumer: src/addons/base/models/ir_autovacuum.py.
Verificador Consumer de este comportamiento aún por delimitar con los fixtures y criterio descritos; no se excluye el contrato.

### index_method_reconciliation

check_indexes y TableObject aplican esquema, pero método/parcialidad/unicidad deben observarse en PG. Índices Odoo literales no son automáticamente requisitos de Django.

Consumer: src/orm/registry.py, src/orm/table_objects.py.
Verificadores: tests/unit/orm/test_registry_schema_axis.py — ver evidencia/condición individual, no PASS por existencia

### translated_record_storage_query

La divergencia varchar/jsonb sigue abierta; importer PO sólo anotar etiquetas no resuelve CRUD/fallback/filter por idioma. No se ejecuta migración sin preservación y autorización.

Consumer: src/orm/fields_textual.py, src/tools/translate.py.
Verificador Consumer de este comportamiento aún por delimitar con los fixtures y criterio descritos; no se excluye el contrato.

### json_cache_value_normalization

0420 prueba default anidado aislado y roundtrip JSONB. Copy-on-read/conversión de tuplas y normalización general de caché Json son obligaciones adicionales no aceptadas por ese arreglo.

Consumer: src/orm/fields_misc.py.
Verificadores: tests/unit/orm/test_json_defaults.py — ver evidencia/condición individual, no PASS por existencia

### many2many_search_security

M2M search requiere reglas del comodelo y testigos relacionales; el flag bypass y predicado unitario no prueban todos los resultados autorizados.

Consumer: src/orm/domains.py, src/orm/fields_relational.py.
Verificadores: tests/unit/orm/test_domain_any_with_rights.py — ver evidencia/condición individual, no PASS por existencia

### onchange_virtual_record_compute

Onchange debe producir delta virtual y origen; BaseModel.new falta y el camino web usa adaptaciones. No se copia TestCase nativo ni se admite el flujo sin resolver esa dependencia.

Consumer: addons/web/models/models.py, src/orm/models.py.
Verificador Consumer de este comportamiento aún por delimitar con los fixtures y criterio descritos; no se excluye el contrato.

### one2many_inverse_cache_recompute

One2many plano carece de toda caché de Field; se deben medir los dos extremos después de comandos/inverse/recompute. Descartar faltantes0559 no resuelve este contrato.

Consumer: src/orm/fields_relational.py, src/orm/fields.py.
Verificadores: tests/unit/orm/test_fields_relational_update_inverse.py — ver evidencia/condición individual, no PASS por existencia

### float_rendering_adapter

El candidato previo src/addons/base/models/ir_qweb_fields.py no existe en este checkout; el addon html_editor no demuestra ese conversor de base. Render de float exige formato/localización/precisión frente al conversor de salida. El almacenamiento Float/Decimal o round() no demuestra HTML/string correcto.

Consumer: src/tools/float_utils.py, addons/html_editor/models/ir_qweb_fields.py.
Verificador Consumer de este comportamiento aún por delimitar con los fixtures y criterio descritos; no se excluye el contrato.

### related_translation_propagation

El montaje related copia metadata, pero propagación multilingüe exige almacenamiento y contexto por idioma. La bandera translate no acepta GEN0060 ni recomputación traducida. Consumer ResGroups.full_name está demostrado divergent: retorna desde compute en vez de asignar y la lectura recursa; evidencia nonstored-consumer.json, relacionado0415/0417, no otro hallazgo por grupo.

Consumer: src/orm/fields.py, src/orm/fields_textual.py.
Verificadores: tests/unit/orm/test_related_field_setup.py — ejecutado (ver outcomes por nodeid)

### reflection_schema_and_indexes

Reflexión y actualización de columnas/index dependen de esquema real; prueba de setup en memoria no prueba DDL ni ausencia de pérdida de datos.

Consumer: src/orm/registry.py, src/orm/fields.py.
Verificadores: tests/unit/orm/test_registry_schema_axis.py — ver evidencia/condición individual, no PASS por existencia

### ui_consumer_constraints

Constraints de tours/formularios necesitan Consumer UI y recursos equivalentes; web_tour no recuperado en runtime. No imputar TASK0406 ni crear otra auditoría UI independiente.

Consumer: addons/web, src/addons/test_orm.
Verificador Consumer de este comportamiento aún por delimitar con los fixtures y criterio descritos; no se excluye el contrato.

### web_read_projection_security

web_read proyecta campos pero debe respetar ACL/row-rules/propiedades. La delegación declarada a DRF no es aceptación de seguridad para toda proyección.

Consumer: addons/web/models/models.py, src/orm/models.py.
Verificadores: tests/unit/orm/test_access_manager.py — ver evidencia/condición individual, no PASS por existencia

### view_metadata_access_adaptation

Metadatos de vista/default-form precisan tipo de vista/campos/acceso y Consumer de salida. No hay equivalencia demostrada por existencia de IrUiView o XML nativo.

Consumer: src/addons/base/models/ir_ui_view.py, addons/web/models/models.py.
Verificador Consumer de este comportamiento aún por delimitar con los fixtures y criterio descritos; no se excluye el contrato.

### web_save_serialization

web_save coordina valores/comandos y salida; create de un registro no acredita secuencia completa ni rollback,permisos y serialización del flujo web.

Consumer: addons/web/models/models.py, src/orm/models.py.
Verificadores: tests/unit/orm/test_create.py — ver evidencia/condición individual, no PASS por existencia


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

## Verificación de cumplimiento y cierre de brechas — 2026-10-21

### TASK-API-0416

Fixture corregido en f5bb655c: el cierre de DDL usa conexión nueva después de comprobar ausencia de dirty/tocompute/patches. Control anterior reproduce base.public_user/autocommit, frontera nueva pasa.41pytestPASS incluyendo teardown; no se sembró actor ni se modificó Transaction.flush.

Continuación: Aceptar el resultado conjunto final del lote y revisión/CI; no atribuir este error de fixture a obligación de implementar0379.

### TASK-API-0417

0fc622dc reutiliza NewId como clave privada del caché existente para computes contextuales sin columna con pkNone. Preserva valores por instancia/contexto y constructor, invalidación y protección recursiva; pk sigueNone.131casosPASS y controles sin identidad/identidad compartida fallan2/1. El Consumer original antes divergente pasa con0SQL.

Continuación: Revisión/CI e integración autorizada pendientes. La falla acotada sin pk ya está corregida; BaseModel.new/origin y protocolo virtual completo GEN0579 no quedan aceptados.

### TASK-API-0415

Estado completed histórico intacto. Despacho/asignación vigente se conserva; el Consumer real ahora también conserva contextos sin pk mediante caché existente. Nueva prueba de segunda lectura conserva metadata del método mockeado, evitando un positivo que ignorara depends_context.

Continuación: No reimplementar fábrica NonStored; revisar delta0417 y aceptar sólo contratos probados, no todoORM.

### TASK-GEN-0559

3ffa958e/2f01be1b preservados, helpers sin cambios;16PGPASS de regresión tras modificación material de lectura/cache. No nueva implementación o admisión.

Continuación: Esperar CI/revisión/integración autorizada; no declarar todaGEN0559 niORM completo.

El criterio previo de que la lectura contextual sin pk exigía todoBaseModel.new queda corregido por prueba del adaptador de caché existente. GEN0579 completo y0379 actor de seguridad conservan estado/alcance; no nuevas TASK. Ver scripts/evidence/orm-acceptance-close-20261021T234504/README.md para matriz de cumplimiento y resultado conjunto.

Cierre verificado del incremento actual:47pytestPASS con migraciones nativas PostgreSQL y teardown del código final conjunto;131PASS focalizados,214PASS/1XFAIL y16PG0559 conservados. No sumar poblaciones solapadas ni declarar CI/merge.

## Incremento module-state

TASK-API-0382, sesión168b0fdf-bfe4-590b-b6c0-b6be124c124a/local737, conserva pending y owner codex-module-lifecycle. Se añade sólo este registro al alcance histórico; no se considera la población exhaustiva.

Catalogue refresh no longer derives operational states from imported apps. Administrative requests validate dependencies/authorization, lock and queue transitions in one database. Two real databases retain distinct states, concurrent requests and rollback; mixed-database batches with colliding IDs are rejected. Installation itself is not executed by these requests.

Complete effective registry and schema/data/hooks loader using existing mechanisms. Global automation signals still lose explicit DB alias on metadata writes; prototype isolated process composition is not production integration. TASK-API-0173 identity checked; no arbitrary relocation of capability identities or historical migration rewrite.

Evidencia y resultados definitivos: scripts/evidence/orm-module-state-20261022T032053/README.md. Sin aceptación integral ni merges.

# Contratos reales del ORM y clasificación contextual

Intervención de ANÁLISIS Y VERIFICACIÓN, sin implementación funcional.
Consumer API 61ea5e9f6c379a9808d71c2a5fd801fd150be0f0; Docs
3a24685c89bcd8293234547990745d32798b2fa7; Thyrox
9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f. No se rehicieron inventarios generales.
Referencia Odoo Community 19, odoo-tools@abe4040ec1a45beee90fb694e4eae4453e46b389.
Se añadió sólo odoo/sql_db.py al extracto parcial: blob y SHA256 verificados en
sql-db-provenance.json. Su extracción no instala un runtime de Odoo.

## Nuevos resultados reproducibles

1. Registry.cursor está declarado READY por el clasificador histórico, pero
   bajo transacción manual conserva INTRANS y un advisory lock al salir bien;
   con SELECT 1/0 conserva INERROR. Odoo declara commit al salir bien y limpieza
   al cerrar. Django CursorWrapper.__exit__ sólo cierra. La prueba obtiene un
   lock transaccional de id aleatorio y lo observa desde otra conexión propia:
   discrimina un cierre superficial de una transacción terminada. Se limpiaron
   las dos conexiones con rollback/close; no se creó tabla ni escribió dato.
   No extrapola a todos los contextos autocommit ni acepta pool, hooks o réplica.
2. El control positivo transaction.atomic de Django termina en IDLE y libera
   el lock tanto con éxito como con error SQL. Acredita ese subcontrato nativo;
   no implementa el adaptador Consumer faltante.
3. Catálogo actual de 15 filas: is_modifying_relations declara un atributo de
   instancia como dotted path de clase; no resuelve, primitives está vacío y
   el predicado da BUILDABLE. Sobre una FK real sin dependientes, is_relation
   es True pero el método Consumer y la rama exacta Odoo dan False. La bandera
   no es el contrato completo. Que el método ya exista tampoco está expresado
   por la etiqueta BUILDABLE. Ninguna fila tiene ambas declaraciones vacías;
   el vacío real se alcanza cuando falla la resolución de installed.
4. Test_field_triggers existente: 22 PASS, cero intentos de conexión. Sus
   28 warnings de búsqueda sobre campos sin columna se preservan.
5. Domains: ocho comparaciones contra el cuerpo original
   _optimize_any_with_rights coinciden, con campo real ResGroups y protocolo
   acotado para los accesos model.env.su y condition._field. Los dos controles
   negativos en memoria detectan pérdida de elevación/bypass. No se acepta
   SQL, reglas por fila, dominios anidados ni la representación completa Odoo.
6. Registry.setup_signaling real: falla por siete tablas ausentes en QA,
   mediante un único SELECT. Se registra como dependencia concreta; no se
   ejecutaron migraciones ni se bloquearon por ello los otros contratos.
7. H-API-1082 ya corrigió la propuesta de unificar INVENTORY: declaraciones
   locales, con su sucesor #363 retirado. No se normalizan claves ni se crea
   otra autoridad. Los consumidores literales examinados son tests locales.
8. Se recuperaron stalled en task_continuation.OUTCOMES y Superseded en el
   control de generaciones de snapshots: son referentes distintos de TASK.
   No se crearon enums/campos para los candidatos conceptuales del documento.

Integración: se actualizó sólo la referencia develop de API y se verificaron
blobs idénticos de cuatro fuentes y dos suites contra origin/develop@ed55e6d5.
No hubo merge; los seis PR siguen abiertos y sin APPROVED. La brecha de cursor
es heredada en la base, no una regresión causada por esta auditoría.
El CI sobre 61ea5e9f terminó FAILURE con firma res_users/sync_apps H-API-1120;
el log actual completo se preserva comprimido con hash. No se repitió la suite.

## Comandos, interfaces y precondiciones

Desde la raíz API, UV_CACHE_DIR de la sesión, PYTHONPATH=src:<Thyrox>/src,
ODOO_TOOLS apuntando al extracto verificado para las sondas de referencia:

- uv run --frozen python <este run>/outputs/cursor_transaction_contract.py
- uv run --frozen python <este run>/outputs/signaling_precondition.py
- uv run --frozen python <este run>/outputs/real_registry_classifier_cases.py
- uv run --frozen python <este run>/outputs/domain_reference_predicate.py
- uv run --frozen python <este run>/outputs/existing_field_trigger_tests.py

Todos terminaron exit 0 porque sus aserciones confirman los resultados esperados;
esto NO convierte la brecha funcional observada en PASS del contrato.
Las rutas scratch de salida son detalles de esta VM, no autoridad de instalación.
El wrapper de signaling lee el setup del archivo de cursor adyacente.

El setup usa credenciales sintéticas sólo en memoria para las sondas sin DB;
para cursor/signaling se selecciona exclusivamente el perfil QA de DESARROLLO
ya declarado en DB/.env.example, conexión localhost, sin escribir .env. Un guard
impide conexión durante django.setup y se retira sólo en las dos sondas con DB
expresamente autorizadas. No se utiliza el conftest global ni se retiran marcas
django_db para fingir pruebas de persistencia. No hay DDL/DML de aplicación.

Provider usado, revisión arriba: session.job_runs.jobs_dir (núcleo read-only),
scaffold_run, declare_workbench, settle; workbench.manifest.readers existentes y
claimsCommand para reservas administrativas sin TASK ficticia. El extractor
histórico extract_both_sides.bodies se reutiliza para los cuerpos de Registry.
Consulta de tareas: bin/agent_store buscar-tareas --query <setup_signaling,
señalización, cursor, Registry, inventario, H-API-980, H-API-1082> con filtros
según el Consumer; ninguna coincidencia acredita por sí sola identidad/ownership.
No se modificó el store ni se acuñó un identificador para el nuevo contraste.

Claims observados al comenzar: API 0, Docs 1, Provider 49; no son prueba de
procesos vivos y no se tocaron reservas ajenas. Podman, llama-server y Ollama
no tenían ejecutable ni proceso observado. No se lanzó una TASK con modelo.
El PostgreSQL de Docker sigue siendo infraestructura Codex; las sondas no lo
convierten en recurso gestionado Thyrox. Los commits locales de Thyrox siguen
preservados según el expediente; no se intentó otro push ni se eludieron gates.

El análisis existente de Docs (BaseModel v1.4.0) contiene la matriz de contratos,
roles de dependencias, propuesta conceptual y pruebas para una eventual
transición; no es una migración autorizada. El expediente previo conserva el
resumen. No se declara completa la auditoría global del ORM.

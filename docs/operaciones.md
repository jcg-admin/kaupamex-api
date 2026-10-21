# docs/operaciones.md

Runbook de operaciones para kaupamex-api.

---

## Setup del entorno de desarrollo (una vez)

```bash
# 1. Clonar y configurar (uv crea .venv desde pyproject.toml + uv.lock)
git clone <repo>
cd kaupamex-api
uv sync

# 2. Variables de entorno
cp src/.env.example src/.env
# Editar src/.env — credenciales de PostgreSQL y SECRET_KEY

# 3. Aplicar migraciones
cd src
uv run python manage.py migrate

# 4. Aplicar migraciones en la base QA (para pytest)
DJANGO_SETTINGS_MODULE=config.settings.testing \
  uv run python manage.py migrate

# 5. Crear superusuario (opcional)
uv run python manage.py createsuperuser

# 6. Levantar el servidor
uv run python manage.py runserver
```

Para provisionar la base y el rol en PostgreSQL (ver `kaupamex-db`):

```bash
sudo bash provisioners/postgresql/db_setup.sh          # base kaupamex_core
sudo bash provisioners/postgresql/db_setup.sh --qa     # base kaupamex_core_qa
```

Para entornos con servidor de BD dedicado: ver `kaupamex-db/docs/integracion-api.md`.

---

## Verificar la conexión a la base de datos

```bash
cd src

# Verificar que Django puede conectarse a la BD de desarrollo
python manage.py check --database default

# Verificar que las migraciones están al día (desarrollo)
python manage.py showmigrations

# Verificar estado de migraciones en la base QA (tests)
DJANGO_SETTINGS_MODULE=config.settings.testing \
  python manage.py showmigrations

# Verificar estado completo de la BD (desde kaupamex-db)
bash ../kaupamex-db/scripts/verify_postgres.sh
```

---

## Tests

```bash
cd src

# Suite completa (--reuse-db ya esta en addopts de pytest.ini)
uv run pytest --reuse-db -q

# Solo un addon
uv run pytest tests/unit/<addon>/ tests/integration/<addon>/ -q --reuse-db
```

Los tests usan la base `kaupamex_core_qa` — nunca tocan `kaupamex_core`. Ver
`pytest.ini` y `config/settings/testing.py`.

---

## Migraciones

```bash
cd src

# Crear una nueva migración
python manage.py makemigrations <app>

# Aplicar en desarrollo
python manage.py migrate

# Aplicar en la base QA (necesario cuando se agregan tablas)
DJANGO_SETTINGS_MODULE=config.settings.testing \
  python manage.py migrate

# Ver el SQL que generaría una migración (sin aplicarla)
python manage.py sqlmigrate <app> <migration_number>
```

---

## Servidor de desarrollo

```bash
cd src

# Arrancar en el puerto por defecto (8000)
python manage.py runserver

# Arrancar en otro puerto
python manage.py runserver 0.0.0.0:8080
```

---

## Recolección de archivos estáticos (para despliegue)

```bash
cd src
python manage.py collectstatic --noinput
```

---

## Diagnóstico

```bash
cd src

# Verificar configuración de Django
python manage.py check

# Verificar configuración con settings específicos
DJANGO_SETTINGS_MODULE=config.settings.production \
  python manage.py check --deploy

# Ver el schema de la BD activa
python manage.py inspectdb | head -30
```

---

## Variables de entorno requeridas

| Variable | Entorno | Descripción |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | todos | `config.settings.<env>` |
| `SECRET_KEY` | todos | Clave secreta de Django |
| `DB_NAME` | dev/prod | Base de producción/desarrollo (`kaupamex_core`) |
| `DB_USER` | dev/prod | Rol Django |
| `DB_PASSWORD` | dev/prod | Contraseña Django |
| `DB_SOCKET` | dev/prod | Directorio del socket Unix (en libpq el socket ES el host) |
| `DB_HOST` | dev/prod | Host de PostgreSQL |
| `DB_PORT` | dev/prod | Puerto de PostgreSQL |
| `DB_QA_NAME` | testing | Base QA para pytest (`kaupamex_core_qa`) |
| `DB_QA_USER` | testing | Rol QA |
| `DB_QA_PASSWORD` | testing | Contraseña QA |
| `EMAIL_HOST` | producción | Servidor SMTP |
| `EMAIL_HOST_USER` | producción | Usuario SMTP |
| `EMAIL_HOST_PASSWORD` | producción | Contraseña SMTP |
| `FRONTEND_URL` | producción | URL pública del UI React |
| `UI_DIST` | producción | Ruta al build de React |

Las variables de BD deben coincidir con `kaupamex-db/.env`.
Ver `kaupamex-db/docs/integracion-api.md` para la tabla de
equivalencias completa.


## Autoridad local y continuidad portable — propuesta verificada parcialmente

Esta sección complementa el plan vigente de `completar-raiz-orm`. No traslada
TASK ni documentos, no sustituye los AGENTS ni convierte este runbook en otro
plan rector. Los ejemplos operativos anteriores deben contrastarse con settings,
lock y servicio actuales antes de ejecutarse; no son comandos de este lote.

API posee código, pruebas, configuración y evidencia técnica. La propuesta es
que también gobierne sus contratos y decisiones locales. Hasta una decisión
legítima de adopción, la iniciativa y los anchors RST vigentes siguen en Docs.
La intranet conserva estándares, arquitectura transversal y portafolio. Thyrox
coordina, pero la ubicación de su SQLite no le transfiere propiedad funcional.

La instalación declarada usa Django 6.0.5, DRF 3.16.1 y psycopg/PostgreSQL >=14.
Requerir PostgreSQL no requiere automáticamente el checkout de DB; probar REST
no requiere UI. Odoo tools es referencia fijada, sin import productivo implícito.
No se probó aquí una instalación limpia o la suite completa sin Docs. Sí pasaron
imports acotados con un guard de lectura Docs y su control negativo; no es
sandbox de sistema operativo ni aceptación de arranque/ORM.

### Inicio y admisión

1. Leer AGENTS y reglas locales; recuperar objetivo/unidad en el plan vigente.
2. Comprobar repositorio propietario, Git/HEAD/rama, operaciones pendientes,
   cambios ajenos y revisiones publicadas. No rehacer inventario de ramas.
3. Usar `task_ids.mapping_from_store/lookup` y
   `agent_store.resolve_store_dir(create=False)/connect_readonly` para identidad
   existente. La lectura no debe invocar `connect()`, que migra/resincroniza.
4. Reconciliar contrato, iniciativa, propiedad funcional, owner operativo,
   dependencias y claim. Owner nulo no indica disponibilidad. `submodule` y
   prefijo GEN no bastan para adjudicar el proyecto propietario.
5. Recuperar evidencia por revisión y ejecutar SHA256SUMS desde su directorio;
   coincidencia de hash identifica contenido, no autoría ni conformidad.
6. Admitir sólo con contrato, dependencias satisfechas, verificador independiente,
   identidad/ownership, recursos cualificados y autorización específica. Los
   mecanismos genéricos son de Thyrox; no crear otro TaskStore o coordinador.

### Ejecución, verificación y publicación

- Trabajar sólo en rutas/repositorios autorizados, usando claims nativos para
  el alcance propio; no reasignar claims ajenos.
- Usar `session.job_runs` y `workbench.manifest` para run y límites. El campo
  destination no redirige automáticamente salidas; verificar el directorio real.
- Registrar fuente/revisión, entradas, preparación, comando, entorno, ejecución,
  exit code, aserciones, controles negativos, evidencia, hash, integración y
  aceptación. Mantener completo/fallido/en curso/no ejecutado separados.
- Usar `record_environment` con ejecutable explícito para el alcance medido.
  `tree_fingerprint` sólo cubre src/tests/bin por defecto; un snapshot nativo
  tiene generación y procedencia, no es una copia operativa arbitraria del store.
- Reintentos, frontier, selección, verificación e integración genéricas pertenecen
  a Thyrox; no presentar ingeniería Codex como inferencia de un modelo local.
- Publicar sólo por rama/PR autorizados con hooks y revisión; el commit publicado
  no implica merge o aceptación. No deshabilitar gates para evitar deuda heredada.

### Cierre, transferencia y recuperación

El ejecutor saliente conserva referencias verificables, no otra copia de estado.
El entrante debe poder responder estos 18 datos usando las autoridades existentes:

| Dato recuperable | Fuente existente |
| --- | --- |
| Objetivo/unidad | Plan vigente y contrato referenciado |
| Repositorio/rama | Git y alcance autorizado |
| TASK activa | Cita estable y par sesión/task del store |
| Agente/claim | Ledger nativo de claims, separado de propietario funcional |
| Operaciones terminadas | Manifiestos asentados y resultados |
| Operaciones todavía activas | Manifest más proceso/trabajo comprobado; no sólo PID |
| Implementación publicada | Commit/HEAD remoto |
| Verificaciones ejecutadas | Comando, revisión y evidencia |
| Verificaciones satisfactorias | Assertions y controles, no sólo exit0 |
| Fallos | Resultado y clasificación heredada/regresión/no evaluado |
| Parciales | Manifest y límites explícitos |
| Dependencias pendientes | Store crudo, texto reconciliado y contrato |
| Documentos modificados | Diff/commit y autoridad |
| Commits y PR | Git y estado remoto |
| Recursos reservados | Claims/admisión nativa actual, sin inferir de historial |
| Próxima acción | Frontier nativo más las seis condiciones de admisión |
| Prohibiciones | Autorización vigente y reglas locales |
| Evidencia comprobatoria | Run, rutas/hashes, fuente y revisión |

last_verified_state, interrupted_work y continuation_frontier son distinciones
conceptuales, no campos nuevos. Un manifest incompleto no prueba actividad; un
trabajo aceptado no debe repetirse por empezar otra sesión. Verificar cambios
posteriores, integridad y claims antes de reanudar. No inferir utilidad de un PID.

Control ejecutado: un proceso fresco, sin transcript, resolvió cuatro identidades,
la dependencia GEN0062/GEN0060, evidencia, heads y claim1072; un hash falso fue
rechazado. La prueba de transferencia real entre agentes, infraestructura runtime
y restauración/reversión siguen pendientes. Los scripts de control del run son
sondas aisladas, no interfaz productiva o almacén nuevo de continuación.

Controles históricos obligatorios: TASK-API-0406 no es web_tour; 0417→0418 requiere
reconciliar corrección parcial 20dc122b; GEN0062 depende de GEN0060 en la misma
sesión. La proyección `task_source` conocida pierde una arista y TASK1072 conserva
claim vm-r: no corregirla ni usarla como única autoridad de elegibilidad.

### Publicación documental y adopción futura

El publicador existente valida intención/generación/blob y RST bajo gestión;
rechaza la disposición API/docs en el control de formato. No demuestra aún
agregación universal. Conservar enlaces por commit y anchors históricos; aprobar
por artefacto autoridad, ubicación y mapa de referencias antes de trasladar.
No copiar todo Docs ni añadir un include de checkout externo al build API.

Se propone separación lógica por Consumer conservando de momento el store
central físico. La alternativa de bases por proyecto exige resolver identidad,
relaciones cruzadas, concurrencia, respaldo y reversión; no está aprobada.
No añadir enums/esquemas, renumerar o migrar estados por esta propuesta.

Riesgos activos: Makefile de idioma y pre-commit buscan el checker en Docs;
el segundo omite ese gate si no lo encuentra. Esto no acredita verificación
independiente. Cualificar mecanismo genérico/configuración antes de cambiarlo.
Los accesos internos de web_read/agrupación/web_save no prueban pasar por DRF:
contrastar dos usuarios, permisos por registro/capacidad y caller real antes de
concluir vulnerabilidad o conformidad. No basta la existencia de HasCapability.

La búsqueda focal también identifica snapshot-tasks/refresh-board como publicación
de tablero destinada a Docs, separada de la lectura del store. No ejecutarlos
para simular un control readonly. user_wiring resuelve Consumer genérico; en la
proyección pura de sync_local_settings los parámetros explícitos eliminan Docs,
pero los defaults históricos aún lo nombran. No se modificaron hooks o settings.

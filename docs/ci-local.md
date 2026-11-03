# Validación local y CI: TASK-API-0478

Antes de publicar un cambio ejecuta `make ci-verify` contra PostgreSQL exclusivo.
GitHub ejecuta ese mismo target con el perfil Python 3.12 fijado en Make.
`uv` resuelve o descarga ese intérprete; esto no cualifica Python 3.13/3.14.
Requiere `uv`,
gcc/make, libpng, zlib y `pg_isready` (postgresql-client); el target usa
`uv sync --frozen`, valida el destino,
compila PDF y ejecuta la suite completa con `--create-db --maxfail=1`.
Las etapas son secuenciales incluso con `make -j`: un fallo impide las siguientes.
No usa `|| true`, reintentos ni filtros que oculten pruebas. Make devuelve un
estado no cero y muestra el código original de la etapa; pytest conserva sus
códigos (fallo, error de colección, interrupción o ausencia de pruebas).

Provisiona una **base desechable y un rol exclusivos con CREATEDB** mediante el
mecanismo de infraestructura existente. pytest-django recrea la base; ser dueño
sin CREATEDB no basta. Nunca apuntes este comando a QA compartida. Declara
`DJANGO_SETTINGS_MODULE=config.settings.testing`, `PYTHONPATH=src`, las claves
`DB_*` y `DB_QA_*` requeridas y `SECRET_KEY` sólo en el entorno del proceso.
`DB_QA_NAME` debe comenzar con `kaupamex_ci_`; el harness de evidencia ya existente
usa `orm_bootstrap_`, también admitido. `CI_DATABASE_DISPOSABLE` debe contener
exactamente ese nombre. Autoriza su recreación: no acredita por sí mismo propiedad
de una base ajena. Configura host/socket, puerto y TLS según la infraestructura.
No edites `.env`. El comando no provisiona ni elimina roles, contenedores o HBA;
la creación y limpieza pertenecen al mecanismo que otorgó el recurso exclusivo.

Para la sesión Cloud se reutiliza el harness PostgreSQL ya verificado:

```bash
ORM_QA_CONTAINER=kaupamex-postgres-cloud \
ORM_QA_HOST=127.0.0.1 ORM_QA_BRIDGE=172.17.0.1 \
uv run --frozen python \
  scripts/evidence/orm-bootstrap-compute-20261021T210528/probes/qa_context.py \
  bash -ec 'case "$DB_QA_USER" in orm_bootstrap_*)
    docker exec -u postgres "$ORM_QA_CONTAINER" psql -X -v ON_ERROR_STOP=1 \
      -d postgres -c "ALTER ROLE \"$DB_QA_USER\" CREATEDB";;
    *) exit 2;; esac
    CI_DATABASE_DISPOSABLE="$DB_QA_NAME" make ci-verify'
```

El harness crea un recurso propio, exporta las conexiones sin mostrar secretos y
limpia sólo sus recursos al finalizar. Sus dependencias (Docker y contenedor
preparado) son específicas de Cloud; no se necesitan en un runner con PostgreSQL
ya provisionado. La instancia de GitHub usa un service container aislado por run.
El rol CREATEDB es únicamente el rol aleatorio que acaba de crear ese harness.
En la sesión sin privilegios de instalación se extrajeron las cabeceras libpng
de la misma versión del runtime en un prefijo del workspace y se obtuvo
`pg_isready` del contenedor PostgreSQL existente. Para ese caso se declaran
`CPATH`, `LIBRARY_PATH` y `PATH` sólo en la invocación; procedencia y versiones
quedan en la evidencia de TASK-API-0478. No se cambia el compilador, el helper
ni el conftest para ocultar esas dependencias.

`test-results/pytest.xml` queda disponible incluso cuando pytest falla. GitHub
intenta subirlo con `always()`; una ausencia por fallo anterior o timeout no es
una aprobación. Los logs completos permanecen en Actions; para evidencia local
usa el hogar de jobs/evidencia resuelto por Thyrox y conserva el exit code si
usas `tee` (`set -o pipefail`). No archives variables ni credenciales.

Un primer error detiene la suite: las pruebas posteriores **no están evaluadas**.
Se corrige o clasifica su causa antes de repetir; no se presenta el subconjunto
como suite aprobada. El drift histórico de migraciones TASK-API-0093 conserva
su autoridad; no se añade `makemigrations --check` como requisito nuevo sin
reconciliarlo. Los checkers de los hooks existentes siguen vigentes.

La validación local reduce la espera, pero Actions sigue siendo la comprobación
independiente del PR y su combinación con la base. No desactives protecciones ni
modifiques hooks para saltarla. No equivale a aceptación integral del ORM ni a
inferencia de modelos locales. Thyrox mantiene TASK, identidad, claims y evidencia;
este target sólo declara la verificación específica del Consumer.

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
sudo bash provisioners/postgresql/db_setup.sh          # base kaupamex_db
sudo bash provisioners/postgresql/db_setup.sh --qa     # base kaupamex_qa
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

Los tests usan la base `kaupamex_qa` — nunca tocan `kaupamex_db`. Ver
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
| `DB_NAME` | dev/prod | Base de producción/desarrollo (`kaupamex_db`) |
| `DB_USER` | dev/prod | Rol Django |
| `DB_PASSWORD` | dev/prod | Contraseña Django |
| `DB_SOCKET` | dev/prod | Directorio del socket Unix (en libpq el socket ES el host) |
| `DB_HOST` | dev/prod | Host de PostgreSQL |
| `DB_PORT` | dev/prod | Puerto de PostgreSQL |
| `DB_QA_NAME` | testing | Base QA para pytest (`kaupamex_qa`) |
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

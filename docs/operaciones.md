# docs/operaciones.md

Runbook de operaciones para PracticaYoruba-api.

---

## Setup del entorno de desarrollo (una vez)

```bash
# 1. Clonar y configurar (uv crea .venv desde pyproject.toml + uv.lock)
git clone <repo>
cd e-commerce-api
uv sync

# 2. Variables de entorno
cp practicayoruba/.env.example practicayoruba/.env
# Editar practicayoruba/.env — credenciales de MariaDB y SECRET_KEY

# 3. Aplicar migraciones
cd practicayoruba
uv run python manage.py migrate

# 4. Aplicar migraciones en el schema QA (para pytest)
DJANGO_SETTINGS_MODULE=config.settings.testing \
  uv run python manage.py migrate

# 5. Crear superusuario (opcional)
uv run python manage.py createsuperuser

# 6. Levantar el servidor
uv run python manage.py runserver
```

Para entornos Ubuntu con MariaDB gestionado localmente (todo en una máquina):

```bash
sudo bash scripts/bootstrap.sh
```

Para entornos con servidor de BD dedicado: ver `PracticaYoruba-db/docs/integracion-api.md`.

---

## Verificar la conexión a la base de datos

```bash
cd practicayoruba

# Verificar que Django puede conectarse a la BD de desarrollo
python manage.py check --database default

# Verificar que las migraciones están al día (desarrollo)
python manage.py showmigrations

# Verificar estado de migraciones en el schema QA (tests)
DJANGO_SETTINGS_MODULE=config.settings.testing \
  python manage.py showmigrations

# Verificar estado completo de la BD (desde e-commerce-db)
bash ../e-commerce-db/scripts/verify.sh
python ../e-commerce-db/scripts/check_db.py
```

---

## Tests

```bash
cd practicayoruba

# Suite completa
pytest

# Solo tests unitarios
pytest -m unit

# Solo tests de integración
pytest -m integration

# Solo tests de la app users
pytest ../tests/unit/users/
pytest ../tests/integration/auth/

# Con cobertura
pytest --cov=apps --cov-report=term-missing
```

Los tests usan el schema `practicayoruba_qa` — nunca tocan
`practicayoruba_db`. Ver `pytest.ini` y `config/settings/testing.py`.

---

## Migraciones

```bash
cd practicayoruba

# Crear una nueva migración
python manage.py makemigrations <app>

# Aplicar en desarrollo
python manage.py migrate

# Aplicar en el schema QA (necesario cuando se agregan tablas)
DJANGO_SETTINGS_MODULE=config.settings.testing \
  python manage.py migrate

# Ver el SQL que generaría una migración (sin aplicarla)
python manage.py sqlmigrate <app> <migration_number>
```

---

## Servidor de desarrollo

```bash
cd practicayoruba

# Arrancar en el puerto por defecto (8000)
python manage.py runserver

# Arrancar en otro puerto
python manage.py runserver 0.0.0.0:8080
```

---

## Recolección de archivos estáticos (para despliegue)

```bash
cd practicayoruba
python manage.py collectstatic --noinput
```

---

## Diagnóstico

```bash
cd practicayoruba

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
| `DB_NAME` | dev/prod | Schema de producción |
| `DB_USER` | dev/prod | Usuario Django |
| `DB_PASSWORD` | dev/prod | Contraseña Django |
| `DB_HOST` | dev/prod | Host de MariaDB |
| `DB_PORT` | dev/prod | Puerto de MariaDB |
| `DB_QA_NAME` | testing | Schema QA para pytest |
| `DB_QA_USER` | testing | Usuario QA |
| `DB_QA_PASSWORD` | testing | Contraseña QA |
| `EMAIL_HOST` | producción | Servidor SMTP |
| `EMAIL_HOST_USER` | producción | Usuario SMTP |
| `EMAIL_HOST_PASSWORD` | producción | Contraseña SMTP |
| `FRONTEND_URL` | producción | URL pública del UI React |
| `UI_DIST` | producción | Ruta al build de React |

Las variables de BD deben coincidir con `PracticaYoruba-db/.env`.
Ver `PracticaYoruba-db/docs/integracion-api.md` para la tabla de
equivalencias completa.

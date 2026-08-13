# kaupamex-api

Backend eCommerce — Django REST Framework + PostgreSQL + JWT.

## Prerequisitos

- Python 3.12 o superior
- PostgreSQL 16 (mínimo efectivo 14, ADR-028) corriendo localmente
- `uv` (gestor de toolchain Python — D-031/H-14). Instalar:
  `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Setup

```bash
# 1. Crear el .venv e instalar dependencias desde pyproject.toml + uv.lock
#    (uv sync es reproducible y nunca toca el Python del sistema → sin PEP 668)
uv sync

# 2. Configurar variables de entorno
cp src/.env.example src/.env
# Editar src/.env con las credenciales de PostgreSQL

# 3. DJANGO_SETTINGS_MODULE es obligatorio y explícito: sin él,
#    kaupamex-bin cae al default de src/cli/command.py — que es
#    config.settings.production, no development (H-API-394).
export DJANGO_SETTINGS_MODULE=config.settings.development

# 4. Aplicar migraciones — kaupamex-bin es el punto de entrada del
#    producto (equivalente de odoo-bin), no manage.py directo
uv run python kaupamex-bin migrate

# 5. createcachetable — Django no la incluye en el framework de
#    migraciones (config.settings.base: CACHES usa DatabaseCache).
#    Sin esta tabla, cualquier endpoint DRF (throttling global)
#    responde 500 en la primera peticion real. Idempotente.
uv run python kaupamex-bin createcachetable

# 6. Crear superusuario
uv run python kaupamex-bin createsuperuser

# 7. Levantar el servidor de desarrollo
uv run python kaupamex-bin server
```

`uv run <cmd>` ejecuta dentro del `.venv` gestionado por uv (fija el
intérprete; no requiere `source .venv/bin/activate`). Para correr los
tests: `uv run pytest`.

Para provisionar la base y el rol en PostgreSQL (ver `kaupamex-db`):

```bash
sudo bash provisioners/postgresql/db_setup.sh          # base kaupamex_core
sudo bash provisioners/postgresql/db_setup.sh --qa     # base kaupamex_core_qa
```

El provisioner crea las bases `kaupamex_core` (desarrollo) y `kaupamex_core_qa`
(tests) con el rol `django_user`, y verifica el mínimo efectivo del motor.

## Endpoints

### Autenticacion — /api/v1/auth/

```
POST   register/                registrar nuevo usuario
POST   login/                   obtener access + refresh token (JWT)
POST   refresh/                 renovar access token
POST   logout/                  invalidar refresh token
GET    profile/                 ver perfil del usuario autenticado
PATCH  profile/                 editar perfil
POST   change-password/         cambiar contrasena
POST   password-reset/          solicitar token de recuperacion
POST   password-reset/confirm/  restablecer contrasena con token
POST   verify-email/            verificar email con token
POST   resend-verification/     reenviar email de verificacion
GET    addresses/               listar direcciones
POST   addresses/               crear direccion
PUT    addresses/{id}/          editar direccion
DELETE addresses/{id}/          eliminar direccion
```

### Administracion de usuarios — /api/v1/admin/

```
GET    users/         listar usuarios (admin)
GET    users/{id}/    ver perfil de usuario (admin)
PATCH  users/{id}/    suspender o reactivar usuario (admin)
POST   users/         crear usuario desde el panel admin
```

### Catalogo — /api/v1/catalogue/

```
GET  /                 listar productos activos (paginado)
GET  search/           buscar productos por texto
GET  {slug}/           detalle de producto
```

### Configuracion — /api/v1/config/

```
GET   settings/   leer configuracion del sitio (SiteSettings)
PATCH settings/   actualizar configuracion (admin)
```

### Documentacion interactiva

```
GET  /api/schema/           schema OpenAPI (JSON)
GET  /api/schema/swagger-ui/ Swagger UI
GET  /api/schema/redoc/      Redoc
```

## Tests

```bash
uv run pytest --reuse-db -q
```

El archivo `pytest.ini` apunta a `config.settings.testing`, que usa la base
`kaupamex_core_qa`. Los tests nunca tocan `kaupamex_core`.

## Estructura

```
src/
  addons/           addons Django (monolito modular — sale, catalogue, account, ...)
  config/
    settings/
      base.py       configuracion base
      development.py
      testing.py
      production.py
    urls.py
kaupamex-bin        punto de entrada del producto (equivalente de odoo-bin)
pyproject.toml      deps canonicas ([project] + grupo dev) — fuente unica
uv.lock             grafo congelado (uv sync lo aplica)
scripts/            checkers de calidad + provisioners/postgresql/
```

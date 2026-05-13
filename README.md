# PracticaYoruba API

Backend eCommerce — Django REST Framework + MariaDB + JWT.

## Prerequisitos

- Python 3.11 o superior
- MariaDB 11.8 corriendo localmente
- `pip` disponible en el PATH

## Setup

```bash
# 1. Crear y activar entorno virtual
python3 -m venv venv
source venv/bin/activate        # Linux / macOS
# source venv/Scripts/activate  # Windows Git Bash

# 2. Instalar dependencias de desarrollo
pip install -r requirements/development.txt

# 3. Configurar variables de entorno
cp practicayoruba/.env.example practicayoruba/.env
# Editar practicayoruba/.env con las credenciales de MariaDB

# 4. Aplicar migraciones y crear superusuario
cd practicayoruba
python manage.py migrate
python manage.py createsuperuser

# 5. Levantar el servidor de desarrollo
python manage.py runserver
```

Para entornos Ubuntu con MariaDB gestionado por el proyecto:

```bash
sudo bash scripts/bootstrap.sh
```

El script crea los schemas `practicayoruba_db` (desarrollo) y
`practicayoruba_qa` (tests), aplica migraciones y verifica el entorno.

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
cd practicayoruba
pytest
```

El archivo `pytest.ini` apunta a `config.settings.testing`, que usa el
schema `practicayoruba_qa`. Los tests nunca tocan `practicayoruba_db`.

## Estructura

```
practicayoruba/
  apps/
    users/          autenticacion, perfiles, direcciones
    catalogue/      productos, categorias, busqueda
    settings_app/   configuracion global del sitio (SiteSettings)
  config/
    settings/
      base.py       configuracion base
      development.py
      testing.py
      production.py
    urls.py
  manage.py
requirements/
  base.txt          Django, DRF, simplejwt, mysqlclient, Pillow
  development.txt   + pytest, pytest-django, factory-boy
scripts/
  bootstrap.sh      setup completo para Ubuntu con MariaDB
```

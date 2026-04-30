# PracticaYoruba API

Backend eCommerce — Django REST Framework + PostgreSQL + JWT.

## Setup rapido

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/development.txt

cp practicayoruba/.env.example practicayoruba/.env
# Editar .env con credenciales de BD

cd practicayoruba
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Endpoints disponibles

```
POST /api/v1/auth/login/    obtener access + refresh token
POST /api/v1/auth/refresh/  renovar access token
POST /api/v1/auth/logout/   invalidar refresh token

GET  /api/schema/swagger/   documentacion interactiva
```

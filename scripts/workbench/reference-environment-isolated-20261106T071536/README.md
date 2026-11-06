# Entorno de referencia aislado de odoo19c

TASK-API-0498 decía que cargar `odoo.orm.models` exigía añadir werkzeug,
lxml_html_clean, psycopg2 y rnc2rng al Consumer. Esa premisa no estaba
demostrada: el `ModuleNotFoundError` describía el intérprete con que se cargó
la referencia, no una necesidad de Kaupamex.

## Separación

| Entorno | Qué contiene | Quién lo declara |
|---|---|---|
| Referencia | venv desechable fuera del repositorio, instalado desde `odoo19c: requirements.txt` | la propia referencia |
| Consumer | `.venv` desde `pyproject.toml` y `uv.lock`, sin cambios | Kaupamex |

El proceso de referencia corre con `-I -B`: no ve `src/`, ni los settings de
Django, ni los parches que el Consumer cuelga sobre Django (el defecto de
medición de H-API-1089). Los diferenciales con modelo comparan trazas
serializadas entre ese subproceso y el puerto.

## Sustituciones declaradas

- `python-ldap` retirado: compila contra `lber.h`, ausente en el contenedor.
  Sólo lo usa `auth_ldap`.
- `psycopg2==2.9.10` → `psycopg2-binary==2.9.10`: mismo código en rueda; la
  compilación exige `libpq-fe.h`.

## Resultado

Ver `outputs/record.json`: referencia exit 0 (59 módulos `odoo`, Django
ausente del proceso), control con el intérprete del Consumer exit 1, y
`odoo-tools` sin cambios.

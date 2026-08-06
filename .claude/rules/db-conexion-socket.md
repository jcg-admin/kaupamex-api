# Conexión a DB — Socket Unix (gate ejecutable)

Actualizado: 2026-08-06 (motor MariaDB → PostgreSQL, ADR-028).

## Hecho del proyecto

La DB se conecta por SOCKET Unix en entornos locales (WSL2, dev, contenedor).

**En libpq el socket ES el host, no una opción aparte.** Un `HOST` que empieza
con `/` designa el *directorio* del socket, y el `PORT` nombra el archivo
dentro de él (`.s.PGSQL.5432`). Por eso los settings resuelven:

```python
_DB_SOCKET = config('DB_SOCKET', default='')
...
'HOST': _DB_SOCKET or config('DB_HOST'),
```

Si `DB_SOCKET`/`DB_QA_SOCKET` está seteada → conexión por socket.
Si no → TCP (`DB_HOST`/`DB_PORT`, típicamente `127.0.0.1:5432`).

> **Cambio respecto a la versión MariaDB de esta regla.** Con `mysqlclient` el
> socket era `OPTIONS['unix_socket']` y el gate leía esa clave. Con psycopg esa
> clave **no existe**: buscarla devuelve siempre `<NONE>` y el gate diría "TCP"
> incluso conectando por socket. El gate de abajo mide el `HOST` real.
> Ver H-API-305.

## Gate (obligatorio antes de migrar o correr tests de integración)

Desde `/home/user/kaupamex-api`, ejecuta y **cita la salida**:

```bash
cd /home/user/kaupamex-api && \
  DJANGO_SETTINGS_MODULE=config.settings.testing uv run python -c \
  "from django.db import connection as c; \
   print('ENGINE:', c.settings_dict['ENGINE']); \
   print('HOST:', c.settings_dict['HOST'], '| PORT:', c.settings_dict['PORT'])"
```

Interpretación:

- `HOST` empieza con `/` (p.ej. `/var/run/postgresql`) → **OK, usa socket**.
- `HOST` es `127.0.0.1` → TCP. En cloud/CI puede ser lo esperado; en local
  revisa `src/.env` y `DB_QA_SOCKET` antes de continuar.
- `ENGINE` distinto de `django.db.backends.postgresql` → bug de configuración.

## Estado conocido de este entorno

Gate ejecutado 2026-08-06 en el contenedor:

```
ENGINE: django.db.backends.postgresql
HOST: /var/run/postgresql | PORT: 5432
server_version: 160013 | can_rollback_ddl: True
```

**Socket activo.** El cluster `16/main` responde
(`pg_isready` → `/var/run/postgresql:5432 - accepting connections`) y la suite
completa corre verde: **2 235 passed, 5 skipped, 0 failed**.

## Los dos fallos que parecen de credenciales y no lo son

1. **`FATAL: Peer authentication failed for user "django_user"`.** El
   `pg_hba.conf` por defecto de Debian asigna `peer` al canal local, así que la
   misma contraseña que funciona por TCP falla por socket. La regla explícita
   para el rol de aplicación debe ir **por encima** de la línea genérica
   (`pg_hba` evalúa de arriba abajo, primera coincidencia gana). La instala
   `db: provisioners/postgresql/db_setup.sh` de forma idempotente. Ver H-DB-05.

2. **`permission denied to create database`.** `CREATEDB` es un **atributo
   global del rol**, sin predicado de nombre — no hay equivalente del
   `GRANT ... company\_%` de MariaDB. El rol de aplicación lo necesita para
   aprovisionar bases por empresa. Ver H-DB-06.

## Arranque del motor

En Debian PostgreSQL se opera **por cluster**, no por proceso suelto:

```bash
pg_isready                       # ¿responde?
pg_lsclusters                    # Ver Cluster Port Status ...
sudo pg_ctlcluster 16 main start # arrancar
```

`initdb`/`pg_ctl`/`postgres` **no** están en `PATH` a propósito. El script
idempotente equivalente a `start_db.sh` está pendiente (T-005 de la iniciativa
`migrar-motor-mariadb-a-postgresql`).

## Regla de diagnóstico

Si una migración o test falla por conexión, corre el gate **primero** y cita la
salida antes de tocar código. Un fallo socket-vs-TCP aparece como error de
código pero es de config. El gate dice con exactitud cuál conexión está activa.

## Referencias

- `src/config/settings/base.py` — resolución socket/TCP + `sslmode`
- `src/config/settings/testing.py` — equivalente `DB_QA_SOCKET`
- `docs: source/backend/adr/adr-028-postgresql.rst` — la decisión de motor
- `db: .claude/skills/db-postgres/SKILL.md` — cómo se opera el motor
  (cluster de Debian, binarios, mínimo efectivo)

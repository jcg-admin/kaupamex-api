# Conexión a DB — Socket Unix (gate ejecutable)

## Hecho del proyecto

La DB se conecta por SOCKET Unix en entornos locales (WSL2, dev).
Documentado en `practicayoruba/config/settings/base.py:77-89`:

```python
_DB_SOCKET = config('DB_SOCKET', default='')
if _DB_SOCKET:
    _DB_OPTIONS['unix_socket'] = _DB_SOCKET
```

Si `DB_SOCKET` está seteada → mysqlclient usa `unix_socket` e **ignora HOST/PORT**.
Si `DB_SOCKET` no está seteada → fallback TCP (`127.0.0.1:3306`).
`testing.py` sigue el mismo patrón con `DB_QA_SOCKET`.

## Gate (obligatorio antes de migrar o correr tests de integración)

Desde `/home/user/e-comerce-api`, ejecuta y **cita la salida**:

```bash
cd /home/user/e-comerce-api && \
  PYTHONPATH=practicayoruba DJANGO_SETTINGS_MODULE=config.settings.testing \
  python -c "from django.db import connection; \
    print('unix_socket:', connection.settings_dict.get('OPTIONS',{}).get('unix_socket','<NONE>'))"
```

Interpretación:
- Imprime una ruta `.sock` → **OK, usa socket**. Procede.
- Imprime `<NONE>` → **TCP fallback activo** (`DB_QA_SOCKET` no seteada).
  - En cloud/CI: comportamiento esperado — MariaDB corre en `127.0.0.1:3306`.
  - En local WSL2: inesperado — revisa `.env` y `DB_QA_SOCKET` antes de continuar.

## Estado conocido de este entorno

**Actualizado 2026-06-02** (el estado de 2026-05-29 quedó obsoleto). Gate
ejecutado hoy en el contenedor:

```
unix_socket: /run/mysqld/mysqld.sock
HOST: 127.0.0.1 PORT: 3306
```

**Socket activo** (`DB_QA_SOCKET` seteada). Tras `bash db/scripts/start_db.sh`,
MariaDB 11.8 levanta por socket y `uv run pytest --reuse-db` corre verde
(26 cart tests, 7.40s). El contenedor SÍ puede correr tests db+api por
socket — ver la regla del superproyecto
`.claude/rules/contenedor-corre-db-api-tests.md`.

> Histórico (2026-05-29): el gate daba `unix_socket: <NONE>` (TCP fallback).
> Ya no aplica. **Gotcha del contenedor:** el `TMPDIR` del entorno
> (`/tmp/claude-0`) no es escribible por `mysql` → InnoDB aborta (Errcode
> 13); `start_db.sh` ya pasa `--tmpdir=/tmp` para evitarlo (db@f8b32ba).

## Regla de diagnóstico

Si una migración o test falla por conexión, corre el gate **primero** y cita la salida
antes de tocar código. Un fallo socket-vs-TCP aparece como error de código pero es de
config. El gate dice con exactitud cuál conexión está activa.

## Referencias

- `practicayoruba/config/settings/base.py:77-89` — lógica socket/TCP
- `practicayoruba/config/settings/testing.py` — `DB_QA_SOCKET` equivalente
- ADR-008 (`adr-008-mariadb-arranque-sin-systemd.rst`) — arranque sin systemd en este entorno

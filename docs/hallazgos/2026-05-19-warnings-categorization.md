# Pytest warnings categorization — 2026-05-19

## Baseline

Comando ejecutado:

```bash
cd practicayoruba && DJANGO_SETTINGS_MODULE=config.settings.testing \
  ../.venv/bin/pytest ../tests/ -W default --tb=no -q
```

Resultado: **45 failed, 271 passed, 384 warnings, 341 errors in 276.33s**.

(El briefing mencionaba 648 warnings; la corrida actual reporta 384,
posiblemente porque otros agentes paralelos modificaron tests/imports que
ahora fallan antes de emitir warnings.)

## Tabla de categorias

| Categoria (Warning class)         | Mensaje (prefijo)                                                                 | Origen                                                       | Conteo |
|-----------------------------------|------------------------------------------------------------------------------------|--------------------------------------------------------------|--------|
| `jwt.warnings.InsecureKeyLengthWarning` | "The HMAC key is 27 bytes long, which is below the minimum recommended length of 32 bytes for SHA256." | `.venv/.../jwt/api_jwt.py:147` (encode) y `:365` (decode) | 384    |

Solo existe **una clase de warning** en todo el log. Ambos call-sites
(encode/decode) provienen de `PyJWT` invocado por `rest_framework_simplejwt`
con la `SIGNING_KEY` por defecto del proyecto (`SECRET_KEY` ==
`django-insecure-CHANGE-ME`, 27 bytes < 32 bytes).

No se observaron:

- `DeprecationWarning` (Django 5 / DRF / pytest).
- `RemovedInDjango60Warning`.
- `PytestUnknownMarkWarning` (los markers `unit`, `integration`, `api` ya
  estan declarados en `pytest.ini`).
- `UserWarning` sobre timezone-naive datetime.
- Warnings de `drf-spectacular`.

## Fix aplicado

`practicayoruba/config/settings/testing.py`: se define
`SIMPLE_JWT['SIGNING_KEY']` con una cadena de >= 32 bytes exclusiva para
tests. Esto evita que PyJWT use `SECRET_KEY` (27 bytes) como clave HMAC-SHA256.

```python
SIMPLE_JWT = {
    **SIMPLE_JWT,
    'SIGNING_KEY': 'testing-signing-key-please-do-not-use-in-production-0123456789',
}
```

Cambio reversible (settings de testing unicamente, no afecta produccion).

## Resultado esperado

`InsecureKeyLengthWarning` debe desaparecer en su totalidad (384 -> 0).
Los warnings totales deben caer a ~0. Errores/fallos de tests son
responsabilidad de otros agentes / iteraciones (estan fuera del scope de
"warning hygiene").

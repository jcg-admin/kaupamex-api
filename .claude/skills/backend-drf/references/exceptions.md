```yml
type: Reference (lazy-load on-demand)
applies_when: Se lanza/maneja un error de API (validación, permiso, 404, condición de negocio) o se razona sobre el cuerpo de una respuesta de error
created_at: 2026-07-18 03:25:29
status: Aprobado
version: 1.0.0
source: DRF api-guide/exceptions
```

# DRF Exceptions — `codigo_error` canónico + handler central (ADR-019)

> DRF captura `APIException`/`Http404`/`PermissionDenied` y devuelve una
> respuesta con status y cuerpo apropiados. El proyecto **conserva ese cuerpo**
> (con la clave canónica `codigo_error`) y añade un `EXCEPTION_HANDLER` central
> que **no cambia la respuesta** — solo **sella el error en el log**.

## El contrato de error — clave `codigo_error` (no solo `detail`)

DRF pone `detail` en el cuerpo del error. El proyecto lo **extiende** con la
clave canónica **`codigo_error`** (string en INGLÉS, canon-idioma) — **390** usos
en `src/addons` (PROVEN 2026-07-18). Un cliente/SPA ramifica por `codigo_error`,
no por el texto de `detail`. Dos vías la producen:

1. **`ValidationError` en serializers/vistas** — **182** `raise ...ValidationError`
   en `src/addons` (PROVEN 2026-07-18). El dict lleva el campo + `codigo_error`
   (ver `validators.md`/`serializers.md`)::

       raise ValidationError({'ordering': ..., 'codigo_error': 'INVALID_ORDERING'})

2. **`APIException` codificadas** — **13** subclases (PROVEN 2026-07-18:
   `authz/exceptions.py` + `finance/exceptions.py`). Cada una fija
   `status_code`/`default_code` en la clase y mete `codigo_error` en el `detail`::

       class DuplicateCode(APIException):
           status_code = 409
           default_code = 'duplicate_code'
           def __init__(self, code):
               super().__init__(detail={
                   'detail': f'Ya existe un concepto con el codigo "{code}".',
                   'codigo_error': 'DUPLICATE_CODE',
               })

   `ReauthRequired` (DEC-12) es el ejemplo insignia: un `403` **machine-readable**
   con `codigo_error='REAUTH_REQUIRED'` + `reauth_url` + `window_seconds`, para que
   el SPA abra el modal de re-password y reintente (ver `authentication.md`).

**Patrón para una condición de negocio codificada:** subclasear `APIException` con
`status_code`/`default_code` y `codigo_error` en el `detail` (módulo
`<app>/exceptions.py`) — **no** un `Response(status=..., data=...)` a mano en la
vista (ese se saltea el handler y es más fácil de desincronizar).

## El `EXCEPTION_HANDLER` central — sella el log, NO cambia el cuerpo

`EXCEPTION_HANDLER = 'core.exception_handling.custom_exception_handler'`
(`config/settings/base.py:273`). A diferencia del ejemplo de la doc de DRF (que
**muta** `response.data`), el del proyecto **preserva** el cuerpo del handler por
defecto y solo añade telemetría (PROVEN 2026-07-18, `core/exception_handling.py`)::

    def custom_exception_handler(exc, context):
        response = drf_exception_handler(exc, context)   # cuerpo intacto (codigo_error)
        try:
            set_request_error(type(exc).__name__, scrub(str(exc)))
        except Exception:
            pass                                          # DEC-LOG-04: no bloqueante
        return response

- **No altera la respuesta al cliente:** delega en el handler de DRF; el
  `codigo_error` y el `detail` salen tal cual. Cambiar el estilo de error se hace
  aquí, pero hoy **no** se hace — el contrato es el de DRF + `codigo_error`.
- **Sella el error en el contexto** (`exception_class`, `error_detail` **scrubbed**,
  DEC-LOG-03) para que `RequestLogMiddleware` lo persista en `RequestLog`, unido al
  trace de `AppLog` por `correlation_id` (ADR-019, SOL-011 T-04, DEC-LOG-07).
- **No bloqueante (DEC-LOG-04):** el sellado va en `try/except` que traga el error;
  si el logging falla, la respuesta de error **no** se altera. (Ojo: este es el
  único `except: pass` sancionado — el checker `check_silent_oks.py` lo tolera por
  el comentario `silent OK because DEC-LOG-04`.)

## Lo que el handler NO cubre — respuestas directas de la vista

El `EXCEPTION_HANDLER` **solo** corre para respuestas generadas por **excepciones
lanzadas**. Un `Response(status=400, data=...)` que la vista devuelve **directo**
(p. ej. la validación manual del export, ver `content-negotiation.md`) **no** pasa
por él → conviene igual meter `codigo_error` a mano en ese `data` para no romper el
contrato. Preferir `raise ValidationError`/`APIException` a `Response(status=...)`
cuando se quiera el sellado + el estilo central.

## Qué NO se usa

- **`drf-standardized-errors`** (3rd-party): 0 (PROVEN 2026-07-18). El contrato de
  error propio (`codigo_error`) ya cumple ese rol; no añadir el paquete.
- **`handler500`/`handler400`** (`server_error`/`bad_request` de DRF): 0 en
  `config/` (PROVEN 2026-07-18). Las excepciones **manejadas** ya renderizan JSON
  via el handler; un 500 **no manejado** cae al handler de Django. Si algún día se
  requiere JSON garantizado también en el 500 no manejado, cablear
  `handler500 = 'rest_framework.exceptions.server_error'` en el URLconf raíz — hoy
  no está.
- Mutar `response.data` en el handler (añadir `status_code` al cuerpo, etc.): no se
  hace; el cuerpo es el de DRF + `codigo_error`.

## Checklist al manejar un error

1. ¿Validación de campo/objeto? → `raise ValidationError({'<campo>': ...,
   'codigo_error': '<CODE>'})` (código en INGLÉS).
2. ¿Condición de negocio codificada (409/422/403 con significado)? → subclase de
   `APIException` en `<app>/exceptions.py` con `status_code`/`default_code` +
   `codigo_error` en el `detail`. No `Response(status=...)` a mano.
3. ¿403 que el SPA debe accionar (reauth)? → patrón `ReauthRequired`
   (`codigo_error` + datos para el reintento).
4. **No** mutar el cuerpo en el `EXCEPTION_HANDLER` ni añadir
   `drf-standardized-errors`; el contrato es DRF + `codigo_error`.
5. ¿Respuesta directa (no excepción)? → meter `codigo_error` a mano (no pasa por el
   handler).

## Referencias cruzadas

- `validators.md` / `serializers.md` — `ValidationError` con `codigo_error` (las
  182 fuentes de validación).
- `authentication.md` — 401 vs 403; `ReauthRequired` (DEC-12) como 403 codificado.
- `permissions.md` — `HasCapability` lanza las denegaciones (403) que el handler
  sella.
- `content-negotiation.md` — el export usa `Response(status=...)` directo (no pasa
  por el handler; mete `codigo_error` a mano).
- Código: `config/settings/base.py:273` (`EXCEPTION_HANDLER`),
  `core/exception_handling.py` (handler central), `addons/finance/exceptions.py` +
  `addons/authz/exceptions.py` (13 `APIException` codificadas).
```

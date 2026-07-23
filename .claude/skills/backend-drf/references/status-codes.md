```yml
type: Reference (lazy-load on-demand)
applies_when: Se devuelve un status HTTP en una Response o se define status_code en una APIException
created_at: 2026-07-18 03:27:20
status: Aprobado
version: 1.0.0
source: DRF api-guide/status-codes
```

# DRF Status codes — el proyecto usa números pelados (drift vs `status.HTTP_*`)

> DRF **desaconseja** los códigos numéricos pelados en `Response` y ofrece
> `status.HTTP_400_BAD_REQUEST`, etc. El estado **real** del proyecto es el
> inverso: el número pelado (`status=400`) domina sobre la constante. Esta
> referencia documenta el estado real y la recomendación, sin fingir cumplimiento.

## Estado real — número pelado > constante nombrada

PROVEN 2026-07-18 en `src/addons` (sin tests — no hay tests bajo `src/addons`):

| Forma | Usos | Doc DRF |
|---|---|---|
| `status=NNN` pelado en `Response(...)` | **255** | desaconsejado |
| `status.HTTP_NNN_*` (constante) | **89** | recomendado |
| `status.is_success()`/`is_client_error()`/… helpers | **0** | — |

Es decir: ~**74%** de los status en respuestas van como número pelado
(255/(255+89), PROVEN). El más frecuente es `status=400` (108), luego `404` (36),
`201` (25), `200` (21), `409` (17). Los archivos más densos: `backups/views.py`,
`voucher/views.py`, `users/tokens.py`, `users/session_views.py`.

**Consecuencia práctica:** el código es funcionalmente correcto (`400` == 
`status.HTTP_400_BAD_REQUEST`), pero **menos legible/greppeable** que si usara la
constante — justo lo que la doc de DRF advierte. Es **deuda de consistencia de
severidad BAJA**, no un bug.

## La recomendación (para código nuevo)

Para **código nuevo**, preferir la constante nombrada — es la convención que DRF
recomienda y hace el status auto-explicativo::

    from rest_framework import status
    from rest_framework.response import Response

    return Response({'detail': ..., 'codigo_error': 'X'},
                    status=status.HTTP_400_BAD_REQUEST)

No es obligatorio "migrar los 255 en masa" (churn sin ganancia funcional); sí
**no aumentar** la deuda: lo nuevo usa `status.HTTP_*`. Si se toca un archivo de
los densos por otra razón, alinear de paso los status de ese archivo es un
oportunismo válido (no una tarea aparte).

## `status_code` en `APIException` — el número SÍ es idiomático

Las **13** `APIException` codificadas (ver `exceptions.md`) fijan
`status_code = 409` / `422` / `403` como **atributo de clase** — PROVEN 2026-07-18.
Ahí el número pelado es el **idioma de DRF** (la propia doc lo escribe así:
`status_code = 503`), no el anti-patrón: no es un `Response(status=...)`, es la
definición de la excepción. **No** cambiar esos a `status.HTTP_*` — el patrón de
la clase es correcto tal cual.

## Catálogo de códigos en uso — el set real del proyecto

Estos son **todos** los status que aparecen en `src/addons` (unión de
`status=NNN` pelado + `status.HTTP_*` + `status_code` de clase), con su conteo
PROVEN 2026-07-18 y su significado en el contrato del proyecto. **No** se usa
ningún otro código del catálogo de DRF fuera de esta lista:

La columna **Constante destino** es el **nombre canónico** al que debe migrar
cada número pelado (`from rest_framework import status`). Al cambiar
`status=NNN` → constante, usar **exactamente** ese nombre — no inventar
variantes:

| Código | Usos | Constante destino (`status.…`) | Significado en el proyecto |
|---|---|---|---|
| **200** OK | 27 | `HTTP_200_OK` | Éxito con cuerpo (GET, y acciones que devuelven estado). |
| **201** Created | 38 | `HTTP_201_CREATED` | Recurso creado (`CreateAPIView`/`create()`; ver `generic-views.md`). |
| **202** Accepted | 2 | `HTTP_202_ACCEPTED` | Job **asíncrono** aceptado (backup `backups/views.py:178`, export `reports/views.py:374`) — el trabajo corre después, la respuesta no lo espera. |
| **204** No Content | 12 | `HTTP_204_NO_CONTENT` | Éxito **sin cuerpo**: borrado (`destroy()`) y logout/`session_views.py:107`. |
| **400** Bad Request | 133 | `HTTP_400_BAD_REQUEST` | Validación fallida / petición malformada — el grueso (`ValidationError` con `codigo_error`; ver `exceptions.md`). |
| **401** Unauthorized | 4 | `HTTP_401_UNAUTHORIZED` | **Sin sesión** — no autenticado (ver `authentication.md`). |
| **403** Forbidden | 9 | `HTTP_403_FORBIDDEN` | Sesión válida **sin capacidad** (`HasCapability`) o **reauth** requerida (`ReauthRequired`, `codigo_error=REAUTH_REQUIRED`; ver `permissions.md`). |
| **404** Not Found | 46 | `HTTP_404_NOT_FOUND` | No existe **o** objeto ajeno — el row-scoping de `get_queryset()` da 404, no 403, para no filtrar existencia (ver `filtering.md`/`generic-views.md`). |
| **409** Conflict | 48 | `HTTP_409_CONFLICT` | Conflicto de estado: código duplicado (`DUPLICATE_CODE`), recurso ya en el estado pedido (voucher ya activo), etc. |
| **410** Gone | 1 | `HTTP_410_GONE` | Recurso **eliminado** deliberadamente: tarjeta borrada (`CARD_DELETED`, `payments/views.py:1654`) — distinto de 404 (nunca existió). |
| **422** Unprocessable | 13 | `HTTP_422_UNPROCESSABLE_ENTITY` | Semántica de negocio inválida: campo inmutable (`IMMUTABLE_FIELD`), reglas de negocio (`finance/exceptions.py`). |
| **429** Too Many Requests | 3 | `HTTP_429_TOO_MANY_REQUESTS` | Throttle superado (`Throttled`; ver `throttling.md`). |
| **500** Internal Server Error | 4 | `HTTP_500_INTERNAL_SERVER_ERROR` | Error interno **explícito** que la vista decide devolver (no el 500 no manejado de Django). |
| **502** Bad Gateway | 8 | `HTTP_502_BAD_GATEWAY` | Un **proveedor externo** respondió mal/inesperado: webhook MP (`payments/webhooks.py:507`), guía de retorno (`returns/views.py:653`). |
| **503** Service Unavailable | 10 | `HTTP_503_SERVICE_UNAVAILABLE` | **Error de red** hacia un proveedor externo (MP/paqueterías) — indisponibilidad temporal (`orders/views.py:484`, `settings_app/views.py:229`). |

Ejemplo de la migración (número pelado → constante destino), preservando el
`codigo_error`::

    # Antes
    return Response({'detail': ..., 'codigo_error': 'CARD_DELETED'}, status=410)
    # Después
    return Response({'detail': ..., 'codigo_error': 'CARD_DELETED'},
                    status=status.HTTP_410_GONE)

**Distinción 502 vs 503 (contrato del proyecto):** **503** = no se pudo
**alcanzar** al proveedor (red caída, timeout de conexión) → reintentable pronto;
**502** = el proveedor **respondió** pero con algo inválido/inesperado → no
necesariamente reintentable. Mantener esa separación al integrar un proveedor
nuevo. **410 vs 404:** 410 = existió y fue eliminado a propósito (tarjeta); 404 =
no existe o no es tuyo. **409 vs 422:** 409 = conflicto con el **estado actual**
(duplicado, ya-activo); 422 = la entidad es sintácticamente válida pero **viola
una regla** (inmutabilidad, SoD).

**Nota de calibración:** los conteos son la unión de las tres formas
(`status=NNN` + `status.HTTP_*` + `status_code` de clase) en `src/addons`
(PROVEN 2026-07-18); difieren de la tabla "estado real" de arriba (que separa
pelado vs constante). Un mismo endpoint puede devolver varios de estos.

## Helpers `is_success()` / `is_client_error()` — no se usan

PROVEN 2026-07-18: **0** usos de `status.is_success`/`is_client_error`/
`is_server_error`/`is_redirect`/`is_informational`. Los tests comparan el status
exacto (`== 400`), no la categoría — coherente con contratos de status precisos.
No hace falta introducirlos.

## Checklist

1. **Código nuevo** → `status.HTTP_NNN_*` (constante), no el número pelado.
2. El **código** correcto sale del contrato: 401/403 (auth vs capacidad), 404
   (objeto ajeno), 409/422 (negocio codificado), 429 (throttle), 201/204.
3. `APIException` → `status_code = NNN` como atributo de clase (idioma DRF, no
   cambiar).
4. No migrar los 255 pelados en masa (churn); sí alinear de paso al tocar un
   archivo por otra razón.
5. No introducir los helpers `is_*` — los contratos comparan el status exacto.

## Referencias cruzadas

- `exceptions.md` — `codigo_error` + `APIException` (`status_code` de clase); el
  status acompaña siempre al `codigo_error`.
- `authentication.md` / `permissions.md` — 401 vs 403 (auth vs capacidad; reauth).
- `filtering.md` / `generic-views.md` — 404 por row-scoping (no 403).
- `throttling.md` — 429 (`Throttled`).
- Código: `addons/backups/views.py`, `addons/voucher/views.py`,
  `addons/users/session_views.py` (densos en `status=NNN` pelado);
  `addons/finance/exceptions.py` (`status_code` de clase).
```

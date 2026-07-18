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

## Códigos con significado en este proyecto

El catálogo de status no es libre; se alinea con contratos ya establecidos (ver
las referencias cruzadas):

- **401 vs 403** — 401 = sin sesión; 403 = sesión válida sin capacidad
  (`HasCapability`) o reauth requerida (`ReauthRequired`). Ver `authentication.md`/
  `permissions.md`.
- **404 en vez de 403** para objeto ajeno — el row-scoping de `get_queryset()`
  hace que un id fuera de alcance dé 404, no 403 (no filtrar existencia). Ver
  `filtering.md`/`generic-views.md`.
- **409/422** — condiciones de negocio codificadas (`DUPLICATE_CODE` 409,
  `IMMUTABLE_FIELD` 422) via `APIException` con `codigo_error`. Ver `exceptions.md`.
- **429** — throttling (`Throttled`). Ver `throttling.md`.
- **201/204** — creación / borrado sin cuerpo (`generic-views.md`).

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

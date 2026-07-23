```yml
type: Reference (lazy-load on-demand)
applies_when: Se limita la tasa de un endpoint (anti-brute-force / anti-enumeración / anti-spam) con throttle_scope o throttle_classes
created_at: 2026-07-18 03:09:47
status: Aprobado
version: 1.0.0
source: DRF api-guide/throttling
```

# DRF Throttling — límite de tasa por endpoint

> El throttle controla la **tasa** de peticiones (estado temporal), no la
> autorización. **No es una medida de seguridad dura** (la IP se puede
> falsificar; usa operaciones no atómicas de la caché) — es política de negocio +
> protección básica contra sobreuso, brute-force y enumeración.

## Default global — anon + user; desactivado en tests

`DEFAULT_THROTTLE_CLASSES` = `AnonRateThrottle` + `UserRateThrottle` (PROVEN
2026-07-18, `config/settings/base.py:278-281`), con
`DEFAULT_THROTTLE_RATES['anon'] = '100/hour'` y `['user'] = '1000/hour'`. En
tests se **desactiva**: `testing.py:76` → `DEFAULT_THROTTLE_CLASSES = []` (los
tests no deben chocar con el rate limit). El throttle usa la **caché de Django**
(`DatabaseCache`; ver `caching.md`).

## Patrón del proyecto — throttle por scope: **tres piezas que deben alinear**

El proyecto limita endpoints sensibles con `ScopedRateThrottle`. Un scope
funciona **sólo** si las **tres** piezas están presentes:

1. `throttle_classes = [ScopedRateThrottle]` en la vista (**quien lee el scope**).
2. `throttle_scope = '<scope>'` en la vista.
3. `DEFAULT_THROTTLE_RATES['<scope>'] = 'N/hour'` en settings.

PROVEN 2026-07-18: **32** referencias a `ScopedRateThrottle`, **22** overrides de
`throttle_classes`, y ~24 `throttle_scope` cableados. Scopes vigentes (con su
justificación de seguridad documentada en settings, muchos atados a un hallazgo
H-CICLO*): `register 5/h`, `password_reset 5/h`, `password_confirm 10/h`,
`email_verify 10/h`, `resend_verification 3/h`, `contact 5/h`, `addresses 30/h`,
`change_password 5/h`, `voucher_apply 20/h`, `newsletter_subscribe/confirm/
unsubscribe`, `question_ask 10/h`, `review_create 10/h`, `checkout`,
`initiate_payment`, `cart`, …

## Gotcha crítico — `throttle_scope` SIN `throttle_classes` es un no-op silencioso

**`throttle_scope` por sí solo no hace nada.** Es `ScopedRateThrottle` quien lee
el scope; si no está en `throttle_classes`, DRF **ignora el scope en silencio** y
el endpoint queda sin su límite. PROVEN — el comentario de
`contact/views.py:66` (H-CICLO26-01)::

    # H-CICLO26-01: throttle_scope sin throttle_classes es silenciosamente
    # ignorado por DRF — ScopedRateThrottle es quien lee el scope y aplica
    # el rate configurado en DEFAULT_THROTTLE_RATES['contact'] = '5/hour'.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'contact'

**Regla:** al proteger un endpoint, verificar las **tres** piezas. Un
`throttle_scope` huérfano da falsa sensación de protección.

**Corolario:** poner `throttle_classes = [ScopedRateThrottle]` **overridea** el
default global — la vista scoped ya **no** recibe `Anon`/`UserRateThrottle`. Está
bien porque el scope cubre el POST sensible; pero si un método secundario (p. ej.
un GET) debe conservar el límite anon, tenerlo en cuenta (`questions/views.py:64`
lo documenta: el GET sin scope hereda el `AnonRateThrottle` global sólo si la
vista **no** overridea `throttle_classes`).

## Rate — formato y múltiples throttles

- Formato `N/<periodo>`: `s`/`m`/`h`/`d` (sólo cuenta el primer carácter;
  `5/hour` = `5/h`).
- **Ráfaga + sostenido**: para dos límites por usuario se subclasea
  `UserRateThrottle` con `scope` distinto (`burst`/`sustained`) y se listan ambos.
  Hoy el proyecto usa un scope por endpoint, no burst+sustained global.

## FBV — `throttle_scope` no existe; subclasear `UserRateThrottle`

`ScopedRateThrottle` lee `view.throttle_scope`, un **atributo de clase** que la
FBV no tiene. Para limitar un endpoint FBV se subclasea `UserRateThrottle` con
`scope` fijo (la tasa sale de `DEFAULT_THROTTLE_RATES[scope]`) y se aplica con
`@throttle_classes([...])`. Es la receta de `views.md` (throttle en FBV) — la que
necesita la migración a FBV de self-account.

## `@action` — su `throttle_classes` overridea el del ViewSet

Un `@action(detail=True, throttle_classes=[...])` fija el throttle de esa acción,
por encima del nivel-ViewSet (ver `viewsets.md`).

## Custom throttle — no se usa

Un throttle a medida subclasea `BaseThrottle` + `allow_request(self, request,
view)` (+ `wait()` opcional → header `Retry-After`). PROVEN 2026-07-18: **0**
subclases de `BaseThrottle`/`RateThrottle` propias; **`NUM_PROXIES` no está
seteado** (identificación de IP por `X-Forwarded-For`/`REMOTE_ADDR` default). No
introducir un throttle a medida sin una necesidad que `Scoped`/`User`/`Anon` no
cubra.

## Checklist al limitar un endpoint

1. ¿CBV/APIView? → las **tres** piezas: `throttle_classes = [ScopedRateThrottle]`
   + `throttle_scope = '<scope>'` + `DEFAULT_THROTTLE_RATES['<scope>']`.
2. Verificar que el scope **no** quedó huérfano (sin `ScopedRateThrottle` no
   aplica — H-CICLO26-01).
3. ¿FBV? → subclase de `UserRateThrottle` con `scope=` + `@throttle_classes`
   (ver `views.md`).
4. Documentar el rate con su razón (anti-brute-force / anti-enumeración /
   anti-spam), como en `DEFAULT_THROTTLE_RATES`.
5. No confiar en el throttle como defensa dura (IP falsificable); es política de
   sobreuso.

## Referencias cruzadas

- `views.md` — receta de **throttle en FBV** (`UserRateThrottle` + `scope=`).
- `viewsets.md` — `@action(throttle_classes=...)` overridea el nivel-ViewSet.
- `caching.md` — el throttle se apoya en la caché de Django (`DatabaseCache`).
- `permissions.md` — throttle vs permiso: ambos corren antes del cuerpo; el
  throttle es estado temporal.
- Código: `config/settings/base.py:278-296+` (`DEFAULT_THROTTLE_RATES` con
  justificaciones), `addons/contact/views.py:66` (gotcha H-CICLO26-01),
  `addons/users/views.py` (scopes de auth).
```

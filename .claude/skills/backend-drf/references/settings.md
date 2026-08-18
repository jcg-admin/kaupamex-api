```yml
type: Reference (lazy-load on-demand)
applies_when: Se toca el bloque REST_FRAMEWORK, se razona sobre un default global de DRF, o se busca qué política aplica sin override por-vista
created_at: 2026-07-18 03:38:44
status: Aprobado
version: 1.0.0
source: DRF api-guide/settings
```

# DRF Settings — el bloque `REST_FRAMEWORK` del proyecto (mapa maestro)

> Toda la config de DRF vive en un solo dict `REST_FRAMEWORK` en
> `config/settings/base.py`. Esta referencia es el **índice** de esa config:
> qué está fijado explícitamente (con su ADR y su referencia dedicada) y qué
> rige por **default de DRF**. Es la vista de pájaro de las otras 28 referencias.

## Lo que el proyecto FIJA (base.py, PROVEN 2026-07-18)

| Key | Valor | Por qué / referencia |
|---|---|---|
| `DEFAULT_AUTHENTICATION_CLASSES` | `[CsrfExemptSessionAuthentication]` | Auth de **sesión** HttpOnly, CSRF-exenta (SameSite=Lax + `__Host-`); JWT instalado pero **dormant** (ADR-018). Ver `authentication.md`. |
| `DEFAULT_PERMISSION_CLASSES` | `[IsAuthenticated]` | **Piso** global (fail-closed a autenticado). **No** es la última palabra: cada vista **añade `HasCapability`** (DEC-11) y las públicas hacen opt-out explícito a `AllowAny`. Ver `permissions.md`. |
| `DEFAULT_RENDERER_CLASSES` | `[JSONRenderer]` | JSON-only en prod (browsable apagado). Ver `renderers.md`. |
| `DEFAULT_SCHEMA_CLASS` | `drf_spectacular.openapi.AutoSchema` | Contrato OpenAPI por **drf-spectacular**, no el schema nativo. Ver `schema.md`. |
| `EXCEPTION_HANDLER` | `core.exception_handling.custom_exception_handler` | Sella el error en `RequestLog` **sin cambiar el cuerpo** (preserva `codigo_error`); ADR-019, no bloqueante DEC-LOG-04. Ver `exceptions.md`. |
| `DEFAULT_THROTTLE_CLASSES` | `[AnonRateThrottle, UserRateThrottle]` | Defense-in-depth (DEC-THR-1); **desactivado en tests**. Ver `throttling.md`. |
| `DEFAULT_THROTTLE_RATES` | dict de ~20 scopes | `anon`/`user` + scopes por endpoint sensible (`register`, `voucher_apply`, `checkout`, `payment_return`, …), cada uno con su hallazgo H-CICLO*. Ver `throttling.md`. |

**El `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]` es un matiz que engaña:**
el default global es sólo el piso. La autorización real la da `HasCapability`
**por vista** (fail-closed: sin capacidad → 403). Nunca leer "el default es
IsAuthenticated" como "basta estar autenticado" — ver la invariante de seguridad
en `permissions.md` y el `CLAUDE.md` de `api`.

## Overrides por entorno (PROVEN 2026-07-18)

DRF se configura una vez en `base.py` y los entornos **mutan** el dict:

- **`development.py`** — `REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [...]`
  re-añade el **browsable** renderer (sólo dev). Ver `renderers.md`.
- **`testing.py`** — `REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []` **apaga**
  el throttle en tests (por eso la fixture autouse `clear_rate_limit_cache`
  complementa; ver `testing.md`/`throttling.md`).

No hay más overrides de `REST_FRAMEWORK` en otros settings (PROVEN).

## Lo que rige por DEFAULT de DRF (no se fija — decisión implícita)

Cada uno tiene su referencia dedicada donde se explica **por qué** el default
basta:

| Key (no fijada) | Default de DRF | Consecuencia / referencia |
|---|---|---|
| `DEFAULT_PARSER_CLASSES` | JSON + Form + MultiPart | Entrada estándar; 1 override por-vista. Ver `parsers.md`. |
| `DEFAULT_CONTENT_NEGOTIATION_CLASS` | `DefaultContentNegotiation` | Trivial (JSON-only); 1 passthrough en export. Ver `content-negotiation.md`. |
| `DEFAULT_PAGINATION_CLASS` / `PAGE_SIZE` | `None` / `None` | **Sin** paginación global; se pagina por-vista. Ver `pagination.md`. |
| `DEFAULT_FILTER_BACKENDS` | (vacío) | Filtrado manual en `get_queryset()`; no django-filter. Ver `filtering.md`. |
| `DEFAULT_VERSIONING_CLASS` / `ALLOWED_VERSIONS` | `None` | Versionado por prefijo de URL (`v1`/`v2`), no por DRF. Ver `versioning.md`. |
| `DEFAULT_METADATA_CLASS` | `SimpleMetadata` | `OPTIONS` no se usa; contrato por `/api/schema/`. Ver `metadata.md`. |
| `URL_FORMAT_OVERRIDE` | `'format'` | `?format=` habilitado por default → colisión que el export neutraliza. Ver `format-suffixes.md`. |
| `TEST_REQUEST_DEFAULT_FORMAT` | `'multipart'` | Por eso los tests pasan `format='json'` explícito. Ver `testing.md`. |
| `COERCE_DECIMAL_TO_STRING` | `True` | `DecimalField` (dinero) serializa como **string** (sin pérdida de precisión). Ver `serializer-fields.md`. |
| `DATETIME_FORMAT` / `DATE_FORMAT` | `'iso-8601'` | Fechas en ISO-8601 (coincide con la convención del proyecto). |
| `NON_FIELD_ERRORS_KEY` | `'non_field_errors'` | Errores sin campo; el contrato propio añade `codigo_error` encima. Ver `exceptions.md`. |
| `UNICODE_JSON` / `COMPACT_JSON` / `STRICT_JSON` | `True` | JSON unicode, minificado, estricto (sin `nan`/`inf`). |

## Cómo se leen las settings — atributos de política, no `api_settings`

El proyecto **no** lee el `api_settings` de DRF directamente (PROVEN 2026-07-18:
el único `api_settings` importado es el de **SimpleJWT** en `users/tokens.py`).
La config se consume vía los **policy attributes** de cada vista
(`permission_classes`, `throttle_scope`, `renderer_classes`, …) que overridean el
default por-vista — el patrón de todas las referencias de este skill. Si se
necesita leer un default en código, `from rest_framework.settings import
api_settings` resuelve el string-import a la clase; pero es raro y casi siempre
innecesario.

## Reglas al tocar `REST_FRAMEWORK`

1. **Un cambio de política global** va en el dict de `base.py`, con **comentario
   citando el ADR/hallazgo** que lo motiva (patrón de todo el bloque: cada key
   tiene su ADR-018/019, DEC-THR-1, H-CICLO*).
2. **Diferencia por entorno** → mutar el dict en `development.py`/`testing.py`
   (como el browsable de dev y el throttle-off de tests), no duplicar el bloque.
3. **No** re-habilitar JWT en `DEFAULT_AUTHENTICATION_CLASSES` sin una decisión de
   producto (app móvil) — hoy es dormant a propósito (ADR-018).
4. **No** relajar `DEFAULT_PERMISSION_CLASSES` ni asumir que basta: la autorización
   es `HasCapability` por vista (DEC-11).
5. Un scope de throttle nuevo se declara en `DEFAULT_THROTTLE_RATES` **y** se ancla
   con `throttle_scope` + `ScopedRateThrottle` en la vista (tres piezas; ver
   `throttling.md`).

## Referencias cruzadas

Este archivo es el índice; cada key remite a su referencia:
`authentication.md` · `permissions.md` · `renderers.md` · `parsers.md` ·
`content-negotiation.md` · `pagination.md` · `filtering.md` · `versioning.md` ·
`metadata.md` · `schema.md` · `exceptions.md` · `status-codes.md` ·
`throttling.md` · `format-suffixes.md` · `serializer-fields.md` · `testing.md`.

- Código: `config/settings/base.py` (bloque `REST_FRAMEWORK`),
  `config/settings/development.py:8` (browsable), `config/settings/testing.py:76`
  (throttle off).
```

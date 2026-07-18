```yml
type: Reference (lazy-load on-demand)
applies_when: Se monta un endpoint nuevo (elegir prefijo/namespace de URL) o se razona sobre v1 vs v2 del API
created_at: 2026-07-18 03:14:57
status: Aprobado
version: 1.0.0
source: DRF api-guide/versioning
```

# DRF Versioning — v1/v2 por prefijo de URL, no por DRF

> DRF ofrece varios esquemas de versionado (URL, header, query). El proyecto
> **no** habilita el versionado de DRF: versiona por **prefijo de URL + namespace
> de Django**, y `request.version` es siempre `None`.

## El versionado de DRF está DESACTIVADO

PROVEN 2026-07-18: **0** `DEFAULT_VERSIONING_CLASS` / `ALLOWED_VERSIONS` /
`DEFAULT_VERSION` / `VERSION_PARAM` en settings, y **0** `versioning_class` /
`request.version` en `src/addons`. Por lo tanto:

- `request.version` **siempre es `None`** — la maquinaria de DRF (esquema,
  `reverse()` version-aware, `ALLOWED_VERSIONS`) no aplica.
- **No** se varía comportamiento por versión: `get_serializer_class()` ramifica
  por lectura/escritura o por rol (ver `serializers.md`/`viewsets.md`), **no** por
  `request.version`.

## Cómo versiona el proyecto — prefijo de URL + namespace de Django

El versionado es una **convención de URLconf** (`config/urls.py`), no un esquema
DRF. Dos superficies:

- **`api/v1/`** — **sólo webhooks externos**: `api/v1/payments/` y
  `api/v1/logistics/` (PROVEN 2026-07-18, `config/urls.py:42-43`). Son el
  contrato **estable** con proveedores externos (Mercado Pago, paqueterías) que
  no controlamos — no se rompe.
- **`api/v2/`** — **el API de la aplicación** (comprador + admin): catalogue,
  cart, wishlist, orders, returns, reviews, questions, support, inventory,
  newsletter, contact, notifications, referral, y los `admin/*`. Es la superficie
  viva del producto.

Cada include de `v2` lleva un **namespace de Django** con sufijo `_v2`
(`catalogue_v2`, `cart_v2`, `admin_core_v2`, …). El namespace **no** es
versionado DRF: sirve para **desambiguar `reverse()`** cuando varias apps montan
bajo el mismo prefijo (p. ej. muchas bajo `api/v2/admin/`). `reverse()` se resuelve
con `namespace:name` (`cart_v2:cart-list`), no con la versión.

## Consecuencias operativas

1. **Endpoint nuevo del producto** → montar bajo `api/v2/<dominio>/` con su
   namespace `<app>_v2` en `config/urls.py`. No inventar un `v3` ni un esquema de
   header/query.
2. **Cambio incompatible** → no se resuelve con `request.version` (está off). Si
   algún día se necesita romper el contrato, sería un **prefijo de URL nuevo**
   (`api/v3/...`) con su namespace — decisión de producto, no un branch por
   versión dentro de la vista.
3. **Webhook** → queda en `api/v1/` (contrato externo estable). No migrar
   webhooks a v2 sin coordinar con el proveedor.
4. `reverse()` de un endpoint versionado → usar el namespace:
   `reverse('cart_v2:cart-list')`.

## Qué NO se usa

- `NamespaceVersioning`/`URLPathVersioning`/`AcceptHeaderVersioning`/
  `QueryParameterVersioning`/`HostNameVersioning` de DRF: ninguno (0 config). El
  prefijo `v1`/`v2` es Django puro, no el esquema DRF (aunque el `_v2` de los
  namespaces se le parezca).
- `BaseVersioning` a medida / header `X-API-Version`: no.
- Serializers hyperlinked que dependan de la versión para `reverse()`: no aplica
  (relaciones por PK, ver `serializer-relations.md`).

## Checklist al montar un endpoint

1. ¿Es del producto (comprador/admin)? → `api/v2/<dominio>/` + namespace
   `<app>_v2` en `config/urls.py`.
2. ¿Es un webhook externo? → `api/v1/<proveedor>/` (contrato estable).
3. **No** ramificar por `request.version` (es `None`); la variación de
   serializer va por lectura/escritura o rol.
4. `reverse()` con `namespace:name`.

## Referencias cruzadas

- `routers.md` / `viewsets.md` — el router se monta bajo el `include(...,
  namespace='<app>_v2')` del prefijo `api/v2/`.
- `serializers.md` — `get_serializer_class` ramifica por lectura/escritura, no
  por versión.
- `authentication.md` — el `api/v1/` de webhooks convive con la auth de sesión
  del `api/v2/` (los webhooks tienen su propia verificación de firma).
- Código: `config/urls.py:42-81` (montaje `api/v1/` webhooks + `api/v2/` app con
  namespaces `_v2`).
```

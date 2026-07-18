```yml
type: Reference (lazy-load on-demand)
applies_when: Se cachea la respuesta o el cómputo de un endpoint (reporte, payload caro) o se razona sobre la caché de capacidades
created_at: 2026-07-18 03:08:06
status: Aprobado
version: 1.0.0
source: DRF api-guide/caching
```

# DRF Caching — cachear cómputo, no la respuesta

> DRF se apoya en las utilidades de caché de Django. Este doc fija **cómo** el
> proyecto cachea: caché de **bajo nivel** por cómputo (no `cache_page`), más la
> caché de capacidades del authz.

## Backend — `DatabaseCache`, no Redis/Memcached

`CACHES['default']` = `django.core.cache.backends.db.DatabaseCache` sobre
`cache_table`, `TIMEOUT=300`, `MAX_ENTRIES=5000` (PROVEN 2026-07-18,
`config/settings/base.py:545-552`). La caché vive en la **BD**, no en un store en
memoria. Implicación: barata de operar (sin infra extra) pero cada hit es una
consulta a `cache_table` — cachear cómputos **caros** (agregaciones, reportes),
no respuestas triviales.

## Patrón del proyecto — caché de **bajo nivel** `cache.get/set`

El proyecto cachea con `from django.core.cache import cache` y el par
`cache.get(key)` / `cache.set(key, payload, ttl)`, **no** con `cache_page`. PROVEN
2026-07-18: **41** usos de `cache.get/set`, **0** de `cache_page`. Referencia
canónica — `reports/views.py`::

    _CACHE_TTL = 300  # 5 min — UC-REP-01
    def get(self, request):
        days = parse_period(request.query_params.get('period'))
        key = f'reports:sales:{days}'
        payload = cache.get(key)
        if payload is None:
            payload = build_sales_payload(days)
            cache.set(key, payload, self._CACHE_TTL)
        return Response(payload)

Convenciones del patrón:

- **TTL explícito por vista** en `_CACHE_TTL` (reports usa 300 / 600 / 30 / 3600
  según la volatilidad del reporte), no el `TIMEOUT` global implícito.
- **Clave namespaced** `dominio:tema:<param>` (`reports:sales:<days>`) — incluye
  los inputs que determinan el resultado (el `period`), para no servir un payload
  de otro parámetro.
- Se cachea el **payload computado** (dict serializable), no el objeto `Response`.

## Por qué no `cache_page`

`cache_page` cachea la **respuesta entera por URL** y sólo `GET`/`HEAD` con
**200**. Con datos **por usuario** + auth de **sesión** (ver `authentication.md`),
cachear por URL **filtraría** el contenido de un usuario a otro salvo que se
añada `@vary_on_cookie`. El proyecto lo evita cacheando a bajo nivel con una clave
que incluye los inputs reales; los reportes cacheados son **agregados no
sensibles por usuario** (métricas de tienda), así que la clave no necesita el
usuario. **Si algún día se usa `cache_page`** en un endpoint per-usuario,
`@vary_on_cookie` (o `@vary_on_headers`) es obligatorio para no fugar datos entre
sesiones.

## Caché de capacidades — `invalidate_capabilities` al cambiar rol

El authz **cachea las capacidades resueltas por usuario** (`has_capability`,
`resolution.py`) para no recomputar el árbol de roles en cada petición. Esa caché
se **invalida** con `invalidate_capabilities(user_id)` cuando cambia la
asignación de roles (PROVEN 2026-07-18: `admin_views.py:254`, `bootstrap.py:25`).

**Invariante para tests y para código que asigna roles:** tras conceder/quitar un
rol o capacidad, **llamar `invalidate_capabilities(user.id)`** — si no, la caché
sirve el set viejo y el 403/200 no cambia. Es exactamente por esto que los tests
de autorización hacen `seed_authz` + `assign_buyer_role(u)` +
`invalidate_capabilities(u.id)` (ver `SKILL.md` Phase 11).

## Checklist al cachear

1. ¿Cómputo caro (reporte, agregación)? → caché de bajo nivel
   `cache.get(key)`/`cache.set(key, payload, ttl)`; **no** `cache_page`.
2. Clave `dominio:tema:<inputs>` que incluya todo lo que cambia el resultado;
   TTL explícito por la volatilidad del dato.
3. ¿El dato es per-usuario? → la clave DEBE incluir el usuario (o no cachearlo);
   con `cache_page`, `@vary_on_cookie` obligatorio.
4. ¿Asignaste/quitaste un rol o capacidad? → `invalidate_capabilities(user.id)`.
5. No introducir Redis/Memcached ni deps de caché sin una necesidad que
   `DatabaseCache` no cubra.

## Referencias cruzadas

- `response-object.md` — se cachea el payload (dict), la vista devuelve
  `Response(payload)`.
- `authentication.md` — auth de sesión: por qué `cache_page` sin `vary_on_cookie`
  fuga entre usuarios.
- `permissions.md` / `SKILL.md` Phase 11 — la caché de capacidades y el
  `invalidate_capabilities` de los tests.
- Código: `addons/reports/views.py` (`_CACHE_TTL` + `cache.get/set`),
  `addons/authz/resolution.py` (`has_capability`/`invalidate_capabilities`),
  `config/settings/base.py:545` (`CACHES` = DatabaseCache).
```

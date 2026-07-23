```yml
type: Reference (lazy-load on-demand)
applies_when: Un endpoint devuelve una URL absoluta (imagen, descarga, callback) en su respuesta
created_at: 2026-07-18 03:23:56
status: Aprobado
version: 1.0.0
source: DRF api-guide/reverse
```

# DRF Returning URLs — `build_absolute_uri`, no el `reverse` de DRF

> DRF ofrece `rest_framework.reverse.reverse(...)` (como el de Django pero
> devuelve URL **absoluta** usando el `request` para host/puerto). El proyecto
> **no** lo usa: cuando necesita una URL absoluta en una respuesta, llama
> **`request.build_absolute_uri(...)`** directamente.

## El `reverse` de DRF NO se usa

PROVEN 2026-07-18: **0** usos de `rest_framework.reverse` / `reverse_lazy` de DRF
en `src/`. La razón por la que la doc de DRF ofrece su `reverse` — que el
**self-describing/browsable API** hiperenlace su salida automáticamente — es un
no-op aquí: el browsable renderer está apagado en producción (ver `renderers.md`)
y las relaciones son por **PK**, no hyperlinked (`Hyperlinked*` = **0**, ver
`serializer-relations.md`). Sin salida navegable ni serializers hyperlinked, el
`reverse` request-aware de DRF no aporta.

## El patrón real — `request.build_absolute_uri(...)`

Cuando una respuesta debe incluir una URL absoluta (imagen de producto, avatar,
archivo de descarga), el proyecto usa `request.build_absolute_uri(...)` — **13**
usos en `src/addons` (PROVEN 2026-07-18). Dos familias:

- **URL de un media/asset** (lo más común): el `SerializerMethodField` construye
  la URL absoluta de la imagen desde el `request` del contexto::

      def get_cover_url(self, obj):
          request = self.context.get('request')
          cover = obj.cover
          return request.build_absolute_uri(cover.image.url) if request else cover.image.url

  Ejemplos: `orders/serializers.py:91,230`, `cart/serializers.py:35`,
  `users/models.py:292` (avatar), `settings_app/serializers.py:302`.
  **Gotcha:** si el `request` no está en el contexto, cae a la URL **relativa**
  (`cover.image.url`) — por eso el serializer debe recibir
  `context={'request': request}` (los genéricos de DRF lo inyectan solo; ver
  `serializers.md`).

- **URL de descarga a mano**: se arma la ruta y se absolutiza con el `request`
  (`inventory/views.py:577`, reporte de import CSV)::

      download_url = request.build_absolute_uri(
          f'/api/v2/admin/inventory/import-reports/{job.pk}.csv'
      )

Ambas cumplen el consejo de la doc de DRF (devolver **URI absoluta**, no relativa)
sin el `reverse` de DRF: la absolutización la da `build_absolute_uri`, no una
resolución `viewname → path` request-aware.

## `django.urls.reverse` — resolución de nombre, no absolutización

Para resolver `viewname → path` (sin host) el patrón es el `reverse` de **Django**
(`django.urls.reverse`), no el de DRF. Si además se necesita absoluto, se compone
con `build_absolute_uri(reverse('<namespace>:<name>'))`. Recordar que el ruteo es
por **namespace `_v2`** (ver `versioning.md`): `reverse('cart_v2:cart-list')`, no
un `name` pelado.

## Qué NO se usa

- `rest_framework.reverse.reverse` / `reverse_lazy`: 0. No importarlos "por
  costumbre DRF" — para URL absoluta va `build_absolute_uri`; para resolver un
  name va `django.urls.reverse`.
- Serializers `Hyperlinked*` / `HyperlinkedIdentityField`: 0 (relaciones por PK,
  ver `serializer-relations.md`). El `reverse` de DRF que esos serializers usan
  internamente no aplica.

## Checklist al devolver una URL

1. ¿URL absoluta de un media/asset en una respuesta? →
   `request.build_absolute_uri(obj.<file>.url)` en un `SerializerMethodField`,
   con `request` en el contexto (fallback relativo si falta).
2. ¿URL absoluta de una ruta propia (descarga, callback)? →
   `request.build_absolute_uri(f'/api/v2/...')` o
   `build_absolute_uri(reverse('<ns>:<name>'))`.
3. ¿Solo resolver `viewname → path` (sin host)? → `django.urls.reverse` con el
   namespace `_v2`.
4. **No** usar `rest_framework.reverse` ni serializers hyperlinked.

## Referencias cruzadas

- `serializer-fields.md` — `SerializerMethodField` (donde vive el
  `build_absolute_uri` de las imágenes).
- `serializers.md` — inyección de `context={'request': request}` (necesaria para
  que `build_absolute_uri` no caiga a relativo).
- `serializer-relations.md` — relaciones por PK, no hyperlinked (por eso el
  `reverse` de DRF no aplica).
- `renderers.md` — browsable apagado en prod (el hiperenlazado auto que motiva el
  `reverse` de DRF no aporta).
- `versioning.md` — `reverse('<app>_v2:<name>')` con namespace.
- Código: `orders/serializers.py:91,230`, `cart/serializers.py:35`,
  `users/models.py:292`, `inventory/views.py:577` (`build_absolute_uri`).
```

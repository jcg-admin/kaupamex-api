```yml
type: Reference (lazy-load on-demand)
applies_when: Se construye la respuesta de una vista DRF (return Response(...))
created_at: 2026-07-18 02:40:41
status: Aprobado
version: 1.0.0
source: DRF api-guide/responses
```

# DRF `Response` — construir la respuesta

> Cargar cuando una vista devuelve datos. `Response` subclasa
> `SimpleTemplateResponse`: se inicializa con **datos sin renderizar** (Python
> primitives) y DRF hace content-negotiation para elegir el renderer.

## Regla principal — `Response(data, status=...)` con primitivos

- Firma: `Response(data, status=None, template_name=None, headers=None,
  content_type=None)`.
- `data` = **primitivos de Python** (dict/list/str/num/bool). Los renderers **no**
  manejan instancias de modelo Django → serializar antes:
  `Response(MiSerializer(obj, context={'request': request}).data)`.
- `status`: default **200**. En este proyecto se pasa **explícito** siempre que
  no sea 200 (201/400/401/403/409…). Usar `rest_framework.status`
  (`status.HTTP_201_CREATED`) o el entero directo — ambos aparecen en el repo;
  preferir la constante en código nuevo por legibilidad. (PROVEN 2026-07-18: 38
  archivos con `return Response(`, 22 con `status=` explícito.)

## Requiere `APIView` / `@api_view`

- Devolver `Response` **exige** que la vista sea `APIView` o `@api_view`: son
  quienes fijan `accepted_renderer` / `accepted_media_type` /`renderer_context`
  antes de devolver, y ejecutan la content-negotiation. Una función Django
  desnuda que devuelva `Response` **no** renderiza bien.

## Cuerpo canónico del proyecto

- **Éxito:** un dict o `serializer.data`. Ej.: `Response({'enabled': True}, status=200)`.
- **Error de negocio (4xx):** `Response({'codigo_error': 'X', 'detail': '...'},
  status=4xx)` — clave canónica `codigo_error` (no `error_code`; el gate
  canon-idioma lo vigila). Ver también los errores de parsing/validación que DRF
  mapea solo (`ParseError`→400, `UnsupportedMediaType`→415; ver
  `request-object.md`).

## Headers y cache

- `Response` extiende `SimpleTemplateResponse`; setear headers al estilo estándar
  o vía el arg `headers`::

      resp = Response(data, status=200)
      resp['Cache-Control'] = 'no-cache'
      return resp

## Excepción — NO usar `Response` para streaming/binario

- Para descargas grandes o binarios se devuelve `StreamingHttpResponse` /
  `FileResponse` de Django, no `Response` (los renderers no aplican). Caso real
  en el repo: `addons/reports/exports.py:48` (`StreamingHttpResponse` CSV) y
  `addons/reports/views.py:508` (`FileResponse`). Es la única razón para NO
  devolver `Response` en un endpoint.

## Atributos útiles (tests / middleware)

- `.data` — datos sin renderizar (lo que asertan los tests:
  `resp.data['codigo_error']`).
- `.status_code` — código numérico (`assert resp.status_code == 400`).
- `.content` — bytes renderizados (sólo tras `.render()`, que corre en el ciclo
  estándar; no llamarlo a mano).

## Checklist al devolver

1. ¿Los datos son primitivos? Si hay modelos → serializar primero.
2. `status` explícito si no es 200.
3. Error de negocio → `{'codigo_error', 'detail'}`.
4. ¿Streaming/binario? → `StreamingHttpResponse`/`FileResponse`, no `Response`.
5. La vista es `APIView`/`@api_view` (si devuelve `Response`).

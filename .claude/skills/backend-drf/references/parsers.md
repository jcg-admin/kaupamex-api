```yml
type: Reference (lazy-load on-demand)
applies_when: Un endpoint recibe algo distinto de JSON (subida de archivo/CSV, form-data) y hay que fijar parser_classes
created_at: 2026-07-18 02:54:20
status: Aprobado
version: 1.0.0
source: DRF api-guide/parsers
```

# DRF Parsers — cómo se puebla `request.data`

> El **consumo** de `request.data` vive en `request-object.md`. Este doc es
> el **parser**: qué clase interpreta el body según el `Content-Type`, y cuándo
> hay que fijar `parser_classes` (subidas de archivo).

## Cómo se elige el parser

Al acceder a `request.data`, DRF lee el header **`Content-Type`** de la petición y
elige, de la lista de `parser_classes` de la vista, el parser cuyo `media_type`
coincide. La lista es siempre un conjunto de clases; el parser que gana puebla
`request.data`.

Gotcha del cliente: si no se fija `Content-Type`, la mayoría de los clientes cae
en `application/x-www-form-urlencoded` — que casi nunca es lo deseado. Un cliente
que envía JSON debe fijar `Content-Type: application/json`.

## Default del proyecto — no se overridea

El proyecto **no** declara `DEFAULT_PARSER_CLASSES` (PROVEN 2026-07-18: 0 hits en
`src/config/settings/base.py`; sólo aparece en el default de DRF, `.venv/.../
rest_framework/settings.py`). Por lo tanto rige el default de DRF:

| Parser | `media_type` | Puebla |
|---|---|---|
| `JSONParser` | `application/json` | `request.data` (dict) |
| `FormParser` | `application/x-www-form-urlencoded` | `request.data` (`QueryDict`) |
| `MultiPartParser` | `multipart/form-data` | `request.data` + `request.FILES` |

Es decir: JSON **y** form-data (con archivos) funcionan sin configurar nada. La
inmensa mayoría de los endpoints recibe JSON y **no** toca `parser_classes`.

## Cuándo fijar `parser_classes` — subidas de archivo

Se overridea sólo cuando el endpoint recibe un archivo. Estado del repo (PROVEN
2026-07-18): **1** override de `parser_classes` en `src/addons`, **0**
decoradores `@parser_classes` (FBV), **0** parsers a medida (`BaseParser`).

El caso real: subida de imagen en una reseña —
`reviews/views.py:279` `parser_classes = [MultiPartParser, FormParser]`. El par
`MultiPartParser` + `FormParser` es el patrón para **soportar form-data HTML por
completo** (campos de archivo y no-archivo). Con él, `request.FILES` queda
poblado.

Los otros consumidores de archivo del repo son subidas **CSV** que leen
`request.FILES.get('file')` (PROVEN 2026-07-18: `inventory/views.py:522`,
`catalogue/views.py:989` y `:1224`, `catalogue/price_sync_views.py:93`) — se
apoyan en que `MultiPartParser` **ya está en el default**, sin override propio.

- **`FileUploadParser`** (subida de archivo crudo, `media_type='*/*'`, un solo
  archivo bajo la clave `'file'`) **no se usa** en el repo. Se reserva para
  clientes nativos que suben el binario crudo; para subidas web (form-data) o
  clientes con soporte multipart, se usa `MultiPartParser`. Como su `media_type`
  matchea cualquier tipo, si se usara debería ser el **único** parser de la vista.

## Parser a medida — no se usa aquí

Un parser propio subclasea `BaseParser`, fija `.media_type` e implementa
`parse(self, stream, media_type, parser_context)` devolviendo lo que poblará
`request.data`. Estado del repo (PROVEN 2026-07-18): **0** subclases de
`BaseParser`. No hay necesidad — JSON + form + multipart cubre la superficie. No
introducir un parser a medida (ni deps de terceros como YAML/XML/MessagePack) sin
un media type nuevo que el API deba aceptar de verdad.

## Checklist al recibir algo que no es JSON

1. ¿El body es JSON? → no tocar nada (el default lo parsea).
2. ¿Subida de archivo por form-data (imagen, CSV)? →
   `parser_classes = [MultiPartParser, FormParser]`; leer el archivo de
   `request.FILES.get('file')`.
3. ¿Necesitas un media type nuevo que DRF no trae? → sólo entonces un
   `BaseParser` a medida — verificar antes que el default no lo cubra.
4. No usar `request.POST`/`request.FILES` para leer campos de datos normales —
   eso va por `request.data` (ver `request-object.md`).

## Referencias cruzadas

- `request-object.md` — el consumo de `request.data`/`request.FILES`.
- `views.md` — dónde encajan `parser_classes` (policy attribute) y su decorador
  FBV `@parser_classes`; el gotcha de `self.action` en `get_parsers`.
- Código: `addons/reviews/views.py:279` (único override), `addons/catalogue/
  views.py` + `addons/inventory/views.py` (subidas CSV vía default).
```

```yml
type: Reference (lazy-load on-demand)
applies_when: El schema generado no coincide con la API — hay un warning de introspección, un campo mal tipado, o un endpoint sin request/response
created_at: 2026-07-18 03:46:15
status: Aprobado
version: 1.0.0
source: drf-spectacular workflow & schema customization
```

# Customización del schema — los 7 pasos, mapeados al proyecto

> Escalera de menor→mayor esfuerzo para acercar el schema a la API real. Aplicar
> **en orden**: casi todo se resuelve en el paso 2 (`@extend_schema`). Los pasos
> 5-7 (extensiones/hooks) son para casos que la introspección no alcanza.

## Paso 1 — `queryset` + `serializer_class` (introspección base)

drf-spectacular infiere casi todo de `queryset` y `serializer_class` (y de
`get_serializer_class()`/`get_serializer()` si existen). **Antes** de decorar,
verificar que la vista los expone. En este proyecto muchas vistas son FBV/`APIView`
con `serializer_class` explícito (ver `backend-drf/references/generic-views.md`);
si falta, la introspección tiene poco con qué trabajar → paso 2.

## Paso 2 — `@extend_schema` (el 95% de los casos)

Es el mecanismo dominante (**354** usos PROVEN). Solo se overridea **lo que la
introspección no descubrió**: `parameters`, `request`, `responses`, `summary`,
`tags`, `deprecated`. Detalle y patrones: `extend-schema` (referencia dedicada,
por pieza). Nota de `responses`: acepta dict por status/media-type — p.ej.
`{200: Ser, 404: None}` o `{(200, 'application/pdf'): OpenApiTypes.BINARY}` (útil
para el export de `reports`, ver `backend-drf/references/renderers.md`).

**`@extend_schema_view` — NO se usa en este proyecto (PROVEN: 0).** El doc lo
ofrece para anotar métodos de clases base o `@action`s sin tener dónde colgar el
decorador. El estilo del proyecto es **anotar el método directamente** (se
sobrescribe el `list`/`retrieve` y se decora ahí, que el propio doc reconoce como
válido). No introducir `@extend_schema_view` salvo que se anote un método que **no
se sobreescribe**.

## Paso 3 — `@extend_schema_field` + type hints (campos)

Para un `SerializerField`/`SerializerMethodField` que no se tipa solo: **72** usos
PROVEN. Toma un `OpenApiTypes` o un tipo Python básico o un `Serializer`. Es el
patrón del proyecto para los `SerializerMethodField` (ver
`backend-drf/references/serializer-fields.md`)::

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_field_custom(self, obj):
        ...

## Paso 4 — `@extend_schema_serializer` — NO se usa (PROVEN: 0)

El doc lo ofrece para `exclude_fields`, ejemplos (`OpenApiExample`) o `many=False`
en envelopes. El proyecto **no** lo usa (0), consistente con `OpenApiExample` = 0
(el estilo no embebe ejemplos en el schema). No introducirlo sin una necesidad
concreta (p.ej. ocultar un campo interno de un serializer que no se puede tocar).

## Paso 5 — Extensiones (para código de librería / introspección imposible)

Cuando no se puede decorar la clase (viene de una librería) o la introspección es
imposible, una **extensión** engancha sin tocar el original. **Se auto-registran**
al definirse (via `__init_subclass__`) — por eso viven en el `schema.py` de la app
(detalle: `per-app-schema`, por pieza). Cinco tipos; el proyecto usa **3**
(PROVEN 2026-07-18):

| Tipo | Usos | Para qué | En el proyecto |
|---|---|---|---|
| `OpenApiAuthenticationExtension` | 1 | documentar un auth scheme de librería | `CsrfExemptSessionScheme` (cookieAuth, ADR-018) |
| `OpenApiSerializerExtension` | 2 | serializer con `to_representation`/envelope raro | `PYTokenObtainPairSerializerExtension` (login) |
| `OpenApiViewExtension` | 2 | reemplazar la vista solo para el schema (`view_replacement`, 1 uso) | `TokenBlacklistViewFix` (logout simplejwt) |
| `OpenApiSerializerFieldExtension` | **0** | equivalente a `@extend_schema_field` para campos de librería | se prefiere el decorador (paso 3) |
| `OpenApiFilterExtension` | **0** | filtros/paginación de librería | no aplica (filtrado manual, no django-filter) |

**Desviación del doc — apps.py `ready()`:** el doc recomienda importar el
`schema.py` en `AppConfig.ready()`. **Aquí NO se hace** — un import dentro de un
método lo bloquea `check_no_lazy_imports`. La vía sancionada es el **PREPROCESSING
hook** `register_app_schema_extensions`, que importa los `schema.py` antes de
generar (ver `spectacular-settings.md`; comentario en `addons/users/apps.py`). Es
la diferencia clave entre la doc y este proyecto.

**`priority`:** solo relevante si se subclasa una extensión built-in (las built-in
tienen `priority=-1`; hay que subir el propio). El proyecto no lo necesita hoy.

## Paso 6 — POSTPROCESSING hooks

Corren al final, sobre el OpenAPI root object. El proyecto tiene
`collect_app_tags` (`base.py:411`). **Gotcha del doc PROVEN correctamente:** fijar
`POSTPROCESSING_HOOKS` **reemplaza** el default, así que hay que **re-añadir**
`drf_spectacular.hooks.postprocess_schema_enums` — el proyecto lo mantiene
(`base.py:409`, junto a `collect_app_tags`). No borrarlo al añadir un hook nuevo.

## Paso 7 — PREPROCESSING hooks

Corren antes de generar, sobre la lista de operaciones. El proyecto tiene
`register_app_schema_extensions` (`base.py:418`, el que fuerza el import de las
extensiones) + el built-in `preprocess_exclude_path_format` (`base.py:415`, quita
las operaciones duplicadas con sufijo `{format}` — coherente con no usar
format-suffixes, ver `backend-drf/references/format-suffixes.md`).

## Orden de decisión (resumen)

1. ¿Falta `serializer_class`/`queryset`? → añadirlo (paso 1).
2. ¿Params/responses/summary mal? → `@extend_schema` (paso 2).
3. ¿Un campo mal tipado? → `@extend_schema_field` (paso 3).
4. ¿Una vista/serializer/auth de **librería** que no puedo decorar? → extensión en
   el `schema.py` de la app (paso 5), **no** en `ready()`.
5. ¿Transformación global del schema (tags, enums)? → hook en `base.py` (pasos
   6/7), re-añadiendo el enum hook.

## Referencias cruzadas

- `spectacular-settings.md` — los hooks (PRE/POST) y por qué el PREPROCESSING
  registra las extensiones (no `ready()`).
- `extend-schema` (por pieza) — patrones del paso 2.
- `per-app-schema` (por pieza) — dónde viven las extensiones (paso 5).
- `enum-overrides` (por pieza) — el paso 6 sobre enums.
- `backend-drf/references/serializer-fields.md` — `@extend_schema_field` (paso 3).
- Código: `addons/users/schema.py` (las 3 extensiones), `config/spectacular_hooks.py`
  (hooks), `config/settings/base.py:409-418` (registro de hooks).
```

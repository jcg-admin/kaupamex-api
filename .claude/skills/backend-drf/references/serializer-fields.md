```yml
type: Reference (lazy-load on-demand)
applies_when: Se declara o modifica un campo de serializer (SerializerMethodField, source, DecimalField de dinero, ChoiceField, write_only/read_only)
created_at: 2026-07-18 02:59:25
status: Aprobado
version: 1.0.0
source: DRF api-guide/fields
```

# DRF Serializer fields — campos y core arguments

> Complementa `serializers.md`: el serializer declara campos; este doc fija qué
> campos y qué `core arguments` usa el proyecto. Todos se importan de
> `from rest_framework import serializers` y se refieren como
> `serializers.<Campo>`.

## Core arguments — los que el proyecto usa de verdad

| Argumento | Uso en el proyecto |
|---|---|
| `read_only=True` | salida sí, entrada ignorada — campos calculados/server-set (**105** inline, PROVEN 2026-07-18) |
| `write_only=True` | entrada sí, no vuelve en la representación — secretos como `password` (**20**) |
| `required=False` | el campo puede faltar en la entrada |
| `default=` | valor si no se envía (implica `required=False`; **no** aplica en PATCH) |
| `allow_null` / `allow_blank` | `None` / `""` válidos (para texto, preferir `allow_blank`) |
| `source=` | mapea el campo a otro atributo/método/ruta con puntos (**67**, ver abajo) |
| `validators=[...]` | validadores de campo (funciones que lanzan `ValidationError`) |

`default` + `required` juntos es **inválido** (error). Un `default` callable con
`requires_context=True` recibe el field (patrón de `CurrentUserDefault`, que el
proyecto **no** usa — la inyección va en la vista, ver `serializers.md`).

## `SerializerMethodField` — el campo calculado de sólo lectura (muy usado)

Estado del repo (PROVEN 2026-07-18): **113** declaraciones — el segundo campo más
usado tras `CharField` (198). Es read-only; toma su valor de un método
`get_<campo>(self, obj)` del serializer::

    dias_desde_alta = serializers.SerializerMethodField()
    def get_dias_desde_alta(self, obj):
        return (now() - obj.date_joined).days

**Cuidado N+1:** si `get_<campo>` navega relaciones (`obj.orders.count()`,
`obj.user.email`), dispara una consulta por objeto en una lista. Anotar el
queryset con `select_related`/`prefetch_related` en `get_queryset()` (ver
`generic-views.md`) o precalcular con `annotate()`.

## `source=` — mapear a otro atributo (67 usos)

`source` puebla el campo desde otro atributo, un método sin args, o una ruta con
puntos: `serializers.EmailField(source='user.email')`. **Mismo N+1:** una ruta con
puntos que cruza una relación necesita `select_related`/`prefetch_related`.
`source='*'` pasa el objeto completo al campo (para representaciones anidadas a
medida) — hoy no se usa en el repo, pero es la vía si hiciera falta.

## Dinero — `DecimalField(max_digits, decimal_places=2)`, nunca `FloatField`

Estado del repo (PROVEN 2026-07-18): **34** `DecimalField`, patrón
`DecimalField(max_digits=12, decimal_places=2)`. El dinero se representa con
`Decimal`, **no** `FloatField` (float pierde precisión en centavos). Por default
`COERCE_DECIMAL_TO_STRING=True`, así que un `DecimalField` se serializa como
**string** en el JSON (`"199.90"`) — el cliente debe tratarlo como string, no como
número flotante.

## `ChoiceField` — desde `choices=` del modelo

Estado del repo (PROVEN 2026-07-18): **13** `ChoiceField`. `ModelSerializer` lo
genera solo cuando el campo del modelo tiene `choices=…`. Para choices textuales
preferir `allow_blank`; para numéricas, `allow_null` (no ambos a la vez).

## Archivos — `ImageField`/`FileField` exigen `MultiPartParser`

Estado del repo (PROVEN 2026-07-18): **2** `ImageField`, **2** `FileField`. Sólo
funcionan con `MultiPartParser`/`FileUploadParser` — JSON no soporta subida de
archivo. Fijar `parser_classes = [MultiPartParser, FormParser]` en la vista (ver
`parsers.md`). `ImageField` valida que sea imagen (requiere Pillow, ya instalado).

## Compuestos y otros — uso puntual

- `ListField(child=...)` (**6**) / `DictField(child=...)` (**5**) — validan lista
  o dict de un `child` field; `JSONField` (**1**) valida primitivos JSON.
- `PrimaryKeyRelatedField` (**5**) — relación por PK (el default de
  `ModelSerializer`; ver `serializers.md`).
- `UUIDField` (**2**), `RegexField` (**1**), `EmailField` (**10**),
  `BooleanField` (**16**), `DateTimeField` (**13**) — según el tipo del dato.
- `HiddenField(default=...)` / `ReadOnlyField` — puntuales; `HiddenField` no
  aparece en `partial=True` (PATCH).

## Campo a medida — no se usa (usar `SerializerMethodField` o nested)

Un campo a medida subclasea `serializers.Field` y overridea
`to_representation`/`to_internal_value` (+ `fail('code')` con `error_messages`
para errores limpios). Estado del repo (PROVEN 2026-07-18): **0** subclases de
`serializers.Field`. La lectura calculada se resuelve con `SerializerMethodField`;
el reshape de datos, con un **nested serializer** (`source='*'` + campos con su
propio `source`) antes que con un campo a medida (recomendación de la doc de DRF:
el nested serializer trae validación gratis). No introducir un campo a medida ni
`drf-extra-fields`/`drf-compound-fields` sin una necesidad que esos dos no cubran.

## Checklist al declarar un campo

1. ¿Calculado de sólo lectura? → `SerializerMethodField` + `get_<campo>`;
   cuidar N+1 (anotar el queryset).
2. ¿Otro atributo/ruta? → `source=`; cuidar N+1 si cruza relación.
3. ¿Dinero? → `DecimalField(max_digits, decimal_places=2)`, nunca `FloatField`;
   sale como string en JSON.
4. ¿Secreto? → `write_only=True`. ¿Server-set/calculado? → `read_only=True`.
5. ¿Archivo? → `ImageField`/`FileField` + `parser_classes` MultiPart (ver
   `parsers.md`).
6. ¿Reshape complejo? → nested serializer con `source='*'`, no un campo a medida.

## Referencias cruzadas

- `serializers.md` — el serializer que agrupa los campos; validación 3 niveles.
- `generic-views.md` — `select_related`/`prefetch_related` para el N+1 de
  `SerializerMethodField`/`source`.
- `parsers.md` — `MultiPartParser` para `ImageField`/`FileField`.
- Código: cualquier `addons/*/serializers.py`; patrón de dinero
  `DecimalField(max_digits=12, decimal_places=2)`.
```

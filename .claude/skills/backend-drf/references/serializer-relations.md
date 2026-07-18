```yml
type: Reference (lazy-load on-demand)
applies_when: Se representa una relación (FK/M2M/O2O/inversa) en un serializer — por PK, por slug, o anidada
created_at: 2026-07-18 03:01:06
status: Aprobado
version: 1.0.0
source: DRF api-guide/relations
```

# DRF Serializer relations — representar relaciones de modelo

> Complementa `serializers.md`/`serializer-fields.md`: cómo se representa un
> `ForeignKey`/`ManyToManyField`/`OneToOneField` (y sus inversas) en un
> serializer. La regla que atraviesa todo: **el N+1 lo optimiza el programador,
> no DRF**.

## Regla transversal — N+1: DRF no optimiza el queryset

DRF **no** aplica `select_related`/`prefetch_related` automáticamente ("sería
demasiada magia"). Un campo relacional con `many=True` sobre un queryset grande
dispara una consulta por objeto. Es responsabilidad de la vista anotar el
queryset en `get_queryset()` (ver `generic-views.md`): `select_related` para
FK/O2O, `prefetch_related` para inversas/M2M. Aplica a **todos** los estilos de
abajo.

## Default — `PrimaryKeyRelatedField` (por PK)

`ModelSerializer` representa las relaciones por **PK** por default (no hay
`HyperlinkedModelSerializer` en el proyecto; ver `serializers.md`). Estado del
repo (PROVEN 2026-07-18): **5** `PrimaryKeyRelatedField` explícitos, **2**
`SlugRelatedField`, **0** `StringRelatedField`, **0** `HyperlinkedRelatedField`/
`HyperlinkedIdentityField`.

**El campo relacional escribible SIEMPRE lleva `queryset=` explícito** (DRF 3
eliminó la derivación automática del queryset). Sin `queryset` un campo
relacional debe ser `read_only=True`. PROVEN 2026-07-18: los 5
`PrimaryKeyRelatedField` del repo llevan `queryset=` (o `read_only`).

## Idioma del proyecto — `<campo>_id` escribible + nested de lectura

El patrón canónico para un FK: un campo `<campo>_id` **write_only** que acepta el
id de entrada y lo mapea al FK con `source=`, mientras la **lectura** usa un
serializer anidado o el objeto. PROVEN (`logistics/serializers.py:55`)::

    order_id = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(), source='order', write_only=True,
    )

Así el cliente **manda un id** y **recibe** la representación rica. Para M2M el
mismo patrón con `many=True` (`catalogue/serializers.py:402`:
`category_ids = PrimaryKeyRelatedField(source='categories', many=True,
queryset=Category.objects.all())`). `allow_null=True` para FK nullable
(`catalogue/serializers.py:607`).

## `SlugRelatedField` — por un campo único, no el PK

Representa la relación por un campo del target (que debe ser `unique=True` si es
escribible). PROVEN 2026-07-18: **2** usos — `logistics/serializers.py:59`
(`slug_field='order_number'`, escribible con `queryset`) y
`company/serializers.py:46` (`slug_field='code', many=True, read_only=True`). Se
usa cuando el identificador natural del cliente no es el PK (número de orden,
código de módulo).

## Nested — lectura declarativa; escritura explícita

- **Lectura anidada:** un serializer como campo, con `many=True` para to-many y
  `read_only=True` si sólo se lee. PROVEN 2026-07-18: **70** usos de
  `Serializer(many=True...)` — el estilo dominante para incrustar relaciones en la
  respuesta.
- **Escritura anidada:** el nested es read-only por default; para escribir hay que
  escribir `.create()`/`.update()` explícitos que guarden los hijos
  (`validated_data.pop('tracks')` → crear/actualizar) — ver `serializers.md`. El
  proyecto no usa `drf-writable-nested`.

## Relaciones inversas — explícitas, por `related_name`

Las relaciones **inversas** no las incluye `ModelSerializer` automáticamente: se
agregan a `Meta.fields` con el `related_name` del FK. PROVEN 2026-07-18: **307**
declaraciones de `related_name=` en modelos — el proyecto nombra sus inversas, así
que se referencian por ese nombre (no por `<modelo>_set`).

## M2M con `through` — read-only por default

Un campo relacional que apunta a un `ManyToManyField` con `through=` es
**read-only** por default; si se declara explícito hay que fijar
`read_only=True`. Para exponer los campos extra del modelo intermedio, se
serializa el **through como nested**. PROVEN 2026-07-18: **3** `through=` en
modelos.

## Campo relacional / genérico a medida — no se usa

- **Custom `RelatedField`:** subclasear `RelatedField` + `to_representation`
  (+`to_internal_value` si escribible). PROVEN 2026-07-18: **0** subclases. Cuando
  la representación por PK/slug/nested no basta, se resuelve con nested serializer
  antes que con un RelatedField a medida.
- **`GenericForeignKey`:** requeriría un campo a medida que discrimine por tipo.
  PROVEN 2026-07-18: **0** `GenericForeignKey`/`GenericRelation` en `src/addons` —
  el proyecto no serializa genéricas de Django por esta vía. No introducir
  `rest-framework-generic-relations` sin una relación genérica real que exponer.

## Checklist al representar una relación

1. ¿Escritura por id + lectura rica? → `<campo>_id = PrimaryKeyRelatedField(
   queryset=..., source='<campo>', write_only=True)` + nested de lectura.
2. ¿Identificador natural distinto del PK? → `SlugRelatedField(slug_field=...)`.
3. ¿Sólo lectura anidada? → `SubSerializer(many=True, read_only=True)`.
4. ¿Escritura anidada? → `.create()`/`.update()` explícitos.
5. ¿Inversa? → agregarla a `fields` por su `related_name`.
6. **Siempre**: anotar el queryset de la vista con `select_related`/
   `prefetch_related` (N+1).
7. Campo relacional escribible → `queryset=` obligatorio (o `read_only=True`).

## Referencias cruzadas

- `serializers.md` — el serializer contenedor; nested writable con `.create()`.
- `serializer-fields.md` — `source=` y el N+1 de campos que cruzan relación.
- `generic-views.md` — `select_related`/`prefetch_related` en `get_queryset()`.
- Código: `logistics/serializers.py` (`<campo>_id` write_only + `SlugRelatedField`),
  `catalogue/serializers.py` (M2M `category_ids`), `company/serializers.py`
  (`SlugRelatedField` read-only por `code`).
```

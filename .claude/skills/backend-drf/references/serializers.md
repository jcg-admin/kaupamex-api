```yml
type: Reference (lazy-load on-demand)
applies_when: Se crea o modifica un serializer (validación, campos, nested, create/update) para un endpoint DRF
created_at: 2026-07-18 02:57:40
status: Aprobado
version: 1.0.0
source: DRF api-guide/serializers
```

# DRF Serializers — validación y contrato de datos

> El serializer traduce entre modelos/objetos y primitivos, y **valida** la
> entrada. Es donde vive el contrato de datos del endpoint. Este doc fija las
> convenciones del proyecto; la mecánica completa está en la doc de DRF.

## Base — `ModelSerializer` (dominio) + `Serializer` (acción)

Estado del repo (PROVEN 2026-07-18, `class \w+(...)` en `src/addons`): **98**
`ModelSerializer`, **77** `Serializer` plano, **0** `HyperlinkedModelSerializer`,
**0** `ListSerializer`, **0** `BaseSerializer`.

- **`ModelSerializer`** — recurso mapeado a un modelo. Genera campos + validadores
  (incl. `unique_together`) desde el modelo y hereda los **validators del campo
  del modelo** (`max_length`, `unique`, etc.). Provee `.create()`/`.update()`
  simples.
- **`Serializer`** plano — payload de una acción que no es un modelo (login,
  confirmar 2FA, request de negocio). Se declaran los campos a mano.
- **`HyperlinkedModelSerializer` no se usa** — las relaciones se representan por
  **PK** (default de `ModelSerializer`), no por hyperlinks. El API es JWT +
  React-UI, sin browsable en prod, así que no hay necesidad de URLs `HATEOAS`.

## Campos — lista explícita, nunca `__all__`

`Meta.fields` se declara **explícito** siempre. Estado del repo (PROVEN
2026-07-18): **0** usos de `fields = '__all__'`. Es la recomendación fuerte de
DRF: `'__all__'` expone datos nuevos sin querer cuando el modelo crece. Atajos
del `Meta`:

- **`read_only_fields`** — tupla de campos de sólo lectura (58 usos en el repo).
- **`extra_kwargs`** — kwargs por campo sin declararlo entero; el patrón canónico
  es `{'password': {'write_only': True}}` (5 usos). Si el campo ya está declarado
  explícito, `extra_kwargs` se ignora.

## Validación — tres niveles, sellada a 400 por el handler central

1. **Campo (validador del modelo)** — heredado por `ModelSerializer` sin código.
2. **`validate_<campo>(self, value)`** — validación de un campo (47 en el repo);
   devuelve el valor o lanza `serializers.ValidationError`. No corre si el campo
   es `required=False` y no vino.
3. **`validate(self, data)`** — validación cruzada entre campos (19 en el repo);
   ej. "fin después de inicio".

En la vista: `serializer.is_valid(raise_exception=True)` (40 en el repo). El
`ValidationError` resultante lo **sella el handler central de excepciones**
(`core.exception_handling`, ADR-019) a un **400** con la forma canónica del error
(clave `codigo_error`; ver `views.md`). No se construye el 400 a mano tras un
`is_valid()` fallido — se usa `raise_exception=True`.

## `to_representation` / `to_internal_value` — no se overridean

Estado del repo (PROVEN 2026-07-18): **0** overrides de `to_representation` y
**0** de `to_internal_value`. La representación **no** se personaliza a ese nivel;
cuando un recurso necesita forma distinta de lectura vs escritura, se usan
**serializers separados** seleccionados con `get_serializer_class()` (ver
`viewsets.md`), no un `to_representation` a medida. Si aparece la necesidad de
override, es la excepción — documentarla.

## Inyección de contexto — en la vista, no `CurrentUserDefault`

Datos que no vienen en el request (usuario actual, hora) se inyectan al **guardar
en la vista**: `serializer.save(user=request.user)` / hook `perform_create`
(ver `generic-views.md`). Cualquier kwarg extra de `.save()` entra a
`validated_data` en `.create()`/`.update()`. Estado del repo (PROVEN 2026-07-18):
**0** usos de `CurrentUserDefault` — la inyección vive en la capa de vista, no en
el `default=` del campo. (Excepción reconocida de DRF: un campo read-only que es
parte de un `unique_together` con el usuario sí usaría
`PrimaryKeyRelatedField(read_only=True, default=CurrentUserDefault())`; hoy no
ocurre en el repo.)

## Nested — lectura declarativa; escritura explícita

- **Lectura anidada:** el `Serializer` es un `Field`; se anida como campo, con
  `many=True` para listas y `required=False` si acepta `None`.
- **Escritura anidada:** DRF 3 **exige** escribir `.create()`/`.update()`
  explícitos para nested writable (el default de `ModelSerializer` no los
  soporta). El proyecto **no** usa `drf-writable-nested` ni `depth=` (PROVEN
  2026-07-18: 0 `list_serializer_class`, 0 `depth =`). Un create/update de
  relaciones se escribe a mano (`validated_data.pop('nested')` → crear/actualizar
  las partes), o se encapsula en un **manager** del modelo.

## Múltiples objetos — `many=True`

`Serializer(queryset, many=True)` serializa una lista (crea un `ListSerializer`
hijo por dentro). El default deserializa múltiples para **create**, no para
update; un multiple-update requiere `list_serializer_class` a medida — no se usa
hoy en el repo.

## `partial=True` — para PATCH

Un update parcial (PATCH) pasa `partial=True` al instanciar el serializer, para
no exigir todos los campos `required`.

## Herencia de serializers

Se puede heredar campos/métodos de un serializer base. **Ojo:** el `Meta` interno
**no** hereda implícitamente — si se quiere, `class Meta(Base.Meta)` explícito.
Recomendación de DRF (y del proyecto): declarar las opciones del `Meta`
explícitas en vez de heredarlas.

## Terceros — no se usan

`marshmallow`, `serpy`, `drf-writable-nested`, `drf-flex-fields`, `drf-pydantic`,
etc. **no** se usan. La superficie (ModelSerializer + Serializer + validación de 3
niveles + serializers separados por lectura/escritura) cubre el proyecto. No
introducir una dep de serialización sin una necesidad que el core no cubra.

## Checklist al escribir un serializer

1. ¿Mapea a un modelo? → `ModelSerializer` (hereda validators del campo). ¿Payload
   de acción? → `Serializer` plano.
2. `Meta.fields` **explícito** (nunca `'__all__'`); `read_only_fields` /
   `extra_kwargs` (`write_only` para secretos) según haga falta.
3. Validación: `validate_<campo>` (un campo), `validate` (cruzada); en la vista
   `is_valid(raise_exception=True)` → 400 sellado con `codigo_error`.
4. Contexto (usuario/hora) → `save(user=...)`/`perform_create` en la vista, no
   `CurrentUserDefault`.
5. Lectura vs escritura distinta → serializers separados + `get_serializer_class`,
   no `to_representation`.
6. Nested writable → `.create()`/`.update()` explícitos (o manager); sin
   `depth=`/`drf-writable-nested`.

## Referencias cruzadas

- `views.md` — `is_valid(raise_exception=True)` + handler central (400 con
  `codigo_error`).
- `generic-views.md` / `viewsets.md` — `perform_create`/`save(user=...)` y
  `get_serializer_class` (lectura vs escritura).
- `request-object.md` — `MiSerializer(data=request.data)` alimenta el serializer.
- Código: cualquier `addons/*/serializers.py`; ej. patrón `write_only` de
  password + `.create()` con `set_password`.
```

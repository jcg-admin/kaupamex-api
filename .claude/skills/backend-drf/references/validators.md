```yml
type: Reference (lazy-load on-demand)
applies_when: Se reutiliza lógica de validación (validador de campo, UniqueValidator, unique_together) entre serializers
created_at: 2026-07-18 03:02:58
status: Aprobado
version: 1.0.0
source: DRF api-guide/validators
```

# DRF Validators — validación reutilizable

> Complementa `serializers.md` (validación de 3 niveles): este doc es la
> validación **reutilizable** — validadores función/clase, `UniqueValidator`,
> `unique_together`. En DRF la validación vive **entera en el serializer**, no en
> la instancia del modelo.

## Dónde vive la validación — en el serializer, no en el modelo

A diferencia de `ModelForm` (que valida parte en el form, parte en la instancia),
DRF valida **todo en el serializer**. Ventaja: `repr(serializer)` muestra
exactamente las reglas aplicadas, sin validación oculta en el `.save()` del
modelo. Con `ModelSerializer` esto se genera solo; con `Serializer` plano se
declara explícito.

## Reutilización del proyecto — validadores **función** en `<app>/validators.py`

El mecanismo de reutilización del proyecto es el **validador función** en un
módulo `validators.py` por app. PROVEN 2026-07-18: existen
`base_vat/validators.py`, `base_bank/validators.py`,
`authz_password_policy/validators.py`. Un validador función es cualquier callable
que lanza `serializers.ValidationError` al fallar::

    def validate_clabe(value):
        if not _clabe_ok(value):
            raise serializers.ValidationError('CLABE inválida')

Se cablea en el campo con `validators=[...]`. PROVEN 2026-07-18: **55**
`validators=[...]` inline en campos de serializer — la vía por la que los
validadores función se aplican. (Los mismos validadores se reusan como
`MinLengthValidator`/función en el modelo; `ModelSerializer` los hereda.)

- **Validador clase** (parametrizable, `__call__`, `requires_context=True` para
  recibir el field): DRF lo soporta, pero el proyecto **no** lo usa (PROVEN
  2026-07-18: **0** `requires_context`). La parametrización se resuelve con
  factories de función; si hiciera falta estado, un validador clase es la vía —
  hoy no ocurre.

## `UniqueValidator` — unicidad de un campo

Aplica el `unique=True` del modelo a nivel serializer. PROVEN 2026-07-18: **3**
usos explícitos::

    slug = serializers.SlugField(
        validators=[UniqueValidator(queryset=BlogPost.objects.all())])

Se pone en el **campo**. `ModelSerializer` lo genera solo para campos `unique=True`
del modelo; el uso explícito es para `Serializer` plano o control fino.

## `UniqueTogetherValidator` — se genera solo

Aplica `unique_together` a nivel serializer, en el **`Meta.validators`**. PROVEN
2026-07-18: **0** declaraciones explícitas — `ModelSerializer` lo **genera
automáticamente** desde el `unique_together` del modelo, y el proyecto se apoya en
esa generación (no lo declara a mano).

**Constraint implícita:** `UniqueTogetherValidator` trata **todos** sus campos
como `required` (salvo los que tienen `default`). Si un endpoint necesita uno de
esos campos `required=False`, el comportamiento se vuelve ambiguo.

## Casos ambiguos — `.validate()` o la vista, NO clobber de `Meta.validators`

DRF documenta desactivar el validador auto con `Meta.validators = []` en casos
ambiguos (un campo del unique-together como `required=False`; update de nested
donde la instancia no está disponible para excluirse del check de unicidad).
PROVEN 2026-07-18: **0** `Meta.validators = []` en el repo — el proyecto **no**
desactiva los validadores auto. Cuando aparece un caso ambiguo, la validación se
escribe explícita en `.validate()` (19 usos, ver `serializers.md`) o en la vista,
sin borrar el `Meta.validators` generado. Si algún día hace falta desactivarlo, es
la excepción documentada, no el default.

## Defaults avanzados — no se usan (contexto va en la vista)

`CurrentUserDefault`, `CreateOnlyDefault` y `HiddenField(default=...)` sirven para
alimentar un validador con un valor que el cliente no envía (usuario, hora).
PROVEN 2026-07-18: **0** `CurrentUserDefault`, **0** `CreateOnlyDefault`. El
proyecto inyecta ese contexto en la **vista** (`save(user=request.user)` /
`perform_create`; ver `serializers.md`/`generic-views.md`), no con un `default=`
de campo. (`HiddenField` no aparece en `partial=True`/PATCH — otra razón para no
depender de él.)

## Debug — imprimir el `repr` del serializer

Ante duda de qué validadores/campos genera un `ModelSerializer`, imprimir
`repr(MiSerializer())` en `manage.py shell` muestra el `UniqueValidator`,
`UniqueTogetherValidator` y demás reglas exactas. Para casos complejos, la doc de
DRF (y el proyecto) prefiere declarar el `Serializer` explícito antes que confiar
en la generación implícita.

## Checklist de validación reutilizable

1. ¿Lógica reusable de un campo? → validador **función** en `<app>/validators.py`;
   cablear con `validators=[...]`.
2. ¿Unicidad de un campo en `Serializer` plano? → `UniqueValidator(queryset=...)`.
   En `ModelSerializer` se genera solo.
3. ¿`unique_together`? → lo genera `ModelSerializer`; no declararlo a mano.
4. ¿Caso ambiguo (unique_together con `required=False`, nested update)? →
   `.validate()` o la vista; **no** `Meta.validators = []` salvo excepción
   documentada.
5. ¿Valor que el cliente no manda (usuario/hora)? → inyectar en la vista
   (`save(...)`), no `CurrentUserDefault`.

## Referencias cruzadas

- `serializers.md` — validación de 3 niveles (`validate_<campo>`/`validate`/
  `is_valid(raise_exception=True)`).
- `serializer-fields.md` — `validators=[...]` como core argument del campo.
- `generic-views.md` — inyección de contexto en `perform_create`/`save`.
- Código: `base_vat/validators.py`, `base_bank/validators.py`,
  `authz_password_policy/validators.py` (validadores función reusables).
```

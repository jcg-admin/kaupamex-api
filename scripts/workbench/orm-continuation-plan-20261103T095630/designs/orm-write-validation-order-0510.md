# TASK-API-0510 — orden validación / inverso en `BaseModel.write` y `check_access` en `_create`

Diseño de solo lectura. Referencia: odoo19c = `/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0` (no se anotó el commit de odoo-tools; se leyó el árbol materializado). Puerto: `/home/user/kaupamex-api/src/orm/models.py` (11 814 líneas, `wc -l`).

## 1. Referencia (odoo19c `odoo/orm/models.py`)

### 1.1 `_validate_fields` (`:1253-1268`)
Corre cada método de `_constraint_methods` si `not field_names.isdisjoint(check._constrains) and excluded_names.isdisjoint(check._constrains)`, sobre `self.sudo()`. Retorno temprano si no hay métodos (`:1257-1259`).

### 1.2 `write` (`:4334-4518`) — orden exacto
1. `:4374-4375` vacío → `True`.
2. `:4377-4382` `check_access('write')`; acceso de campo; `ValueError` ante nombre desconocido.
3. `:4385-4396` `bad_names` (`id`, `parent_path`, columnas de log) y `write_uid`/`write_date`.
4. `:4398-4430` clasificación: `field_values`, `determine_inverses[field.inverse].append(field)` (`:4416`), x2many con inverso se lee antes (`:4408-4415`), `fnames_modifying_relations`, `protected`.
5. `:4433-4437` recómputo forzado de calculados no asignados.
6. `:4440` `with env.protecting(protected, self):`
   - `:4459` `self.modified(fnames_modifying_relations, before=True)`
   - `:4461` `real_recs = self.filtered('id')`
   - `:4467-4468` `field.write(self, value)` por `write_sequence`
   - `:4481` `self.modified(vals)`
   - `:4483-4484` `flush_model([_parent_name])` si cambia el padre
   - **`:4486-4491`** `# validate non-inversed fields first` — `inverse_fields = [f.name for fs in determine_inverses.values() for f in fs]`; `real_recs._validate_fields(vals, inverse_fields)`
   - **`:4493-4511`** por grupo: re-escritura de no almacenados invalidados (`:4494-4497`, condición `not field.store and (not field.inherited or field.type not in x2many) and any(field._cache_missing_ids(real_recs))`); `fields[0].determine_inverse(real_recs)` (`:4501`) con reenvoltura de `AccessError` si `fields[0].inherited` (`:4502-4511`)
   - **`:4513-4514`** `# validate inversed fields` — `real_recs._validate_fields(inverse_fields)`
7. `:4516-4517` `_check_company(list(vals))` si `_check_company_auto`; `:4518` `return True`.

Consecuencia semántica que hay que portar: una restricción que nombra **algún** campo invertido no corre en la primera pasada (vetada por `excluded_names`) y corre una sola vez en la segunda, después del inverso. Una restricción que **sólo** nombra campos no invertidos corre **antes** del inverso; si levanta, el inverso no se ejecuta.

### 1.3 `create` / `_create`
- `create`: `self.check_access('create')` al entrar (`:4640`); tras `_create`, inversos; `:4739-4741` `data['record']._validate_fields(data['inversed'], data['stored'])`.
- `_create`: `:4948-4949` `records._validate_fields(name for data in data_list for name in data['stored'])`; **`:4950` `records.check_access('create')`** — tras validar; `:4951` `return records`.

## 2. Estado del puerto

### 2.1 `BaseModel.write` (`models.py:10665-10692`)
`check_access('write')` (`:10678`), acceso de campo (`:10679-10685`), luego `for record in self: super(BaseModel, record).write(vals)` (`:10686-10687`) y una sola `self._validate_fields(vals)` (`:10691`, comentario `≙ real_recs._validate_fields(vals, inverse_fields) (:4491)` en `:10690` — el comentario cita la llamada con exclusión pero el código no excluye). No hay segunda validación ni `filtered('id')`.

### 2.2 `RecordLoaderMixin.write` (`models.py:3046-3236`; clase en `:2742`)
Por fila: `_group_written_inverses(values)` (`:3076`), `_warm_x2many_before_inverse` (`:3077`), `_protected_while_writing` (`:3078`), recómputo forzado (`:3079-3086`), y dentro de `env().protecting(protected, self)` (`:3092`): m2m, `setattr`+`save`, relacionales, o2m, `self.modified(...)` (`:3224`), y **`determine_inverse` por grupo** (`:3227-3228`). Fuera del alcance: `if not hasattr(type(self), '_from_ids'): self._validate_fields(written)` (`:3232-3233`) — para un `BaseModel` (tiene `_from_ids`) la validación se omite aquí y la hace `BaseModel.write`.

**Orden real hoy para un `BaseModel`:** escribir → `modified` → inverso (por FILA, N llamadas para N registros) → validar `vals` sin exclusión. Es decir: la restricción de un campo no invertido corre **después** del inverso, y si levanta el inverso ya corrió.

Segunda divergencia, colateral: el inverso se despacha por registro, no una vez sobre `real_recs` (`:4501`). Para un singleton no se observa; para N registros, el método inverso recibe N recordsets de uno.

### 2.3 `_validate_fields` (`models.py:6135-6181`, asignado a `Model` en `:6767`)
Ya porta los dos filtros (`:6174-6181`) con comparación por campo canónico (`:6170-6175`). **No cambia.**

### 2.4 `create` / `_create`
- `create` (`:866`): `AccessQuerySet(model=cls).none().check_access('create')` (`:953`) ≙ `:4640`; inversos (`:1067-1096`); `data['record']._validate_fields(data['inversed'], data['stored'])` (`:1098-1100`) ≙ `:4739-4741`. **Orden ya correcto.**
- `_create` (`:1200`): valida almacenados (`:1279-1287`) ≙ `:4948-4949`. **Falta** `records.check_access('create')` ≙ `:4950` (grep `check_access('create')` en el archivo: sólo `:884` docstring y `:953`).

### 2.5 Lo que dicen H-API-1212 y FLOW.md
- `kaupamex-docs: …/completar-raiz-orm/hallazgos/hallazgo-H-API-1212-create-y-write-no-validaban-restricciones-almacenadas.rst:68-71`: *«La separación de ``write`` en validación de no-inversos e inversos y el ``check_access('create')`` tras validar en ``_create``: TASK-API-0510. ``test_15_constraint_inverse`` y el modelo ``test_orm.compute.inverse``: TASK-API-0510 (mismo flujo de escritura).»*
- `scripts/workbench/constraint-validation-flow-20261110T051341/FLOW.md:251-256` (§8): *«2. Separar en `write` la validación de no-inversos e inversos y `check_access('create')` tras validar en `_create` (TASK-API-0510).»* El punto 1 de §8 (modelo `test_orm.compute.inverse`) ya está cerrado: el modelo existe (`src/addons/test_orm/models/test_orm.py:1318-1373`) y `test_15_constraint_inverse` está porteado (`tests/integration/test_orm/test_compute_inverse.py:93-115`).
- Candidato (`…/candidates/orm-write-validation-order-0510.jsonl`): obligaciones `:4488-4491`, `:4493-4514`, `:4948-4950`; `verify` = `tests/unit/orm/test_write_validation_order.py tests/integration/test_orm/test_compute_inverse.py`; las `xfail(strict)` de SQL quedan fuera.

## 3. Consumidores

- `tests/integration/test_orm/test_compute_inverse.py:93-115` (`test_15_constraint_inverse`): restricción `@constrains('bar','baz')` sobre `test_orm.compute.inverse` (`test_orm.py:1352-1355`), inverso `_inverse_bar` (`:1346-1349`). Las aserciones usan `sorted(log)` → **ciegas al orden**. Además, como la restricción nombra `bar` (invertido), con el flujo de la fuente corre una vez tras el inverso — igual que hoy. **No observa el cambio** (siguen verdes).
- `tests/unit/orm/test_determine_inverse.py:135-205` sobre `crm.lead` (`addons/crm/models/crm_lead.py:165`, `models.BaseModel`): singleton; `test_two_fields_sharing_one_inverse_call_it_once` (`:191-205`) exige una sola llamada por grupo — se conserva si el despacho se mueve a `BaseModel.write` con el mismo agrupamiento. Riesgo de regresión si el inverso se despachara dos veces (mixin + BaseModel).
- `tests/integration/test_orm/test_constraints.py` y `tests/unit/hr_skills/*` (FLOW.md §7): restricciones sin inverso; con `inverse_fields = []` la primera validación es idéntica a la actual. La segunda (`_validate_fields([])`) no corre nada.
- Subconjunto derivado (comando citado):
  `grep -rlE "_validate_fields|determine_inverse|test_orm.compute.inverse|_check_constraint|_inverse_" --include=*.py tests/ | sed 's|/[^/]*$||' | sort | uniq -c`
  → 18 directorios; los de mayor peso: `tests/unit/orm` (16), `tests/integration/base` (5), `tests/unit/base` (3), `tests/integration/test_orm` (2), más uno en `stock`, `crm`, `account`, `purchase`, `sale_timesheet`, `base_address_extended` (2), `base_vat`, `base_sparse_field`, `analytic`, `authz_timeout`, `authz_totp`, `account_fleet`, `tools`, `fixtures`.

## 4. Contrato

### 4.1 Ediciones (todas en `src/orm/models.py`)

**(a) `RecordLoaderMixin.write` (`:3046-3236`)** — cuerpo cambia en una sola guarda: el bucle `for fields in determine_inverses.values(): fields[0].determine_inverse(self)` (`:3227-3228`) se ejecuta **sólo** si `not hasattr(type(self), '_from_ids')` (misma guarda que ya usa la validación en `:3232`). Un modelo Django conserva su flujo por fila sin cambio. Docstring/comentario: el `BaseModel` despacha en su `write` (`:4493`).

**(b) `BaseModel.write` (`:10665-10692`)** — reemplazar la validación única por el flujo de la fuente:
```python
for record in self:
    super(BaseModel, record).write(vals)
determine_inverses = self._group_written_inverses(vals)   # ≙ :4399,:4416
inverse_fields = [field.name for fields in determine_inverses.values()
                  for field in fields]                     # ≙ :4490
real_recs = self.filtered('id')                            # ≙ :4461
protected = self._protected_while_writing(vals)            # ≙ :4401,:4419-4430
with env().protecting(protected, self):                    # ≙ :4440
    real_recs._validate_fields(vals, inverse_fields)       # ≙ :4491
    for fields in determine_inverses.values():             # ≙ :4493
        for field in fields:                               # ≙ :4494-4497
            if (not getattr(field, 'store', True)
                    and (not getattr(field, 'inherited', False)
                         or field.type not in ('one2many', 'many2many'))
                    and any(field._cache_missing_ids(real_recs))):
                field.write(real_recs, vals[field.name])
        try:
            fields[0].determine_inverse(real_recs)         # ≙ :4501
        except AccessError as error:                       # ≙ :4502-4511
            if getattr(fields[0], 'inherited', False):
                ...reenvolver con el mensaje de la fuente...
            raise
    real_recs._validate_fields(inverse_fields)             # ≙ :4514
return True
```
Notas de implementación (verificar al escribir, no supuestas): (i) `_group_written_inverses` y `_protected_while_writing` son métodos del mixin que leen `model_field_registry(type(self))` (`:3397-3425`, `:3314-3340`) — operan sobre la clase, válidos sobre un recordset; (ii) confirmar que `field.write(records, value)` existe para un campo no almacenado en este árbol antes de portar `:4494-4497`; si no existe, ese paso se declara divergencia con condición de cierre en vez de inventarlo; (iii) `env`/`AccessError`/`_` ya importados en el módulo — comprobar con grep; (iv) `self.modified(vals)` y el resto siguen en el mixin, por fila, antes de la validación — divergencia preexistente, fuera de esta unidad.

**(c) `DefaultGetMixin._create` (`:1200-1289`)** — tras el bloque de validación (`:1279-1287`) y antes de `return records` (`:1289`): `records.check_access('create')` ≙ `:4950`. Para el modelo Django `records` es el `QuerySet`/lista que `_create` devuelve: usar la misma forma que `create` (`:953`, `AccessQuerySet`) o `cls._from_ids(...)` para el `BaseModel` — medir qué tipo tiene `records` en `:1289` antes de escribir la línea.

**Funciones cuyo cuerpo cambia:** `RecordLoaderMixin.write`, `BaseModel.write`, `DefaultGetMixin._create`. `_validate_fields`, `create`, `_group_written_inverses`, `_protected_while_writing`, `determine_inverse`: sin cambio.

### 4.2 Pruebas rojas — `tests/unit/orm/test_write_validation_order.py`
Sobre `test_orm.compute.inverse` con un registro de orden **no ordenado** (`log` sin `sorted`). Para los casos que necesitan una restricción que sólo nombre `baz`, parchear temporalmente un método `@constrains('baz')` en el colector (`registry.constraint_methods`) o, preferible, añadir al modelo de prueba un segundo método `_check_baz_only` gobernado por `context['log_baz']` — **eso toca `src/addons/test_orm/models/test_orm.py`, que no está en `owned`**: ver §5.

1. *Restricción de no invertido antes del inverso.* Given un registro y una restricción que sólo nombra `baz`, When `write({'baz': 'x', 'bar': 'y'})` con log, Then `log == ['constraint_baz', 'inverse', ...]` (la de `baz` precede a `inverse`). Hoy: `['inverse', 'constraint_baz']` → ROJO.
2. *Una restricción de no invertido que levanta corta el inverso.* Given `@constrains('baz')` que levanta `ValidationError`, When `write({'baz': 'malo', 'bar': 'y'})` dentro de `assert_raises(ValidationError)`, Then `'inverse' not in log`. Hoy el inverso ya corrió → ROJO.
3. *Restricción que nombra un invertido corre después, una vez.* Given `@constrains('bar','baz')` (la existente), When `write({'bar': 'Ho', 'baz': 'Hu'})`, Then `log == ['inverse', 'constraint']` (sin `sorted`, una sola `constraint`). Hoy verde — es el control positivo que debe seguir verde (y cae si se retira el `excluded_names` de la primera pasada: correría dos veces).
4. *Inverso una vez por grupo sobre el lote.* Given dos registros, When `(r1 | r2).write({'bar': 'z'})` con un inverso que anota `len(self)`, Then se anota `[2]` una vez. Hoy `[1, 1]` → ROJO.
5. *`_create` comprueba acceso tras validar.* Given un usuario sin permiso `create` sobre el modelo y una restricción que levanta sobre los valores, When `create(...)`, Then levanta `AccessError` en `create` antes (`:953`, igual que la fuente `:4640`) — este caso no discrimina `:4950`. Discriminante real: espiar `check_access` sobre el recordset y afirmar que `_create` lo llama con `'create'` después de `_validate_fields` (orden de llamadas registrado). Hoy ninguna llamada desde `_create` → ROJO.

Creación (ya alineada, `:1098-1100`): un caso de control `create({'baz': 'x', 'bar': 'y'})` con la restricción de `baz` — en la fuente la de almacenados corre en `_create` (`:4949`) **antes** del inverso de `create`; afirmar `log` empieza por `constraint_baz`. Debe estar verde hoy; si está rojo, la premisa de §2.4 es falsa y se reabre.

### 4.3 Anulación
- Retirar la exclusión (`real_recs._validate_fields(vals)` sin `inverse_fields`) → cae exactamente el caso 3 (restricción dos veces).
- Mover la primera validación después del inverso → caen 1 y 2.
- Retirar la guarda `_from_ids` en (a) → cae `test_two_fields_sharing_one_inverse_call_it_once` (doble despacho) y el caso 4 cambia.
- Retirar `check_access('create')` de `_create` → cae el caso 5.
Tras cada anulación: restaurar, `git diff --stat` vacío y borrar `__pycache__` antes de leer (regla de bytecode de `niveles-de-retencion.md`).

### 4.4 Subconjunto a ejecutar (cuando el gate en curso termine)
`uv run pytest -q --reuse-db -p no:cacheprovider tests/unit/orm/test_write_validation_order.py tests/integration/test_orm/test_compute_inverse.py tests/unit/orm/test_determine_inverse.py tests/integration/test_orm/test_constraints.py tests/unit/hr_skills`, y luego `-n 4` sobre los 18 directorios del comando de §3 (cambio en `BaseModel.write` = mecanismo transversal del ORM espejado: la suite completa es obligatoria antes del PR por `alcance-de-la-suite.md`).

## 5. Riesgos y bloqueos

- **BLOQUEADO (alcance):** los casos 1, 2 y el control de creación necesitan una restricción que nombre sólo un campo no invertido. `test_orm.compute.inverse` sólo tiene `@constrains('bar','baz')`. Opciones: (i) ampliar `owned` a `src/addons/test_orm/models/test_orm.py` para añadir un método gobernado por contexto (sin columna nueva → sin migración), o (ii) registrar el método en la prueba mediante el colector. Decide quien despacha; (ii) acopla la prueba a internos de `registry.constraint_methods`.
- **DESCONOCIDO:** si `field.write(records, value)` existe para campos no almacenados en este árbol (`:4494-4497`). Condición de cierre: `grep -n "def write" src/orm/fields.py` y leer su firma. Si no existe, se declara divergencia en el docstring en vez de portar ese paso.
- **DESCONOCIDO:** tipo de `records` al final de `_create` (`:1289`) para modelos Django — decide qué `check_access` aplica. Condición: leer `:1240-1289`.
- **Riesgo:** mover el inverso fuera del `protecting` por fila al de recordset — si un `modified` posterior (en el mixin, por fila) invalida el valor de un campo no almacenado antes de que `BaseModel.write` despache, el inverso lee vacío; el paso `:4494-4497` existe en la fuente precisamente para eso. Por eso no es opcional.
- **Riesgo:** `self.filtered('id')` — confirmar que `filtered` (`:10423`) acepta una cadena en este árbol; si no, `self.filtered(lambda record: record.id)` como en `:9578`.
- **Riesgo:** `_check_company` sigue por fila dentro del mixin, no al final (`:4516-4517`) — divergencia preexistente, no la introduce esta unidad; declararla, no arreglarla aquí.
- Las `xfail(strict)` de SQL de `test_compute_inverse.py:27-30` siguen fuera (dependen de retirar `save()`), y este cambio no debe hacerlas pasar: si una pasa, `strict` la delata.

## Decisión del orquestador (2026-11-25)

- Confirmado contra `odoo19c: models.py:1253-1268`: un check corre si alguno de
  sus campos está en `field_names` y NINGUNO en `excluded_names`, así que
  `@constrains('bar','baz')` queda fuera de la primera pasada y corre una vez
  tras el inverso (caso 3 correcto).
- Punto 7: NO se añade una restricción a `src/addons/test_orm/models/test_orm.py`;
  ese modelo espeja `odoo19c: odoo/addons/test_orm/models/test_orm.py:548-569`,
  que sólo declara `('bar','baz')`, e inventarle un método rompería la
  fidelidad. Antes de escribir los casos 1-2: buscar en el árbol un modelo real
  con un campo inverso y un `@constrains` sobre otro campo; si no existe, la
  prueba añade el check por `_constraint_methods` (atributo con el mismo nombre
  que la fuente) y lo restaura en `finally`.
- Los tres puntos del 8 se miden antes del RED.

## Contrato final (orquestador, 2026-11-25, leído en odoo19c models.py:4461-4518)

Orden de la fuente dentro del alcance de protección: escribir los campos
(`field.write(self, value)` por `write_sequence`), `self.modified(vals)`,
flush de `_parent_name` si aplica, `real_recs._validate_fields(vals,
inverse_fields)`, y por cada grupo de inversos: reescribir los no almacenados
que perdieron la caché y `fields[0].determine_inverse(real_recs)` (envolviendo
el `AccessError` de un heredado). Tras el bucle, `_validate_fields(
inverse_fields)`. Fuera del alcance, `_check_company(list(vals))` si
`_check_company_auto`.

Puerto:

- `RecordLoaderMixin.write` despacha el inverso y valida sólo para filas de
  Django (`not hasattr(type(self), '_from_ids')`, la guarda que ya usa la
  validación). Para un `BaseModel` devuelve los grupos de inversos que
  determinó, para que `BaseModel.write` los despache una vez por lote.
- `BaseModel.write`: escribe cada registro sin inverso, valida
  `(vals, inverse_fields)`, despacha cada grupo una vez sobre
  `self.filtered('id')` dentro de `env().protecting(...)` de esos campos, y
  valida `inverse_fields`.
- Los tres puntos del 8, medidos por lectura: `Field.write(records, value)`
  existe en `fields_relational.py:3336` y `fields_properties.py:612`, no en
  `Field` base: la reescritura de no almacenados se mide antes del RED;
  `filtered` acepta cadena (por confirmar con una prueba); el `check_access(
  'create')` de `_create` es una pieza aparte del mismo contrato (`:4950`).
- `_check_company` por lote: fuera de esta unidad (declarado en el diseño).

## Pruebas finales (orquestador, 2026-11-25)

La prueba de la referencia (`odoo19c: test_orm/tests/test_fields.py:822-850`,
`test_15_constraint_inverse`) compara con `assertCountEqual`: no fija el orden,
y su modelo sólo declara `@api.constrains('bar', 'baz')`. Casos de
`tests/unit/orm/test_write_validation_order.py`:

1. Con el modelo tal cual: escribir `bar` en DOS registros llama al inverso
   una vez (el `log` lleva un solo `'inverse'`); hoy, una por registro.
2. Con un check `@api.constrains('baz')` colgado en la clase por la prueba (y
   retirado en `finally`, con `clear_marked_methods` antes y después: es el
   mecanismo por el que un addon añade una restricción), escribir `bar` y
   `baz`: el `log` en orden es `['constraint-baz', 'inverse', 'constraint']`.
3. Si ese check falla, el inverso no corre (`log` sin `'inverse'`).
4. Control: escribir sólo `baz` da `['constraint-baz', 'constraint']` y ningún
   inverso.

Anulación: sin el despacho por lote caen 1 y 2; sin la primera validación con
exclusión caen 2 y 3.

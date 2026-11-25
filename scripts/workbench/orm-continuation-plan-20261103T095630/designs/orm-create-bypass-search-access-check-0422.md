# TASK-API-0422 — check de `bypass_search_access` en `create` (diseño)

Investigación de sólo lectura. Referencia: `odoo19c` =
`/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0`. Puerto: `/home/user/kaupamex-api`.
No se ejecutó pytest, ni Django, ni git de escritura.

## 1. Referencia

`odoo19c: odoo/orm/models.py:4664-4689` — bucle de clasificación de `create`, por registro y por clave:

```python
for key, val in vals.items():
    field = self._fields.get(key)
    ...
    if field.store: stored[key] = val
    if field.inherited:
        inherited[field.related_field.model_name][key] = val
    elif field.inverse and field not in precomputed: ...
    if field.compute and (not field.readonly or field.precompute): protected.update(...)
    if field.type == 'many2one' and field.bypass_search_access and not self.env.su:
        self.env[field.comodel_name].browse(field.convert_to_cache(val, self)).check_access('read')
```

Contexto exacto:
- Está **dentro** del `for key, val` (`:4671`), después de la protección de computados, y **antes** de crear
  los padres de `_inherits` (`:4691-4706`) y de `_create` (`:4709`).
- Sólo `many2one` (incluye el delegado: `delegate` implica `bypass_search_access`,
  `odoo19c: odoo/orm/fields_relational.py:257-259`). Los x2many no se comprueban aquí.
- Un campo heredado (`field.inherited`) también pasa por la condición si es m2o con bypass del padre; en la
  práctica el delegado es un campo **propio** del hijo, así que se comprueba cuando el llamador **da** el id del
  padre. Si no lo da, no está en `vals` y no hay check (el padre se crea después).
- `val` vacío (`False`) → `convert_to_cache` da `None` → `browse(None)` vacío → `check_access` sobre vacío no
  falla. No hay rama explícita: el vacío pasa por construcción.
- `env.su` → no hay check.

**El gemelo en `write` existe**, pero no en `models.py`: vive en `Many2one.write`,
`odoo19c: odoo/orm/fields_relational.py:400-411`, y envuelve el error:
`AccessError(_("Failed to write field %s", self) + "\n" + str(e))`. `grep -n bypass_search_access odoo/orm/models.py`
sólo da `:2064` (read_group) y `:4687` (este).

**En el puerto el gemelo de `write` NO existe**: `grep -rn bypass_search_access src/orm` da sólo la declaración
(`fields_relational.py:246,292,863-878`), dominios (`fields_relational.py:2504,2718`, `domains.py:2838`),
`inherits.py:263` y `models.py:7999` (read_group). Ningún `write` lo consulta. → sucesor (§5).

## 2. Puerto

- `create`: `DefaultGetMixin.create`, `src/orm/models.py:864-866` (decoradores + `def`). `BaseModel` hereda de
  `DefaultGetMixin` (`src/orm/models.py:6934`); no hay otro `def create(` en `models.py`.
- Bucle de clasificación: `src/orm/models.py:996-1024`; `for key, val in vals.items():` en `:1001`;
  `field, origin = found` y `continue` para heredados (`:1006-1009`); protección en `:1019-1020`;
  `protected.update(_protected_on_create(...))` y `data_list.append(data)` después del `for`.
- Padres de `_inherits`: `:1027-1048`; `_create`: `:1051`.
- Docstring que declara la divergencia: `src/orm/models.py:924-928`. **Su premisa es falsa hoy**: dice
  "`grep -rn bypass_search_access src addons` → 0"; medido, `src/orm/inherits.py:263` marca cada FK delegado con
  `bypass_search_access(fk_field)` (helper en `src/orm/fields_relational.py:867-878`), y el atributo está en la
  clase de Django (`fields_relational.py:863-864`: `ForeignKey`/`ManyToManyField` = False por defecto).
  Esa viñeta se retira en el mismo cambio.
- `_create_field_lookup` (`src/orm/models.py:1444-1469`) devuelve el campo por `name` **o por `attname`**
  (`partner` / `partner_id`), así que `val` puede ser instancia, entero o `None/False`.
- `su`: `orm.environments.is_su()` (`src/orm/environments.py:207-209`, ContextVar `_su`, default False `:148`);
  ya importado/usado en `models.py` (`check_access` `:443`).
- `check_access('read')`:
  - Recordset de acceso: `AccessQuerySet.check_access` (`src/orm/models.py:437-448`) — ACL primero, luego
    `ir.rule` (`_check_access`, `:409-435`); no comprueba nada bajo `is_su()`.
  - Patrón existente para "fila de Django o recordset": `_check_delegate_access` en
    `src/orm/inherits.py:131-155`: si la instancia tiene `check_access` lo usa; si no,
    `type(delegate)._default_manager.filter(pk=...)` y `check_access` **sólo si el queryset lo tiene**; si no,
    no comprueba (silencioso). Mismo criterio que debe seguir este check.
- Many2one en el puerto = `ForeignKey` (incluye `OneToOneField`, subclase; ojo: `OneToOneField.many_to_one` es
  False, así que el discriminador es `isinstance(field, ForeignKey)`, no `field.many_to_one`).

## 3. Consumidores (dónde dispararía)

Ningún campo declara `bypass_search_access=True` a mano en `src/` ni `addons/` (el grep sólo da la declaración,
tests y `inherits`). Los únicos portadores reales son los **FK delegados** que pone `apply_inherits`
(`src/orm/inherits.py:255-263`, invocado en `:396`). Modelos con `_inherits` (grep `^\s*_inherits\s*=`):
`src/addons/base/models/res_users.py` (ResUsers, `DefaultGetMixin`, `:476`), `src/addons/base/models/ir_cron.py`
(IrCron, `:397`), `src/addons/test_orm/models/test_orm.py` (`:647`, `:843`),
`addons/product/models/product_product.py` (`product_tmpl_id`, `:132`; `BaseModel`, `:111`),
`addons/product/models/product_document.py` (`:27`), `addons/website/models/website_page.py` (`:135`),
`addons/account/wizard/setup_wizards.py`.

Dispara cuando un **no-su** crea uno de esos registros **dando** el id del padre sin permiso de lectura sobre él.
Es la conducta de la referencia. Los tests de `create` existentes corren bajo `sudo()`
(`tests/unit/orm/test_create.py:49-144`), así que no caen. Candidatos a revisar (no medido si son no-su con
padre dado): 47 archivos de `tests/` nombran `ResUsers.create|IrCron.create|ProductProduct.create`
(`grep -rln ... tests | wc -l`). Lo decide el subconjunto derivado del §4, no esta lectura.

## 4. Contrato

### Edición (una función cambia de cuerpo + un helper nuevo)

1. `src/orm/models.py` — helper de módulo nuevo, junto a `_creation_flags` (`:1387`):

```python
def _check_bypassed_comodel_read(field, value):
    """El comodelo de un many2one con ``bypass_search_access``, leído antes del alta.

    ≙ ``odoo19c: odoo/orm/models.py:4686-4687``. ``convert_to_cache`` se reduce a
    sacar el pk: instancia → ``pk``, entero → él mismo, vacío → nada que comprobar.
    Fila de un modelo sin ``check_access`` en su manager: no se comprueba, igual
    que ``orm.inherits._check_delegate_access``.
    """
    pk = getattr(value, 'pk', value)
    if not pk:
        return
    rows = field.related_model._default_manager.filter(pk=pk)
    if hasattr(rows, 'check_access'):
        rows.check_access('read')
```

2. `DefaultGetMixin.create` (`src/orm/models.py:866`), en el bucle, tras `protected.update(_computed_group(field))`
   (`:1020`), al mismo nivel que el `if compute`:

```python
if (isinstance(field, ForeignKey)
        and getattr(field, 'bypass_search_access', False)
        and not is_su()):
    _check_bypassed_comodel_read(field, val)
```

   (`ForeignKey` llega por el `from django.db.models import *` de `:64`; `getattr` porque `found` puede ser una
   relación inversa sin el atributo — `_creation_flags`, `:1391-1398`.)
3. Docstring de `create`: retirar la viñeta `:924-928` y añadir el paso al listado numerado ("check de lectura del
   comodelo de un many2one con `bypass_search_access`, `:4686-4687`").

No se reutiliza `_check_delegate_access` importándolo: `inherits` importa de `orm.fields_relational`; que
`models.py` importe `orm.inherits` no está medido como libre de ciclo (DESCONOCIDO), y el helper son 6 líneas.

### Pruebas rojas — `tests/unit/orm/test_create_bypass_search_access.py`

Fixture (patrón de `tests/unit/orm/test_related_traversal_access.py:52-80`): grupo + usuario `reader` +
`ir.model.access` read/create sobre `test_orm.related_foo` y `test_orm.related_bar`; `ir.rule` sobre
`test_orm.related_bar` con `domain_force="[('name','!=','secret-bar')]"`; barras `secret-bar` y `open-bar`
creadas bajo `sudo()`. Campo: `TestOrmRelatedFoo.bar_id` (`src/addons/test_orm/models/test_orm.py:546-547`),
con `bypass_search_access=True` puesto en el test y restaurado en `finally` (patrón de
`tests/unit/orm/test_domain_any_with_rights.py:58-68`).

1. **Given** bypass activo, `user_scope(reader)` sin su; **When** `RelatedFoo.create([{'name': 'x', 'bar_id': secret_bar}])`;
   **Then** `AccessError`, y no se creó ninguna fila foo.
2. Igual que 1 pero `bar_id=secret_bar.pk` (vía `attname`/entero) → `AccessError`.
3. **Given** bypass activo, mismo usuario **en `sudo()`**; **When** create con `secret_bar` → **Then** pasa.
4. **Given** bypass **inactivo** (default False); **When** create no-su con `secret_bar` → **Then** pasa
   (la referencia no comprueba en `create` sin bypass).
5. **Given** bypass activo; **When** create no-su con `bar_id=None` y con `open_bar` → **Then** pasan.

### Anulación

Retirar la llamada del punto 2: caen exactamente 1 y 2; sobreviven 3, 4, 5. Restaurar, borrar `__pycache__`
(`find src tests -name __pycache__ -type d -exec rm -rf {} +`), `git diff --stat` vacío.

### Subconjunto derivado

```bash
grep -rlE "bypass_search_access|_inherits|DefaultGetMixin|\.create\(\[" --include=*.py tests/ \
    | sed 's|/[^/]*$||' | sort | uniq -c
```
Mínimo: `tests/unit/orm/` + `tests/integration/test_orm/` + los directorios de `res_users`, `ir_cron`,
`product` que salgan del grep. `create` es mecanismo transversal (ORM espejado): la regla pide además la suite
completa antes de PR.

## 5. Riesgos y abiertos

- **Riesgo funcional real:** todo alta no-su de `res.users`, `ir.cron`, `product.product`, `product.document`,
  `website.page` con padre explícito pasa a exigir lectura del padre. Correcto según referencia; puede destapar
  tests no-su con fixtures sin ACL del padre. Se mide con el subconjunto.
- **Comodelos sin `AccessQuerySet`** (manager plano de Django): el check es no-op silencioso, igual que
  `_check_delegate_access`. DESCONOCIDO cuántos FK con bypass apuntan a uno. Condición de cierre: listar
  `field.related_model._default_manager` de los FK delegados y ver si su queryset tiene `check_access`
  (requiere `django.setup()`, prohibido aquí).
- **Id inexistente:** `_check_access` evalúa `Rule._get_failing(...).exists()` (`models.py:428-430`) sobre el
  filtro; un pk que no existe da conjunto vacío → no falla (en la referencia tampoco falla aquí; fallaría luego).
- **Mensaje de error:** la referencia no envuelve el error en `create` (sí en `write`). No envolver.
- **Sucesor obligatorio — gemelo en `write`:** `Many2one.write` de `odoo19c: fields_relational.py:407-411` no
  tiene contraparte en el puerto (`DefaultGetMixin.write`/`BaseModel.write`, `src/orm/models.py:3046`, sin
  consulta del atributo). Registrar TASK sucesora con cita durable antes de cerrar 0422.
- **Docstring falso:** `src/orm/models.py:924-928` afirma 0 portadores; hay N vía `inherits`. Corregirlo es parte
  de la unidad (estado heredado incorrecto).

## Revisión del orquestador (2026-11-25)

- DESCONOCIDO del ciclo de imports, cerrado por lectura: `src/orm/inherits.py:77-88`
  importa sólo `orm.environments`, `orm.fields_relational`, `orm.registry` y
  `orm.utils`, y ninguno de los cuatro importa `orm.models` (grep de
  `^(from orm\.models|from orm import models|import orm\.models)`: 0 en cada uno).
  Se reutiliza `inherits._check_delegate_access` (`:131`) en vez del helper nuevo.
- Sucesor obligatorio antes de cerrar 0422: el gemelo de `Many2one.write`
  (`odoo19c: fields_relational.py:407-411`, "Failed to write field").

## Contrato final (orquestador, 2026-11-25)

Se revierte la nota anterior: `inherits._check_delegate_access(delegate)`
recibe una **instancia** del padre (`delegate.pk`, `type(delegate)`), y en
`create` el valor del Many2one llega como entero, instancia de Django o
recordset. Reutilizarla obligaría a fabricar instancias sin fila. Se escribe el
helper del diseño, `_check_bypassed_comodel_read(field, value)`, con el mismo
patrón (`AccessQuerySet` del manager del comodelo; no-op bajo `is_su()`), sin
importar `orm.inherits` (no hay ciclo, pero tampoco hace falta).

Funciones cuyo cuerpo cambia en `src/orm/models.py`: `DefaultGetMixin.create`
(la llamada en el bucle de clasificación y el docstring falso de `:924-928`);
nueva `_check_bypassed_comodel_read`.

Sucesor registrado como fila del plan, no como prosa: el gemelo de
`Many2one.write` (`odoo19c: fields_relational.py:407-411`,
"Failed to write field") es la unidad `orm-write-bypass-search-access-check-0422`.

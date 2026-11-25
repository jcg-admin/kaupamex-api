# TASK-API-0404 — guarda `ondelete='restrict'` hacia `IR_MODELS` ciega a la etiqueta de Django

Diseño listo para implementar. Investigación de sólo lectura: sin pytest, sin
base de datos, sin escritura en ningún repo.

## 1. Referencia (odoo19c — gobierna)

- `odoo19c: odoo/orm/fields.py:37-40` — la tupla:
  `IR_MODELS = ('ir.model', 'ir.model.data', 'ir.model.fields',
  'ir.model.fields.selection', 'ir.model.relation', 'ir.model.constraint',
  'ir.module.module')`.
- `odoo19c: odoo/orm/fields_relational.py:274-282` — default de la política
  (`'restrict' if self.required else 'set null'`, con la rama transitoria).
- `odoo19c: odoo/orm/fields_relational.py:283-288` — `'set null'` + required →
  `ValueError`.
- `odoo19c: odoo/orm/fields_relational.py:289-294`, verbatim:

  ```python
  if self.ondelete == 'restrict' and self.comodel_name in IR_MODELS:
      raise ValueError(
          f"Field {self.name} of model {model._name} is defined as ondelete='restrict' "
          f"while having {self.comodel_name} as comodel, the 'restrict' mode is not "
          f"supported for this type of field as comodel."
      )
  ```

  En la fuente `comodel_name` es siempre el `_name` punteado: no hay segundo
  vocabulario. Nota: la guarda corre DESPUÉS del default (`:274-282`), así que
  un m2o **requerido sin `ondelete`** hacia `ir.model` también levanta en la
  fuente (ver §5, riesgo R2).

## 2. Puerto — estado medido

- `src/orm/registry.py:247-250` — `IR_MODELS` idéntica a la fuente (punteada).
- `src/orm/fields_relational.py:1221-1311` — `_apply_ondelete(args, kwargs)`:
  - `:1250-1267` sin `ondelete` → default; retorna temprano, **sin** guarda de
    `IR_MODELS`.
  - `:1293-1296` normaliza el destino: `comodel = args[0] if args else None`;
    si es `str` lo usa tal cual, si es clase usa `name_of(comodel)`.
  - `:1297-1302` la guarda: `if declared == 'restrict' and comodel_name in IR_MODELS`.
  - **Defecto 1 (el de la tarea):** `'base.IrModel'` (o `'base.irmodel'`) llega
    como `str` y se compara literal contra la tupla punteada → no está → pasa.
  - **Defecto 2 (adyacente, mismo cuerpo):** si el destino viene por
    `kwargs['to']` y no posicional, `comodel` es `None` y la guarda no mira
    nada (`:1293`).
- `src/orm/fields_relational.py:1550-1556` — `Many2one` llama
  `_apply_ondelete` ANTES de `_translate_comodel`; el comentario lo justifica:
  la guarda compara la cadena punteada.
- `src/orm/fields_relational.py:1366-1398` — `_is_source_name(value)`:
  `'.' in value and value == value.lower()`. Ciego declarado a `label_lower`
  (`'base.irmodel'`), que leería como `_name`.
- `src/orm/fields_relational.py:1424-1462` — `_deferred_comodel`: ya resuelve
  la ambigüedad con `apps.get_model(comodel, require_ready=False)` y captura
  `(LookupError, ValueError)` (`:1447-1461`). Ése es el camino a reutilizar
  para la mitad "ya cargado".
- `src/orm/registry.py:513-519` — `name_of(model)` lee `__dict__['_name']`.
- `src/orm/registry.py:522-525` — `model_by_name(name)`.
- `src/orm/registry.py:528-565` — `model_by_key(key)`: acepta `_name` o
  etiqueta de Django, pero con `apps.get_model(app_label, model_name)`
  (require_ready=True por defecto → `check_models_ready`), inutilizable en la
  Fase 2 de carga. **No** se usa; se usa la forma de `_deferred_comodel`.
- `django/apps/registry.py:188-206` (paquete instalado) — `get_model(...,
  require_ready=False)` sólo exige `check_apps_ready`; acepta `'app.Model'` y
  el nombre de modelo es insensible a caja (`:194`), así que
  `'base.irmodel'` y `'base.IrModel'` resuelven a la misma clase.
- `src/addons/base/models/ir_model.py:345,358` — `class IrModel` con
  `_name = 'ir.model'` (app `base`). Los otros seis: `:890` `ir.model.fields`,
  `:1842` `ir.model.fields.selection`, `:2244` `ir.model.constraint`, `:2476`
  `ir.model.relation`, `:2960` `ir.model.data`; `ir_module.py:189`
  `ir.module.module`.
- **Fase diferida existente:** `src/orm/fields.py:2259-2266` —
  `_field_contribute_to_class` invoca `field.setup_nonrelated__(self, cls)` con
  la clase ya construida. Hoy lo cuelga sólo `Many2one` cuando la política salió
  del default (`fields_relational.py:1605-1611`). Y `_setup_nonrelated`
  (`:1313-1350`) ya usa `lazy_related_operation` (`:1338-1348`) cuando
  `field.remote_field.model` sigue siendo `str` — ése es "el mismo camino
  diferido" para la mitad "todavía no cargado".

### ¿Es resoluble el destino en el momento de `_apply_ondelete`?

Depende del orden de carga, y los dos casos existen:

| Caso | Momento de construir | Resolución |
|---|---|---|
| destino ya registrado (p. ej. `mail`, `base_sparse_field` → `base.IrModel`) | `apps.get_model(label, require_ready=False)` devuelve la clase | inmediata → `name_of(cls)` |
| destino aún no importado (modelo de `base` declarado antes que `IrModel` en el mismo addon) | `LookupError` | diferida: fase `setup_nonrelated__` + `lazy_related_operation` |

## 3. Consumidores en el árbol real (¿rompe algo la guarda corregida?)

Medido por AST sobre `src/` y `addons/` (sin migraciones), llamadas a
`Many2one`/`ForeignKey` con destino constante en cualquiera de los siete
modelos, en cualquiera de las dos grafías:

```
src/addons/base/models/ir_rule.py 202 Many2one base.IrModel {'on_delete': 'models.CASCADE'}
addons/mail/models/mail_alias.py 170 Many2one base.IrModel {'on_delete': 'models.CASCADE'}
addons/mail/models/mail_alias.py 199 Many2one base.IrModel {'on_delete': 'models.SET_NULL'}
addons/base_sparse_field/models/ir_model_fields.py 149 Many2one base.IrModelFields {'on_delete': 'models.CASCADE'}
```

Y todas las llamadas `Many2one(..., ondelete=...)` del árbol: 10 en
`src/addons/test_orm/models/test_orm.py` (todas `'cascade'` hacia
`test_orm.*`) y 1 en `addons/account/models/account_payment.py:86`
(`'base.ResPartner'`, `'restrict'`).

**Conclusión: 0 regresiones del árbol real.** Ninguna declaración combina
destino `IR_MODELS` con `ondelete='restrict'`; las cuatro hacia IR usan el
vocabulario de Django (`on_delete=`), que sale por la rama temprana `:1259-1265`
y no toca la guarda.

*Métrica:* llamadas `Many2one`/`ForeignKey` por AST con primer argumento (o
`to=`) constante de cadena.
*Ciega a:* destinos pasados como **clase** (`Many2one(IrModel, ...)`) o como
variable — éstos ya los cubre `name_of` en `:1295-1296` si llevan `ondelete=`;
la AST no los listó.

## 4. Contrato de la edición

### Archivos: `src/orm/fields_relational.py`, `tests/unit/orm/test_many2one_ondelete.py`.

### Funciones cuyo cuerpo cambia

1. **NUEVA** `_restrict_target_name(comodel)` en `fields_relational.py`
   (junto a `_apply_ondelete`). Devuelve el `_name` punteado del destino o el
   centinela `_UNRESOLVED` (nuevo objeto de módulo, o reutilizar
   `tools.misc.SENTINEL` ya importado en `:127`):
   - `None` → `None`;
   - no-`str` (clase) → `name_of(comodel)`;
   - `str` con exactamente un punto → `apps.get_model(comodel,
     require_ready=False)`; si resuelve → `name_of(cls)` (cubre `'base.IrModel'`
     y `'base.irmodel'`); `except (LookupError, ValueError): pass` con el
     comentario `silent OK because` exigido por `check_silent_oks` (mismo
     patrón que `:1453-1459`);
   - si `_is_source_name(comodel)` → `comodel` (`'ir.model'`,
     `'ir.model.fields'`: varios puntos o no resoluble por Django);
   - resto (`'base.IrModel'` aún no cargado) → `_UNRESOLVED`;
   - `'self'` → `None` (sin punto: no es ninguno de los dos vocabularios,
     `:1373-1374`).

   Orden: Django primero, igual que `_deferred_comodel` (`:1447-1462`); hoy
   los dos vocabularios no se solapan (`:1387-1390`), así que el orden no
   desempata nada.

2. **`_apply_ondelete`** (`:1221-1311`):
   - `comodel = args[0] if args else kwargs.get('to')` (cierra el defecto 2);
   - `comodel_name = _restrict_target_name(comodel)`;
   - guarda `:1297`: si `declared == 'restrict' and comodel_name in IR_MODELS`
     → mismo `ValueError` (texto actual intacto);
   - si `declared == 'restrict' and comodel_name is _UNRESOLVED` → devolver un
     quinto valor `restrict_deferred=True` (o ampliar la tupla de retorno:
     `args, kwargs, declared, from_default, guard_deferred`).
   - Actualizar el docstring (caso 3) y el comentario `:1286-1292`: la
     afirmación "sin resolver el modelo" deja de ser cierta para la etiqueta de
     Django.

3. **NUEVA** `_check_restrict_comodel(field, model)` — la fase diferida:
   - si `field.ondelete != 'restrict'` → return;
   - `comodel = field.remote_field.model`; si es `str` →
     `lazy_related_operation(lambda _m, _c, field=field:
     _raise_if_ir_model(field, _m, _c), model, comodel)`; si no →
     `_raise_if_ir_model(field, model, comodel)`.
   - `_raise_if_ir_model(field, model, comodel)`: `if name_of(comodel) in
     IR_MODELS: raise ValueError(...)` con el mensaje completo de la fuente
     (`Field {field.name} of model {name_of(model) or model._meta.label} ...`)
     — aquí sí hay nombre y modelo, que el momento de construir no tiene.

4. **`Many2one`** (`:1550-1611`):
   - desempaquetar el nuevo valor de `_apply_ondelete`;
   - componer la fase: hoy `setup_nonrelated__` es un solo atributo. Si
     `ondelete_from_default` y `guard_deferred` pueden coincidir? **No**: el
     diferido sólo nace con `ondelete='restrict'` declarado, y `from_default`
     sólo con `ondelete` vacío o ausente → son excluyentes, así que basta
     `elif guard_deferred: field.setup_nonrelated__ = _check_restrict_comodel`.
     Dejar un `assert`/comentario que declare la exclusión.
   - Rama `not has_column` (`:1557-1590`) y `company_dependent` (`:1530-1542`):
     la guarda no aplica (no hay FK); `company_dependent` sale antes de
     `_apply_ondelete`, así que no cambia.

### Pruebas rojas (en `tests/unit/orm/test_many2one_ondelete.py`)

Nueva clase `TestTheRegistryGuardSeesBothVocabularies`:

1. **Etiqueta de Django, destino cargado, levanta** — Given `IrModel` cargado
   (pytest-django ya hizo `setup`); When `fields.Many2one('base.IrModel',
   ondelete='restrict', null=True)`; Then `pytest.raises(ValueError,
   match='ir.model')`. (Hoy pasa sin error → ROJO.)
2. **`label_lower`, levanta** — `fields.Many2one('base.irmodelfields',
   ondelete='restrict', null=True)` → `ValueError` con `ir.model.fields`.
   (Hoy `_is_source_name` lo lee como `_name` inexistente → pasa → ROJO.)
3. **Destino por `to=`, levanta** — `fields.Many2one(to='ir.model',
   ondelete='restrict', null=True)` → `ValueError`. (ROJO por defecto 2.)
4. **Control: destino no-IR con etiqueta, pasa** —
   `fields.Many2one('base.ResPartner', ondelete='restrict', null=True)` →
   `remote_field.on_delete is RESTRICT`. (Verde antes y después: discrimina
   que la guarda no levanta por la sola presencia de etiqueta.)
5. **Control: `'set null'` hacia IR con etiqueta, pasa** —
   `fields.Many2one('base.IrModel', ondelete='set null', null=True)` →
   `SET_NULL`.
6. **Diferido** — con `isolate_apps('addons.stock')` (precedente:
   `tests/unit/orm/test_checks_unknown_comodel.py:56`), Given
   `class ReferrerProbe(Model): t = fields.Many2one('stock.LateIrModelProbe',
   ondelete='restrict', null=True)` con `Meta.app_label='stock'` (construye sin
   error: el destino no existe); When se declara
   `class LateIrModelProbe(Model): _name = 'ir.model'` en el mismo registro
   aislado; Then `pytest.raises(ValueError)` alrededor de esa declaración.
   `_register` ignora clases de registros aislados (`registry.py:333-335`), así
   que el `_name` no colisiona con el `IrModel` real; `name_of` lee `__dict__`.

Corregir además el docstring del módulo (`:42-48`): la "ceguera" declarada y
"Sucesor registrado: TASK-API-0404" pasan a "cerrado".

### Anulación (debe discriminar)

- Retirar la resolución por `apps.get_model` en `_restrict_target_name` →
  caen exactamente 1 y 2; 3-6 no cambian.
- Retirar `kwargs.get('to')` → cae sólo 3.
- Retirar la fase `_check_restrict_comodel` (no colgar el hook) → cae sólo 6.
- 4 y 5 no caen en ninguna anulación: son controles negativos. Borrar
  `__pycache__` antes de leer la restauración (`niveles-de-retencion.md`).

### Subconjunto derivado

```bash
grep -rlE "_apply_ondelete|ondelete=|fields_relational|setup_nonrelated__" \
    --include=*.py tests/ | sed 's|/[^/]*$||' | sort | uniq -c
```

Medido (sólo por el patrón `fields_relational|_apply_ondelete|ondelete=`): 40
en `tests/unit/orm`, 9 en `tests/integration/test_orm`, 6 en `tests/unit/base`,
y 1-2 en account, fleet, hr, hr_recruitment, mail, product, stock, website,
scripts, fixtures, integration/base, integration/product. Mínimo obligatorio:
`tests/unit/orm/test_many2one_ondelete.py`,
`tests/unit/orm/test_many2one_ondelete_transient.py` (comparte el hook de fase),
`tests/unit/orm/test_fields_module_symbols.py` (afirma sobre `IR_MODELS`),
`tests/unit/orm/test_restrict_ondelete_*.py`,
`tests/integration/test_orm/`. Como `Many2one` es ORM espejado
(`test-execution-protocol.md`), la suite entera aplica al cerrar el bloque.

## 5. Riesgos, BLOQUEADO y DESCONOCIDO

- **R1 — excepción dentro de `class_prepared`.** El caso diferido levanta en
  `do_pending_operations` al registrarse el destino, es decir, dentro de
  `ModelBase.__new__` de `IrModel`. La señal usa `send` (no `send_robust`) y
  el error aborta la carga — es lo correcto para un error de programa (la
  fuente también levanta en su fase de setup), pero el traceback apuntará al
  destino, no al referente: el mensaje debe nombrar `field.name` y el modelo.
- **R2 — divergencia adyacente, fuera del alcance de la unidad.** La fuente
  aplica `:289` también al `'restrict'` que sale del DEFAULT (`:282` va antes).
  El puerto: (a) con `on_delete=` de Django retorna antes (correcto, no hay
  `ondelete` en esa declaración); (b) sin `on_delete` ni `ondelete` y
  `null=False` (`:1266-1267`) tampoco mira `IR_MODELS`. Medido: 0
  declaraciones del árbol caen en (b) hacia IR (las 4 llevan `on_delete=`).
  Sucesor a registrar con cita durable (`bin/task_ids`) — no se acuña aquí
  (sólo lectura).
- **R3 — `apps.get_model` antes de `apps_ready`.** `check_apps_ready` levanta
  `AppRegistryNotReady` si un `Many2one` se construyera antes de la Fase 1.
  `_deferred_comodel` corre el mismo riesgo y no lo captura (`:1453`); los
  campos sólo se construyen en cuerpos de clase (Fase 2). Mantener la misma
  tupla `(LookupError, ValueError)` por coherencia; DESCONOCIDO si algún guion
  construye un `Many2one` fuera de `setup` — condición de cierre: grep de
  `fields.Many2one(` fuera de cuerpos de clase en `scripts/`.
- **R4 — ampliar la tupla de retorno de `_apply_ondelete`.** Medido: sólo la
  llama `Many2one` (`:1550-1551`); grep `_apply_ondelete` en `tests/` da 0
  archivos. Riesgo bajo; verificar con `grep -rn "_apply_ondelete" src tests`.
- **R5 — migraciones.** Las migraciones declaran `'base.irmodel'` en
  `label_lower` (`:1376-1385`), pero con `models.ForeignKey(...,
  on_delete=...)` de Django, no con `fields.Many2one(ondelete=)`: no pasan por
  la guarda. No medido archivo por archivo; condición de cierre:
  `grep -rn "ondelete=" src/**/migrations addons/**/migrations` → 0 esperado.
- Nada BLOQUEADO.

## Decisión del orquestador (2026-11-25)

R2 NO va a sucesor: es la misma guarda. En la fuente el default se resuelve
antes de la comprobación (`odoo19c: fields_relational.py:280-282`) y la guarda
de `:289` corre sobre el valor resuelto, así que un Many2one `required` sin
`ondelete` hacia un modelo de `IR_MODELS` también rehúsa. En el puerto, la rama
sin clave `ondelete` (`src/orm/fields_relational.py:1255-1266`) retorna antes
de la guarda con la política provisional. La comprobación se cuelga del mismo
punto diferido (`_check_restrict_comodel` en `setup_nonrelated__`) cuando la
política final resulta `'restrict'`, sea declarada o por default; el caso del
`on_delete=` de Django explícito sigue fuera (el llamador fijó la política en
el vocabulario del stack). Caso RED adicional: `Many2one('ir.model',
required=True)` sin `ondelete` rehúsa con el mensaje de la fuente. Medir antes
de implementar que ninguna declaración del árbol cae en ese caso (AST:
Many2one required hacia IR_MODELS sin `ondelete` ni `on_delete`).

## Contrato final (orquestador, 2026-11-25)

La bandera de la fase diferida NO puede ser «el atributo `ondelete` vale
`'restrict'`»: las cuatro declaraciones reales hacia IR (`ir_rule.py:202`,
`mail_alias.py:170,199`, `base_sparse_field/ir_model_fields.py:149`) traen
`on_delete=` de Django y son requeridas, así que su atributo queda
`'restrict'` (rama `:1255-1266`) con una FK `CASCADE`. Leer el atributo daría
un falso positivo sobre el árbol real.

Funciones cuyo cuerpo cambia en `src/orm/fields_relational.py`:

- NUEVA `_restrict_target_name(comodel)`: `_name` punteado del destino, `None`
  sin destino, o `SENTINEL` si aún no resuelve.
- `_apply_ondelete`: lee el destino de `args[0]` o de `kwargs['to']`; rehúsa ya
  si `'restrict'` declarado y el destino resuelto está en `IR_MODELS`; devuelve
  un quinto valor `check_restrict`, verdadero sólo cuando la política la decide
  la fuente (sin `on_delete` de Django) y vale `'restrict'` con el destino sin
  resolver, o sale del default.
- NUEVA `_check_restrict_comodel(field, model)`: con la clase lista, si
  `field.ondelete == 'restrict'` y el comodelo (diferido con
  `lazy_related_operation` si aún es cadena) tiene `_name` en `IR_MODELS`,
  `ValueError` con el mensaje completo de `odoo19c: :289-294`.
- NUEVA `_setup_ondelete_phase(field, model)`: `_setup_nonrelated` y después
  `_check_restrict_comodel` (la decisión transitoria puede cambiar la política a
  `'cascade'`, así que va primero; las dos operaciones diferidas sobre el mismo
  comodelo corren en el orden en que se agendaron).
- `Many2one`: cuelga `_setup_ondelete_phase` si la política salió del default
  y `check_restrict`; `_setup_nonrelated` si sólo salió del default;
  `_check_restrict_comodel` si sólo `check_restrict`.

Pruebas (`tests/unit/orm/test_many2one_ondelete.py`), además de los 1-6 de
arriba: 7) `Many2one('ir.model', required=True)` sin `ondelete` en un modelo
aislado rehúsa al declararse la clase; 8) control: el mismo con `on_delete=`
de Django no rehúsa. Anulación: sin `_check_restrict_comodel` caen 6 y 7.

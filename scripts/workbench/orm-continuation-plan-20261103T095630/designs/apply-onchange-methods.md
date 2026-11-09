# `_apply_onchange_methods` — contrato, ruta de Kaupamex y diseño

Referencia: odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`, alias `odoo19c:`.

## Contrato derivado

| Pieza | Referencia | Contrato observable |
|---|---|---|
| firma | `odoo/orm/models.py:6975` | `_apply_onchange_methods(self, field_name, result, excluded_methods=())`, método de `BaseModel` sobre un registro |
| selección | `:6977` | sólo `self._onchange_methods.get(field_name, ())`, en su orden; los de `excluded_methods` se saltan |
| invocación | `:6980` | `method(self)`: la función recibe el registro; un retorno falso termina ahí |
| valores | `:6983-6986` | cada `key` de `res['value']` que esté en `self._fields` y no sea `id` se asigna con `self[key] = val`; las demás se ignoran |
| avisos | `:6987-6994` | `result['warnings'].add((title or _("Warning"), message or "", type or ""))`: el contenedor es un `OrderedSet`, así que un aviso repetido cuenta una vez |
| errores | — | no hay `try`: una excepción del método sube al llamador |
| registro | `:560-593` | `_onchange_methods` recoge los `@api.onchange` por nombre de campo, más los parciales de `change_default` |
| consumidor | `addons/web/models/models.py:2155-2193` | `result = {'warnings': OrderedSet()}`; por pasada, `visited_onchanges` se pasa como `excluded_methods` y se amplía con los métodos de cada campo; un aviso → `result['warning']` con `type` `'dialog'` por defecto; varios → título `_("Warnings")` |

Pruebas de la referencia que lo ejercitan: `odoo/addons/test_orm/tests/test_onchange.py`
(a través de `onchange`, no del método suelto).

## Ruta de Kaupamex antes del cambio

- Registro: `orm.registry.onchange_methods` (`src/orm/registry.py:1058-1095`),
  sin `change_default` (0 campos lo declaran; tarea #335).
- `BaseModel._onchange_methods` (`src/orm/models.py:5962`) delega en el registro.
- **No existe `BaseModel._apply_onchange_methods`.**
- El único consumidor es `Base.onchange` (`addons/web/models/models.py`), cuyos
  registros son instancias de Django (`CrmStage` no deriva de `BaseModel`).
  Lleva su propia copia por método (`_apply_onchange_method`): contenedor
  `list` con deduplicación a mano y título `_('Aviso')`.

## Responsabilidades

| Responsabilidad | Dueño |
|---|---|
| mapa campo → métodos | `orm.registry.onchange_methods` (sin cambio) |
| despacho y propagación | una función de módulo en `src/orm/models.py` |
| interfaz del registro ORM | `BaseModel._apply_onchange_methods` |
| adaptación Django | `addons/web/models/models.py`: cómo saber si existe el campo y cómo asignarlo (`_model_field`, `_assign`) |

## Diseño

1. `src/orm/models.py`: función de módulo
   `apply_onchange_methods(record, methods, result, excluded_methods,
   has_field, assign, translate)`. Lleva la selección por `excluded_methods`,
   la invocación, la regla de `value` y la de `warning`. Es la única
   implementación del contrato.
2. `BaseModel._apply_onchange_methods(field_name, result, excluded_methods=())`
   la llama con `self._onchange_methods.get(field_name, ())`,
   `self._fields.__contains__`, `self.__setitem__` y `self.env._`.
3. `web`: el bucle pasa a la forma del consumidor de la referencia
   (`visited_onchanges` como `excluded_methods`, ampliado por campo) y llama
   a la misma función con la adaptación Django. El contenedor pasa a
   `OrderedSet`. Se retira `_apply_onchange_method`: su lógica duplicaba el
   contrato.
4. El título por defecto queda en la función: `translate("Warning")`.
   Divergencia de texto declarada: `web` mostraba `'Aviso'`. El literal fuente
   es el de la referencia; la traducción es tarea del catálogo, no del código.

La función de módulo no existe en la referencia: allá el consumidor siempre
es un registro ORM. Aquí hay dos clases de registro y la diferencia es
exactamente cómo se pregunta por un campo y cómo se asigna; el resto es común.

## Pruebas

`tests/unit/orm/test_apply_onchange_methods.py`, sobre registros `new()` de
`test_orm`:

- descubrimiento: `test_orm.discussion._onchange_methods` trae `name`,
  `moderator`, `messages`;
- sobre `test_orm.category`, con `@onchange` declarados en la prueba (la
  semántica que se mide es el despacho, no el método): selección por campo,
  `excluded_methods`, asignación por modificación directa y por `value`,
  claves ignoradas (`id`, campo inexistente), aviso con título por defecto,
  deduplicación, retorno falso y propagación de la excepción;
- la ruta Django la siguen cubriendo `tests/unit/web/test_models_onchange.py`.

Los modelos de `test_orm` con onchange no sirven para la invocación:
`_onchange_messages` lee `message.body`, que aún no está portado
(`test_orm.py:689-700`).

Control de anulación: retirar el cuerpo de `apply_onchange_methods` (o el
método de `BaseModel`) tiene que tumbar las pruebas de invocación y dejar la
de descubrimiento.

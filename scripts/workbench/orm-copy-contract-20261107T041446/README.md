# Contrato de `copy` — flujo de la referencia y adaptación del puerto

Referencia: Odoo 19 Community, `odoo-tools@abe4040ec1`. Unidad:
`orm-models-copy-reference-0485` (TASK-API-0485).

## 1. El contrato de la referencia

| Elemento | En `odoo19c: odoo/orm/models.py` |
|---|---|
| Versión y revisión | Odoo 19 Community, `odoo-tools@abe4040ec1` |
| Módulo y símbolos | `BaseModel.copy_data` (`:5406-5463`), `copy_translations` (`:5465-5528`), `copy` (`:5530-5545`) |
| Firmas | `copy_data(self, default=None) -> list[dict]`; `copy_translations(self, new, excluded=())`; `copy(self, default=None) -> Self` |
| Entradas | un recordset de N registros y un `default` opcional |
| Precondiciones | ninguna: `copy` sobre un recordset vacío devuelve uno vacío |
| Flujo de control | ver abajo |
| Dependencias | `_fields`, `field.copy`, `field.inherited`, `_inherits`, `MAGIC_COLUMNS`, `field.convert_to_write`, `Command.create`/`Command.set`, `_filtered_access('read')`, `create`, `with_context` |
| Consumidores | los `copy`/`copy_data` de cada addon, que llaman `super()` y reciben una lista |
| Valor de retorno | `copy_data`: una lista de dicts, `None` por un registro ya visto; `copy`: los registros nuevos, en el orden de `self` |
| Excepciones | las del `create` (acceso, restricciones) |
| Cambios de estado | registros nuevos y sus líneas `One2many` con `copy=True`; los `Many2many` enlazan los mismos destinos |
| Persistencia y transacción | un `create` por lote; todo en la transacción del llamador |
| Seguridad | sólo se copian los enlaces `Many2many` que el usuario puede leer |
| Pruebas originales | `test_fields.py:2647` (`default` sobre `_inherits` y sobre `One2many` no copia traducciones), `test_onchange.py:989` (atributo `copy` y cómputos) y `:1024` (lote en una consulta) |

Flujo de `copy`:

```
copy(default)
  → with_context(active_test=False).copy_data(default)
      lista negra: MAGIC_COLUMNS + parent_path + FK de _inherits
        (y todo el padre si el default trae el FK)
      fields_to_copy: field.copy, no en default, no en la lista negra
      por registro (guarda __copy_data_seen en el contexto):
        One2many → [Command.create(v) for v in líneas por id .copy_data()]
        Many2many → [Command.set(ids legibles)]
        resto → field.convert_to_write(valor)
  → create(vals_list)
  → por par (viejo, nuevo): copy_translations(nuevo, excluded=default)
      recursión por One2many emparejando por id; traducciones de los
      campos traducibles almacenados
```

## 2. La adaptación del puerto

`CopyMixin` porta la cadena para los modelos que derivan de
`TimeStampedModel` y lo adoptan uno a uno: una instancia, un dict, la guarda
como parámetro `seen` y los hijos `One2many` copiados aparte después del alta
(`copy_children`). Unos quince overrides de addons dependen de esa forma, así
que no se toca.

`BaseModel` es un recordset y no adoptaba `CopyMixin`: `copy` no existía en
sus 43 modelos (`AttributeError` en la rejilla). Se porta en `BaseModel` con
el flujo de la referencia:

| Paso | Adaptación |
|---|---|
| guarda de recursión | `__copy_data_seen` en el contexto, como allá: el contexto congela sus claves, no el `defaultdict` que guarda |
| lista negra | `MAGIC_COLUMNS` + `parent_path` + los FK de `_inherits`, con la misma recursión sobre los padres |
| `One2many` | `Command.create` de las líneas en orden de id, sólo con `copy=True`; el `create` del puerto aplica los comandos del `One2many` declarado |
| `Many2many` | `Command.set` de los ids legibles. Un `Many2many` espejo (`ManyToManyRel`) no lleva atributo `copy`: rige el default de la referencia, `True` |
| escalares | `field.convert_to_write` |
| `active_test` | se pasa como allá: el `_search` del puerto sí filtra por `active` |
| `copy_translations` | el bucle y la recursión por `One2many` se portan; la rama de traducción no tiene nada que copiar, porque la columna guarda un solo idioma (#333) |
| default de `copy` | `_copies`: el atributo `copy`, o el default de la fuente por tipo (`One2many` `False`, `fields_relational.py:869`; el resto `True`, `fields.py:281`). `_fields` incluye las relaciones inversas de Django, que no llevan el atributo: un `ManyToOneRel` no se copia, un `ManyToManyRel` sí |
| `Many2many` a un modelo que no es `BaseModel` | se lee como el gestor de Django; los ids legibles salen de `AccessQuerySet._filtered_access` (`_readable_ids`) |
| `One2many` declarado | se lee hoy como `AccessQuerySet`; `_x2many_records` lo convierte al recordset del comodelo, y rehúsa si el comodelo no es `BaseModel` |

## 3. Lo que el flujo completo destapó fuera de `copy`

- **El `One2many` declarado no se lee como recordset ni aplica su `domain`.**
  `discussion.messages` es un `AccessQuerySet`, y `important_messages`
  (`domain=[('important', '=', True)]`) devuelve los dos mensajes aunque
  ninguno es importante. En la fuente la lectura es el recordset filtrado
  (`One2many.read`). Hallazgo propio, en la iniciativa.
- **`test_orm.message` es un porte parcial**: 6 campos contra más de 15, sin
  `body` ni `author` ni `_check_author`. La rejilla identifica los mensajes
  por `priority`.
- **`test_orm.discussion.message_concat` se declara sin `null=True`**: guarda
  `''` donde la fuente guarda NULL. Queda fuera de la comparación.
- **La razón de `copy_children` en `CopyMixin` caducó**: decía que el
  `Command` del puerto escribe al llamarlo, y hoy devuelve el triple
  (`Command.create({...})` → `(<Command.CREATE: 0>, 0, {...})`). Los modelos
  de `CopyMixin` podrían pasar sus `One2many` por `copy_data` como la fuente;
  sucesor en TASK-API-0485.

## 4. Controles de anulación

Ignorar `field.copy`, saltar el `Many2many`, vaciar el `One2many`, ignorar
el `default` al elegir campos y crear sólo el primero de un lote: cada uno
hace fallar la rejilla. Quedan ciegos, por construcción de la rejilla: el
`convert_to_write` de los escalares (el valor es el mismo), la guarda de
recursión (no hay relación circular), `active_test` (no hay líneas
archivadas), el filtro de enlaces legibles (modo superusuario) y
`copy_translations` (#333).

## 5. Verificación

`tests/unit/orm/test_contract_model_persisted_reference.py` sobre
`orm_refproc_test_orm`: `copy_data` con y sin `default` (incluido un
`default` que pisa el `Many2many`), `copy` de una y de dos discusiones, de un
recordset vacío, y con un `default` que fija el `One2many`.

*Métrica:* el `repr` de cada paso, con ids traducidos a nombres y los
mensajes por `priority` en orden de id (el `test_orm.message` del puerto no
declara `body`).
*Ciega a:* las traducciones almacenadas, la cuenta de consultas del lote y
los modelos de `CopyMixin`.

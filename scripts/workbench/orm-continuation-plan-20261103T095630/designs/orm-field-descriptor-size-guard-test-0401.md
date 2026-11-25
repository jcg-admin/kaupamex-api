# Guarda de tamaño de `FieldDescriptor.__get__` (`orm-field-descriptor-size-guard-test-0401`)

TASK-API-0401. Fila de propuesta: `candidates/orm-field-descriptor-size-guard-test-0401.jsonl`
del commit `fd816c6e` (rama `wt/account-mc2c2`; no está en esta rama, se
leyó con `git show`).

## Lo que dice la referencia

`odoo19c: odoo/orm/fields.py:1641-1661` — `Field.__get__` mide
`len(record._ids)` antes de tocar la caché:

- dos o más ids: `record.ensure_one()` levanta *"Expected singleton"* y
  `assert False, "unreachable"` (`:1653-1658`);
- cero ids: devuelve `convert_to_record(convert_to_cache(False, ...))`, el
  valor nulo del campo (`:1659-1661`);
- un id: sigue hacia los cómputos pendientes y la caché (`:1663` en adelante).

## Lo que tiene el puerto (medido)

- `src/orm/fields.py:1599` — `FieldDescriptor`; la guarda vive en
  `__get__`, bloque `own_ids = getattr(instance, '_ids', None)` con
  `instance.ensure_one()` y `raise AssertionError('unreachable')`, y la rama
  vacía con `_attribute_value(field.convert_to_cache(False, ...))`.
- La primera rama del descriptor (acierto del almacén `__dict__` de Django)
  sólo devuelve directamente cuando `len(ids) == 1`: con dos ids o ninguno el
  valor sembrado en `__dict__` NO se entrega y la lectura cae en la guarda.
- `src/orm/models.py:9776` — `ensure_one` levanta
  `ValueError("Expected singleton: %r" % (self,))`; el `repr` empieza por el
  `_name` del modelo.
- El docstring de `FieldDescriptor` ya no enumera tres ramas (la fila de
  propuesta pedía confirmarlo): sólo describe el enganche nativo de Django.
- Premisa de la fila verificada: no hay prueba que lea un campo llano sobre
  un recordset de dos ids (`grep` de `own_ids` y de `.label` en `tests/`).

## Símbolos

Sólo pruebas: ninguna función del puerto cambia de cuerpo. El control de
anulación retira temporalmente el bloque `own_ids` de
`FieldDescriptor.__get__` y lo restaura desde una copia (`cmp`).

## Pruebas (`tests/unit/orm/test_field_descriptor_size_guard.py`)

Sonda propia `orm.size.guard.probe` (`managed = False`, sin tabla) con un
`fields.Char` `label`; recordsets construidos con `BaseModel._from_ids`, sin
base de datos.

1. dos ids con el valor sembrado en `__dict__`: levanta `ValueError`
   anclado a `Expected singleton: orm\.size\.guard\.probe` — el ancla al
   `repr` separa a `ensure_one` del descriptor de `id`, que también dice
   *"Expected singleton"* pero con `ids=(...)`;
2. dos ids sin valor sembrado: la misma excepción;
3. recordset vacío con el valor sembrado: devuelve `False`, el nulo del
   `Char`, no el valor sembrado;
4. singleton con el valor sembrado: devuelve el valor.

Anulación esperada: caen 1, 2 y 3 (dependen de la guarda); 4 sobrevive.

## Lo que no cierra

Nada de la obligación `:1641-1661`. La rama de acceso por campo
(`:1647-1651`) tiene sus propias pruebas (`test_contract_field_groups_reference.py`)
y queda fuera de esta unidad.

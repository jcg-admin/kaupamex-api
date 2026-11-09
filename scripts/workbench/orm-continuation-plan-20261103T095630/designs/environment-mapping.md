# Unidad 6e-0 — `Environment` como `Mapping`

Autoridad: `odoo19c: odoo/orm/environments.py:40` —
`class Environment(Mapping[str, "BaseModel"])` — y sus métodos de mapeo
`:101-122` (`__contains__`, `__getitem__`, `__iter__`, `__len__`,
`__eq__`/`__ne__`/`__hash__` por identidad), odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389`.

## Hueco medido

`_read_group_groupby_properties` (unidad 6e) llama `self.env.get(comodel)`.
En Kaupamex `Environment` declara los cuatro métodos del protocolo y la
identidad, pero **no** hereda de `collections.abc.Mapping`, así que no tiene
`get`, `keys`, `items` ni `values` (medido:
`AttributeError: 'Environment' object has no attribute 'get'`). No es una
necesidad particular de `read_group`: cualquier consumidor del contrato del
entorno la tiene.

## Decisión

Se adopta la base de la fuente, `collections.abc.Mapping` (como `abc.Mapping`). Los mixins que aporta
(`get`, `keys`, `items`, `values`) se derivan de `__getitem__`, `__iter__` y
`__len__`, que ya existen. `__eq__`, `__ne__`, `__hash__` y `__contains__`
propios prevalecen sobre los de `Mapping` (el `__eq__` de `Mapping`
compararía contenidos; aquí, como en la fuente, es identidad).

Adaptación vigente, sin cambio: `__getitem__` devuelve la clase del modelo
(no un recordset vacío), así que `get` y `values` devuelven clases.

## Casos (`tests/unit/orm/test_environment_mapping.py`)

1. `isinstance(env, Mapping)`;
2. `env.get(nombre)` → la clase; `env.get('no.existe')` → `None` y el
   valor por defecto dado;
3. `list(env.keys()) == list(env)`;
4. dos entornos con los mismos ejes siguen siendo iguales por identidad y
   hashables (no los compara `Mapping.__eq__`).

Anulación: retirar la base `Mapping` hace caer 1-3; el 4 no depende de ella
y debe seguir verde (control de que la identidad no la aporta `Mapping`).

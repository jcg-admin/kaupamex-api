# `Environment.__getitem__` devuelve un recordset (TASK-API-0485)

Estado: diagnóstico medido sobre `c9c7b545`. El diseño de la transición se
decide aquí y se implementa por grupos coherentes.

## Contrato de la referencia

`odoo19c: odoo/orm/environments.py:105-107` (odoo-tools `abe4040ec1`):

```python
def __getitem__(self, model_name: str) -> BaseModel:
    """ Return an empty recordset from the given model. """
    return self.registry[model_name](self, (), ())
```

`env['x']` es **un recordset vacío** con el entorno, no la clase. La fuente
nunca llama al modelo desde la clase: `self.env['res.currency.rate']` en
`models.py:1976` es el recordset.

## Estado aquí

`src/orm/environments.py:929-952` devuelve la **clase** (`MODELS_BY_NAME`) y,
como respaldo, la etiqueta de Django. La diferencia se cubre hoy con dos
mecanismos:

- el descriptor `_on_empty_recordset` (`src/orm/models.py:6168`), aplicado a
  11 métodos, que entrega `owner._from_ids(env(), (), ())` cuando se llaman
  sobre la clase;
- `env['x'].browse(())` en el código que necesita el recordset (13 llamadas
  `_from_ids(env(), (), ())` en `src` y `addons`).

Defecto con forma de ejemplo: `src/orm/models.py:7186` escribe
`self.env['res.currency.rate']()` —instancia la clase— donde la fuente lee
el recordset.

## Consumidores que dependen de la clase (medido)

Instrumento: `probes/env_flow_census.py` (uso directo de `env[...]`, y
`X = env[...]` seguido dentro de su función).

| Uso que exige la clase | Total | Ejemplos |
|---|---|---|
| `X.objects` | 37 (+1 directo) | `src/modules/loading.py:184`, `src/orm/models.py:4737`, `src/orm/fields_relational.py:2294` |
| `X is …` | 15 (+6 directos, todos en tests) | `src/modules/loading.py:137`, `src/orm/models.py:4974` |
| `isinstance(…, X)` | 15 | `src/orm/fields_relational.py:733`, `src/orm/models.py:5898` |
| `issubclass(X, …)` | 8 | `src/orm/models.py:5100`, `:5899`, `:5998` |
| `X(...)` | 6 (+1 directo) | `src/orm/models.py:2244`, `:2611`, `:4301`, `:7186` |
| `X._base_manager` / `_default_manager` | 9 | `src/orm/models.py:1739`, `src/orm/fields_relational.py:714` |
| `type(X)` | 2 | `tests/integration/test_orm/test_env_alias_recordset.py:75` |

Reparto: 50 en `src` + `addons`, 48 en `tests`.

*Métrica:* nodos AST cuyo valor viene de `env[...]` (directo o por una
variable asignada en la misma función) usados en una de esas posiciones.
*Ciega a:* el flujo entre funciones (una clase devuelta y usada en otro
sitio); una variable reasignada con otro origen en la misma función, que
se cuenta igual —el conteo es una cota superior por sitio y una cota
inferior por flujo—; los comodelos de Django (`res.users`, `res.groups`),
que no son `BaseModel` y seguirán devolviendo la clase.

## Lo que el cambio tiene que preservar

1. **Comodelos de Django**: no tienen recordset (`_from_ids`). `env['x']`
   sobre ellos sigue devolviendo la clase. **Divergencia declarada**, con la
   misma razón que en `many2many-write-family.md`: la referencia no tiene
   modelos que no sean `BaseModel`.
2. **El gestor de Django** (`objects`, `_base_manager`): un manager no se
   alcanza desde una instancia (`Manager isn't accessible via … instances`).
   Cada consumidor pasa a `type(records)` o a `records._model_class` (nombre
   a fijar), o se reescribe al método del ORM equivalente.
3. **Identidad e herencia** (`is`, `issubclass`, `isinstance(…, X)`): se
   comparan clases; pasan a `type(env['x'])`.
4. **Llamadas `X(...)`**: instanciar un modelo de Django. Cada una se
   revisa contra la fuente; la de `:7186` es un defecto y se corrige.

## Transición por grupos

| Grupo | Contenido | Prueba |
|---|---|---|
| G0 | `:7186` (`self.env[...]()`) → el recordset, como la fuente | `sum_currency` del `read_group` |
| G1 | los 50 consumidores de `src`/`addons` pasan a no depender de que `env[...]` sea la clase (`type(...)`, métodos del ORM) — sin cambiar todavía `__getitem__` | regresión completa: comportamiento igual |
| G2 | `__getitem__` devuelve `model._from_ids(self, (), ())` para un `BaseModel` | `test_environment_mapping.py` y las 6 aserciones `is` de tests pasan a comparar `type(...)`, con su razón |
| G3 | `_on_empty_recordset` y los `browse(())` defensivos quedan redundantes: se retiran | anulación: retirar G2 hace caer las pruebas de G2 |

G1 antes que G2 porque deja el cambio de contrato en un solo commit
pequeño y reversible; G1 es neutro por construcción y su verde no prueba
nada por sí solo, por eso su control es G2.

## Pendiente

- Medir el flujo entre funciones (clases devueltas por funciones auxiliares
  como `_inherits_parent`).
- Fijar el accesor de la clase desde un recordset (`type(records)` es lo que
  usa la fuente; preferirlo sobre un nombre nuevo).

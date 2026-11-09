# `Field.index` sin índice en la base

Referencia: `odoo-tools@abe4040ec1a45beee90fb694e4eae4453e46b389`, Odoo 19 Community.

## Contrato de la referencia

- `odoo/orm/fields.py:279` — `index: str | None = None`, *"how the field is
  indexed in database"*.
- `odoo/orm/registry.py:831-880` (`check_indexes`): valores admitidos
  `'btree'`, `'btree_not_null'`, `'trigram'`, `True`, `False`, `None`.
  `True`/`'btree'` → índice btree sobre la columna; `'btree_not_null'` →
  btree parcial `WHERE col IS NOT NULL`; `'trigram'` → GIN `gin_trgm_ops`
  (con `unaccent` si es indexable). Un campo traducido sólo admite trigram.
  Se ejecuta al cargar el registro, en cada actualización de módulo.

## Estado de Kaupamex (medido)

- La costura de `Field.__init__` (`src/orm/fields.py:1134-1163`) retira lo que
  Django no conoce: `index` queda como atributo y en `_args__`, pero
  `db_index` sigue en False.
- `Registry.check_indexes` está portado (`src/orm/registry.py:2700`) y sólo
  corre en `init_models`, que las migraciones no usan.
- Campos con `index` y sin índice real en el árbol cargado: cuatro
  (`res.partner.ref`=True, `test_orm.category.parent_path`=True,
  `res.partner.barcode`='btree_not_null',
  `account.analytic.plan.default_applicability`='btree_not_null').

## Diseño

- En la costura, `index` en `(True, 'btree')` sin `db_index` declarado se
  traduce a `db_index=True` — el mismo patrón que `required` → `blank`.
  Django genera la migración del índice btree.
- **Divergencia declarada:** el nombre del índice es el de Django, no el de
  `make_index_name` (`{tabla}__{campo}_index`); `check_indexes` lo buscaría
  por nombre, pero no corre sobre esquemas migrados.
- `'btree_not_null'` y `'trigram'` quedan fuera de esta unidad: piden un
  `Meta.indexes` con condición o una extensión (`pg_trgm`), y su mecanismo
  natural aquí es la contribución del campo a la clase. Se registran como
  abiertos.

## Controles previstos

- Sin la traducción en la costura: cae el caso de `db_index` y la migración
  vuelve a no tener índice (`makemigrations --check` limpio sin ella).

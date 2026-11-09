# Índice parcial de los campos dependientes de empresa

Referencia: `odoo-tools@abe4040ec1a45beee90fb694e4eae4453e46b389`, Odoo 19 Community.

## Contrato de la referencia

- Un campo `company_dependent` toma `index='btree_not_null'` por defecto
  (`odoo/orm/fields.py`, `_setup_attrs`; aquí `src/orm/fields.py:1350`).
- `Registry.check_indexes` (`odoo/orm/registry.py:871-882`): con
  `btree_not_null` y `company_dependent`, la expresión es
  `("col" IS NOT NULL)`, método btree y `WHERE "col" IS NOT NULL`. Nombre:
  `make_index_name(tabla, campo)` = `{tabla}__{campo}_index`
  (`odoo/tools/sql.py:779-781`).
- El optimizador de dominios añade `IS NOT NULL` a la condición para que
  PostgreSQL use ese índice (aquí ya portado, `src/orm/fields.py:1339`).

## Estado de Kaupamex (medido)

- Dos campos dependientes de empresa en el árbol cargado:
  `res.partner.barcode` y `account.analytic.plan.default_applicability`, los
  dos con `index='btree_not_null'` y **ningún** índice en la base.
- `check_indexes` no corre sobre esquemas migrados (H-API-1199).

## Diseño

- `CompanyDependent.contribute_to_class` añade a `cls._meta.indexes` un
  `models.Index` funcional sobre `ExpressionWrapper(Q(col__isnull=False))`
  con `condition=Q(col__isnull=False)` cuando `index == 'btree_not_null'`.
  Django genera la migración.
- **Divergencia declarada de nombre:** Django limita el nombre a 30
  caracteres (`models.E034`) y el de la referencia para
  `default_applicability` mide 50. Se usa un nombre derivado y acotado
  (prefijo de la tabla y el campo con un sufijo hash), estable entre
  ejecuciones.
- Fuera de alcance: `btree_not_null` en campos que no son dependientes de
  empresa (la rama `else` de `check_indexes`, `WHERE col IS NOT NULL` sobre
  la columna) y `trigram`.

## Controles previstos

- Sin la contribución del índice: cae el caso de la tabla y
  `makemigrations --check` propone retirar los dos índices.

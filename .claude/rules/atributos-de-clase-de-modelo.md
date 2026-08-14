# Atributos de clase de modelo — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/atributos-de-clase-de-modelo.md`. Aquí sólo
el invariante operativo:

**Todo modelo declara `_name` y `_description`** con los valores verbatim de la
referencia. Se llaman **atributos de clase de modelo**
(`odoo19c: odoo/orm/model_classes.py:261`, `_init_model_class_attributes`);
`_name` es *el nombre del modelo en notación de punto*, `_description` es *el
nombre informal del modelo* (`odoo/orm/models.py:392-393`, verbatim).

```python
class ProductRemoval(TimeStampedModel):
    _name = 'product.removal'
    _description = 'Removal Strategy'
```

`_description` **no** sustituye a `Meta.verbose_name`, que sigue en español.
`Meta.db_table` debe coincidir con `_name.replace('.', '_')` —lo verifica
`orm.registry.check_table_matches_name()`, hoy 0 divergencias.

**Prospectivo:** modelo nuevo o portado, lleva los dos; modelo existente que se
toca por cualquier motivo, se le añaden. Sin barrido en bloque de los 290
restantes.

**Segunda cláusula — el SITIO del archivo** (H-API-578): antes de crear un
archivo en una raíz espejada (`src/orm` ↔ `odoo/orm`, `src/tools` ↔
`odoo/tools`, `addons/<x>` ↔ `addons/<x>`), **listar la raíz de la referencia**:

```bash
ls $ODOO19C/odoo/orm/     # ¿ya existe el hogar de este símbolo?
```

`check_porte_completo` compara símbolos **dentro de un archivo dado**: es
estructuralmente ciego a un archivo que la referencia no tiene. Gate de conjunto
por raíz: tarea #334.

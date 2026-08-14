# Atributos de clase de modelo — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/atributos-de-clase-de-modelo.md` (v2.0.0).
Aquí sólo el invariante operativo:

**Si la clase de la referencia declara atributos de clase, se portan TODOS los
que declare. Si no declara ninguno, no se inventa ninguno.**

> **v1 estaba mal** y decía *"todo modelo declara `_name` y `_description`"*.
> Medido sobre 3344 clases de `odoo19c`: sólo el **35 %** declara `_name` (el
> resto son **extensiones**, con `_inherit` y sin nombre propio), y el universo
> es de **al menos 24** atributos, no dos. Coste: el porte de `stock_picking.py`
> declaró **2 de 5** en cada clase y se presentó como completo (:ref:`h-api-580`).

## El procedimiento es un comando, no una lista de memoria

```bash
python3 -c "import ast,pathlib,sys
ref=pathlib.Path(sys.argv[1]).read_text(); L=ref.splitlines()
[print(c.name, [(x.id,n.lineno) for n in c.body if isinstance(n,ast.Assign)
  for x in n.targets if isinstance(x,ast.Name) and x.id.startswith('_')])
 for c in ast.parse(ref).body if isinstance(c,ast.ClassDef)]" $ODOO19C/addons/<x>/models/<y>.py
```

Lo que salga es el contrato. Cada atributo se porta o declara su divergencia;
ninguno se omite en silencio.

## Los más frecuentes (medidos en `odoo19c`)

`_inherit` 2588 · `_name` 1173 · `_description` 1099 · `_order` 379 ·
`_rec_name` 122 · `_check_company_auto` 76 · `_allow_sudo_commands` 41 ·
`_rec_names_search` 36 · `_inherits` 21 · `_auto` 16 · `_table` 15 ·
`_parent_store` 12 · `_log_access` 12. Universo declarado en
`odoo19c: odoo/orm/models.py:370-464`, cada uno con su comentario `#:`.

**Se declaran verbatim y NO sustituyen a su forma Django** — `_description`
convive con `Meta.verbose_name`, `_order` con `Meta.ordering`, `_table` con
`Meta.db_table` (que debe coincidir con `_name.replace('.', '_')`; lo verifica
`orm.registry.check_table_matches_name()`).

**Tres cosas distintas comparten el prefijo `_`:** los atributos de ORM (esta
regla); los **objetos de tabla** de 19 (`_name_uniq = models.Constraint(...)`,
`_x_index = models.Index(...)` — su hogar aquí es `Meta.constraints` /
`Meta.indexes`, con el nombre conservado); y las constantes de módulo
(`_OUTLOOK_SCOPE`), que se portan como constantes normales.

**Prospectivo:** modelo nuevo o portado, lleva los de su fuente; modelo
existente que se toca, se le completan. Sin barrido en bloque.

**Segunda cláusula — el SITIO del archivo** (H-API-578): antes de crear un
archivo en una raíz espejada (`src/orm` ↔ `odoo/orm`, `src/tools` ↔
`odoo/tools`, `addons/<x>` ↔ `addons/<x>`), **listar la raíz de la referencia**:

```bash
ls $ODOO19C/odoo/orm/     # ¿ya existe el hogar de este símbolo?
```

`check_porte_completo` compara símbolos **dentro de un archivo dado**: es
estructuralmente ciego a un archivo que la referencia no tiene, y **no mira los
atributos de clase en absoluto**. Gate de conjunto por raíz: tarea #334.

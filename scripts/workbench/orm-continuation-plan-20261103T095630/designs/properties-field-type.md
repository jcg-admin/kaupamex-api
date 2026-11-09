# Unidad 6e-1 — `Properties.type = 'properties'`

Autoridad: `odoo19c: odoo/orm/fields_properties.py:52` (`type = 'properties'`)
y `:849` (`type = 'properties_definition'`), odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389`.

## Hueco medido (lo destapó la RED de la unidad 6e)

`TestOrmMessage._fields['attributes'].type` devuelve **`'json'`**. `Field.type`
lo puebla `orm.fields.type_for`: sin atributo de clase `type`, cae al tipo
interno de Django (`JSONField` → `'json'`). La fuente declara
`type = 'properties'` en la clase.

El docstring de `Properties` justificaba no declararlo con que *"un
`models.Field` de Django no lleva atributo `type`"*. Eso dejó de ser cierto
cuando `Field.type = property(type_for)` se instaló, y `type_for` ya lee el
atributo de clase de `Reference`, `Many2oneReference` y `SelectionField`.

Consecuencia: **todo** sitio portado que pregunta `field.type == 'properties'`
es inalcanzable para un campo de propiedades — medido: 11 en
`src/orm/models.py` (lectura, `_read_group*`, prelectura de la
especificación web) y 2 en `src/orm/domains.py` (la optimización de
fechas de propiedades y la clasificación de campos x2many). La RED de 6e los
recorre por la rama de ruta many2one y falla con *"Only many2one path is
accepted"*.

## Decisión

Asignar `type = 'properties'` a `Properties` y
`type = 'properties_definition'` en `PropertiesDefinition`, como la fuente.
`type_for` ya prefiere el atributo de clase; no se toca. El reflejo en
`ir.model.fields` pasa de `json` a `properties`, que es el tipo de la fuente.

Es transversal: activa caminos de dominios, lectura y agrupado. Exige la
regresión amplia de la revisión que lo contiene.

## Casos (`tests/unit/orm/test_properties_field_type.py`)

1. `attributes` de `test_orm.message` → `'properties'`;
2. `attributes_definition` de `test_orm.discussion` → `'properties_definition'`;
3. `type_for` del campo da lo mismo (el reflejo de `ir.model.fields`).

Anulación: retirar el atributo de clase de `Properties` hace caer 1 y 3.

## Forma de la asignación (decidida por el control de admisión)

Se asignan **tras las clases** (`Properties.type = 'properties'`), como los
atributos que `orm/fields.py` instala sobre `models.Field`. Declararlos
dentro del cuerpo desplazaba el índice de las sentencias siguientes y
renovaba la huella de 43 líneas largas heredadas de `Properties`; una
sentencia al final del módulo no desplaza nada. El objeto que `type_for`
lee es el mismo.

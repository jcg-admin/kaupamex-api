# `DomainCondition._to_q` con `child_of` / `parent_of`

Descubierto en la unidad `account-journal-payment-method-lines-0515`
(`designs/journal-payment-method-lines.md`): con `account.journal` sobre
`BaseModel`, la regla multiempresa del diario llega a
`ir.rule._get_failing` como `('company_id', 'parent_of', [...])` y
`_to_q` levanta `Operador no soportado al compilar`.

## Referencia

- `_operator_hierarchy` (`odoo19c: odoo/orm/domains.py:1707-1760`): en el
  nivel `FULL` el optimizador reescribe `child_of`/`parent_of` a un dominio
  simple (`id in` los de la jerarquía, o `_FALSE_DOMAIN` si el valor es
  `False`).
- La evaluación en memoria lo resuelve igual: sube a `FULL` y evalúa el
  resultado (`odoo19c: odoo/orm/domains.py:1045-1047`).
- `_get_failing` (`odoo19c: odoo/addons/base/models/ir_rule.py:79-110`) no
  compila hojas a mano: busca con `search_count`, que optimiza el dominio
  antes de generar SQL. Una hoja `parent_of` nunca llega sin reescribir al
  compilador de la fuente.

## Nuestro estado

`_as_predicate` ya hace la subida a `FULL` (`src/orm/domains.py`, bloque
«≙ `:1045-1047`»). `_to_q`, el compilador a `Q` que usa
`ir.rule._get_failing` aquí, no: normaliza y compila la hoja directamente.

## Cambio

En `_to_q`, una condición `child_of`/`parent_of` se optimiza a `FULL` y se
compila el resultado, como `_as_predicate`. Sin mecanismo nuevo: es el
optimizador portado.

## Pruebas

`tests/unit/orm/test_domain_to_q_hierarchy.py`: `('company_id',
'parent_of', [c])` sobre diarios filtra los de la empresa `c`; con lista
vacía no devuelve ninguno; anulación: sin la subida a `FULL`, los dos casos
levantan.

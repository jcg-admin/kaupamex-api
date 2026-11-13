# `unlink` en todo modelo: depende de la adopción de `BaseModel`

Creado: 2026-11-13T06:26:05 (UTC). TASK-API-0485, dependencia TASK-API-0397.

## Contrato

`BaseModel.unlink` (`odoo19c: odoo/orm/models.py`) borra el recordset
`self`: ACL de borrado, descarte de cómputos pendientes, volcado, `DELETE`
e invalidación de toda la caché.

## Medido (`7212e552`)

Aquí `unlink` vive sólo en `BaseModel` (`src/orm/models.py:8820`) y
opera sobre `self.ids` y `type(self)` como recordset. Lo tienen los 63
modelos que derivan de `BaseModel`; faltaba en 376 de los modelos de
producción en el censo de `outputs/basemodel-reach-20261113/`.

## Por qué no se adopta como `copy` o `create`

`copy` y `create` son métodos de clase o de instancia que ya funcionan
sobre una fila de Django (`CopyMixin`, `DefaultGetMixin`). `unlink` no:
su receptor es un recordset, y una fila de Django sin `BaseModel` no lo
es. Adoptarlo exigiría escribir un segundo `unlink` sobre instancias. Habría
entonces dos implementaciones del mismo paso, y la fuente sólo tiene una.

## Decisión

`unlink-universality-0485` queda bloqueada hasta que los modelos deriven de
`BaseModel` (TASK-API-0397, por grupos). No es una divergencia aceptada:
es el orden de construcción. La misma dependencia rige `write`/`_write`,
`search` y `browse`, y el `env[...]` que devuelve la clase
(`designs/environment-getitem-recordset.md`).

# `utm` sobre `BaseModel`, con su ACL

Creado: 2026-11-13T17:14:33 (UTC). TASK-API-0397 (unidad `basemodel-adoption-0397`).

## Contrato

- Los cinco modelos de `odoo19c: addons/utm/models/` (`utm.campaign`,
  `utm.medium`, `utm.source`, `utm.stage`, `utm.tag`) son `BaseModel`:
  `env['utm.source']` es un recordset, con `create`, `unlink`, `search`.
- `odoo19c: addons/utm/security/ir.model.access.csv` (odoo-tools
  `abe4040ec1`): diez filas, CRUD sin borrado para `base.group_user` en
  campaña/medio/fuente, sólo lectura en etapa/etiqueta, todo para
  `base.group_system`.

## Por qué la ACL va en el mismo pase

Al derivar de `BaseModel`, `check_access` gobierna el acceso. El grupo A de
HR quedó «verificado sólo para el superusuario» porque su ACL no se portó
(`designs/hr-basemodel-dependencies.md`). Aquí no se repite: sin las filas,
un usuario interno quedaría denegado en los cinco.

## Mecanismo — corregido en `a40f3f22`

La primera versión (`e9fb9b5b`) sembró la ACL con una lista Python y la
migración `utm/0007`: un mecanismo paralelo existiendo ya el de la fuente.
Ahora `utm/security/ir.model.access.csv` es copia fiel, declarada en `data`
del manifiesto, y la carga el ciclo de instalación con su identificador
externo (`designs/security-data-by-manifest.md`). La herencia de `BaseModel`
es Python y no cambia columnas.

## Pruebas

`tests/unit/utm/test_utm_basemodel_acl.py`: los cinco modelos son
`BaseModel`; las filas son las del CSV; un usuario interno crea una fuente y
no la borra; sólo lee etiquetas.

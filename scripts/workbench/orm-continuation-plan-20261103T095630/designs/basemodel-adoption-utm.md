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

## Mecanismo (EXTEND)

`addons.base.security.ir_model_access._seed` gana el parámetro `rows`; `utm`
declara las suyas, derivadas del CSV con `probes/derive_base_acl.py` (10
derivadas, 0 sin modelo), con dos entradas: `seed` (catálogo de
`tests/conftest.py`) y `seed_utm_acl` (migración `utm/0007`). La herencia de
`BaseModel` es Python y no cambia columnas.

## Pruebas

`tests/unit/utm/test_utm_basemodel_acl.py`: los cinco modelos son
`BaseModel`; las filas son las del CSV; un usuario interno crea una fuente y
no la borra; sólo lee etiquetas.

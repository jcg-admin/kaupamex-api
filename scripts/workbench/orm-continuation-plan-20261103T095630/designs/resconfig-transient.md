# Diseño pendiente — `res.config` transitorio (TASK-API-0485)

Fecha: 2026-11-09T01:20:26.

## Contrato (odoo19c)

`class ResConfig(models.TransientModel)` y
`class ResConfigSettings(models.TransientModel)`
(`odoo/addons/base/models/res_config.py:13,99`). Con `Model0._transient`,
`resolve_depends` corta en el primer salto a un modelo normal
(`odoo/orm/fields.py:820-824`): tocar `res.company.country_id` no recalcula
ajustes transitorios, y el aviso «should be searchable» no aparece.

## Aquí (medido)

- `ResConfig(models.CopyMixin, models.Model)`
  (`src/addons/base/models/res_config.py:162`), sin `_transient`.
- `SiteConfigSettings` es `managed = False` (sin tabla), declarado como
  equivalente del `TransientModel` en su `Meta`.
- 11 clases derivan de `ResConfig`/`ResConfigSettings`
  (`grep -rln "ResConfigSettings)\|(ResConfig)" src addons`).
- `orm.models_transient.TransientModel` existe (`_transient = True`, vacío
  por `updated_at`) y exige las columnas de `LOG_ACCESS_COLUMNS`
  (`model_classes._check_transient_log_access`): declarar sólo
  `_transient = True` en `ResConfig` rompe la importación.

## Opciones

| Opción | Qué toca |
|---|---|
| A. `ResConfig` deriva de `TransientModel` y tiene tabla, como la referencia | 11 subclases, migraciones, la política `ondelete` de sus FK (`fields_relational._setup_nonrelated`), el vacío periódico |
| B. mantener el formulario sin tabla y declarar la especie por otra vía que `resolve_depends` lea | el contrato de `_transient` (ya no significaría «tiene vacío») |

Las dos cambian una decisión de arquitectura declarada (el ajuste sin tabla).
Queda para el ejecutor. Mientras tanto el aviso se mantiene: no se silencia.

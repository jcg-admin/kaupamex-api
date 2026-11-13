# Contratos de `BaseModel` frente a `TimeStampedModel` y `CopyMixin`

Creado: 2026-11-13T05:41:28 (UTC). TASK-API-0485 (obligaciones de `src/orm`) y TASK-API-0397
(`BaseModel` propio). Referencia: `odoo19c: odoo/orm/models.py`
(`BaseModel`, 188 nombres únicos). Medición sobre `fe9a477e`.

## Instrumentos

- Alcance por nombre: `basemodel-contract-reach-20261105T021145/probes/channel_census.py`
  (REUSE), salida en `outputs/basemodel-reach-20261113/`.
- Dueño en el MRO y clasificación: sondas en línea sobre el registro vivo
  (`apps.get_models()`), citadas abajo.

*Métrica:* presencia del nombre en la **clase** del modelo (o en lo que
`env[...]` devuelve, que hoy es la clase).
*Ciega a:* si el método presente **cumple** el contrato; un nombre presente
no es un contrato verificado. La verificación es por unidad (plan.jsonl).

## Clasificación de los 443 modelos concretos de `addons`

| Base | Modelos | con `CopyMixin` | con `DefaultGetMixin` |
|---|---|---|---|
| `TimeStampedModel` | 284 | 11 | 19 |
| `BaseModel` | 63 (10 de producción: `base.IrAttachment`, `hr.HrEmployee`, 8 de `hr_skills`/`hr_recruitment_skills`; 53 de `test_orm`) | — (heredado de `BaseModel`) | 63 |
| sólo Django | 96 | 2 | 6 |

`env['res.partner']` devuelve la **clase** `ResPartner`
(`designs/environment-getitem-recordset.md`); la fuente devuelve un
recordset vacío (`environments.py:105-107`).

## Qué aporta cada pieza (dueño medido en el MRO)

| Capacidad | Fuente | Dueño aquí | Universal |
|---|---|---|---|
| `create_date`/`write_date`/`create_uid`/`write_uid` | metaclase `models.py:274-292` | `TimeStampedModel` + `adopt_log_access` (`class_prepared`) | sí (los dos caminos) |
| hora de transacción en el sellado | `cr.now()` | `TransactionClockSaveMixin` | por `TimeStampedModel` |
| `write` | `models.py:4400-4520` | `RecordLoaderMixin.write` | por `TimeStampedModel`; ausente en 94 de 396 de producción |
| `_write`/`_write_multi` | `models.py:4520-4608` | `BaseModel` | **no**: ausente en 386 de 396 |
| `create`/`_create` | `models.py:4700-4900` | `DefaultGetMixin` (declarado a mano) | **no**: `create` ausente en 354, `_create` en 362 |
| `unlink` | `models.py` (`unlink`) | `BaseModel` | **no**: ausente en 376 |
| `copy`/`copy_data` | `models.py:5406-5463, 5530-5545` | `CopyMixin` (declarado a mano) | **no**: `copy` ausente en 372, `copy_data` en 363 |
| `copy_translations` | `models.py:5465` | parche sobre la clase | sí (374 por parche) |
| `modified` y recómputo | `models.py` (`modified`, `_compute_field_value`) | `modified`: parche sobre `django.db.models.Model`; `_compute_field_value`: `BaseModel` | `modified` sí; `_compute_field_value` ausente en 386 |
| `search`/`browse`/`read`/`exists`/`filtered`/`mapped` | `BaseModel` | `BaseModel` | **no**: ausentes en 384-386 |
| `display_name` | `models.py:473,1421-1543` | `DisplayNameMixin` + `adopt_display_name` | sí |
| `_load_records` y cadena | `models.py:5054-5108` | `RecordLoaderMixin` | en 299; plan `record-loader-universality-0485` pendiente |
| `action_archive`/`toggle_active` | `models.py` | `ArchiveMixin` | por `TimeStampedModel`; ausente en 103 |
| `_check_company`/`_check_company_domain` | `models.py:451,3997,4009` | `CheckCompanyMixin` | ausente en 99/95 |
| cachés (`ormcache`) y su invalidación | `registry.py:971-1001` | `orm.registry` por base (`c89eed08`, `ea4e91a9`, `332c2b41`) | sí |
| transacción, señal y reintento | `http.py:2267`, `service/model.py:160-240` | `UnitOfWorkMiddleware` (`7fa471df`) | por petición |
| permisos (`check_access`, …) | `models.py:4100-4135` | `adopt_access_manager` sobre el manager | parcial (`check_access_rights`/`rule` ausentes en 386) |
| alias de base | `env.cr` | `routers.domain_alias`, `registry_for_alias` | sí |

## Juicio

- `TimeStampedModel` **sí** satisface las columnas de auditoría, el reloj,
  `write`, `display_name`, archivado, empresa, `get_base_url` y la carga
  de datos. Se conserva.
- **No** es completo frente a `BaseModel`: `create`, `unlink`, `copy`
  y todo el recordset (`search`, `browse`, `_write`, `_compute_field_value`, …)
  faltan en la mayoría de los 396 modelos de producción. La decisión vigente
  (H-API-1083, TASK-API-0397) es que los modelos portados **deriven de
  `BaseModel`**; 10 de producción ya lo hacen.
- La cabecera de `timestamped_mixin.py` llama a la auto-inyección del
  log-access «alternativa diferida»: ya existe (`adopt_log_access`,
  `base/0110`). Se corrige.

## Obligaciones que siguen (cada una, unidad del plan)

1. `copy-universality-0485`: `copy`/`copy_data` en todo modelo
   (`CopyMixin` en `TimeStampedModel` y adopción para los de sólo Django).
2. `create-universality-0485`: `create`/`_create` en todo modelo.
3. `unlink-universality-0485`: `unlink` de la fuente en todo modelo.
4. Adopción de `BaseModel` por grupos (TASK-API-0397), que trae el recordset
   completo y hace de `env[...]` un recordset.

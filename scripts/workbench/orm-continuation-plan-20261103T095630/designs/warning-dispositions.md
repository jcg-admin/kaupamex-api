# Registro de avisos observados y su disposición (3.2.14-C §3-§6)

Fecha: 2026-11-09T01:20:26. Cada fila cita su evidencia; ninguna se silencia con filtros.

| Aviso | Origen | Reproducción | Causa | Disposición | Evidencia |
|---|---|---|---|---|---|
| `Too many iterations for flushing fields!` | `orm.environments.Environment.flush_all` | reproducido: `write` + `flush_all` sobre `test_orm.related` | `pre_save` de `auto_now` volvía a marcar sucio `updated_at` dentro del mismo `save`; la fecha en caché divergía de la persistida | **defecto funcional demostrado → corregido** | H-API-1188, `api@c5e9ed15`, `tests/unit/orm/test_flush_convergence.py` |
| `Field <ForeignKey: country> in dependency of base_setup.SiteConfigSettings.company_country_code should be searchable` (y `company_country_group_codes`) | `orm.fields` `resolve_depends` | reproducido al cargar el registro | la referencia corta en el primer salto de un modelo transitorio a uno normal (`odoo/orm/fields.py:820-824`); `ResConfig` aquí no declara `_transient` | **divergencia demostrada, corrección pendiente de decisión** — ver `resconfig-transient.md` | H-API-1188 («no cierra») |
| `UV_NATIVE_TLS` / `native-tls` deprecated | `uv` | en cada invocación | variable y ajuste del entorno del contenedor, no del repositorio | **configuración del entorno**: fuera del Consumer; no se toca | salida de `uv run` |
| `fields.W342` en `fleet.FleetVehicleLogServices.account_move_line` | system check de Django | en `makemigrations` | `ForeignKey(unique=True)` | **divergencia de restricción**: la referencia declara `account_move_line_id = fields.Many2one(..., index='btree_not_null')  # One2one` sin unicidad (`odoo19c: addons/account_fleet/models/fleet_vehicle_log_services.py:10`); aquí `unique=True` (`addons/account_fleet/models/fleet_vehicle_log_services.py:277`) añade una restricción de base que la referencia no impone. Unidad pendiente bajo la TASK del addon `account_fleet` | salida de `makemigrations` del 2026-11-09 |

La disposición de cada aviso se deriva de su efecto medido, no de que las
pruebas sigan en verde.

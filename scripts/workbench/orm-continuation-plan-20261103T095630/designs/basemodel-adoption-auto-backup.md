# Adopción de `BaseModel`: `auto_backup`

Creado: 2026-11-18T18:51:53 (UTC). TASK-API-0397, hija de `basemodel-adoption-0397`,
re-clasificada por la corrección del censo (`basemodel-adoption-program.md`,
«propio se medía contra un solo árbol»).

## La fuente

`odoo-tools: 18.x/app-odoo-18.0/app_auto_backup` (LGPL-3; copia +
adaptación con atribución). No hay versión 19 en `odoo-tools`
(`ls 19.x/`: `industry-19.0`, `odoo-19.0`, `odoo19-enterprise-main`).

- `DbBackup(models.Model)`, `_name = 'db.backup'`,
  `_description = 'Backup configuration record'` (`models/db_backup.py:27-29`).
- `DbBackupDetails(models.Model)`, `_name = 'db.backup.details'`,
  `_description`, `_order = 'id desc'` (`models/db_backup_details.py:9-12`).
- `security/user_groups.xml`: la categoría `module_management`, el grupo
  `group_manager` y `base.group_system` implicando a `group_manager`.
- `security/ir.model.access.csv`: tres filas (`base.group_no_one` y
  `group_manager` sobre `db.backup`; `group_manager` sobre
  `db.backup.details`).
- `data`: `user_groups.xml` antes que el CSV (`__manifest__.py:57-63`).

## Este árbol

Los dos modelos ya llevan el `_name` y los atributos de la fuente, sobre
`TimeStampedModel`. No carga ni el XML de grupos ni el CSV.

## Divergencias de mecanismo, por la base 19

1. **El módulo se llama `auto_backup`, no `app_auto_backup`.** Las
   referencias `app_auto_backup.<id>` del XML se escriben sin prefijo (el
   módulo propio) para que resuelvan en este árbol.
2. **`res.groups.category_id` no existe en la base 19.** La 18 liga el
   grupo a su categoría; la 19 lo hace con `res.groups.privilege`
   (`category_id` en el privilegio y `privilege_id` en el grupo), como
   `odoo19c: addons/account/security/account_security.xml:40-44,59`. Se
   declara un privilegio `res_groups_privilege_auto_backup` con la
   categoría de la fuente, y el grupo lo usa.

## Decisión

Base `(models.BaseModel, TimeStampedModel)` en los dos; `user_groups.xml`
y el CSV adaptados por (1) y (2), en `data` y en el orden de la fuente.

## RED

1. Los dos son `BaseModel`; `auto_backup` sale de `PENDING` del
   trinquete.
2. `group_manager` existe y `base.group_system` lo implica.
3. Las tres filas del CSV con sus identificadores externos.
4. Un usuario interno no lee `db.backup.details`; uno de
   `group_system` sí (por la implicación).

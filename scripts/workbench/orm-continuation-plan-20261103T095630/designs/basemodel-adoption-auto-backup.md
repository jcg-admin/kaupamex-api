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

## Bloqueo medido (2026-11-18)

El GREEN cargó el XML y el CSV, pero `schedule_backup` falla con
`PermissionDenied`: sus crons corren con `user` nulo
(`IrCron.objects.filter(user__isnull=True).count()` → 7 de 7), y un
`BaseModel` deniega sin usuario. En la fuente el cron corre como
`base.user_root`. Prerrequisito: `ir-cron-user-root.md`. El trabajo de esta
unidad queda en un parche del scratchpad y se reaplica cuando aquélla
asiente.

**Lo que también midió el GREEN:** `base.group_system` es `noupdate` en
`base`, así que en modo de actualización el cargador no le añade
`group_manager` (`AND NOT ir_model_data.noupdate`, `src/addons/base/models/ir_model.py:3379`,
igual que la fuente). En una instalación nueva sí. La prueba carga el XML
en `mode='init'` para medir la instalación.

## Bloqueo cerrado y ejecución (2026-11-18)

Los dos prerrequisitos asentaron: `ir-cron-user-root-0485` (el cron corre como
`base.user_root`) e `ir-cron-env-su-0485` (lo hace con la elevación de su
usuario, ≙ `odoo19c: odoo/orm/environments.py:66`). Se volvió a aplicar el
parche.

La prueba ya no fija el entorno a mano: `_run_as_cron` llama a
`cron._callback()`, el mismo camino que sigue el ejecutor de crons. Así mide
el contrato completo (usuario y elevación) y no una copia del contrato.

Resultados:

- `tests/integration/auto_backup/` y `test_basemodel_reach.py`: 74 passed.
- `auto_backup` ya no figura en `PENDING`.
- Consumidores derivados
  (`grep -rlE "DbBackup|auto_backup|db\.backup" --include=*.py tests/`, sin el
  `conftest.py` de la raíz): 6194 passed, 65 skipped, 2 xfailed con `-n 4`.

**Lo que la medición corrigió.** La primera prueba del ACL leía las filas que
la base reutilizada ya tenía. Al retirar el CSV del manifiesto no caía
ninguna aserción: no medía el manifiesto. Ahora el fixture `installed_data`
retira esas filas y vuelve a cargar los datos con `load_data` en
`mode='init'`, el paso real de la instalación.

Anulaciones, cada una medida por separado (`tests/integration/auto_backup/`):

| Se retira | Caen |
|---|---|
| la fila `ir.model.access.csv` de `data` | `test_the_acl_is_the_reference_csv_with_its_external_ids` y `test_only_a_backup_manager_reads_the_backups` (2 de 52) |
| la implicación de `base.group_system` | `test_the_system_group_implies_the_backup_manager` y la de lectura (2 de 52) |
| `models.BaseModel` de `DbBackupDetails` | la de tipo y todas las de `schedule_backup`, que crean el detalle por el recordset |

**Admisión de estilo.** Al cambiar las bases de `DbBackup` cambia el contexto
sintáctico de cada línea de la clase, así que su deuda heredada se contó como
nueva: 21 E501 y un E305, que se pagaron. Las seis supresiones
`# noqa: BLE001 — <motivo>` se volvieron comentarios `# <motivo>`. `BLE001`
es de flake8-blind-except, y ningún linter de este repo lo aplica (ni
`pyproject.toml` ni el entorno). Para pycodestyle, en cambio, un `noqa` sin
código silenciaba la línea entera. Sin el pragma, las seis miden 79
caracteres o menos.

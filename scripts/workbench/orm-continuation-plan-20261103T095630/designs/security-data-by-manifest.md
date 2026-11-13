# La seguridad de un addon se carga por su manifiesto, como en la referencia

Creado: 2026-11-13T22:17:24 (UTC). TASK-API-0397. Corrige `designs/basemodel-adoption-utm.md`.

## Contrato de la referencia

Un addon declara en `data` de `__manifest__.py` su `security/*.xml` y su
`security/ir.model.access.csv`; `load_module_graph` los carga con
`load_data`/`convert_file` **después** de dejar el esquema del módulo al día
(`odoo19c: odoo/modules/loading.py`), con los modelos vivos. Cada fila de
ACL, grupo y regla queda con su identificador externo.

## Estado medido

- El ciclo existe aquí: `addons.base.install_cycle.load_modules_after_migrate`
  sobre `post_migrate` llama a `modules.loading.load_modules`, que en orden
  de grafo ejecuta `init_models` y `load_data` de cada manifiesto.
- Dos addons ya lo usan: `uom` (`e5ef3952`) y `hr`/`hr_skills`
  (`8ab54be4`), con copia fiel de los archivos y las omisiones declaradas en
  la cabecera del XML.
- La tensión del «paso 0» de `designs/hr-basemodel-dependencies.md` (cargar
  con modelos vivos desde una migración) la resuelve ese ciclo: corre tras
  `migrate`, con el esquema completo, igual que la fuente.

## Corrección de `utm` (`e9fb9b5b`)

`utm` sembró su ACL con una lista Python y la migración `utm/0007`. Era un
mecanismo paralelo al de la fuente, existiendo ya el fiel:
- `utm/security/ir.model.access.csv` pasa a ser copia fiel del CSV de la
  referencia, declarada en `data`;
- se retiran `addons/utm/security/ir_model_access.py`, su registro en
  `tests/conftest.py`, la migración `0007` y el parámetro `rows` de
  `_seed` de `base`, que quedaría sin uso;
- en las bases de prueba de esta VM, las filas que sembró `0007` (sin
  identificador externo) y el registro de `utm.0007` en `django_migrations`
  se retiran: su procedencia es esa migración, y el CSV vuelve a crearlas
  con su identificador.

## `sales_team`

- `crm.tag`, `crm.team` y `crm.team.member` derivan de `BaseModel`.
- `security/sales_team_security.xml` y `security/ir.model.access.csv`,
  copia fiel, en `data`. Omisiones declaradas en la cabecera del XML:
  `mail.group_mail_canned_response_admin` (la seguridad de `mail` no está
  portada) y `base.user_admin` (no existe en este árbol). Existen y se
  conservan `base.module_category_sales`, `base.user_root` y
  `base.group_user`; `company_ids` está en el contexto de las reglas.

## Pruebas

Por addon: sus modelos son `BaseModel`; los grupos, filas y reglas existen
con su identificador externo; un usuario interno sólo lee `crm.team` y
`crm.team.member` y no lee `crm.tag` (fila global en cero); un vendedor
crea etiquetas y no las borra. Anulación: quitar el CSV de `data` hace caer
las pruebas de acceso.

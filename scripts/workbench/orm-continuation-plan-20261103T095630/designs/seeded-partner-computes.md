# Los contactos sembrados por migración, sin sus calculados almacenados

Diagnóstico medido el 2026-11-16T21:01:57 sobre el fallo del gate ci-multidb de
`a3723a61` (`outputs/gates/ci-multidb-a3723a61/`, revisión registrada
`9d1f1adf`: `a3723a61` más un commit sólo de diseño).

## El fallo

14 de 15 pruebas de `test_multidb_isolation.py` en `ERROR`, las 14 con la
misma causa al aprovisionar una base de empresa:

```text
tools.convert.ParseError: while parsing addons/account/security/account_security.xml:247
Dominio inválido: AttributeError("'NoneType' object has no attribute 'id'")
"[... ('partner_id','child_of',[user.commercial_partner_id.id])]"
```

## La causa, medida

1. `ir.rule._check_domain` evalúa el dominio con `user` = el usuario del
   entorno, que al cargar módulos es `SUPERUSER_ID` (`modules/loading.py:252`).
2. `base.partner_root` lo crea la migración `0106_seed_root_user` con el
   modelo **histórico**, que no ejecuta cómputos: su `commercial_partner_id`
   queda nulo. Lo mismo `base.public_partner` (`0113`).
3. En `orm_x2hokp_qa` el valor existe (`5730 → 5730`) porque los
   sembradores de `tests/conftest.py` vuelven a pasar con los modelos vivos.
   Por eso la suite completa sale verde y sólo una base construida desde
   cero falla.
4. La regla es la primera que lee `user.commercial_partner_id`; entró con
   `4068c254` («Load the account security of the reference»), posterior al
   último aprovisionamiento verde (`b314f6e7`). El arreglo de NewId de
   `a3723a61` no interviene.

Descartado midiendo: que el contacto no se calcule al crearse (por Django y
por el ORM se calcula, `7244 → 7244`), y que usuario y contacto se lean en
bases distintas (el router manda los dos a la base del entorno).

## La fuente

El contacto se crea por el ORM y `_compute_commercial_partner` lo apunta a
sí mismo cuando no tiene padre (`odoo19c: odoo/addons/base/models/
res_partner.py:515-528`). Una columna calculada sobre filas existentes la
calcula el ORM (`odoo19c: odoo/orm/models.py:3220-3238`).

## El arreglo

`base/migrations/0116_partner_commercial_fields.py`:
`ComputeStoredFields('base', 'respartner', ['commercial_partner_id',
'commercial_company_name'])`, después de toda migración que siembra
contactos. Es el mecanismo de TASK-API-0516; en una base de empresa corre
dentro del `company_scope` de `_migrate_company_database`, y si el esquema
va atrasado espera al `post_migrate`, que lo vacía antes de cargar datos
(`addons/base/apps.py:131-135`).

No se tocó `seed_root_user`: copiar el cómputo en la siembra sería una
segunda fuente de verdad del cómputo.

## Verificación

- `tests/unit/base/test_partner_commercial_fields_migration.py`, 5 pruebas.
  Anulación (calcular sólo `commercial_company_name`): caen exactamente las
  4 que dependen de `commercial_partner_id`; sobrevive la de dependencias.
- El contrato real es aprovisionar desde cero: ci-multidb vuelve a correr.

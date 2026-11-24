# `BaseModel` trae la coherencia de empresa, como en la fuente

Fecha: 2026-11-24T11:12:33. TASK-API-0397. Defecto confirmado durante la
unidad `account-reconcile-partner-comodel-0397`: stop-on-error, clase A
(un `create` o `write` por el ORM revienta).

## Referencia

odoo19c: odoo/orm/models.py:4009-4012 — `_check_company` es un método de
`BaseModel`. `create` y `write` lo invocan cuando `_check_company_auto` es
verdadero, y cualquier modelo puede declarar el atributo.

## Defecto medido

`BaseModel` (`src/orm/models.py:6929`) no hereda `CheckCompanyMixin`, pero su
`create` lo invoca (`src/orm/models.py:1102-1104`), igual que su `write`.
Recorrido del registro el 2026-11-24 (`apps.get_models()`, subclases de
`BaseModel` con `_check_company_auto = True`): 23 lo obtienen porque otro
mixin trae `CheckCompanyMixin` (`TimeStampedModel`), y **8 no lo tienen**:
`AccountCashRounding`, `AccountMoveLine`, `AccountGroup`,
`AccountJournalGroup`, `AccountReconcileModel`, `AccountReconcileModelLine`,
`AccountReportExternalValue` y `AccountSetupBankManualConfig`. Seis los
añadieron las unidades U1–U5 de `account`; sus pruebas creaban por
`objects.create` y no pasaban por el `create` del ORM.

## Qué cambia

1. `BaseModel` añade `CheckCompanyMixin` a sus bases, antes de `Model`.
2. Cuatro clases que ya derivan de `BaseModel` y nombraban el mixin a mano
   lo retiran, porque esa declaración rompe la linealización C3 en cuanto
   `BaseModel` lo incluye: `AccountAnalyticApplicability`,
   `AccountAnalyticLine`, `AccountAnalyticAccount` y
   `AccountFinancialYearOp`. Las clases sobre `models.Model` que lo nombran
   (`ResPartnerBank`, `ResCurrency`, `ResCurrencyRate`, `IrCron`) no
   cambian.
3. El estado de migraciones no cambia (`makemigrations --check`: sin
   cambios).

## Pruebas

`tests/unit/orm/test_basemodel_check_company.py`:

- `test_every_basemodel_that_checks_the_company_can_check_it` — recorre el
  registro: ninguna subclase de `BaseModel` con `_check_company_auto`
  carece de `_check_company`;
- `test_basemodel_carries_the_company_check` — el método está en el MRO de
  `BaseModel` mismo;
- `test_a_reconcile_rule_writes_through_the_orm` — `write` de una regla de
  conciliación con un Many2many termina sin error.

Anulación: sin `CheckCompanyMixin` en `BaseModel` caen las tres (la tercera
con el `AttributeError` del episodio).

## Citas de la fuente por archivo

- `src/orm/models.py`: odoo19c: odoo/orm/models.py:4009-4012.

## Símbolos tocados por archivo

- `src/orm/models.py`: `BaseModel`.
- `addons/analytic/models/analytic_plan.py`: `AccountAnalyticApplicability`.
- `addons/analytic/models/analytic_line.py`: `AccountAnalyticLine`.
- `addons/analytic/models/analytic_account.py`: `AccountAnalyticAccount`.
- `addons/account/wizard/setup_wizards.py`: `AccountFinancialYearOp`.

## Lo que este corte no cierra

Nada propio de la unidad. Es un cambio transversal (`src/orm`): su
verificación es la suite entera.

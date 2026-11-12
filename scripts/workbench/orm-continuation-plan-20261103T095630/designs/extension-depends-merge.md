# Las extensiones en el sitio conservan las dependencias de la base

TASK-API-0485, plan `orm-extension-depends-merge-0485`. Autoridad:
odoo-tools `abe4040ec1`.

## Contrato de la fuente

`Field.get_depends` (`odoo19c: odoo/orm/fields.py:584-599`) recorre
`resolve_mro(model, compute)`: la función más derivada primero y la base al
final, y hace `depends.extend(func._depends)` por función. Dos funciones que
declaran el mismo nombre lo aportan dos veces; una misma función no.

## El defecto, medido

Aquí una extensión de addon no añade una clase al MRO. `chain_method` y
`wrap_method` (`src/orm/method_chain.py`) instalan un envoltorio en el sitio
con `functools.wraps(func)`, que copia sólo el `_depends` de la extensión, y
enlazan la implementación previa en `_chain_previous`. `get_depends` leía el
envoltorio y no seguía el enlace.

Censo de los campos calculados cuyo cómputo es una cadena (probe inline sobre
`apps.get_models()`, `field_depends` contra la unión de los eslabones):

| Campo | Antes | Después |
|---|---|---|
| `ResUsers.display_name` | completo | completo |
| `IrActionsServer.available_model_ids` | `[]` (perdía `state`) | `['state']` |
| `ResPartnerBank.display_name` | `[]` (perdía `acc_number`) | `['acc_number']` |
| `ProductSupplierinfo.display_name` | `[]` (nada que perder) | `[]` |
| `StockLot.display_name` | completo, con la base contada dos veces | completo, cada función una vez |
| `StockRule.picking_type_code_domain` | `[]` (perdía `action`) | `['action']` |
| `AccountPaymentMethodLine.name` | `()` y sin cadena (sustituido con `setattr`) | `['payment_method.name']` |

Antes: 6 campos encadenados, 3 con dependencias completas. Después: 7 y 7.

## Corrección

1. `method_chain.chain_links(func)`: los eslabones, de la extensión a la base,
   tomando `_chain_origin` de cada envoltorio y siguiendo `_chain_previous`.
   `chain_depends(func, model)`: su unión ordenada sin repetidos.
2. `get_depends`: por cada función de `resolve_mro`, recorre sus eslabones.
   Cada función cuenta una vez (`seen` por identidad): `resolve_mro` ya
   devuelve la base desde la clase padre y la cadena la alcanza otra vez.
   Los valores repetidos entre funciones distintas se conservan, como en la
   fuente.
3. `account_payment` instala `_compute_name` con `wrap_method` (la base
   primero, el `super()` de la fuente) en vez de capturar la base y
   sustituirla con `setattr`.

No hay una segunda autoridad de dependencias: el grafo sigue siendo
`registry.field_depends`, derivado de `get_depends`.

## Lo que no cierra

La dependencia propia de la extensión de `account_payment`,
`payment_provider_id.name`, no se declara: `payment_provider` es aquí una
`property` sobre el vínculo, no un campo, y el grafo no puede recorrerla. Se
declara cuando `payment_provider_id` se porte como `Many2one`.

## Pruebas

`tests/unit/orm/test_method_chain_depends.py` (10). Anulaciones:

- `get_depends` sin recorrer la cadena: caen el registro y el recálculo (2);
- la extensión sustituida con `setattr`: los mismos 2;
- `chain_links` sin `_chain_previous`: caen 8, sobrevive la deduplicación;
- `chain_depends` sin deduplicar: cae 1;
- `get_depends` sin `seen`: cae el de la base contada una vez (1).

Tres campos ganan disparos nuevos, así que el cambio es transversal: suite
completa antes de publicar.

# Unidad 6 — `purchase-line-lifecycle-0122`, y por qué va antes que los CHECK

Fuente: `odoo19c: addons/purchase/models/purchase_order_line.py`
(odoo-tools `abe4040ec1`).

## El orden del plan se corrige con evidencia

El plan dice que `purchase-line-checks-0122` va tras la unidad 5 porque
`date_planned` forma parte de `_accountable_required_fields` (`:98-101`):

    CHECK(display_type IS NOT NULL OR is_downpayment OR
          (product_id IS NOT NULL AND product_uom_id IS NOT NULL
           AND date_planned IS NOT NULL))

Medido al cerrar la unidad 5: `date_planned` sólo lo escribe el cómputo
cuando **no** salta la línea, y la salta si `technical_price_unit !=
price_unit`. Una línea creada con precio explícito queda sin fecha. En la
fuente eso no ocurre por dos piezas de `create` (`:288-302`):

1. `values.update(self._prepare_add_missing_fields(values))` (`:635-645`):
   con `order_id` y `product_id` presentes y algún campo de onchange ausente,
   construye `self.new(values)`, llama a `onchange_product_id()` y copia los
   ausentes —entre ellos `date_planned`, `product_uom_id`, `name`—.
2. `if values.get('price_unit') and not values.get('technical_price_unit'):
   values['technical_price_unit'] = values['price_unit']`: el precio dado
   viaja con su técnico, así que un cambio posterior de cantidad sí vuelve
   a calcular. Lo que protege el precio en el alta es la **protección** del
   ORM sobre el valor dado (`_protected_on_create`), no la guarda.

Sin la unidad 6, el CHECK rechazaría toda línea con precio explícito.
Orden: 6 → checks. `purchase-line-checks-0122` debe depender también de
`purchase-line-lifecycle-0122`.

## A medir antes de escribir

- que `new()` + `onchange_product_id()` funcione sobre una línea sin `pk`
  (el defecto `orm-related-scalar-unsaved-0485` afecta a `update()` y a los
  `related` escalares; `onchange_product_id` usa `_compute_tax_id`, que hoy
  exige la fila guardada para el `Many2many`);
- qué pruebas existentes crean líneas sin producto ni `display_type`: el
  CHECK las rechazará y la fuente también; se completan los datos, no el
  código (precedente de la unidad 1).

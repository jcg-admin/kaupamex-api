# Entorno del registro en el x2many y caché tras un borrado de Django

Dos huecos de `src/orm` que la adopción de `sale.order` (U3b,
`designs/sale-basemodel-u3b-order.md`) destapó al ser el primer modelo
`BaseModel` con un One2many hacia otro `BaseModel` recorrido desde código
elevado y referenciado por FK desde modelos de Django.

## 1. El x2many usa `env()` y no `record.env`

**Medido.** Un carrito elevado (`order.sudo()`, como `sale_order_sudo` de
`odoo19c: addons/website_sale/models/website.py:679`) devuelve en
`order.order_line` líneas en el entorno **ambiente**; `line.product` comprueba
entonces la ACL con el usuario de la petición y deniega
(`POST /api/v2/cart/snapshots/` → 403, `src/orm/models.py:6697`).

**Referencia.** `odoo19c: odoo/orm/fields.py:1642-1650` — `Field.__get__`
toma `env = record.env`: el valor relacional de un registro vive en su
entorno.

**Decisión.** `_x2many_descriptor_get` (`src/orm/models.py`) se envuelve con
`_in_record_environment` (`src/orm/fields.py`), el mismo envoltorio que ya usa
`FieldDescriptor`: activa `record.env` antes de construir el recordset, así
que `env()` dentro del accesor es el del registro.

## 2. Un `delete()` de Django no invalida la caché de los registros `BaseModel`

**Medido.** Borrar un `ShippingMethod` (modelo de Django) aplica el
`on_delete=SET_NULL` de `SaleOrder.carrier` por el colector de Django; tras
`refresh_from_db()`, `order.carrier_id` sigue en el id borrado, porque la caché
del entorno conserva el valor previo
(`tests/integration/sale/test_sale_order_parity_e1.py:74`).

**Referencia.** `odoo19c: odoo/orm/models.py` `unlink` termina con
`self.env.invalidate_all(flush=False)`: *«invalidate the whole cache, since
the orm does not handle all changes made in the database, like cascading
delete!»*. Nuestro `BaseModel.unlink` ya lo hace (`src/orm/models.py:9129`).

**Decisión.** Un receptor de `post_delete` sin `sender` invalida la caché del
entorno activo (`invalidate_all(flush=False)`) cuando el modelo borrado **no**
es `BaseModel`: es el equivalente, para un borrado que no pasa por
`BaseModel.unlink`, de la misma línea de la fuente. Los `BaseModel` se saltan
porque su `unlink` ya invalida.

## Símbolos, referencia y prueba

Prueba: `tests/unit/orm/test_record_env_x2many_and_django_delete.py`.

| Símbolo | Referencia | Prueba |
|---|---|---|
| `_x2many_descriptor_get` envuelto por `_in_record_environment` | `odoo19c: odoo/orm/fields.py:1642-1650` | `test_the_lines_of_an_elevated_order_live_in_its_environment` |
| `_invalidate_after_django_delete` (receptor de `post_delete`) | `odoo19c: odoo/orm/models.py` `unlink` → `invalidate_all(flush=False)` | `test_a_django_delete_invalidates_the_cached_set_null` |

*Ciega a:* el `refresh_from_db` de un registro cuya caché cambió por SQL crudo
fuera de cualquier borrado; eso no lo cubre ninguna de las dos reglas.

# Adopción de BaseModel: res.country + res.country.state — análisis previo (basemodel-adoption-0397)

Estado: **implementado el 2026-11-26** (sección «Implementación», al final).
El primer intento se revirtió sin commit; lo medido entonces sigue abajo.

## Referencia

- `odoo19c: odoo/addons/base/models/res_country.py` — `class ResCountry(models.Model)` y `class CountryState(models.Model)`.
- ACL (`ir.model.access.csv:46-57`): lectura para `group_public`,
  `group_portal` y `group_user`; escritura para `group_partner_manager` y
  `group_system`.

## Lo que el cambio de base destapa

Con sólo cambiar las dos bases (sin migración: `makemigrations --check` sin
cambios; estilo en verde), el subconjunto derivado
(`ResCountry|res.country|country_id|state_id` en `tests/`, 66 archivos,
`-n 4`) dio **17 failed, 1084 passed, 2 xfailed**. Tres causas, cada una con
sus consumidores:

1. **Lectura rehusada** (8): `PermissionDenied: No tiene permiso para consultar
   registros de «Country»` al leer el país de un partner o de una compañía
   dentro del alcance de un usuario sin grupo de los que la fuente autoriza.
   Hay que decidir por consumidor si la fuente lee con `sudo` (cómputos de
   compañía, etiqueta de VAT) o si el usuario de la prueba debe llevar
   `base.group_user`, como en la fuente.
2. **Reverso como recordset** (2): `country.state_ids` y `country.city_ids`
   dejan de ser gestores de Django; `.count()` falla y la API es `len()` /
   `mapped`, como en la fuente.
3. **Many2one vacío como recordset vacío** (`assert res.country() is None` y
   las pruebas de `test_computed_many2one_absence.py`): el contrato de esas
   pruebas fija `None` para la ausencia, y bajo BaseModel la ausencia es el
   recordset vacío, que es la forma de la fuente. Las pruebas describen el
   comportamiento previo y hay que reescribirlas contra la fuente, no al revés.

Fallos medidos:

- `tests/integration/base/test_format_address_and_vat_label.py::TestTheVatLabelReachesItsField::test_the_field_that_takes_the_label_is_named`
- `tests/integration/base/test_format_address_and_vat_label.py::TestTheVatLabelReachesItsField::test_a_country_without_label_touches_nothing`
- `tests/integration/base/test_res_partner_labels.py::TestVatLabel::test_it_takes_the_label_of_the_active_company_country`
- `tests/integration/base/test_res_partner_labels.py::TestVatLabel::test_a_country_that_declares_no_label_falls_back`
- `tests/integration/base/test_computed_many2one_absence.py::test_empty_computed_relation_does_not_look_up_a_false_primary_key`
- `tests/integration/base/test_computed_many2one_absence.py::test_explicit_constructor_none_is_readable_without_another_field_access`
- `tests/integration/base/test_computed_many2one_absence.py::test_real_missing_reference_still_raises_the_target_error`
- `tests/integration/sale/test_sale_order_nonstored_fields.py::TestTheFiveComputesCalculateWhatTheSourceCalculates::test_tax_country_falls_back_to_the_company`
- `tests/unit/account/test_account_report_tax_tags.py::TestExpressionSaveCreatesItsTag::test_saving_the_expression_again_does_not_duplicate_the_tag`
- `tests/unit/base/test_base_geo.py::TestResCountry::test_state_ids_reverse_relation`
- `tests/unit/base/test_ir_fields_relational.py::TestTheNameSubfield::test_a_visible_name_resolves`
- `tests/unit/base_vat/test_vies_and_iap.py::test_perform_vies_validation_skips_a_number_from_the_company_country`
- `tests/unit/base/test_ir_fields_relational.py::TestTheNameSubfield::test_several_matches_warn_without_failing`
- `tests/unit/base/test_ir_fields_relational.py::TestTheManyToOneConverter::test_it_resolves_through_the_subfield`
- `tests/unit/base_address_extended/test_base_address_extended.py::TestResCity::test_country_required_state_optional`
- `tests/unit/base_address_extended/test_base_address_extended.py::TestResCity::test_state_set_null_on_delete`
- `tests/unit/base_address_extended/test_base_address_extended.py::TestResCity::test_cities_reverse_on_country`

## Condición de cierre

Portar cada consumidor contra su línea de la fuente (lecturas con `sudo` donde
la fuente las hace, usuarios de prueba con su grupo, reversos por la API de
recordset, ausencia como recordset vacío), cambiar luego las dos bases y
exigir el subconjunto de los 66 archivos en verde más F2.

## Avance del 2026-11-26: 14 de 17 portados, guardados en un parche

`designs/basemodel-adoption-res-country-state.patch` lleva el cambio de base y
los consumidores ya portados; se aplica con `git apply` sobre el árbol de este
commit. Con él, los diez archivos del parche quedan en verde salvo los tres de
abajo.

- Lecturas rehusadas (8): las pruebas no fijaban usuario, y bajo `BaseModel` la
  ACL rehúsa por defecto; las de la fuente corren como superusuario. Se
  envuelven en `sudo()` (`test_format_address_and_vat_label.py`,
  `test_res_partner_labels.py`, `test_sale_order_nonstored_fields.py`,
  `test_account_report_tax_tags.py`, `test_vies_and_iap.py`,
  `test_ir_fields_relational.py`). Los sitios de producción leen como el
  usuario activo, igual que la fuente.
- **Defecto real de consumidor**: `AccountAccountTag.get_tax_tags_domain`
  filtraba `country=<recordset vacío>` y no casaba la etiqueta con país nulo,
  así que un segundo `save()` duplicaba la etiqueta. La fuente recibe
  `country_id` (`False` sin país, `odoo19c: addons/account/models/account_account_tag.py:88-95`);
  el parche filtra por `country or None`.
- Reversos (`state_ids`, `cities`): `len()` en lugar de `.count()`.
- Ausencia de `state_id`: `not c.state_id` en lugar de `is None`.

## Lo que queda abierto: el contrato de `test_computed_many2one_absence.py`

Tres pruebas fijan, para un `Many2one` calculado en un modelo de Django
(`ResCompany.country`), que la ausencia se lee `None` y que un id inexistente
levanta `ResCountry.DoesNotExist`. Con `res.country` en `BaseModel` la lectura
da `res.country()` y no levanta, que es la forma de la fuente para todo
modelo. Cambiarlo toca el `Many2one` de cualquier dueño Django con comodelo
`BaseModel`, no sólo esta unidad: se decide leyendo `Many2one.__get__` y el
diseño que introdujo ese contrato, no por inferencia. Hasta entonces la unidad
no se aplica.

## Decisión sobre el contrato de ausencia

Resuelta midiendo el código, no por inferencia. `NonStoredMany2oneAccessor`
(`src/orm/fields.py:1508-1525`) declara que la regla la fija el **comodelo**:
uno del ORM entrega su recordset vacío, como `Many2one.convert_to_record`
(`odoo19c: odoo/orm/fields_relational.py:354-358`); uno de Django da `None`.
`_forward_get_object` (`src/orm/models.py:6658-6676`) hace de un id de un
comodelo `BaseModel` un `browse` sin consulta, sin `DoesNotExist`. Ningún
diseño fijaba `None` para dueños de Django: `test_computed_many2one_absence.py`
describía el comportamiento con `res.country` en Django. Sus tres casos se
reescriben contra la regla documentada: la ausencia es `res.country()` sin
consultas, y el id inexistente es un `browse` cuyo campo levanta `MissingError`.

## Implementación (2026-11-26)

`ResCountry(models.BaseModel)` y `ResCountryState(models.BaseModel)`; sin
migración (`makemigrations --check` sin cambios). Lo de
`designs/basemodel-adoption-res-country-state.patch` más los tres casos de
arriba. La función de producción cuyo cuerpo cambia:

- `AccountAccountTag.get_tax_tags_domain` filtra por `country or None`.
  Referencia: `_get_tax_tags_domain` (`odoo19c: addons/account/models/account_account_tag.py:88-95`).
  Pruebas: `tests/unit/base/test_country_state_basemodel.py::test_an_empty_country_filters_tax_tags_by_null`
  y `tests/unit/account/test_account_report_tax_tags.py::TestExpressionSaveCreatesItsTag::test_saving_the_expression_again_does_not_duplicate_the_tag`.

Subconjunto derivado (`ResCountry|res.country|country_id|state_id|\.country\b|country_code`,
74 archivos, `-n 4`): **1210 passed, 2 xfailed**.

## Anulaciones

- `get_tax_tags_domain` sin `or None`: caen exactamente las dos pruebas de la
  etiqueta nombradas arriba (2 de 13).
- `ResCountryState` de vuelta a `RecordLoaderMixin, models.Model`: cae
  exactamente `test_country_and_state_are_basemodel[ResCountryState]` (1 de 3).

Ambas restauradas y verificadas con `cmp`.

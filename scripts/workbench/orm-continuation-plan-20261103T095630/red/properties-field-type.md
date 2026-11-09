# RED — unidad 6e-1 (`Properties.type`)

Revisión base: `453c66b8`. Diseño: `designs/properties-field-type.md`.

```
uv run --frozen pytest -q --reuse-db -p no:cacheprovider \
    tests/unit/orm/test_properties_field_type.py
3 failed — AssertionError: assert 'json' == 'properties' (y
'properties_definition')
```

## GREEN, consumidores y anulación

`3 passed`. El cambio activó la optimización de fechas de propiedades en
`to_q`, que lee la definición en la base con la comprobación de lectura,
como la fuente (`odoo19c: odoo/orm/domains.py:1661-1688`). Tres casos de
`TestSearchByProperty` suponían compilar sin base y sin usuario: se les dio
la base de pruebas y un entorno de superusuario. `test_fields_properties.py`
+ el nuevo: `50 passed`.

Sin `type = 'properties'` en `Properties` caen exactamente 2 (el tipo y su
reflejo); el de `PropertiesDefinition` no depende de él.

Transversal: activa 11 sitios de `src/orm/models.py` y 2 de
`src/orm/domains.py`. La regresión amplia de la revisión es obligatoria.

Al tocar `test_fields_properties.py`, el gate de identificadores rehusó tres
claves de propiedad en español que ya fallaban en `HEAD` (medido sobre una
copia de la versión de `HEAD`: las mismas tres). Se tradujeron dentro de la
prueba (`'inventada'` → `'invented'`, `'sobra'` → `'extra'`, `'marca'` →
`'brand'`); son datos de la prueba, sin efecto en el árbol.

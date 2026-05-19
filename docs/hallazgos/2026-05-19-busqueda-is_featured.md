# Hallazgo 2026-05-19: TestBusqueda errors — Product.is_featured ausente

## Cluster investigado

`tests/integration/catalogue/test_sprint5.py::TestBusqueda` y `TestBusquedaFiltrosAvanzados` (UC-CAT-03 / UC-SRCH-01).

## Sintoma

Todos los tests del cluster fallan en setup con:

```
TypeError: Product() got unexpected keyword arguments: 'is_featured'
```

12 ERROR + algunos errores derivados en `TestBusquedaFiltrosAvanzados` (mismas fixtures).

## Causa raiz

Las fixtures `product_oshun`, `product_yemaya`, `product_sin_stock`, `product_inactivo` invocan `Product.objects.create(..., is_featured=True/False, ...)` (test_sprint5.py lineas 47, 65), pero el modelo `apps.catalogue.models.Product` no declara ningun campo `is_featured`. Solo tiene `is_active` y `is_published` (models.py linea 84-85). El test `test_busqueda_featured_aparece_primero` ademas asume que la respuesta serializada incluye `is_featured`, lo cual tampoco existe en `ProductSearchSerializer` (serializers.py linea 218 — campos declarados explicitamente).

Es una desincronizacion modelo/test: o el feature "producto destacado" se descarto sin actualizar los tests, o nunca se llego a implementar.

## Decision

**Skip-fix (fuera de scope de sesion).** La correccion requiere:

1. Decidir si la columna `is_featured` debe existir en el modelo (decision producto).
2. Si se agrega: nueva migracion, exponerla en `ProductSearchSerializer.Meta.fields`, ajustar orden de busqueda (`-is_featured, -relevance`).
3. Si no: actualizar tests para quitar el kwarg y eliminar `test_busqueda_featured_aparece_primero` o reescribirlo contra otro criterio de prioridad.

La instruccion de sesion explicita: "Don't touch the migrations themselves; if a test fails due to a model issue, document it." Se documenta y no se aplica fix.

## Impacto en re-baseline

12 errors de TestBusqueda + ~5 errors de TestBusquedaFiltrosAvanzados (heredan las mismas fixtures) provienen de esta unica causa. Resolverla bajaria ~17 errors del total.

## Tickets sugeridos

- BL-CAT-XX: definir si Product tiene atributo destacado (producto)
- TST-CAT-XX: realinear test_sprint5.py con el modelo actual una vez tomada la decision

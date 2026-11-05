# Unidades contractuales del ORM — evidencia por unidad

Banco donde se acumula, unidad por unidad, la evidencia de refutación de las
pruebas de contrato de `completar-raiz-orm`: qué mutación se aplicó al código
bajo prueba, qué defecto representa y qué prueba cayó. Referencia: `odoo19c`
en `odoo-tools@abe4040ec1a45beee90fb694e4eae4453e46b389`.

## Search Existing

| Candidato | Por qué no basta |
|---|---|
| `orm-continuation-plan-20261103T095630` | plan y asiento de unidades; no guarda mutaciones |
| `orm-symbol-presence-census-20260910T175850` | inventario y filas de evidencia; no guarda mutaciones |
| bancos por análisis (`basemodel-contract-reach-*`, `orm-command-intenum-*`) | uno por pregunta; las unidades rutinarias no justifican un banco cada una |

Veredicto: MISSING; un banco acumulativo, un archivo de salida por unidad.

## Salidas

- `outputs/<módulo>-<símbolo>-mutations.txt`: cada mutación, las pruebas que cayeron y el conteo.

Cada mutación se aplica a una copia restaurable del archivo y se verifica la
restauración con `cmp` antes de la siguiente.

Métrica: pruebas que caen por mutación.
Ciega a: defectos que ninguna de las mutaciones elegidas representa.

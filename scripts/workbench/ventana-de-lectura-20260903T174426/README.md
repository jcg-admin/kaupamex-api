# La ventana de lectura: cuando leer el archivo entero paga

Nace de `H-API-1072`. Cinco episodios de porte donde la afirmacion salio de una
ventana `sed`/`grep` que no incluia al refutador, y un sexto donde la prosa que
los documentaba dejo un tramo entero de tamanos **sin veredicto** — el ejecutor
lo detecto preguntando *"solo estas usando 95 % y 1 %, que pasa con el otro
4 %?"*.

## La pregunta

Leer un archivo entero cuesta mas tokens que una ventana. La comparacion
correcta no es esa: es contra el coste del episodio que la ventana produce. La
pregunta operativa es **en que tramo de tamano el ahorro deja de pagar**, y
para las dos poblaciones que se leen al portar: nuestro arbol y la referencia.

## Como se corre

```bash
eval "$(python3 scripts/reference_roots.py --env)"
python3 measure_reading_window_cost.py api=src odoo19c=$ODOO19C/odoo
python3 measure_reading_window_cost.py api=src --json      # para encadenarlo
```

## Lo medido (2026-09-03)

| Poblacion | Archivos | Cabe entero siempre |
|---|---|---|
| `api: src/` | 293 | **281 (95.9 %)** |
| `odoo19c: odoo/` | 534 | **510 (95.5 %)** |

Las dos distribuciones coinciden, asi que el criterio vale para las dos. El
tramo `>4000` son 3 archivos en cada poblacion — y el mayor de todos es
`odoo19c: odoo/orm/models.py`, 7130 lineas (~79 850 tokens): al portar contra
el, la ventana es obligatoria y por eso mismo tiene que declarar su corte.

## Por que el control importa

`tests/` no verifica que los numeros sean bonitos: verifica que **la particion
sea total** y que **ningun tramo se quede sin veredicto**, que es exactamente
el defecto del episodio 6. Un hueco entre tramos es invisible mirando los
tramos de uno en uno; solo aparece al encadenarlos.

Discrimina, medido: con el tramo `1501-4000` retirado caen 4 de 14 casos y
sobreviven los 10 que no dependen de el
(`outputs/control-discrimina-20260903T174426.txt`).

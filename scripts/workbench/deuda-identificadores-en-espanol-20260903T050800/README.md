# Deuda de identificadores en espanol — se puede barrer, y no es homogenea

Medido 2026-09-03T05:09:26 sobre `scripts/identifier_language_baseline.txt`.

## La pregunta

Si las **1024** entradas congeladas se pueden barrer con lo que ya existe, o
hace falta construir algo. El ejecutor lo pidio explicito: *"ya no queremos
Deuda heredada"*.

## La respuesta: no hace falta construir un instrumento

`scripts/rename_identifiers.py` ya renombra **por token y por posicion**, con
el guard de 3.12+ que la f-string exige (H-API-607). Lo que faltaba era el
**lexico** y el **reparto**, y esta pieza los produce.

## El censo

```
entradas: 1024 · nombres distintos: 766 · archivos: 176
por raiz: tests 760 · addons 241 · src 23
```

## Lo que cambia el plan

Las palabras que dominan el baseline **no son sustantivos**: son conectores —
`de` 140, `el` 139, `con` 80, `por` 79, `del` 64, `en` 62. Un conector
dentro de un identificador significa que el identificador es una **frase**, y
una frase no se traduce palabra a palabra:

```
test_crea_la_linea_con_el_producto
  MAL  test_creates_the_line_with_the_product   (palabra a palabra)
  BIEN test_it_creates_the_line_for_the_product (leyendo que mide)
```

Reparto por **forma**, no por raiz (`probes/split_mechanical_from_judgement.py`):

| clase | entradas | % | tests | addons | src |
|---|---|---|---|---|---|
| **mecanica** — sin conector, se cierra con el mapa | **499** | 48 % | 290 | 187 | 22 |
| **juicio** — con conector, se reescribe leyendo | **525** | 51 % | 470 | 54 | 1 |

La clase de juicio se concentra en **tests** (470 de 525, el 90 %). El codigo
de produccion es casi todo mecanico: 209 de sus 264 entradas.

## El plan, por tramos

1. **209 mecanicas de `addons` + `src`** — codigo de produccion, mapa
   mecanico. Donde mas importa y donde mas barato sale.
2. **290 mecanicas de `tests`** — mismo mapa, otro alcance.
3. **55 de juicio en `addons` + `src`** — pocas, y son API que se lee.
4. **470 de juicio en `tests`** — por archivo; los 12 primeros concentran
   ~250, asi que el barrido no es plano.

Cada tramo cierra con su subconjunto derivado en verde y **encoge el
baseline**. La condicion de cierre no es «bajar el conteo» sino **retirar el
archivo**: mientras exista, el gate admite deuda.

## Lo que este censo NO puede ver

- Si dos entradas con el mismo nombre son la misma ligadura o dos distintas:
  lo decide el reescritor por posicion, no el censo.
- El identificador espanol que el lexico del gate no sabe ver — el baseline es
  **cota inferior**, no el universo.
- La frase **sin** conectores (`test_producto_borrado_falla`), que cae en
  «mecanica» y no lo es: la cifra de 525 es cota inferior de la clase que
  exige juicio.
- Si una traduccion propuesta colisiona con un nombre ya ligado en ese ambito.
- Los **nombres de archivo** en espanol, que mide otro gate
  (`docs: check_script_naming.py --idioma`).

## Como se re-mide

```bash
python3 scripts/workbench/deuda-identificadores-en-espanol-20260903T050800/measure_spanish_identifier_debt.py
python3 scripts/workbench/deuda-identificadores-en-espanol-20260903T050800/probes/split_mechanical_from_judgement.py
```

Las cifras envejecen con cada tramo del barrido: se leen del comando, no de
este documento.

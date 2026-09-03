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
para las CINCO poblaciones que se leen al portar: nuestro arbol y los cuatro
alias de la referencia. Medir una sola y concluir sobre «la referencia» es el
eje de la version que :ref:`h-api-76` y :ref:`h-api-227` ya registraron.

## Como se corre

```bash
python3 measure_reading_window_cost.py api=src --reference   # nuestro arbol + los 4 alias
python3 measure_reading_window_cost.py api=src --json        # para encadenarlo
```

Las raices de la referencia salen de `scripts/reference_roots.py`, nunca de
literales: copiarlas aqui seria la segunda fuente de verdad que su propio
docstring prohibe (`H-API-335`).

## Lo medido (2026-09-03)

| Poblacion | Archivos .py | Cabe entero siempre (<=1500) |
|---|---|---|
| `api: src/` | 293 | 281 (**95.9 %**) |
| `odoo18c` (sin su anidado) | 7 988 | 7 898 (98.9 %) |
| `odoo18c/enterprise` (sin alias) | 13 869 | 13 768 (99.3 %) |
| `odoo18e` | 11 989 | 11 902 (99.3 %) |
| `odoo19c` | 8 566 | 8 459 (98.8 %) |
| `odoo19e` | 7 535 | 7 491 (99.4 %) |

Las seis distribuciones coinciden en lo que decide: **entre el 95.9 % y el
99.4 % cabe entero**. Nuestro arbol es el que menos, y aun asi son 281 de 293.

El tramo `>4000` son 3 archivos aqui y entre 3 y 13 en cada alias. El mayor de
todos es `odoo18e: test_l10n_be_hr_payroll_account/tests/test_payslips_validation.py`,
10 746 lineas (~112 937 tokens); del lado que se porta, `odoo19c: odoo/orm/models.py`
con 7 130 (~79 850). Ahi la ventana es obligatoria, y por eso mismo tiene que
declarar su corte.

## La premisa que se corrigio al medir

En dos pasos, los dos senalados por el ejecutor.

**Uno:** la primera version media **una** raiz y concluia sobre «la
referencia». Son cuatro alias, y los declara `scripts/reference_roots.py`.

**Dos:** al medirlos, `odoo18c` daba 21 857 archivos. Su raiz `18.x/odoo-18`
**contiene** `enterprise/` con 13 869 `.py` dentro; Community 18 real son
**7 988**. La reaccion barata era excluirlo — y es la equivocada: ese anidado
tiene **1292 addons y 191 no existen en** `odoo18e` (`auth_passkey`,
`certificate`, `account_iso20022`, `accountant`...), mas 29 comunes con
licencia distinta.

Importa porque **la licencia decide el mecanismo de porte**: copiar con
atribucion frente a reimplementar. `analisis-inventario-account-cuatro-arboles`
midio que 22 de 75 addons de `account` declaran `LGPL-3` en algun arbol —cuatro
solo en 18— y `analisis-alcance-website-sale-cuatro-arboles`, que **17
cambiaron de veredicto** al mirar las cuatro poblaciones en vez de una. Por eso
el anidado se mide **aparte**, no se descarta ni se funde. Registrado como
`H-API-1073`; su alias es la tarea `#65`.

## Por que el control importa

`tests/` no verifica que los numeros salgan bonitos: verifica que **la
particion sea total** y que **ningun tramo se quede sin veredicto**, que es el
defecto que el ejecutor detecto en la prosa de `H-API-1072`. Un hueco entre
tramos es invisible mirando los tramos de uno en uno; solo aparece al
encadenarlos.

Discrimina, medido: con el tramo `1501-4000` retirado caen 4 de 14 casos y
sobreviven los 10 que no dependen de el
(`outputs/control-discrimina-20260903T174426.txt`).

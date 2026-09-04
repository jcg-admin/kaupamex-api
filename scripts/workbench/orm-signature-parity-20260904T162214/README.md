# La firma: el cuarto eje que ningun instrumento del arbol medía

Nace de la tarea **#367**. La directiva del ejecutor enumera cuatro cosas que se
portan —**archivos, clases, funciones y firmas de funcion**— y los dos censos
del eje ORM cubren las tres primeras. La cuarta esta declarada como ceguera,
verbatim, en el manifiesto del censo de raiz:

> La firma. Un simbolo con el mismo nombre y otros parametros cuenta como
> presente.

`check_porte_completo`, que cubre el resto del arbol, tampoco la compara.
Consecuencia: **un puerto con el nombre correcto y otros parametros pasa los dos
gates** — el conteo generoso contra el que `porte-completo-no-parcial.md` ya
advierte sin instrumento que lo vea.

## Como se corre

```bash
cd /home/user/kaupamex-api
eval "$(python3 scripts/reference_roots.py --env)"

python3 scripts/workbench/orm-signature-parity-20260904T162214/signature_parity.py
python3 scripts/workbench/orm-signature-parity-20260904T162214/signature_parity.py --detalle
uv run pytest scripts/workbench/orm-signature-parity-20260904T162214/tests/ -q
bash scripts/workbench/orm-signature-parity-20260904T162214/neutralize_and_measure.sh
```

Sin `$ODOO19C` el instrumento **rehusa con exit 2 y no emite conteo**: un 0 sin
la referencia seria un verde falso.

## El control, que es lo que hace citable la cifra

Un comparador que devolviera siempre «no diverge» pasa todos los casos
sinteticos que exigen lista vacia. `neutralize_and_measure.sh` le anula
`classify()` en proceso —sin escribir un archivo, asi que no hay nada que
restaurar— y mide **que cae y que sobrevive**:

| | intacto | anulado |
|---|---|---|
| `clear_all_caches` marcado | si | **no** — cae: el control discrimina |
| `init_models` marcado | no | no — sobrevive: mide otra cosa |
| la suite | 20 passed | **9 failed**, 11 passed |

Los dos anclajes son **reales y verificados leyendo la fuente**, no aceptando el
veredicto del propio instrumento, que seria circular:

- `clear_all_caches` diverge — la referencia lo declara metodo de `Registry`
  (`odoo19c: odoo/orm/registry.py:988`, con `self`) y aqui es funcion de modulo
  (`src/orm/registry.py:303`, sin el).
- `init_models` coincide — los cinco posicionales en el mismo orden y `install`
  con default en ambos lados (`:723` contra `:2155`).

## Dos defectos del instrumento que el arbol real destapo

Ninguno lo habria visto un caso fabricado; los dos salieron de correrlo contra
`odoo/orm` y verificar a mano lo que reportaba.

1. **Los stubs de `@typing.overload`.** La referencia declara `constrains` y
   `depends` tres veces cada uno —dos stubs de tipo y la implementacion real—.
   Leer el primero publicaba `(func, /)` como firma de un simbolo cuya firma
   real es `(*args)`: dos divergencias **fabricadas por el instrumento**.
   91 → 89.
2. **El nombre declarado mas de una vez.** 83 nombres distintos (`__eq__`,
   `convert_to_column`, `create`, `read`, `write`…) producian un par arbitrario:
   comparar el `convert_to_column` de la clase A de la fuente contra el que aqui
   aparece primero mide un par que nadie eligio, y su veredicto no informa ni de
   coincidencia ni de divergencia. Quedan **fuera** de la comparacion, con su
   conteo publicado. 89 → 65, sobre un denominador limpio de 352.

## Lo que este trabajo NO cierra

El simbolo **ausente** aqui no es asunto de este instrumento: lo mide el censo
de raiz, y sumar las dos cifras inflaria el eje de firma con deuda que ya tiene
su propio cubo. Los 83 nombres ambiguos exigen calificar por clase, que este
arbol no puede en `models.py` mientras `BaseModel` no exista aqui como clase
—tarea **#365**—. Y el alcance es `odoo/orm` ↔ `src/orm`: extenderlo a las
demas raices espejadas es trabajo aparte.

# El eje de senalizacion de `Registry` — que trae el stack y que hay que construir

Pieza de banco de la tarea **#342** (tramo 5) y de la **#256**.

## La pregunta

De los siete simbolos que `odoo19c: odoo/orm/registry.py` declara entre
`setup_signaling` (`:1036`) y `cursor` (`:1165`), cual cae en cada uno de los
dos cubos del criterio del ejecutor:

- **el stack lo trae hecho** — hay un simbolo instalado y basta llamarlo;
- **el stack tiene con que construirlo** — no hay simbolo hecho, pero las
  primitivas estan y no hace falta ninguna dependencia de fuera.

Y con que entrada del `INVENTORY` se paga cada uno.

## Lo que se midio

```
READY:     1 de 7 — cursor
BUILDABLE: 6 de 7 — setup_signaling, get_sequences, check_signaling,
                    signal_changes, reset_changes, manage_changes
BLOCKED:   0 de 7 — ninguno
```

`BLOCKED: 0` es el resultado que importa: **ningun simbolo del tramo tiene un
bloqueo medido**, asi que los siete se implementan. No se deriva ninguno.

`cursor` es el unico READY porque Django ya entrega el cursor con su propio
pool — `connections[alias].cursor()` hace lo que `self._db.cursor()` de la
fuente. Es divergencia de mecanismo con el mismo contenido.

## Para que existe este eje, y por que no es cosmetico

La fuente guarda una **secuencia por cache** en tablas `orm_signaling_<nombre>`:
`signal_changes` (`:1110`) la incrementa cuando un proceso invalida, y
`check_signaling` (`:1076`) la lee al abrir cada peticion para enterarse de lo
que invalido **otro** proceso. Con `workers = 4` en
`setup/gunicorn.conf.py:93`, sin ese eje una invalidacion local deja a los
otros tres procesos sirviendo contenido viejo. Es la mitad que
:ref:`h-api-980` ya declaro ausente, y la razon de la tarea **#256**.

## La premisa que la medicion corrigio

La premisa de entrada era *«el eje no existe y la invalidacion la resuelve
`clear_cache`»*. Medido, el arbol tiene **dos estructuras de cache paralelas y
disjuntas**:

| Estructura | Donde | Quien la escribe |
|---|---|---|
| de modulo — `_CACHES`, el conjunto `cache_invalidated`, `clear_cache()`, `clear_all_caches()` | `registry.py:136,140,208,227` | los 158 sitios que llaman `clear_cache`; el conjunto se escribe en `:218` y `:234` |
| de instancia — `self.__caches`, la property `Registry.cache_invalidated` sobre un `threading.local` | `registry.py:1658,1884` | hoy, solo los tests |

`signal_changes` tendria que leer la **segunda**, que es la que nadie escribe.
Portar los siete metodos sin reconciliar las dos dejaria un eje que senaliza
siempre cero: un verde que no discrimina — el sub-patron D de
`metrica-decide-la-conclusion.md`. Por eso el tramo 5 incluye la
reconciliacion, y no solo el porte.

## El control que discrimina

```bash
bash scripts/workbench/registry-signaling-axis-support-20260903T063526/neutralize_and_measure.sh
```

Retira `src/` del `PYTHONPATH` y vuelve a correr el clasificador. Con las
primitivas propias fuera de alcance, **cinco de los siete** pasan a `BLOCKED`
y el guion nombra cual falta en cada uno (`tools.sql.SQL`,
`orm.registry._CACHES_BY_KEY`, `orm.registry.Registry.new`). Sin ese
contraste, un clasificador que dijera `BUILDABLE` sin resolver nada pasaria
los siete y el verde no distinguiria «las primitivas estan» de «el instrumento
no las mira».

El control de unidad, escrito antes del instrumento, vive en `tests/`.

## Como se corre

```bash
DJANGO_SETTINGS_MODULE=config.settings.testing PYTHONPATH=src \
    uv run python scripts/workbench/registry-signaling-axis-support-20260903T063526/classify_signaling_axis_support.py

DJANGO_SETTINGS_MODULE=config.settings.testing PYTHONPATH=src \
    uv run pytest scripts/workbench/registry-signaling-axis-support-20260903T063526/tests -q
```

`--json` emite el reparto como JSON; `--strict` sale 1 si algo quedara
bloqueado.

## Que NO responde

Lo declara el `blind_to` del `manifest.json`. Las dos cegueras que mas pesan
aqui: mide que el nombre **resuelve**, no que su conducta coincida con la de
la referencia; y **no mira el esquema** — las siete tablas
`orm_signaling_<nombre>` no existen todavia, y como aqui el DDL lo emiten las
migraciones, su ausencia no aparece como `BLOCKED`. Esa mitad la cierra la
migracion del tramo, no este clasificador.

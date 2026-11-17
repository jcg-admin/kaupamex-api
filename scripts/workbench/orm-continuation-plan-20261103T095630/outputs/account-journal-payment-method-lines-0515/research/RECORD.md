# Investigación delegada — unidad `account-journal-payment-method-lines-0515`

Instrucciones 4.4.0 §11 y 4.4.1. Tres subagentes de sólo lectura, lanzados
en paralelo mientras corría el subconjunto derivado de la unidad.

- `inputs/` — el encargo íntegro de cada lote.
- `proposals/` — el informe final de cada subagente, extraído de su
  transcript por el coordinador (terminaron antes de que 4.4.1 exigiera que
  cada uno escribiera su archivo). `manifest.json` lleva su sha256.
- `verdicts.tsv` — la tabla del coordinador. Los informes son propuestas
  (nivel 3); una fila sube a nivel 2 sólo si el coordinador reprodujo la
  medición, y la columna `verification_command` dice con qué. Las filas
  `UNVERIFIED` y `MISSING` son trabajo pendiente y no se retiran.

Ninguna fila es aceptación: eso lo decide el `verify` de la unidad y su
asiento.

Costo declarado por el arnés (titular, excluye la caché releída): 410 205,
422 602 y 437 021 tokens; 7, 15 y 20 usos de herramienta; 81, 86 y 133 s.

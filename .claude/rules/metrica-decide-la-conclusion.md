# La métrica decide la conclusión — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/metrica-decide-la-conclusion.md`. **No existía
copia aquí** —medido: 0 archivos— y esta regla gobierna cómo se escribe un test,
que es trabajo de este repo. Una sesión con sólo `api` en alcance no la cargaba.

Invariante: **antes de concluir a partir de una medición, declarar qué mide y
qué NO puede ver** (`Métrica:` / `Ciega a:` junto a la cifra). Si "Ciega a"
incluye el fenómeno sobre el que se va a concluir, la conclusión no se emite.

## D — el verde que no discrimina (el que aplica al escribir tests)

Un control —un test, un gate, la premisa de una tarea— **pasa**, y su paso no
distingue *"el fenómeno ocurre"* de *"el instrumento no lo puede ver"*. Nadie lo
nota: el resultado es el esperado.

**Todo control declara qué lo haría fallar, y se prueba contra eso:**

1. **Un test negativo apunta a un objeto que EXISTE.** Un caso que pide
   `/etc/passwd` y afirma 404 pasa por `os.path.isfile` si la ruta no existe —
   aunque la guarda que dice medir no exista.
2. **Un caso de seguridad se mide con la guarda anulada.** Se retira, se corre
   el subconjunto, y **caen exactamente** los casos que dependen de ella. Los
   que sobrevivan miden otra cosa; lo que no vale es no saberlo. Se restaura y
   se verifica con `git diff --stat` vacío.
3. **Una tarea se despacha con su premisa medida, no leída** — Premise Gate 0a
   de `auto-audit-before-writing.md`.

Medido en #639: con el confinamiento sustituido por un `os.path.isfile` pelado,
el subconjunto pasa de **9 passed** a **6 failed, 3 passed** — caen los seis de
confinamiento, sobreviven los dos de permiso y el control positivo. Bajo esa
versión `/etc/passwd` devolvió **200**. Ver :ref:`h-api-766`.

Un test que sigue verde cuando la guarda desaparece no es una red: es un adorno
que da confianza falsa.

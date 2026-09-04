# Porte completo, no parcial — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/porte-completo-no-parcial.md`. Aquí sólo los
invariantes operativos.

**Al portar un archivo se portan TODOS sus símbolos.** Si alguno no se porta, el
artefacto declara **cuántos, cuáles y por qué** — en el archivo y en el commit.
Tres desenlaces válidos para un símbolo que no se porta: divergencia de mecanismo
declarada, bloqueo medido con sucesor registrado, o DESCONOCIDO con su condición
de cierre. Omitirlo no es uno de ellos.

**Si el stack no trae el mecanismo, se construye** — API pública, luego internos
de Django/DRF leídos en el paquete instalado, luego PostgreSQL nativo vía
`SQL()`/`Query`. *"Este ORM no tiene ese constructor"* describe el punto de
partida, no cierra nada.

## La licencia cambia el MECANISMO, nunca la fidelidad

| Licencia | Mecanismo |
|---|---|
| **LGPL-3** (Community) | copia + adaptación con atribución; porte casi literal permitido |
| **AGPL-3** (p. ej. pretix) | reimplementación fiel del patrón; copiar verbatim es decisión del ejecutor (copyleft fuerte) |
| **OEEL-1 / OPL-1** (Enterprise) | reimplementación nativa del patrón y del contrato, sin pegar el texto propietario |

El derecho de autor protege el **texto literal**, no el modelo de datos, el API
ni el comportamiento. Un porte nativo replica los mismos modelos, campos, flujo
y comportamiento con código nuestro: **funcionalmente idéntico**.

**«Es propietario» NO autoriza a portar menos.** Mismo nombre, misma firma,
mismos atributos de clase, mismo comportamiento — sólo cambia que el cuerpo se
escribe en vez de copiarse. Recortar alcance citando la licencia es el camino
barato con otra coartada.

**La postura se lee POR MANIFIESTO.** «Enterprise es propietario» no es
uniforme: medido 2026-08-29, **599 de 1171** addons de `odoo18e` son LGPL-3, y
**5 de 649** de `odoo18c` son OEEL-1.

```bash
grep -oP "'license'\s*:\s*'\K[^']+" \
  "$(python3 -c "import sys;sys.path.insert(0,'scripts');import reference_roots as R
print(R.addon_root('<addon>','<alias>'))")/__manifest__.py"
```

El mecanismo empleado se declara en el docstring del puerto, junto a la
procedencia.

## El guion bajo se porta — es el contrato (H-API-581)

**Un método que la referencia declara `_foo` se porta como `_foo`.** Quitar el
guion bajo no renombra: **promueve el símbolo a API pública**. PEP 8 lo fija —
`_nombre` significa *"uso interno; no lo llames desde fuera"*.

La referencia usa esa frontera a propósito: `activity_schedule` (público) junto a
`_activity_schedule_with_view` (privado), en el mismo archivo. Aplanarlos borra
una distinción escrita a mano.

```python
def _default_activity_type(self):        # BIEN — como la fuente
def default_activity_type(self):         # MAL  — publica lo reservado
```

No son este defecto: (a) que la referencia declare **ambos** (`action_done` y
`_action_done`) — eso es porte parcial, otro instrumento; (b) que el símbolo sea
un **campo** — `_compute_activity_state` es privado porque el público es el campo
`activity_state`.

Medido 2026-08-14: **162** en 47 archivos sobre 529 con contraparte. Prospectivo,
se paga al tocar el archivo. Barrido: **#337**. Gate: **#338**.

## Cómo se mide

```bash
python3 -c "
import ast,pathlib,sys
def met(p):
    return {n.name for c in ast.walk(ast.parse(p.read_text()))
            if isinstance(c,ast.ClassDef) for n in c.body
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
R,M = met(pathlib.Path(sys.argv[1])), met(pathlib.Path(sys.argv[2]))
print('ausentes:', sorted(R-M))
print('despromovidos:', sorted(m for m in R if m.startswith('_')
      and m[1:] not in R and m[1:] in M and m not in M))
" \$ODOO19C/addons/<x>/models/<y>.py addons/<x>/models/<y>.py
```

El conteo de líneas es la señal barata: una diferencia de 2× es una pregunta que
se responde **antes** de commitear. Y cuidado con el conteo generoso — un método
cuenta como portado cuando **hace lo que hace el de la referencia**, no cuando
existe uno con nombre parecido.

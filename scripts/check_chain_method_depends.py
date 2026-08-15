#!/usr/bin/env python3
"""Quien encadena un método declara al addon que lo declara — el gate del orden.

``orm.method_chain.chain_method`` es el ``super()`` que el idioma de extensión
por ``setattr`` no tiene. Su corrección depende **del orden de instalación**:
la cadena se arma en ``AppConfig.ready()``, y ``ready()`` corre en el orden de
``INSTALLED_APPS``, que se deriva del grafo ``depends``.

El defecto
----------

Si el addon que **declara** el símbolo encadenado no está en el ``depends`` del
que lo encadena, el orden entre los dos queda indefinido. Cuando el declarante
corre **después**, su ``setattr`` aterriza encima y sepulta la cadena: el
eslabón instalado antes desaparece sin ``ImportError``, sin fallo de arranque y
sin test rojo — igual que un addon partido entre raíces.

Es lo que registró :ref:`h-api-564`: ``account_qr_code_emv`` extendía
``base.ResPartnerBank`` sin importar ``account``, pero el **terminal** de esa
cadena lo instala ``account/models/res_partner_bank.py``. Al derivar
``LOCAL_APPS`` del grafo, el satélite subió a profundidad 0 y quedó sepultado.

Por qué un ``depends`` medido por imports no lo ve
---------------------------------------------------

Porque el archivo **no importa** al declarante: importa la *clase*, que vive en
otro addon (``base``), y encadena un método que un tercero (``account``)
instaló sobre ella. El grafo de imports es correcto y aun así incompleto — la
arista que importa no es la del módulo, es la del **símbolo**.

Quién cuenta como dueño — y por qué los pares NO
-------------------------------------------------

Dueño del símbolo es quien pone el **fondo** de la cadena, no cualquiera que
contribuya a ella. Tres formas, las tres derivables del AST:

1. el addon que declara la **clase** (tiene que existir antes que nadie cuelgue
   nada de ella);
2. el addon que declara el método en el **cuerpo** de esa clase;
3. el addon que lo instala y del que **otro instalador ya depende** — el
   ancestro común. Es la forma que ``account`` tiene frente a sus satélites, y
   la que un ``depends`` medido por imports no puede ver.

Dos addons que encadenan el mismo método **sin** que uno dependa del otro son
**pares**, no dueños, y este gate no los señala. La referencia los deja
igual de desordenados —``odoo19c: account_qr_code_{emv,sepa}`` declaran ambos
``depends: ['account']`` y ninguno al otro— porque su mecanismo es insensible
al orden ahí: el relevo despacha por ``qr_method`` y el acumulador se reordena
después por secuencia. Exigirles un orden sería inventar una regla que la
referencia contradice.

Qué mide, y qué NO
------------------

*Métrica:* por cada llamada a ``chain_method(Cls, 'nombre', …)``, si cada dueño
de ``Cls.nombre`` —en el sentido de las tres formas de arriba— está en el cierre
transitivo del ``depends`` del que encadena.
*Ciega a:* un método instalado por una vía que no sea ``chain_method``/
``setattr`` con nombre literal (p. ej. ``type()`` dinámico o un nombre
computado); al orden **entre pares**, que queda indefinido a propósito; y a la
homonimia — dos clases distintas con el mismo nombre en addons distintos se
cuentan juntas, lo que puede exigir de más, nunca de menos.

Uso
---

    python3 scripts/check_chain_method_depends.py            # reporte
    python3 scripts/check_chain_method_depends.py --quiet    # sólo el conteo
    python3 scripts/check_chain_method_depends.py --strict   # exit 1 si falla
"""
from __future__ import annotations

import ast
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'src'))

from modules.module import ADDONS_PATHS, load_manifest

#: Funciones que instalan un atributo sobre una clase ajena.
INSTALLERS = ('chain_method', 'setattr')


def addon_of(path: Path, roots=ADDONS_PATHS) -> str | None:
    """El addon al que pertenece el archivo, o ``None`` si está fuera."""
    for root in roots:
        try:
            return path.relative_to(Path(root)).parts[0]
        except ValueError:
            continue
    return None


def _called_name(node: ast.Call) -> str | None:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return None


def _literal_strings(node: ast.AST) -> list[str]:
    """Las cadenas literales que cuelgan del nodo (tuplas/listas anidadas)."""
    return [n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _method_names(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> list[str]:
    """Los nombres de método que la llamada instala.

    Normalmente uno y literal. Cuando es una variable, se resuelve subiendo al
    ``for`` que la liga y tomando las cadenas de su iterable — el idioma con el
    que ``account`` instala sus once terminales de una vez. Sin esta resolución
    el gate sería ciego justo al declarante que el episodio de :ref:`h-api-564`
    dejó fuera del ``depends``.
    """
    arg = call.args[1]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return [arg.value]
    if not isinstance(arg, ast.Name):
        return []

    nodo: ast.AST | None = call
    while nodo is not None:
        if isinstance(nodo, ast.For) and arg.id in _bound_names(nodo.target):
            return _literal_strings(nodo.iter)
        nodo = parents.get(nodo)
    return []


def _bound_names(target: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def scan(roots=ADDONS_PATHS):
    """Recorre el árbol.

    Devuelve ``(declara_clase, cuerpo, instala, llamadas)`` — el cuerpo de la
    clase y la instalación por ``setattr`` se guardan **por separado** porque
    no significan lo mismo: la primera es siempre dueña, la segunda sólo si el
    grafo la pone debajo (ver ``owners``).
    """
    declara_clase: dict[str, set[str]] = defaultdict(set)
    cuerpo: dict[tuple[str, str], set[str]] = defaultdict(set)
    instala: dict[tuple[str, str], set[str]] = defaultdict(set)
    llamadas: list[tuple[str, Path, int, str, str]] = []

    for root in roots:
        for path in sorted(Path(root).rglob('*.py')):
            addon = addon_of(path, roots)
            if addon is None:
                continue
            try:
                tree = ast.parse(path.read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue

            parents = {hijo: padre
                       for padre in ast.walk(tree)
                       for hijo in ast.iter_child_nodes(padre)}

            # ``from <otro addon> import IrHttp as BaseIrHttp`` — el nombre
            # ORIGINAL de cada símbolo importado, por su alias local. Es lo que
            # distingue declarar una clase de heredarla (ver abajo).
            importado_como = {
                (alias.asname or alias.name): alias.name
                for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                for alias in n.names
            }

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Una clase que HEREDA de otra del mismo nombre lógico es la
                    # extensión, no la declaración: no instala nada por sí misma,
                    # así que no es dueña del símbolo. Es el idioma con el que la
                    # referencia extiende ``ir.http`` desde un addon
                    # (``odoo19c: addons/utm/models/ir_http.py``), y sin esta
                    # distinción el gate atribuía ``IrHttp.is_a_bot`` —que define
                    # e instala ``web`` sobre ``base``— a cualquier addon con una
                    # clase llamada ``IrHttp``. Ver :ref:`h-api-635`.
                    hereda_del_mismo = any(
                        isinstance(b, ast.Name)
                        and importado_como.get(b.id) == node.name
                        for b in node.bases
                    )
                    if not hereda_del_mismo:
                        declara_clase[node.name].add(addon)
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            cuerpo[(node.name, item.name)].add(addon)
                    continue
                if not isinstance(node, ast.Call) or len(node.args) < 2:
                    continue
                nombre = _called_name(node)
                if nombre not in INSTALLERS:
                    continue
                cls = ast.unparse(node.args[0])
                for metodo in _method_names(node, parents):
                    instala[(cls, metodo)].add(addon)
                    if nombre == 'chain_method':
                        llamadas.append((addon, path, node.lineno, cls, metodo))

    return declara_clase, cuerpo, instala, llamadas


def manifest_depends(addon: str) -> list[str] | None:
    """``depends`` declarado, o ``None`` si el addon no tiene manifest."""
    manifest = load_manifest(addon)
    return list(manifest.get('depends') or ()) if manifest else None


def transitive_depends(addon: str, cache: dict[str, set[str]],
                       depends_of=manifest_depends) -> set[str]:
    """Cierre transitivo del ``depends`` — lo que el grafo garantiza antes."""
    if addon in cache:
        return cache[addon]
    cache[addon] = set()          # corta ciclos declarados (ver tarea #322)
    directos = set(depends_of(addon) or ())
    total = set(directos)
    for dep in directos:
        total |= transitive_depends(dep, cache, depends_of)
    cache[addon] = total
    return total


def owners(cls: str, metodo: str, declara_clase, cuerpo, instala,
           cache: dict[str, set[str]], depends_of=manifest_depends) -> set[str]:
    """Los dueños del símbolo — las tres formas del docstring del módulo.

    Un instalador es dueño sólo si **otro instalador ya depende de él**: eso lo
    pone en el fondo de la cadena por construcción del grafo. Los instaladores
    mutuamente incomparables son pares y no entran.
    """
    instaladores = instala.get((cls, metodo), set())
    ancestros = {
        candidato for candidato in instaladores
        if any(candidato in transitive_depends(otro, cache, depends_of)
               for otro in instaladores - {candidato})
    }
    return declara_clase.get(cls, set()) | cuerpo.get((cls, metodo), set()) | ancestros


def violations(roots=ADDONS_PATHS, depends_of=manifest_depends):
    """Devuelve ``(fallas, sin_manifest, total_llamadas)``.

    ``depends_of`` se inyecta para poder ejercitar el gate contra un estado
    histórico del árbol sin tocar ningún manifest — ver el control positivo de
    ``tests/unit/scripts/test_check_chain_method_depends.py``.
    """
    declara_clase, cuerpo, instala, llamadas = scan(roots)
    cache: dict[str, set[str]] = {}
    fallas = []
    sin_manifest = set()

    for addon, path, lineno, cls, metodo in llamadas:
        duenos = owners(cls, metodo, declara_clase, cuerpo, instala,
                        cache, depends_of) - {addon}
        if not duenos:
            continue
        if depends_of(addon) is None:
            sin_manifest.add(addon)
            continue
        visibles = transitive_depends(addon, cache, depends_of) | {addon}
        faltan = sorted(duenos - visibles)
        if faltan:
            fallas.append((addon, path, lineno, cls, metodo, faltan))

    return fallas, sorted(sin_manifest), len(llamadas)


def main() -> int:
    quiet = '--quiet' in sys.argv
    strict = '--strict' in sys.argv

    fallas, sin_manifest, total = violations()
    alcance = (f'alcance medido: {total} llamadas a chain_method; '
               f'{len(sin_manifest)} addon(s) sin manifest, no medibles')

    if quiet:
        print(len(fallas))
        return 1 if (strict and fallas) else 0

    if not fallas:
        print(f'OK: todo consumidor de chain_method declara al dueño del '
              f'símbolo que encadena ({alcance})')
        if sin_manifest:
            print(f'  sin manifest: {", ".join(sin_manifest)}')
        return 0

    print(f'FALLA: {len(fallas)} llamada(s) encadenan un símbolo cuyo dueño no '
          f'está en su depends ({alcance}).')
    print('El orden de ready() queda indefinido: si el dueño corre después, su '
          'setattr sepulta la cadena sin avisar.\n')
    for addon, path, lineno, cls, metodo, faltan in fallas:
        print(f'  {addon}  {path}:{lineno}')
        print(f'      encadena {cls}.{metodo} — falta en depends: {faltan}')
    print('\nArreglo: añadir el addon dueño al depends del que encadena.')
    if sin_manifest:
        print(f'No medibles (sin manifest): {", ".join(sin_manifest)}')
    return 1 if strict else 0


if __name__ == '__main__':
    raise SystemExit(main())

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


def _clases_de_callback(tree: ast.AST) -> dict[str, str]:
    """``{nombre_de_función: ClaseDestino}`` de cada ``extend_model(…, luego=fn)``.

    El idioma que la tarea #332 vuelve norma nombra la clase en ``extend_model``
    y no en el ``chain_method``::

        def _chain_res_users(model):
            chain_method(model, '_check_credentials', …)   # ← args[0] es 'model'

        extend_model('base', 'ResUsers', luego=_chain_res_users)

    Sin este mapa el gate registra el instalador bajo la clase ``model``, que no
    existe: las formas 1 y 2 quedan vacías por construcción y la 3 dispara entre
    **pares**, que es justo lo que el docstring del módulo promete no señalar.
    Ver :ref:`h-api-782`.
    """
    de_callback: dict[str, str] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _called_name(node) == 'extend_model'):
            continue
        destino = _literal_strings(ast.Tuple(elts=list(node.args), ctx=ast.Load()))
        if not destino:
            continue
        for kw in node.keywords:
            if kw.arg == 'luego' and isinstance(kw.value, ast.Name):
                de_callback[kw.value.id] = destino[-1]
    return de_callback


def _clase_instalada(call: ast.Call, parents: dict[ast.AST, ast.AST],
                     de_callback: dict[str, str]) -> str:
    """La clase sobre la que instala la llamada, resolviendo el callback.

    Devuelve la fuente del primer argumento tal cual, salvo cuando es un
    **parámetro** de una función que ``extend_model`` pasa como ``luego=``: ahí
    la clase real es la que ``extend_model`` nombra.
    """
    cls = ast.unparse(call.args[0])
    if not isinstance(call.args[0], ast.Name):
        return cls
    nodo: ast.AST | None = call
    while nodo is not None:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parametros = {a.arg for a in nodo.args.args}
            if nodo.name in de_callback and cls in parametros:
                return de_callback[nodo.name]
            return cls
        nodo = parents.get(nodo)
    return cls


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

            de_callback = _clases_de_callback(tree)

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
                cls = _clase_instalada(node, parents, de_callback)
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

    **La forma 2 cierra la pregunta; la 1 no** (:ref:`h-api-782`). Un método
    declarado en el **cuerpo** de la clase existe al definirse la clase, así que
    ningún ``setattr`` de ningún ``ready()`` puede precederlo: el fondo es
    inequívoco y la forma 3 sólo puede añadir un **par** disfrazado de dueño.
    Declarar la *clase* no da esa garantía —el terminal puede instalarlo un
    tercero, que es exactamente el caso de ``account`` frente a
    ``account_qr_code_emv``— así que ahí la forma 3 sigue haciendo falta.

    Medido en el episodio: ``base`` declara ``_check_credentials`` en el cuerpo
    de ``ResUsers``, y aun así la forma 3 elegía además a ``authz_totp`` —porque
    ``authz_totp_mail`` depende de él— y exigía que ``authz_passkey`` lo
    declarara. La referencia dice lo contrario: ``odoo19c:
    auth_passkey/__manifest__.py`` declara ``depends: ['base_setup', 'web']`` y
    **no** nombra a ``auth_totp``. Son pares allá y aquí.
    """
    en_cuerpo = cuerpo.get((cls, metodo), set())
    if en_cuerpo:
        return declara_clase.get(cls, set()) | en_cuerpo

    instaladores = instala.get((cls, metodo), set())
    ancestros = {
        candidato for candidato in instaladores
        if any(candidato in transitive_depends(otro, cache, depends_of)
               for otro in instaladores - {candidato})
    }
    return declara_clase.get(cls, set()) | ancestros


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

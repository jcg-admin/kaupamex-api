#!/usr/bin/env python3
"""Gate: un ``chain_method`` cuyo idioma en la referencia es COMBINAR lleva
``combine=``.

Cierra la tarea #79, sucesora de :ref:`h-api-823`. El relevo por defecto de
``chain_method`` invoca la implementacion previa **solo si la nueva devolvio
``None``**, y un contenedor vacio no es ``None``: el eslabon lo da por
respuesta buena y descarta lo que entrego la previa. Medido en
``res.users.settings``, el eslabon de ``web`` arrancaba en ``{}`` y el formato
perdia ``id`` y ``user`` — sin excepcion, sin simbolo ausente, y con el gate de
porte declarando el archivo completo porque el method existia.

Por que un barrido de una vez no bastaba
=========================================

El defecto de H-API-823 era **latente**: mientras ``base`` no declarara el
method, ``previous`` era ``None`` y el relevo no descartaba nada. Se volvio
destructivo el dia que se porto el method a ``base`` — **sin que ningun archivo
del addon cambiara**. Un barrido mide el arbol de hoy; lo que protege del
manana es un gate que corra en cada commit.

Como decide, y por que no puede decidirlo mirando solo nuestro codigo
=====================================================================

El tipo de retorno NO dice cual de los dos idiomas es: ``dict`` sale igual de
un relevo que de una combinacion. Quien lo dice es **la referencia**, leyendo
como usa su ``super()``:

- ``return super()...``            -> RELEVO      (el default es correcto)
- ``return X if cond else super()`` -> RELEVO      (el ternario es un relevo)
- ``res = super(); return res``     -> RELEVO      (sale intacto)
- ``res = super(); res['x'] = ...`` -> COMBINACION (necesita ``combine``)
- ``res = super(); res |= otro``    -> COMBINACION
- ``return [*super(), propio]``     -> COMBINACION

*Metrica:* las llamadas a ``chain_method`` de ``addons/**``, cruzadas con la
clasificacion del ``super()`` del method homonimo en la referencia.
*Ciega a:* un method que la referencia no declara (no hay con que comparar), un
addon sin contraparte, y un eslabon cuya combinacion la haga una funcion
llamada en vez de una mutacion en line. Las tres se publican con su conteo en
la line de resumen en vez de sumarse al verde.

Deuda heredada
==============

``scripts/chain_combine_baseline.txt``, una entrada por llamada revisada con
su verdict escrito. Una entrada listada no bloquea; una nueva si.
"""
import argparse
import ast
import os
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Raiz del arbol que gobierna. Ver
#: ``referencia-odoo-gobierna-las-decisiones.md``.
import sys as _s, os.path as _op
_s.path.insert(0, _op.dirname(_op.abspath(__file__)))
from reference_roots import tree as _tree
ODOO19C = _tree('odoo19c')

BASELINE = REPO_ROOT / 'scripts' / 'chain_combine_baseline.txt'

#: Addons cuyo nombre aqui no es el de la referencia. Cada entrada es una
#: decision declarada: el prefijo ``authz_`` marca la familia de autorizacion
#: de este arbol, que la referencia llama ``auth_``.
ADDON_ALIAS = {
    'authz_totp': 'auth_totp',
    'authz_totp_mail': 'auth_totp_mail',
}


def _is_super_call(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Call)
            and isinstance(node.func.value.func, ast.Name)
            and node.func.value.func.id == 'super')


def _relay_branches(value):
    """Los sitios de un ``return`` que cuentan como relevo directo.

    Un ``return super()`` obvio, y tambien ``return X if cond else super()`` y
    ``return super() or X``: el resultado de la previa sale intacto, que es lo
    que define el relevo.
    """
    if value is None:
        return []
    if _is_super_call(value):
        return [value]
    if isinstance(value, ast.IfExp):
        return _relay_branches(value.body) + _relay_branches(value.orelse)
    if isinstance(value, ast.BoolOp):
        out = []
        for v in value.values:
            out += _relay_branches(v)
        return out
    return []


def classify(fn):
    """``combinacion`` | ``relevo`` | ``sin-super``.

    COMBINACION exige que el resultado de ``super()`` se **use**: mutado,
    leido, filtrado o envuelto. Un ``res = super(); return res`` es relevo con
    nombre.
    """
    relays = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Return):
            for r in _relay_branches(n.value):
                relays.add(id(r))

    for n in ast.walk(fn):
        if isinstance(n, ast.Return) and n.value is not None:
            for sub in ast.walk(n.value):
                if _is_super_call(sub) and id(sub) not in relays:
                    return 'combinacion'

    names = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and _is_super_call(n.value):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)

    if not names:
        return 'relevo' if relays else 'sin-super'

    bare_returns = {id(n.value) for n in ast.walk(fn)
                    if isinstance(n, ast.Return) and isinstance(n.value, ast.Name)
                    and n.value.id in names}
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and n.id in names \
                and isinstance(n.ctx, ast.Load) and id(n) not in bare_returns:
            return 'combinacion'
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) \
                        and t.value.id in names:
                    return 'combinacion'
        # ``routes |= x`` · ``lista += [...]`` — la mutacion mas comun de la
        # referencia, y la que una version anterior de esta funcion no veia:
        # los cuatro casos que ya llevaban ``combine`` salian como relevo.
        if isinstance(n, ast.AugAssign):
            target = n.target
            if isinstance(target, ast.Subscript):
                target = target.value
            if isinstance(target, ast.Name) and target.id in names:
                return 'combinacion'
    return 'relevo'


def _installed_names(tree):
    """Las llamadas a ``chain_method`` del modulo: ``(line, method, combine)``.

    Resuelve las dos formas del arbol: la llamada directa y el bucle sobre una
    tupla de pares ``(nombre, funcion)``, que es como los addons grandes
    instalan doce metodos de golpe.
    """
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id == 'chain_method' and len(n.args) >= 3 \
                and isinstance(n.args[1], ast.Constant):
            out.append((n.lineno, n.args[1].value,
                        any(k.arg == 'combine' for k in n.keywords)))
        if isinstance(n, ast.For):
            calls = [c for c in ast.walk(n) if isinstance(c, ast.Call)
                     and isinstance(c.func, ast.Name) and c.func.id == 'chain_method']
            if not calls:
                continue
            combine = any(k.arg == 'combine' for c in calls for k in c.keywords)
            for elt in ast.walk(n.iter):
                if isinstance(elt, ast.Tuple) and len(elt.elts) == 2 \
                        and isinstance(elt.elts[0], ast.Constant):
                    out.append((elt.lineno, elt.elts[0].value, combine))
    return out


def reference_file(rel):
    """El archivo homonimo en la referencia, que reparte sus addons en dos
    raices: ``addons/`` y ``odoo/addons/`` — ``base`` vive en la segunda."""
    parts = pathlib.Path(rel).parts
    addon = ADDON_ALIAS.get(parts[1], parts[1])
    tail = pathlib.Path(*parts[2:])
    for root in (ODOO19C / 'addons', ODOO19C / 'odoo' / 'addons'):
        candidate = root / addon / tail
        if candidate.is_file():
            return candidate
    return None


def load_baseline():
    if not BASELINE.is_file():
        return set()
    return {line.split('#')[0].strip()
            for line in BASELINE.read_text().splitlines()
            if line.split('#')[0].strip()}


def sweep(paths=None):
    """Devuelve ``(findings, counts)``.

    ``findings`` son las llamadas sin ``combine`` cuyo homonimo en la
    referencia combina. ``counts`` publica el denominador y las tres
    cegueras, para que un cero no se lea como cobertura.
    """
    files = paths or sorted(REPO_ROOT.joinpath('addons').rglob('*.py'))
    findings, counts = [], {'llamadas': 0, 'ref-ausente': 0,
                              'no-declarado': 0, 'sin-super': 0}
    cache = {}
    for f in files:
        f = pathlib.Path(f)
        if not f.is_absolute():
            f = REPO_ROOT / f
        if not f.is_file() or f.suffix != '.py':
            continue
        text = f.read_text()
        if 'chain_method(' not in text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        rel = f.relative_to(REPO_ROOT).as_posix()
        if not rel.startswith('addons/'):
            continue
        ref = reference_file(rel)
        for line, method, combine in _installed_names(tree):
            counts['llamadas'] += 1
            if ref is None:
                counts['ref-ausente'] += 1
                continue
            if ref not in cache:
                try:
                    cache[ref] = ast.parse(ref.read_text())
                except (OSError, SyntaxError):
                    cache[ref] = None
            ref_tree = cache[ref]
            if ref_tree is None:
                counts['ref-ausente'] += 1
                continue
            fns = [n for n in ast.walk(ref_tree)
                   if isinstance(n, ast.FunctionDef) and n.name == method]
            if not fns:
                counts['no-declarado'] += 1
                continue
            verdict = classify(fns[0])
            if verdict == 'sin-super':
                counts['sin-super'] += 1
            if not combine and verdict == 'combinacion':
                findings.append((rel, line, method))
    return findings, counts


def main():
    p = argparse.ArgumentParser()
    p.add_argument('paths', nargs='*', help='medir solo estos files')
    p.add_argument('--quiet', action='store_true')
    p.add_argument('--strict', action='store_true')
    p.add_argument('--write-baseline', action='store_true')
    args = p.parse_args()

    if not ODOO19C.is_dir():
        print(f'AVISO: no esta el arbol de referencia en {ODOO19C}; '
              'sin el este gate no puede medir nada.')
        return 0

    findings, counts = sweep(args.paths or None)

    if args.write_baseline:
        lines = sorted(f'{r}::{m}' for r, _l, m in findings)
        BASELINE.write_text(
            '# Llamadas a chain_method sin combine= cuyo homonimo en la\n'
            '# referencia COMBINA. Cada entrada lleva su verdict escrito en\n'
            '# el docstring del eslabon: relevo declarado, bloqueo, o divergencia\n'
            '# de mecanismo. Una entrada listada no bloquea; una nueva si.\n'
            + '\n'.join(lines) + '\n')
        print(f'baseline escrito: {len(lines)} entrada(s)')
        return 0

    frozen = load_baseline()
    fresh = [h for h in findings if f'{h[0]}::{h[2]}' not in frozen]

    scope = (f'(alcance medido: {counts["llamadas"]} llamada(s); '
             f'{counts["ref-ausente"]} sin contraparte en la referencia, '
             f'{counts["no-declarado"]} con el metodo no declarado alli, '
             f'{counts["sin-super"]} que la referencia no extiende; '
             f'{len(frozen)} en baseline)')

    if not fresh:
        if not args.quiet:
            print(f'OK: ningun chain_method nuevo sin combine donde la '
                  f'referencia combina {scope}')
        return 0

    print(f'FAIL — {len(fresh)} chain_method sin combine= donde la '
          f'referencia COMBINA:\n')
    for rel, line, method in fresh:
        print(f'  {rel}:{line}  {method}')
    print('\nEl relevo por defecto solo invoca la previa si la nueva devolvio')
    print('None; un contenedor vacio no lo es, asi que la previa se descarta.')
    print('Cablear combine= (merge_dict / extend_list / el que corresponda) o,')
    print('si el eslabon es un relevo declarado o un bloqueo, anadirlo al')
    print(f'baseline con su verdict escrito: {BASELINE.name}')
    print(f'\n{scope}')
    return 1 if args.strict else 0


if __name__ == '__main__':
    sys.exit(main())

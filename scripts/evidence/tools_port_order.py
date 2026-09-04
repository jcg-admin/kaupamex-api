"""Ordenar los archivos ausentes de ``src/tools`` por lo que desbloquean.

Nadie en NUESTRO arbol los invoca todavia (medido por AST: los unicos hits
son homonimos genericos como ``add`` o ``run``), asi que el orden no puede
salir de nuestra demanda. Sale del flujo de la referencia: cuantos archivos
suyos consumen cada uno.
"""
import pathlib
import sys
import time

sys.path.insert(0, 'scripts')

import counterpart_body  # noqa: E402
import reference_flow  # noqa: E402
import reference_roots  # noqa: E402

TREE = reference_roots.tree()
BYTES = {}
ASTS = {}


def bytes_of(path):
    if path not in BYTES:
        try:
            BYTES[path] = path.read_bytes()
        except OSError:
            BYTES[path] = b''
    return BYTES[path]


def entry_of(path):
    if path not in ASTS:
        tree = counterpart_body.parse_file(path)
        ASTS[path] = (None if tree is None
                      else (tree, counterpart_body.declarations_of(path, tree)))
    return ASTS[path]


def main():
    absent = pathlib.Path(
        'scripts/evidence/tools_absent.txt').read_text().split()
    roots = reference_flow.resolve_roots(reference_flow.DEFAULT_ROOTS)
    files = reference_flow.universe_files(roots)
    print(f'universo de la referencia: {len(files)} archivos .py')
    t0 = time.perf_counter()
    for path in files:
        bytes_of(path)
    print(f'lectura de bytes: {time.perf_counter() - t0:.1f}s')

    rows = []
    for name in absent:
        ref = TREE / 'odoo' / 'tools' / f'{name}.py'
        simbolos = [s for s in reference_flow.symbols_of_file(ref)
                    if not s.startswith('_')]
        consumers, with_edge = set(), 0
        for simbolo in simbolos:
            needle = simbolo.encode()
            index = {}
            for path in files:
                if needle not in bytes_of(path):
                    continue
                entrada = entry_of(path)
                if entrada is not None:
                    index[path] = entrada
            decl = reference_flow.declarations_named(index, simbolo)
            sitios = reference_flow.callers_of(index, simbolo, decl)
            fuera = [x for x in sitios if f'/tools/{name}.py' not in x.path]
            if fuera:
                with_edge += 1
            consumers.update(
                str(pathlib.Path(x.path).relative_to(TREE)) for x in fuera)
        rows.append((len(consumers), with_edge, name, len(simbolos),
                      consumers))
        print(f'  {name}.py: {len(simbolos)} publicos, '
              f'{with_edge} con arista, {len(consumers)} consumidores',
              flush=True)

    print(f'\nmedido en {time.perf_counter() - t0:.1f}s; '
          f'{len(ASTS)} archivos parseados de {len(files)}')
    print(f'\n{"archivo":<24} {"publicos":>9} {"con arista":>11} '
          f'{"consumidores":>13}')
    for n_cons, with_edge, name, n_sim, _ in sorted(rows, reverse=True):
        print(f'{name + ".py":<24} {n_sim:>9} {with_edge:>11} '
              f'{n_cons:>13}')

    print('\n--- consumidores por archivo (hasta 8) ---')
    for n_cons, _, name, _, consumers in sorted(rows, reverse=True):
        if consumers:
            print(f'{name}.py:')
            for c in sorted(consumers)[:8]:
                print(f'    {c}')


if __name__ == '__main__':
    raise SystemExit(main())

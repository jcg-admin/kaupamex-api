"""Renombra a inglés los identificadores en español de un archivo de test.

Trabaja por POSICIÓN sobre el texto original: sólo toca los nodos que el AST
declara como identificador (``Name``, ``arg``, ``FunctionDef``, ``ClassDef``),
así que la prosa de docstrings y comentarios queda intacta. Antes de escribir
avisa de toda colisión: un nombre destino ya ligado en la misma función.
"""
import ast
import pathlib
import sys

MAPA = {
    '_otro_marco': '_another_frame',
    'activo': 'active_profiler',
    'actualizar': 'update',
    'ajeno': 'foreign',
    'anidado': 'nested',
    'antes': 'before',
    'aparte': 'separate',
    'consultas': 'queries',
    'conteo': 'count',
    'contexto': 'context',
    'dato': 'item',
    'datos': 'data',
    'declarado': 'declared',
    'entrada': 'entry',
    'entradas': 'entries',
    'esperado': 'wanted',
    'evento': 'event',
    'eventos': 'events',
    'hijo': 'child',
    'hilo': 'current',
    'interno': 'inner_profiler',
    'limite': 'limit',
    'listo': 'ready',
    'llamadas': 'calls',
    'marcador': 'marker',
    'marco': 'own_frame',
    'nombre': 'row_name',
    'otro': 'other',
    'padre': 'parent',
    'padre_en_llamada': 'parent_in_call',
    'perfilador': 'standalone',
    'pila': 'one_stack',
    'pilas': 'stacks',
    'profundidad': 'depth',
    'racha': 'run',
    'rachas': 'runs',
    'rastreador': 'tracker',
    'resultados': 'results',
    'resumen': 'summary',
    'ruta': 'path',
    'seguir': 'keep_going',
    'sesion': 'session',
    'traza': 'trace',
    'uno': 'first',
    'valor': 'value',
    'visto': 'seen',
}


def bound_names(node):
    """Identificadores ligados dentro de una función, sin descender a otra."""
    found = set()
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.add(child.name)
            continue
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
            found.add(child.id)
        elif isinstance(child, ast.arg):
            found.add(child.arg)
        found |= bound_names(child)
    return found


def main(ruta):
    path = pathlib.Path(ruta)
    source = path.read_text()
    tree = ast.parse(source)

    colisiones = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        ligados = bound_names(node) | {a.arg for a in node.args.args}
        for viejo, nuevo in MAPA.items():
            if viejo in ligados and nuevo in ligados:
                colisiones.append((node.name, viejo, nuevo))
    if colisiones:
        for fn, viejo, nuevo in colisiones:
            print(f'COLISION {fn}: {viejo} -> {nuevo} (el destino ya esta ligado)')
        return 1

    puntos = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in MAPA:
            puntos.append((node.lineno, node.col_offset, node.id))
        elif isinstance(node, ast.arg) and node.arg in MAPA:
            puntos.append((node.lineno, node.col_offset, node.arg))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in MAPA:
            # ``def `` mide 4 caracteres antes del nombre
            puntos.append((node.lineno, node.col_offset + 4, node.name))

    lines = source.splitlines(keepends=True)
    for lineno, col, viejo in sorted(puntos, reverse=True):
        line = lines[lineno - 1]
        if line[col:col + len(viejo)] != viejo:
            print(f'DESAJUSTE linea {lineno} col {col}: esperaba {viejo}')
            return 2
        lines[lineno - 1] = line[:col] + MAPA[viejo] + line[col + len(viejo):]

    path.write_text(''.join(lines))
    print(f'renombrados {len(puntos)} identificador(es) en {len(set(p[0] for p in puntos))} linea(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1]))

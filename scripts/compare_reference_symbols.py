"""Compara los símbolos de un archivo de la referencia con los de su puerto.

Instrumento de medición para el porte: lista por clase los métodos, las
asignaciones de campo y los atributos de clase con guion bajo que declara la
fuente, y marca cuáles faltan en el destino. Complementa a
``check_porte_completo.py``, que sólo empareja ``models/``: éste acepta
cualquier par de rutas, así que alcanza a ``wizard/`` y a ``controllers/``.

Uso::

    python3 scripts/compare_reference_symbols.py <ref.py> <destino.py> [...]

Con un solo argumento imprime el inventario de la fuente sin comparar.
"""
import ast
import pathlib
import sys


def inventory(path):
    """Devuelve ``{clase: {'metodos': [...], 'campos': [...], 'attrs': [...]}}``."""
    tree = ast.parse(pathlib.Path(path).read_text())
    out = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        methods, columns, attrs = [], [], []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append((item.name, item.lineno))
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if target.id.startswith('_'):
                        attrs.append((target.id, item.lineno))
                    else:
                        columns.append((target.id, item.lineno))
        out[node.name] = {'metodos': methods, 'campos': columns, 'attrs': attrs}
    return out


def flat_names(path):
    """Todos los nombres declarados en el archivo, sin agrupar por clase."""
    tree = ast.parse(pathlib.Path(path).read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    reference = argv[0]
    targets = argv[1:]
    present = set()
    for target in targets:
        present |= flat_names(target)
    # El guion bajo se conserva al portar, pero un método de la fuente puede
    # haber aterrizado como función de módulo con el mismo nombre.
    for class_name, parts in inventory(reference).items():
        print(f'== {class_name} ({reference})')
        for label in ('attrs', 'campos', 'metodos'):
            for symbol, line in parts[label]:
                if not targets:
                    print(f'   {label:8} {symbol}  :{line}')
                    continue
                verdict = 'OK ' if symbol in present else 'FALTA'
                print(f'   {verdict} {label:8} {symbol}  :{line}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

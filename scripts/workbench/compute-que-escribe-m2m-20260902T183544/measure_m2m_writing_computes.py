"""Que computes escriben una relacion M2M, y cual de ellos NO tiene campo.

#313. La pregunta es doble y el orden importa:

1. cuantos computos del arbol escriben una relacion muchos-a-muchos
   (``.set``/``.add``/``.remove``/``.clear`` sobre un atributo del propio
   registro), y
2. de esos, cuantos NO estan nombrados por ningun ``compute=`` de un campo
   — que es lo que #305 dejo abierto: un ``compute=`` sobre un M2M no tenia
   receptor, asi que esos metodos quedaron llamados a mano desde ``save``.

El recorrido es por AST, no por grep: ``self.tags.set(...)`` y
``record.tag_ids.add(...)`` son la misma forma con distinto receptor, y una
expresion regular sobre el texto no distingue la llamada de su mencion en un
docstring.

*Metrica:* llamadas ``<algo>.<atributo>.<verbo>(...)`` dentro del cuerpo de un
``def _compute_*``, con ``verbo`` en el juego de escritura de un manager
relacional de Django.
*Ciega a:* un computo que escriba el M2M llamando a un ayudante en vez de
hacerlo en su cuerpo, y a uno que lo escriba por asignacion directa —que
Django prohibe desde 1.10, asi que no deberia existir, pero el instrumento no
lo veria.
"""
import argparse
import ast
import json
import pathlib
import sys


VERBOS_DE_ESCRITURA = frozenset({'set', 'add', 'remove', 'clear'})


def m2m_written_by(body):
    """Los atributos que este cuerpo escribe como relacion."""
    written = set()
    for node in ast.walk(body):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in VERBOS_DE_ESCRITURA
                and isinstance(node.func.value, ast.Attribute)):
            continue
        written.add(node.func.value.attr)
    return written


def declared_computes(tree):
    """Los nombres que algun campo del archivo nombra en ``compute=``."""
    declared = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg == 'compute' and isinstance(kw.value, ast.Constant):
                declared.add(kw.value.value)
    return declared


def m2m_field_names(tree):
    """Los campos declarados ``Many2many`` en el archivo, por nombre."""
    names = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
            continue
        func = node.value.func
        called = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
        if called != 'Many2many':
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def scan(roots):
    rows, files = [], 0
    for root in roots:
        for path in sorted(pathlib.Path(root).rglob('*.py')):
            if '/migrations/' in str(path):
                continue
            try:
                tree = ast.parse(path.read_text())
            except SyntaxError:
                continue
            files += 1
            declared, m2m = declared_computes(tree), m2m_field_names(tree)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.FunctionDef)
                        and node.name.startswith('_compute_')):
                    continue
                written = m2m_written_by(node) & m2m
                if not written:
                    continue
                rows.append({
                    'file': str(path),
                    'line': node.lineno,
                    'compute': node.name,
                    'writes': sorted(written),
                    'declared_by_a_field': node.name in declared,
                })
    return rows, files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('roots', nargs='*', default=['addons', 'src'])
    args = parser.parse_args()

    rows, files = scan(args.roots or ['addons', 'src'])
    orphans = [r for r in rows if not r['declared_by_a_field']]
    if args.json:
        json.dump({'rows': rows, 'files_measured': files}, sys.stdout, indent=2)
        return
    for row in rows:
        mark = 'CON campo' if row['declared_by_a_field'] else 'SIN campo'
        print(f"{mark}  {row['file']}:{row['line']}  {row['compute']} "
              f"-> {', '.join(row['writes'])}")
    print(f"\n{len(rows)} computo(s) escriben un M2M declarado en su archivo; "
          f"{len(orphans)} sin campo que los nombre "
          f"(alcance medido: {files} archivos .py, migraciones excluidas)")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Censo de ``related=`` en la referencia — el denominador, no de memoria.

``calibration-verified-numbers.md`` prohíbe transcribir a prosa una cifra que
vive en código: **la prosa nombra el comando, no el número**. Este guion es ese
comando. Publica tres cortes que gobiernan decisiones distintas:

- **cuántos hay** en los addons que este árbol porta — el universo;
- **cuántos NO llevan** ``store`` — el reparto que explica por qué el defecto
  de ``store`` es ``False`` para un ``related`` (``odoo19c:
  odoo/orm/fields.py:455``);
- **cuántos son de un tipo que el despachador de aquí todavía no acepta** — el
  trabajo que queda.

Por qué el patrón equilibra paréntesis
=======================================

Una declaración de campo contiene llamadas anidadas — ``digits=(10, 7)``,
``domain=[('a', '=', b)]``, ``string=_("X")``. Un ``[^)]*`` corta en el primer
paréntesis interno y **parte la declaración**, así que ve unas y no otras según
qué argumento venga antes. Aquí el patrón admite un nivel de anidamiento, que
es el que cubre el corpus medido.

*Ciega a:* una declaración con **dos** niveles de anidamiento
(``domain=[('a', 'in', f(x))]``). Medido al escribirlo: el patrón laxo ve 797 y
éste 791, así que la diferencia son 6 declaraciones. El número que publica es
por tanto una **cota inferior**, y lo dice al imprimirlo.
"""
import argparse
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import addons_roots
import reference_roots

#: Los tipos cuyo constructor acepta ``related=`` hoy — ``Char`` con su rama
#: propia y los cinco que fabrica ``make_dispatcher``
#: (``src/orm/fields_company_dependent.py:411``).
DISPATCHED_TYPES = frozenset({
    'Char', 'Boolean', 'Selection', 'Integer', 'Float', 'Text',
})

#: Una llamada ``fields.X(...)`` que admite un nivel de anidamiento dentro.
FIELD_CALL = re.compile(r'fields\.(\w+)\(((?:[^()]|\([^()]*\))*)\)', re.S)
DECLARES_STORE = re.compile(r'\bstore\s*=')


def declarations_in(tree_root, addons):
    """Cada ``related=`` de la referencia, con su tipo y si declara ``store``."""
    for path in sorted(tree_root.rglob('addons/*/models/*.py')):
        parts = path.parts
        addon = parts[parts.index('addons') + 1]
        if addon not in addons:
            continue
        source = path.read_text(errors='ignore')
        for match in FIELD_CALL.finditer(source):
            field_type, arguments = match.group(1), match.group(2)
            if 'related=' not in arguments:
                continue
            line = source.count('\n', 0, match.start()) + 1
            yield {
                'addon': addon,
                'path': path,
                'line': line,
                'type': field_type,
                'stored': bool(DECLARES_STORE.search(arguments)),
                'dispatched': field_type in DISPATCHED_TYPES,
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alias', default='ODOO19C',
                        help='raíz de la referencia (default: la que gobierna)')
    parser.add_argument('--pendientes', action='store_true',
                        help='listar los que ningún constructor de aquí acepta')
    options = parser.parse_args()

    exported = subprocess.run(
        [sys.executable, str(pathlib.Path(__file__).parent / 'reference_roots.py'),
         '--env'], capture_output=True, text=True, check=True).stdout
    for assignment in re.findall(r'(\w+)=(\S+)', exported):
        os.environ.setdefault(assignment[0], assignment[1].strip('"'))
    tree_root = pathlib.Path(os.environ[options.alias])

    addons = set(addons_roots.addon_names())
    rows = list(declarations_in(tree_root, addons))
    if not rows:
        print(f'ERROR — 0 declaraciones medidas bajo {tree_root}. '
              'NO se emite reparto: un 0 aquí sería un verde falso.',
              file=sys.stderr)
        raise SystemExit(2)

    unstored = [r for r in rows if not r['stored']]
    pending = [r for r in rows if not r['dispatched']]

    if options.pendientes:
        for row in pending:
            relative = row['path'].relative_to(tree_root)
            print(f"{relative}:{row['line']}  fields.{row['type']}")

    by_type = {}
    for row in pending:
        by_type[row['type']] = by_type.get(row['type'], 0) + 1
    print(f'\nrelated= declarados: {len(rows)} en {len(addons)} addons portados')
    print(f'  sin store:  {len(unstored)}  '
          f'({100 * len(unstored) / len(rows):.0f} %)')
    print(f'  con store:  {len(rows) - len(unstored)}')
    print(f'  de un tipo que el despachador NO acepta: {len(pending)}  '
          f'({100 * len(pending) / len(rows):.0f} %)')
    for field_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f'      {field_type:12} {count}')
    print('\n(cota inferior: el patrón admite un nivel de anidamiento; una '
          'declaración con dos niveles no se cuenta)')


if __name__ == '__main__':
    main()

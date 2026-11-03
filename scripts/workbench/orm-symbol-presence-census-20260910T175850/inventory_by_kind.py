#!/usr/bin/env python3
"""Inventario estructural POR TIPO sobre el universo de la referencia.

Por que un modulo hermano y no otro censo
-----------------------------------------
``census_symbol_presence.py`` recorre NUESTROS archivos y busca su homonimo en
la referencia: un archivo que la referencia declara y nosotros no tenemos no
aparece en su informe, asi que su universo no sirve como denominador de
«aplicables». Este modulo invierte el recorrido —parte de cada archivo de la
referencia— y reusa sin copiar lo que ya existe: ``declared_symbols``,
``signature_of``, ``body_class``, ``resolve`` y ``MIRRORED_ROOTS``. Lo unico
nuevo es el recorrido de **atributos de clase**, que el censo hermano no
extrae.

Identidad y categorias
----------------------
Cada simbolo se identifica por ``(revision, modulo, simbolo calificado,
tipo)``: un metodo se califica por su clase (``Clase.metodo``), nunca por su
nombre suelto. Las categorias son excluyentes y cumplen
``aplicables = satisfechos + ausentes + divergentes + no_verificados``:

``satisfied``
    Presente en el archivo espejo con el mismo duenio y, si tiene firma o
    valor, con la misma firma o el mismo valor; cuerpo no vacio.
``absent``
    Ni el simbolo ni (para metodos y atributos) su clase duenia existen en el
    archivo espejo, o el archivo espejo no existe.
``divergent``
    Presente con el mismo duenio, pero la firma, el valor o el cuerpo (stub
    donde la referencia implementa) difieren.
``not_verified``
    Solo hay un homonimo: el nombre existe en el archivo espejo pero con otro
    duenio o de otro tipo. Un homonimo no es un porte (no es TRAE).

*Metrica:* presencia y forma declarativa (firma, valor, cuerpo vacio o no)
por AST, archivo contra archivo espejo.
*Ciega a:* el COMPORTAMIENTO — «satisfecho» significa estructuralmente igual,
no probado; a un simbolo portado a otro archivo (se cuenta ausente aqui); y a
atributos de instancia asignados en ``__init__``.

Uso::

    eval "$(python3 scripts/reference_roots.py --env)"
    PYTHONPATH=scripts uv run python <este archivo> [--roots src/orm src/tools]
"""
import argparse
import ast
import collections
import importlib.util
import json
import pathlib
import subprocess
import sys

RUN_DIR = pathlib.Path(__file__).resolve().parent
REPO = RUN_DIR.parents[2]

_spec = importlib.util.spec_from_file_location(
    '_inventory_census', RUN_DIR / 'census_symbol_presence.py')
_census = importlib.util.module_from_spec(_spec)
sys.modules['_inventory_census'] = _census
_spec.loader.exec_module(_census)

KINDS = ('file', 'class', 'function', 'method', 'attribute', 'property')
CATEGORIES = ('satisfied', 'absent', 'divergent', 'not_verified')
PROPERTY_DECORATORS = ('property', 'cached_property', 'functools.cached_property',
                       'lazy_property', 'tools.lazy_property')


def _is_property(record):
    return any(d in PROPERTY_DECORATORS or d.endswith('.setter')
               or d.endswith('.deleter') for d in record['decorators'])


def class_attributes(path):
    """``{(clase, atributo): valor}`` de las asignaciones a nivel de clase."""
    try:
        tree = ast.parse(pathlib.Path(path).read_text(encoding='utf-8'))
    except (SyntaxError, OSError):
        return {}
    attributes = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for child in node.body:
            if isinstance(child, ast.Assign):
                targets = [t.id for t in child.targets if isinstance(t, ast.Name)]
                value = child.value
            elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                targets, value = [child.target.id], child.value
            else:
                continue
            for name in targets:
                attributes[(node.name, name)] = (ast.unparse(value)
                                                 if value is not None else None)
    return attributes


def typed_symbols(path):
    """Los registros del censo hermano con el tipo ``property`` separado."""
    records = []
    for record in _census.declared_symbols(path):
        record = dict(record)
        if record['kind'] == 'method' and _is_property(record):
            record['kind'] = 'property'
        records.append(record)
    return records


def _qualified(record):
    return f"{record['owner']}.{record['name']}" if record['owner'] else record['name']


def classify_symbol(reference, ours_by_key, ours_names):
    """Categoria y motivo de un simbolo de la referencia frente al espejo."""
    resolved = _census.resolve(reference['name'], set(ours_names))
    if resolved is None:
        return 'absent', 'nombre no resuelto en el archivo espejo'
    mine = ours_by_key.get((reference['owner'], resolved))
    if mine is None and resolved != reference['name']:
        # La resolucion reconocio un prefijo de disolucion (``_field_``,
        # ``_model_``): el simbolo existe con otro mecanismo declarado.
        return 'divergent', f'disuelto en {resolved}'
    if mine is None or mine['kind'] != reference['kind']:
        if reference['owner'] and (reference['owner'], None) not in ours_by_key:
            return 'absent', 'la clase duenia no existe en el archivo espejo'
        return 'not_verified', 'solo homonimo (otro duenio u otro tipo)'
    if reference['kind'] == 'class':
        return 'satisfied', ''
    if mine['body'] == 'stub' and reference['body'] != 'stub':
        return 'divergent', 'cuerpo vacio donde la referencia implementa'
    if mine['signature'] != reference['signature']:
        return 'divergent', 'firma distinta'
    return 'satisfied', ''


def inventory(roots=_census.CENSUS_ROOTS, revision='-'):
    pairs = {label: (ours, ref) for label, ours, ref in _census.MIRRORED_ROOTS}
    rows = []
    for label in roots:
        our_root, reference_root = pairs[label]
        for reference_file in sorted(pathlib.Path(reference_root).rglob('*.py')):
            if reference_file.name == '__init__.py' or 'tests' in reference_file.parts:
                continue
            relative = reference_file.relative_to(reference_root)
            module = f'{label}/{relative}'
            our_file = pathlib.Path(our_root) / relative
            exists = our_file.is_file()
            ours = typed_symbols(our_file) if exists else []
            ours_by_key = {}
            for record in ours:
                key = (record['owner'], record['name'])
                ours_by_key.setdefault(key, record)
                if record['kind'] == 'class':
                    ours_by_key.setdefault((record['name'], None), record)
            ours_names = {r['name'] for r in ours}
            file_rows = []
            for record in typed_symbols(reference_file):
                if exists:
                    category, reason = classify_symbol(record, ours_by_key, ours_names)
                else:
                    category, reason = 'absent', 'archivo espejo inexistente'
                file_rows.append((record['kind'], _qualified(record), category, reason))
            reference_attributes = class_attributes(reference_file)
            our_attributes = class_attributes(our_file) if exists else {}
            our_classes = {owner for owner, _ in our_attributes} | {
                r['name'] for r in ours if r['kind'] == 'class'}
            for (owner, name), value in sorted(reference_attributes.items()):
                if (owner, name) in our_attributes:
                    category, reason = (('satisfied', '')
                                        if our_attributes[(owner, name)] == value
                                        else ('divergent', 'valor distinto'))
                elif owner in our_classes:
                    category, reason = 'absent', 'la clase existe sin el atributo'
                else:
                    category, reason = 'absent', 'la clase duenia no existe'
                file_rows.append(('attribute', f'{owner}.{name}', category, reason))
            if not exists:
                file_category, file_reason = 'absent', 'archivo espejo inexistente'
            elif all(row[2] == 'satisfied' for row in file_rows):
                file_category, file_reason = 'satisfied', ''
            else:
                file_category, file_reason = 'divergent', 'algun simbolo no satisfecho'
            rows.append((revision, module, '', 'file', file_category, file_reason))
            rows.extend((revision, module, q, k, c, r) for k, q, c, r in file_rows)
    return rows


def table(rows):
    counts = {kind: collections.Counter() for kind in KINDS}
    for _, _, _, kind, category, _ in rows:
        counts[kind][category] += 1
    for kind in KINDS:
        total = sum(counts[kind].values())
        assert total == sum(counts[kind][c] for c in CATEGORIES)
    return counts


def reference_revision():
    root = _census.MIRRORED_ROOTS[0][2]
    try:
        return subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return 'no_verificada'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--roots', nargs='+', default=list(_census.CENSUS_ROOTS))
    parser.add_argument('--tsv', type=pathlib.Path,
                        default=RUN_DIR / 'outputs' / 'inventory_by_kind.tsv')
    args = parser.parse_args(argv)
    revision = reference_revision()
    rows = inventory(args.roots, revision)
    args.tsv.parent.mkdir(exist_ok=True)
    with args.tsv.open('w', encoding='utf-8') as out:
        out.write('revision\tmodule\tsymbol\tkind\tcategory\treason\n')
        for row in rows:
            out.write('\t'.join(row) + '\n')
    counts = table(rows)
    labels = {'file': 'Archivos', 'class': 'Clases', 'function': 'Funciones',
              'method': 'Metodos', 'attribute': 'Atributos', 'property': 'Propiedades'}
    print(f'referencia {revision}  raices {" ".join(args.roots)}')
    print('| Tipo | Aplicables | Satisfechos | Ausentes | Divergentes | No verificados |')
    print('|---|---|---|---|---|---|')
    for kind in KINDS:
        c = counts[kind]
        print(f'| {labels[kind]} | {sum(c.values())} | ' +
              ' | '.join(str(c[x]) for x in CATEGORIES) + ' |')
    print(f'salida: {args.tsv}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

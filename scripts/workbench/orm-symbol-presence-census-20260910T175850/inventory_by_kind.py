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
Cada simbolo se identifica por ``(revision, modulo, simbolo calificado por
su clase de la referencia, tipo)``, nunca por su nombre suelto. La categoria
PRINCIPAL sigue la regla de la adenda contractual (§26) y es excluyente:
``aplicables = satisfechos + ausentes + divergentes + no_verificados``.

``satisfied``
    Coincidencia estructural y de firma, ningun desacuerdo de cuerpo y
    evidencia de COMPORTAMIENTO registrada en
    ``outputs/verified_contracts.tsv``
    (un caso de prueba por simbolo). La coincidencia sola no basta.
``divergent``
    Diferencia de cuerpo DEMOSTRADA: un hallazgo del eje ``write_path`` del
    motor ``counterpart_body`` o un cuerpo vacio donde la referencia
    implementa.
``absent``
    El nombre no se declara en ningun lugar del arbol consumidor (``src`` y
    ``addons``), no solo en el archivo espejo.
``not_verified``
    Lo demas: firma distinta, disolucion en ``_field_*``, contraparte con otra
    duena (``paired_by_name``), atributo instalado por el espejo en otra clase
    (``installed_elsewhere``), homonimo, o coincidencia sin evidencia. Son
    diferencias o semejanzas cuyas consecuencias faltan por medir.

Los ejes (estructural, ``write_path``, evidencia) quedan como evidencia
secundaria en la columna ``reason``, no como categorias.

*Metrica:* presencia y forma declarativa (firma, valor, cuerpo vacio o no)
por AST, archivo contra archivo espejo.
*Ciega a:* el comportamiento que ningun caso registrado ejercita; los ejes de
cuerpo que el motor no tiene instalados (sólo ``write_path``); un simbolo
portado bajo otro nombre; y los atributos de instancia de ``__init__``.

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

_engine_spec = importlib.util.spec_from_file_location(
    '_inventory_engine', REPO / 'scripts' / 'counterpart_body.py')
_engine = importlib.util.module_from_spec(_engine_spec)
sys.modules['_inventory_engine'] = _engine
_engine_spec.loader.exec_module(_engine)
_write_path_spec = importlib.util.spec_from_file_location(
    '_inventory_write_path', REPO / 'scripts' / 'check_write_path.py')
_write_path = importlib.util.module_from_spec(_write_path_spec)
sys.modules['_inventory_write_path'] = _write_path
_write_path_spec.loader.exec_module(_write_path)

#: La evidencia de COMPORTAMIENTO: un caso de prueba por simbolo verificado.
#: Es un puntero a la prueba que lo demuestra, no una autoridad nueva: el
#: veredicto lo da el caso al ejecutarse.
EVIDENCE = RUN_DIR / 'outputs' / 'verified_contracts.tsv'

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
    """Los registros del censo hermano con el tipo ``property`` separado.

    Una propiedad con ``setter`` o ``deleter`` se declara dos o tres veces con
    el mismo nombre y es UNA obligación: el accesor se descarta cuando su
    propiedad ya está. Contarlo duplicaba ``Registry.registry_invalidated``,
    ``configmanager.rcfile``, ``LRU.count`` y ``Query.order``.
    """
    records = []
    properties = set()
    for record in _census.declared_symbols(path):
        if any(d in ('overload', 'typing.overload')
               for d in record['decorators']):
            # Una sobrecarga de tipado declara una firma, no un cuerpo: el
            # contrato es la definicion que la sigue. Contarla duplicaba
            # ``mapped``, ``grouped`` y ``__getitem__``.
            continue
        record = dict(record)
        if record['kind'] == 'method' and _is_property(record):
            record['kind'] = 'property'
            key = (record['owner'], record['name'])
            if key in properties:
                continue
            properties.add(key)
        records.append(record)
    return records


def _qualified(record):
    return f"{record['owner']}.{record['name']}" if record['owner'] else record['name']


def structural_axis(reference, ours_by_key, ours_names):
    """El eje ESTRUCTURAL de un simbolo frente al archivo espejo.

    Es evidencia secundaria: dice que se encontro, no si el contrato se
    cumple. Sus valores: ``match``, ``signature``, ``stub``, ``dissolved``,
    ``homonym``, ``owner_absent``, ``unresolved``.
    """
    resolved = _census.resolve(reference['name'], set(ours_names))
    if resolved is None:
        return 'unresolved', ''
    mine = ours_by_key.get((reference['owner'], resolved))
    if mine is None and resolved != reference['name']:
        # La resolucion reconocio un prefijo de disolucion (``_field_``,
        # ``_model_``): el simbolo existe con otro mecanismo declarado.
        return 'dissolved', resolved
    if mine is None or mine['kind'] != reference['kind']:
        if reference['owner'] and (reference['owner'], None) not in ours_by_key:
            return 'owner_absent', ''
        return 'homonym', ''
    if reference['kind'] == 'class':
        return 'match', ''
    if mine['body'] == 'stub' and reference['body'] != 'stub':
        return 'stub', ''
    if mine['signature'] != reference['signature']:
        return 'signature', ''
    return 'match', ''


def engine_pairs(our_file, reference_file):
    """``{simbolo calificado de la referencia: (par, veredicto write_path)}``.

    Reusa ``counterpart_body.pair_declarations`` —sus tres vias, incluida la de
    nombre con duena divergente, que resuelve la contraparte efectiva de un
    ``BaseModel`` disuelto en mixins— y el ``Axis`` de ``check_write_path``: ni
    recorrido ni resolucion propios. El veredicto es ``agree``,
    ``indeterminate``, el nombre del desacuerdo, o ``''`` si algun lado no
    escribe.
    """
    axis = _write_path.WRITE_PATH
    result = {}
    for pair in _engine.pair_declarations(our_file, reference_file):
        mine = _engine.classify(pair.ours, axis.ours, axis)
        theirs = _engine.classify(pair.theirs, axis.reference, axis)
        if _engine.ABSENT in (mine, theirs):
            verdict = ''
        else:
            verdict = _engine.direction(mine, theirs, axis)
            verdict = ('agree' if verdict is None else
                       'indeterminate' if verdict == _engine.INDETERMINATE
                       else verdict)
        result[pair.reference_key] = (pair, verdict)
    return result


def consumer_names(roots=('src', 'addons')):
    """Todo nombre de clase o funcion que el arbol consumidor declara, mas
    los que instala como atributo de otra clase (:func:`installed_names`) y
    los que liga con una asignacion de modulo (:func:`module_bindings`)."""
    names = set()
    for root in roots:
        for path in pathlib.Path(REPO / root).rglob('*.py'):
            if 'migrations' in path.parts or '__pycache__' in path.parts:
                continue
            names.update(r['name'] for r in _census.declared_symbols(path))
            names.update(installed_names(path))
            names.update(module_bindings(path))
    return names


def load_evidence(path=EVIDENCE):
    """``{(modulo, simbolo, tipo): caso}`` de la evidencia de comportamiento."""
    evidence = {}
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines()[1:]:
            module, symbol, kind, test = line.split('\t')
            evidence[(module, symbol, kind)] = test
    return evidence


def principal(kind, structural, write_path, evidence, name_known):
    """La categoria PRINCIPAL, con la regla de la adenda contractual (§26).

    - ``divergent`` exige una diferencia DEMOSTRADA en el cuerpo: un hallazgo
      del eje ``write_path`` o un cuerpo vacio donde la referencia implementa.
    - ``satisfied`` exige coincidencia estructural y de firma, ningun
      desacuerdo de cuerpo y evidencia de comportamiento registrada.
    - ``absent`` exige que el nombre no se declare en ningun lugar del arbol
      consumidor, no solo en el archivo espejo.
    - lo demas es ``not_verified``: una firma distinta, una disolucion o un
      homonimo son diferencias cuyas consecuencias faltan por medir.
    """
    if structural == 'stub' or write_path not in ('', 'agree', 'indeterminate'):
        return 'divergent'
    if structural == 'match' and evidence:
        return 'satisfied'
    if structural in ('unresolved', 'owner_absent') and not name_known:
        return 'absent'
    return 'not_verified'


def inventory(roots=_census.CENSUS_ROOTS, revision='-', known=None,
              evidence=None):
    pairs = {label: (ours, ref) for label, ours, ref in _census.MIRRORED_ROOTS}
    known = consumer_names() if known is None else known
    evidence = load_evidence() if evidence is None else evidence
    rows = []
    for label in roots:
        our_root, reference_root = pairs[label]
        for reference_file in sorted(
                pathlib.Path(reference_root).rglob('*.py')):
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
            paired = engine_pairs(our_file, reference_file) if exists else {}
            file_rows = []
            for record in typed_symbols(reference_file):
                qualified = _qualified(record)
                if exists:
                    structural, detail = structural_axis(record, ours_by_key, ours_names)
                else:
                    structural, detail = 'unresolved', 'archivo espejo inexistente'
                pair, write_path = paired.get(qualified, (None, ''))
                if (pair is not None and pair.route == _engine.BY_NAME
                        and structural in ('homonym', 'owner_absent', 'unresolved')):
                    # La contraparte efectiva vive en otra duena del espejo.
                    structural, detail = 'paired_by_name', pair.key
                test = evidence.get((module, qualified, record['kind']), '')
                category = principal(record['kind'], structural, write_path,
                                     test, record['name'] in known)
                reason = f'structural={structural}{":" + detail if detail else ""};' \
                         f'write_path={write_path or "-"};evidence={test or "-"}'
                file_rows.append((record['kind'], qualified, category, reason))
            reference_attributes = class_attributes(reference_file)
            our_attributes = class_attributes(our_file) if exists else {}
            # Lo que el propio espejo instala en otra clase (H-API-1177): una
            # base abstracta de la referencia, como ``_Relational``, no existe
            # en el puerto, que instala sus atributos en sus propias clases.
            installed_here = installed_names(our_file) if exists else set()
            for (owner, name), value in sorted(reference_attributes.items()):
                qualified = f'{owner}.{name}'
                if (owner, name) in our_attributes:
                    structural = (
                        'match' if our_attributes[(owner, name)] == value
                        else 'value')
                elif name in installed_here:
                    structural = 'installed_elsewhere'
                else:
                    structural = 'unresolved'
                test = evidence.get((module, qualified, 'attribute'), '')
                category = principal('attribute', structural, '', test,
                                     owner in known
                                     or f'{owner}.{name}' in known)
                file_rows.append(('attribute', qualified, category,
                                  f'structural={structural};write_path=-;'
                                  f'evidence={test or "-"}'))
            categories = {row[2] for row in file_rows}
            if not exists and categories <= {'absent'}:
                file_category = 'absent'
            elif 'divergent' in categories:
                file_category = 'divergent'
            elif categories == {'satisfied'}:
                file_category = 'satisfied'
            else:
                file_category = 'not_verified'
            rows.append((revision, module, '', 'file', file_category,
                         f'mirror={"yes" if exists else "no"}'))
            rows.extend((revision, module, q, k, c, r)
                        for k, q, c, r in file_rows)
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


def installed_names(path):
    """Los nombres que ``path`` instala como atributo de OTRA clase, como
    ``nombre`` y como ``Clase.nombre``.

    H-API-1167: el puerto disuelve ``class Field`` en ``models.Field`` de
    Django y le instala atributos de tres maneras que no son ``def`` ni
    ``class``: la asignacion ``models.Field.copy = ...``, ``setattr`` con el
    nombre literal, y un bucle ``for nombre, valor in DICT.items():`` cuyo
    cuerpo llama a ``setattr`` (las claves literales de ``DICT``). Sin esto,
    ``absent`` contaba como ausente lo instalado. La forma ``Clase.nombre``
    —la clase de destino es el ultimo segmento: ``Field`` en
    ``models.Field``— es la que consulta un atributo de clase de la
    referencia.

    No cuenta ``self.x`` ni ``cls.x``, ni lo que ocurre dentro de una
    funcion o una clase: es estado de un objeto, no una instalacion. Y un
    nombre instalado es solo PRESENCIA: queda en ``not_verified`` hasta que
    un contrato lo verifique.
    """
    tree = ast.parse(path.read_text(encoding='utf-8'))
    dicts = {}
    for node in tree.body:
        if (isinstance(node, (ast.Assign, ast.AnnAssign))
                and isinstance(node.value, ast.Dict)):
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target])
            keys = {k.value for k in node.value.keys
                    if isinstance(k, ast.Constant)
                    and isinstance(k.value, str)}
            for target in targets:
                if isinstance(target, ast.Name):
                    dicts[target.id] = keys
    names = set()

    def add(owner, name):
        names.add(name)
        owner_name = _target_class(owner)
        if owner_name:
            names.add(f'{owner_name}.{name}')

    for node in _module_level_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Attribute)
                        and not (isinstance(target.value, ast.Name)
                                 and target.value.id in ('self', 'cls'))):
                    add(target.value, target.attr)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == 'setattr' and len(node.args) >= 2
              and isinstance(node.args[1], ast.Constant)
              and isinstance(node.args[1].value, str)):
            add(node.args[0], node.args[1].value)
        elif (isinstance(node, ast.For) and isinstance(node.iter, ast.Call)
              and isinstance(node.iter.func, ast.Attribute)
              and node.iter.func.attr == 'items'
              and isinstance(node.iter.func.value, ast.Name)):
            calls = [inner for inner in ast.walk(node)
                     if isinstance(inner, ast.Call)
                     and isinstance(inner.func, ast.Name)
                     and inner.func.id == 'setattr' and inner.args]
            for call in calls:
                for key in dicts.get(node.iter.func.value.id, ()):
                    add(call.args[0], key)
        elif (isinstance(node, ast.For)
              and isinstance(node.iter, (ast.Tuple, ast.List))):
            # ``for _key, ... in (('name', ...), ...):`` con
            # ``setattr(models.Field, f'_description_{_key}', ...)``.
            loop_var = (node.target.elts[0]
                        if isinstance(node.target, ast.Tuple)
                        else node.target)
            if not isinstance(loop_var, ast.Name):
                continue
            values = []
            for element in node.iter.elts:
                first = (element.elts[0] if isinstance(element, ast.Tuple)
                         and element.elts else element)
                if (isinstance(first, ast.Constant)
                        and isinstance(first.value, str)):
                    values.append(first.value)
            for inner in ast.walk(node):
                if not (isinstance(inner, ast.Call)
                        and isinstance(inner.func, ast.Name)
                        and inner.func.id == 'setattr'
                        and len(inner.args) >= 2):
                    continue
                for value in values:
                    name = _formatted_name(inner.args[1], loop_var.id, value)
                    if name:
                        add(inner.args[0], name)
    installers = {node.name: node for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.args.args}
    for node in _module_level_nodes(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in installers and node.args):
            for name in _installer_targets(installers[node.func.id]):
                add(node.args[0], name)
    return names


def _installer_targets(function):
    """Lo que una funcion instaladora asigna sobre su PRIMER parametro.

    El puerto de BaseDate instala sus metodos con
    _attach_base_date(models.DateField, ...): el cuerpo asigna
    field_class.<nombre> = ... o llama setattr(field_class,
    '<nombre>', ...), y la clase de destino es el argumento de la llamada
    a nivel de modulo. Una asignacion sobre otro nombre no cuenta: seguir
    alias seria inferir, no leer.
    """
    param = function.args.args[0].arg
    names = []
    for inner in ast.walk(function):
        if isinstance(inner, ast.Assign):
            for target in inner.targets:
                if (isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == param):
                    names.append(target.attr)
        elif (isinstance(inner, ast.Call)
              and isinstance(inner.func, ast.Name)
              and inner.func.id == 'setattr' and len(inner.args) >= 2
              and isinstance(inner.args[0], ast.Name)
              and inner.args[0].id == param
              and isinstance(inner.args[1], ast.Constant)
              and isinstance(inner.args[1].value, str)):
            names.append(inner.args[1].value)
    return names


def module_bindings(path):
    """Los nombres que path liga a nivel de modulo con una llamada o
    un alias: Integer = make_dispatcher('Integer', ...).

    El puerto disuelve las clases de campo de la referencia en las de
    Django y conserva su nombre con una asignacion, no con una class;
    declared_symbols solo ve def y class. Un literal no liga una
    clase y no cuenta. Es presencia del nombre: queda en not_verified.
    """
    tree = ast.parse(path.read_text(encoding='utf-8'))
    names = set()
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and isinstance(node.value, (ast.Call, ast.Name,
                                            ast.Attribute))):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _formatted_name(node, variable, value):
    """El nombre que una f-string como ``f'_related_{_key}'`` produce con
    ``_key = value``, o ``None`` si usa otra cosa que la variable del
    bucle. Un nombre literal se devuelve tal cual."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if not isinstance(node, ast.JoinedStr):
        return None
    parts = []
    for piece in node.values:
        if isinstance(piece, ast.Constant):
            parts.append(str(piece.value))
        elif (isinstance(piece, ast.FormattedValue)
              and isinstance(piece.value, ast.Name)
              and piece.value.id == variable):
            parts.append(value)
        else:
            return None
    return ''.join(parts)


def _target_class(node):
    """El nombre de la clase de destino de una instalacion: el ultimo
    segmento de ``models.Field`` o el nombre de ``Field``."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _module_level_nodes(tree):
    """Los nodos del modulo que no estan dentro de una ``def`` ni de una
    ``class``: es donde se instala un atributo en una clase ajena. Una
    asignacion ``registro.nombre = ...`` dentro de una funcion es estado de
    un objeto, no una instalacion."""
    pending = list(tree.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Lambda)):
            continue
        yield node
        pending.extend(ast.iter_child_nodes(node))


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

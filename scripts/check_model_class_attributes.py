#!/usr/bin/env python3
"""Gate: compara la CABECERA del modelo, no sólo campos y métodos (H-API-580).

Cierra la tarea #336. ``check_porte_completo.py`` compara símbolos —campos y
métodos— dentro de un archivo, y es **ciego a los atributos de clase**
(``_name``, ``_description``, ``_inherit``, ``_order``, …). Por eso un porte
que declara 2 de 5 atributos pasa como completo: el gate de símbolos nunca
mira esa línea. Ya ocurrió dos veces — H-API-580 (``stock_picking.py``, 2 de
5) y H-API-668 (``res_partner.py``, 0 de 9) — y las dos las detectó el
ejecutor, ninguna una re-medición propia.

Contrato: ``.claude/rules/atributos-de-clase-de-modelo.md`` — *"si la clase de
la referencia declara atributos de clase, se portan TODOS los que declare. Si
no declara ninguno, no se inventa ninguno."*

Qué mide
--------

Por cada clase **con contraparte** (mismo nombre en ambos archivos — la
ausencia de la clase entera es el objeto de ``check_porte_completo.py``, no
de éste), extrae por AST los atributos que empiezan con ``_`` declarados
**directamente en el cuerpo de la clase** y distingue tres cosas que
comparten el prefijo y NO son lo mismo:

1. **Atributos de ORM** — el universo declarado en
   ``odoo19c: odoo/orm/models.py:370-464`` (``_init_model_class_attributes``,
   ``odoo19c: odoo/orm/model_classes.py:261``), más ``_check_company_domain``
   y ``_log_access`` que el mismo árbol documenta como patrón de atributo de
   clase aunque su declaración viva fuera de ese rango. Es el objeto de este
   gate: se reportan los que la referencia declara y el puerto no.
2. **Objetos de tabla** — ``_x = models.Constraint(...)`` /
   ``models.Index(...)`` / ``models.UniqueIndex(...)``
   (``odoo19c: odoo/orm/table_objects.py``). Su hogar aquí es
   ``Meta.constraints`` / ``Meta.indexes``; se reportan **aparte**, nunca
   como atributo de ORM ausente.
3. **Constantes de clase** — cualquier otro atributo con prefijo ``_`` que no
   esté en el universo ORM ni sea un objeto de tabla (``_complete_name_
   displayed_types`` es el caso real medido en ``res_partner.py``). Se
   ignoran: no son el objeto de la regla.

Un objeto de tabla de la referencia se da por **portado** cuando aparece en
``Meta.constraints`` / ``Meta.indexes`` con el nombre que ``full_name()``
deriva (``odoo19c: odoo/orm/table_objects.py:54-57`` —
``f'{_table}_{attr[1:]}'``), o con ese sufijo. Sin leer ``Meta``, el gate
reportaba ausente un objeto correctamente portado: un falso positivo sobre
trabajo correcto, que es peor que no medir (:ref:`h-api-675`).

*Métrica:* atributos ``_x`` del universo ORM declarados en la clase de la
referencia y ausentes en la clase homóloga de nuestro puerto, por AST.
*Ciega a:* un objeto de tabla en ``Meta`` cuyo nombre NO conserve el sufijo de
la referencia (se lee como ausente, y es la lectura conservadora correcta);
un atributo presente con el mismo nombre pero con **otro valor**
(el conteo generoso que ``porte-completo-no-parcial.md`` documenta — este
gate mide presencia, no equivalencia semántica); una clase sin contraparte en
absoluto (la mide ``check_porte_completo.py``); un atributo del universo ORM
que este gate no tenga listado (cota inferior, igual que
``check_identifier_language.py``); un atributo repartido en un archivo
hermano del mismo addon (el emparejamiento es archivo-a-archivo, no addon
entero — a diferencia de ``check_porte_completo.py``, porque la cabecera de
una clase vive donde vive la clase, no repartida).

Uso
---

.. code-block:: bash

   python3 scripts/check_model_class_attributes.py                 # barrido default
   python3 scripts/check_model_class_attributes.py --addon base    # un addon
   python3 scripts/check_model_class_attributes.py <archivo.py>... # rutas explícitas (nuestras)
   python3 scripts/check_model_class_attributes.py --quiet
   python3 scripts/check_model_class_attributes.py --strict        # exit 1 si hay incumplidores
   python3 scripts/check_model_class_attributes.py --write-baseline

Baseline
--------

La deuda heredada se congela en
``scripts/model_class_attributes_baseline.txt`` (``kind::addon/relpath::
class::attr``, ``kind`` es ``orm`` o ``table``). Un hallazgo ya listado no
bloquea; uno nuevo, sí. Mismo criterio prospectivo que
``identifier_language_baseline.txt`` (tarea #147) y el grifo cerrado de la
tarea #313: se paga al tocar el archivo, no en un barrido.
"""
import argparse
import ast
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from addons_roots import ADDONS_PATHS, addon_dirs, addon_path  # noqa: E402, F401

#: Raíz del árbol que gobierna (``odoo19c``). Ver
#: ``referencia-odoo-gobierna-las-decisiones.md``: 19 desempata.
import sys as _s, os.path as _op
_s.path.insert(0, _op.dirname(_op.abspath(__file__)))
from reference_roots import tree as _tree
ODOO19C = _tree('odoo19c')

BASELINE = pathlib.Path(__file__).with_name('model_class_attributes_baseline.txt')

#: ``base`` y los addons ``test_*`` viven empaquetados DENTRO de ``odoo/``
#: (``odoo19c: odoo/addons/base``), no bajo la raíz ``addons/`` de los demás
#: (``odoo19c: addons/stock``). Medido: 24 addons bajo ``odoo/addons/`` en
#: este árbol, ``base`` entre ellos. Sin este segundo candidato, ``base`` —el
#: addon del positivo real medido en H-API-668— no resuelve nunca.
_REFERENCE_ADDON_ROOTS = ('addons', 'odoo/addons')


def ref_addon_dir(addon):
    """El directorio del addon en la referencia, probando ambas raíces conocidas."""
    for prefix in _REFERENCE_ADDON_ROOTS:
        candidate = ODOO19C / prefix / addon
        if candidate.is_dir():
            return candidate
    return None


#: El universo de atributos de ORM que un modelo declara, medido en
#: ``odoo19c: odoo/orm/models.py:370-464`` (25 nombres) más dos que el mismo
#: árbol documenta como patrón de atributo de clase aunque su declaración
#: viva fuera de ese rango: ``_check_company_domain`` (sobreescribe el método
#: homónimo — ``odoo/addons/base/models/res_bank.py:78``) y ``_log_access``
#: (``odoo/orm/model_classes.py:219``, sin valor por defecto en la base).
#: Es una **cota inferior** declarada: un atributo de ORM real ausente de
#: esta lista se clasifica como "constante de clase" (categoría 3) y el gate
#: no lo ve.
ORM_ATTRIBUTES = frozenset({
    '_auto', '_register', '_abstract', '_transient',
    '_name', '_description', '_module', '_custom',
    '_inherit', '_inherits',
    '_table', '_table_query',
    '_rec_name', '_rec_names_search',
    '_order',
    '_parent_name', '_parent_store',
    '_active_name', '_fold_name',
    '_translate',
    '_check_company_auto', '_check_company_domain',
    '_allow_sudo_commands',
    '_depends',
    '_log_access',
})

#: Objetos de tabla — ``odoo19c: odoo/orm/table_objects.py``. Un atributo cuyo
#: valor es una llamada a uno de estos tres nombres NO es un atributo de ORM
#: ausente: es un objeto de tabla, y se reporta aparte.
TABLE_OBJECT_CALL_NAMES = frozenset({'Constraint', 'Index', 'UniqueIndex'})


def _call_name(value):
    """El nombre de la llamada (``models.Constraint`` → ``Constraint``), o ``''``."""
    if not isinstance(value, ast.Call):
        return ''
    func = value.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ''


def class_underscore_attrs(class_node):
    """``(orm, table, other)`` — atributos ``_x`` declarados en el CUERPO de la clase.

    Sólo mira las sentencias directas de ``class_node.body`` — ni métodos, ni
    clases anidadas (``class Meta:``), ni nada más profundo. Cada dict mapea
    ``nombre -> lineno``.
    """
    orm, table, other = {}, {}, {}
    for stmt in class_node.body:
        target = value = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name):
            target, value = stmt.targets[0].id, stmt.value
        elif isinstance(stmt, ast.AnnAssign) \
                and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            target, value = stmt.target.id, stmt.value
        if target is None or not target.startswith('_') or target.startswith('__'):
            continue
        if _call_name(value) in TABLE_OBJECT_CALL_NAMES:
            table[target] = stmt.lineno
        elif target in ORM_ATTRIBUTES:
            orm[target] = stmt.lineno
        else:
            other[target] = stmt.lineno
    return orm, table, other


def meta_table_object_names(class_node):
    """``(db_table, {nombres})`` de los objetos de tabla declarados en ``Meta``.

    El hogar de un ``models.Constraint``/``Index`` de la referencia **es**
    ``Meta.constraints`` / ``Meta.indexes`` — lo dice la propia regla. Sin leer
    ese nivel, el gate reporta como ausente un objeto correctamente portado:
    un falso positivo sobre trabajo correcto, que es peor que no medir.

    Devuelve el ``db_table`` declarado (o ``''``) y el conjunto de literales
    que aparecen como ``name=`` dentro de las listas ``constraints``/``indexes``.
    """
    db_table, names = '', set()
    meta = next((s for s in class_node.body
                 if isinstance(s, ast.ClassDef) and s.name == 'Meta'), None)
    if meta is None:
        return db_table, names
    for stmt in meta.body:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)):
            continue
        target = stmt.targets[0].id
        if target == 'db_table' and isinstance(stmt.value, ast.Constant) \
                and isinstance(stmt.value.value, str):
            db_table = stmt.value.value
        elif target in ('constraints', 'indexes'):
            for node in ast.walk(stmt.value):
                if isinstance(node, ast.keyword) and node.arg == 'name' \
                        and isinstance(node.value, ast.Constant) \
                        and isinstance(node.value.value, str):
                    names.add(node.value.value)
    return db_table, names


def table_object_is_placed(attr, db_table, meta_names):
    """¿El objeto de tabla ``_attr`` de la referencia aterrizó en ``Meta``?

    La referencia deriva el nombre real con ``full_name()``
    (``odoo19c: odoo/orm/table_objects.py:54-57``): ``f'{_table}_{attr[1:]}'``.
    Se acepta ese nombre exacto y, como red, cualquiera que termine en el
    sufijo — un puerto puede nombrar su tabla distinto y conservar el sufijo
    de la referencia, que es lo que la regla pide preservar.
    """
    bare = attr.lstrip('_')
    if f'{db_table}_{bare}' in meta_names:
        return True
    return any(name == bare or name.endswith(f'_{bare}') for name in meta_names)


def top_level_classes(path):
    """``{nombre_clase: ClassDef}`` de las clases de MÓDULO (no anidadas), o ``{}``."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return {}
    return {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}


def addon_and_relpath(path):
    """``(addon, relpath)`` si ``path`` vive bajo una raíz de addons; si no, ``(None, None)``.

    ``relpath`` es la ruta DENTRO del addon (p. ej. ``models/res_partner.py``)
    — la misma forma en ambos árboles, el nuestro y el de referencia.
    """
    resolved = path.resolve()
    for root in ADDONS_PATHS:
        if not root.is_dir():
            continue
        try:
            rel = resolved.relative_to(root.resolve())
        except ValueError:
            continue
        parts = rel.parts
        if len(parts) >= 2:
            return parts[0], pathlib.Path(*parts[1:])
    return None, None


def compare_file_pair(addon, relpath, ref_path, our_path):
    """Hallazgos ``(kind, addon, relpath, cls_name, attr, ref_lineno)`` de un par de archivos.

    ``kind`` es ``'orm'`` o ``'table'``. Sólo compara clases **con contraparte**
    homónima en ambos archivos — una clase ausente del todo es el objeto de
    ``check_porte_completo.py``, no de éste.
    """
    ref_classes = top_level_classes(ref_path)
    our_classes = top_level_classes(our_path)
    findings = []
    for cls_name, ref_node in sorted(ref_classes.items()):
        our_node = our_classes.get(cls_name)
        if our_node is None:
            continue
        ref_orm, ref_table, _ = class_underscore_attrs(ref_node)
        our_orm, our_table, _ = class_underscore_attrs(our_node)
        for attr, lineno in sorted(ref_orm.items()):
            if attr not in our_orm:
                findings.append(('orm', addon, str(relpath), cls_name, attr, lineno))
        db_table, meta_names = meta_table_object_names(our_node)
        for attr, lineno in sorted(ref_table.items()):
            if attr in our_table or table_object_is_placed(attr, db_table, meta_names):
                continue
            findings.append(('table', addon, str(relpath), cls_name, attr, lineno))
    return findings


def default_scope():
    """``[(addon, relpath, ref_path, our_path), ...]`` — el barrido por defecto.

    Un archivo por addon bajo ``models/*.py`` (no recursivo), emparejado por
    nombre — el mismo alcance que ``check_porte_completo.py`` ya establece
    para el porte de símbolos. Ampliarlo a subdirectorios o a rutas fuera de
    ``models/`` es alcance para rutas explícitas, no para el barrido default.
    """
    pairs = []
    for addon_dir in addon_dirs():
        addon = addon_dir.name
        ref_addon = ref_addon_dir(addon)
        if ref_addon is None:
            continue
        ref_dir = ref_addon / 'models'
        our_dir = addon_dir / 'models'
        if not ref_dir.is_dir() or not our_dir.is_dir():
            continue
        for ref_py in sorted(ref_dir.glob('*.py')):
            if ref_py.name == '__init__.py':
                continue
            our_py = our_dir / ref_py.name
            if not our_py.is_file():
                continue
            pairs.append((addon, pathlib.Path('models') / ref_py.name, ref_py, our_py))
    return pairs


def explicit_scope(argv_paths):
    """``[(addon, relpath, ref_path, our_path), ...]`` de rutas nuestras dadas por CLI."""
    pairs = []
    for raw in argv_paths:
        our_py = pathlib.Path(raw)
        addon, relpath = addon_and_relpath(our_py)
        if addon is None:
            print(f'AVISO: {raw} no vive bajo ninguna raíz de addons; se omite.')
            continue
        ref_addon = ref_addon_dir(addon)
        ref_py = (ref_addon / relpath) if ref_addon else pathlib.Path('/nonexistent')
        if not ref_py.is_file():
            print(f'AVISO: {raw} — sin contraparte en la referencia '
                  f'({ref_py}); se omite.')
            continue
        pairs.append((addon, relpath, ref_py, our_py))
    return pairs


def load_baseline():
    if not BASELINE.exists():
        return set()
    return {line.strip() for line in BASELINE.read_text().splitlines()
            if line.strip() and not line.startswith('#')}


def finding_key(finding):
    kind, addon, relpath, cls_name, attr, _lineno = finding
    return f'{kind}::{addon}/{relpath}::{cls_name}::{attr}'


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('paths', nargs='*',
                         help='archivos NUESTROS a medir (default: barrido de models/*.py)')
    parser.add_argument('--addon', help='medir sólo este addon (con el barrido default)')
    parser.add_argument('--quiet', action='store_true', help='sólo el conteo')
    parser.add_argument('--strict', action='store_true',
                         help='exit 1 si hay incumplidores fuera del baseline')
    parser.add_argument('--write-baseline', action='store_true',
                         help='congela el estado actual como deuda heredada')
    args = parser.parse_args()

    if not ODOO19C.is_dir():
        print(f'AVISO: no está el árbol de referencia en {ODOO19C}; '
              'sin él este gate no puede medir nada.')
        return 0

    if args.paths:
        pairs = explicit_scope(args.paths)
    else:
        pairs = default_scope()
        if args.addon:
            pairs = [p for p in pairs if p[0] == args.addon]

    findings = []
    for addon, relpath, ref_path, our_path in pairs:
        findings += compare_file_pair(addon, relpath, ref_path, our_path)

    if args.write_baseline:
        lines = sorted({finding_key(f) for f in findings})
        BASELINE.write_text(
            '# Deuda heredada de cabeceras de modelo (tarea #336, H-API-580/668).\n'
            '# Congelada por check_model_class_attributes.py --write-baseline.\n'
            '# kind::addon/relpath::class::attr — kind es orm o table.\n'
            '# Un hallazgo NUEVO no entra aquí: se porta el atributo o se\n'
            '# declara su divergencia (porte-completo-no-parcial.md).\n'
            + '\n'.join(lines) + ('\n' if lines else ''))
        print(f'baseline escrita: {len(lines)} hallazgo(s) '
              f'({len(pairs)} pares de archivo medidos)')
        return 0

    baseline = load_baseline()
    fresh = [f for f in findings if finding_key(f) not in baseline]
    fresh_orm = [f for f in fresh if f[0] == 'orm']
    fresh_table = [f for f in fresh if f[0] == 'table']

    if args.quiet:
        print(len(fresh))
        return 1 if (args.strict and fresh) else 0

    if not fresh:
        print(f'OK: cabeceras de modelo completas ({len(findings)} en deuda '
              f'heredada; alcance medido: {len(pairs)} pares de archivo).')
        return 0

    if fresh_orm:
        print(f'FAIL — {len(fresh_orm)} atributo(s) de ORM ausente(s) '
              f'(alcance medido: {len(pairs)} pares de archivo):\n')
        for kind, addon, relpath, cls_name, attr, lineno in fresh_orm:
            print(f'  {addon}/{relpath} :: {cls_name}.{attr}'
                  f'  (referencia :{lineno})')

    if fresh_table:
        print(f'\nADEMÁS — {len(fresh_table)} objeto(s) de tabla ausente(s) '
              '(se reportan APARTE: su hogar es Meta.constraints/Meta.indexes, '
              'no son atributo de ORM):\n')
        for kind, addon, relpath, cls_name, attr, lineno in fresh_table:
            print(f'  {addon}/{relpath} :: {cls_name}.{attr}'
                  f'  (referencia :{lineno})')

    print(f'\nMedido: {len(pairs)} pares de archivo. Deuda heredada congelada: '
          f'{len(baseline)}.')
    print('Ver .claude/rules/atributos-de-clase-de-modelo.md — la clase de la '
          'referencia se porta con TODOS sus atributos de clase, o ninguno.')
    return 1 if (args.strict and fresh) else 0


if __name__ == '__main__':
    sys.exit(main())

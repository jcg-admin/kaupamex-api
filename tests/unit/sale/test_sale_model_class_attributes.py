"""Atributos de clase de ``sale`` contra la cabecera que declara la referencia.

Origen: tarea #99 — ``atributos-de-clase-de-modelo.md`` (v2.0.0) exige que,
cuando la clase de la referencia declara atributos de clase, se porten
**todos** los que declare; si no declara ninguno, no se inventa ninguno.

Medido antes de escribir este archivo (``odoo19c: addons/sale/models/``, los
once archivos con contraparte en ``addons/sale/models/``):

- Dos clases **son** el modelo (``SaleOrder``, ``SaleOrderLine``): la
  referencia declara ``_name``/``_inherit``/``_description``/``_order``/
  ``_check_company_auto`` (+ ``_rec_names_search`` como ``@property`` en
  ``SaleOrder``), y los dos ya los llevan verbatim en su cabecera de clase —
  puerto de una iniciativa anterior (commits ``bf2017f2``..``b23ec1f0``).
- Ocho clases (en nueve archivos, porque ``analytic.py`` extiende dos) son
  extensiones puras (``_inherit`` sin ``_name``), portadas con
  ``orm.model_classes.extend_model`` en vez de una clase Django — divergencia
  de mecanismo declarada en cada docstring. Siete de esas nueve **no**
  declaraban su cabecera en ninguna parte del archivo; este pase la añade
  como constante de módulo (``_inherit = '<name>'``, con el comentario
  ``la extensión aquí no es clase``), el mismo patrón que ``res_partner.py``
  ya usaba desde la tarea #994.
- ``chart_template.py`` es la única sin ``_inherit`` que declarar: su
  docstring mide que el objeto que extiende (el cargador del plan contable)
  no es un ``AbstractModel`` con ``_inherit`` — es una clase de métodos con
  registro por decorador. Se excluye de este archivo a propósito.

*Métrica:* el atributo de clase (o la constante de módulo, en las
extensiones) declarado aquí, comparado por AST contra la cabecera que la
referencia declara en la clase homónima.
*Ciega a:* el resto de símbolos del archivo — campos, métodos, objetos de
tabla — que ``porte-completo-no-parcial.md`` gobierna con su propio
instrumento; aquí sólo se mide la cabecera.
"""
import ast
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCRIPTS_DIR = str(REPO_ROOT / 'scripts')
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import reference_roots  # noqa: E402  (sys.path se ajusta arriba, no top-level real)

ODOO19C = reference_roots.tree('odoo19c')
REFERENCE_SALE_MODELS = ODOO19C / 'addons' / 'sale' / 'models'
OUR_SALE_MODELS = REPO_ROOT / 'addons' / 'sale' / 'models'

pytestmark = pytest.mark.skipif(
    not REFERENCE_SALE_MODELS.is_dir(),
    reason=(
        'referencia ausente: '
        f'{REFERENCE_SALE_MODELS} no existe (odoo-tools no montado en este '
        'entorno; ver referencia-odoo-gobierna-las-decisiones.md)'
    ),
)


def _literal_or_none(node):
    """El valor de un ``ast.Assign`` si es un literal simple; si no, ``None``.

    Sólo interesan aquí los atributos cuyo valor es comparable letra a letra
    (cadenas, listas de cadenas, booleanos). Un objeto de tabla
    (``models.Constraint(...)``) no lo es — y no le corresponde a este
    archivo, que mide cabecera, no objetos de tabla.
    """
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None


def _class_header_attrs(source_path):
    """``{nombre_de_clase: {atributo: valor}}`` de los ``ast.Assign`` simples
    en el cuerpo de cada clase de ``source_path``.
    """
    tree = ast.parse(source_path.read_text())
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        attrs = {}
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id.startswith('_'):
                    attrs[target.id] = _literal_or_none(stmt.value)
        out[node.name] = attrs
    return out


def _module_level_assigns(source_path):
    """``{nombre: valor}`` de los ``ast.Assign`` simples a nivel de módulo."""
    tree = ast.parse(source_path.read_text())
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                out[target.id] = _literal_or_none(node.value)
    return out


# ---------------------------------------------------------------------------
# Grupo 1 — las dos clases que SON el modelo: _name, _inherit, _description,
# _order, _check_company_auto en la cabecera de la clase Django.
# ---------------------------------------------------------------------------

NAME_OWNING_CLASSES = [
    # (archivo, clase de la referencia, clase nuestra)
    ('sale_order.py', 'SaleOrder', 'SaleOrder'),
    ('sale_order_line.py', 'SaleOrderLine', 'SaleOrderLine'),
]

#: Atributos de cabecera comparables letra a letra por este test. Se excluye
#: ``_rec_names_search`` de ``SaleOrder`` porque la referencia lo declara
#: como ``@property`` (no ``ast.Assign``) y nuestro puerto lo porta también
#: como propiedad — comparar su VALOR estático no aplica a ninguno de los
#: dos lados; existe otro test (``test_sale_order_rec_names_search_is_a_
#: property_here_too``) que sí lo cubre.
HEADER_ATTRS_TO_COMPARE = ('_name', '_inherit', '_description', '_order',
                           '_check_company_auto')


@pytest.mark.parametrize('filename,ref_class,our_class', NAME_OWNING_CLASSES)
def test_name_owning_class_ports_every_header_attribute(
        filename, ref_class, our_class):
    """Cada atributo simple que la referencia declara está, con su valor."""
    ref_attrs = _class_header_attrs(REFERENCE_SALE_MODELS / filename)[ref_class]
    our_attrs = _class_header_attrs(OUR_SALE_MODELS / filename)[our_class]

    faltantes = []
    divergentes = []
    for attr in HEADER_ATTRS_TO_COMPARE:
        if attr not in ref_attrs:
            continue
        if attr not in our_attrs:
            faltantes.append(attr)
        elif our_attrs[attr] != ref_attrs[attr]:
            divergentes.append((attr, ref_attrs[attr], our_attrs[attr]))

    assert not faltantes, (
        f'{filename}::{our_class} no declara {faltantes}, que la referencia '
        f'sí declara en {ref_class}'
    )
    assert not divergentes, (
        f'{filename}::{our_class} diverge de la referencia sin declararlo: '
        f'{divergentes}'
    )


def test_sale_order_rec_names_search_is_a_property_here_too():
    """``_rec_names_search`` de ``SaleOrder`` es ``@property`` en los dos lados.

    La referencia lo declara como propiedad dinámica (depende de
    ``sale_show_partner_name`` en el contexto), no como ``ast.Assign`` — un
    recorrido que sólo mire asignaciones lo pierde en silencio. Este test
    verifica por AST que ambos lados lo declaran como método decorado con
    ``@property``, y que el nuestro nombra el mismo contexto.
    """
    def _has_property_rec_names_search(source_path, class_name):
        tree = ast.parse(source_path.read_text())
        for node in tree.body:
            if not (isinstance(node, ast.ClassDef) and node.name == class_name):
                continue
            for stmt in node.body:
                if (isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and stmt.name == '_rec_names_search'
                        and any(
                            isinstance(d, ast.Name) and d.id == 'property'
                            for d in stmt.decorator_list)):
                    return True
        return False

    assert _has_property_rec_names_search(
        REFERENCE_SALE_MODELS / 'sale_order.py', 'SaleOrder')
    assert _has_property_rec_names_search(
        OUR_SALE_MODELS / 'sale_order.py', 'SaleOrder')

    source = (OUR_SALE_MODELS / 'sale_order.py').read_text()
    assert 'sale_show_partner_name' in source, (
        'el _rec_names_search dinámico debe seguir consultando el mismo '
        'contexto que la referencia (odoo19c: sale_order.py:43-46)'
    )


@pytest.mark.parametrize('filename,ref_class,our_class', NAME_OWNING_CLASSES)
def test_db_table_matches_name_replace_dot_underscore(
        filename, ref_class, our_class):
    """``Meta.db_table`` == ``_name.replace('.', '_')`` — el default de la
    referencia (``odoo19c: odoo/orm/model_classes.py:266``), que aquí es una
    declaración humana y puede divergir sin que nada avise si no se mide.
    """
    tree = ast.parse((OUR_SALE_MODELS / filename).read_text())
    class_node = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == our_class
    )
    attrs = _class_header_attrs(OUR_SALE_MODELS / filename)[our_class]
    name = attrs['_name']

    meta_node = next(
        n for n in class_node.body
        if isinstance(n, ast.ClassDef) and n.name == 'Meta'
    )
    db_table = None
    for stmt in meta_node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == 'db_table':
                    db_table = _literal_or_none(stmt.value)

    assert db_table is not None, f'{our_class}.Meta no declara db_table'
    assert db_table == name.replace('.', '_')


# ---------------------------------------------------------------------------
# Grupo 2 — las extensiones puras: _inherit (+ _description donde la
# referencia lo declare) expresado como constante de módulo, porque el
# mecanismo de este árbol (extend_model) no tiene clase donde ponerlo.
# ---------------------------------------------------------------------------

#: (archivo, clase de la referencia, {atributo referencia: nombre de la
#: constante nuestra}). El nombre de la constante varía porque un archivo
#: puede extender más de un modelo (analytic.py extiende dos).
EXTENSION_ONLY_CLASSES = [
    ('analytic.py', 'AccountAnalyticLine',
     {'_inherit': '_INHERIT_ACCOUNT_ANALYTIC_LINE'}),
    ('analytic.py', 'AccountAnalyticApplicability',
     {'_inherit': '_INHERIT_ACCOUNT_ANALYTIC_APPLICABILITY',
      '_description': '_DESCRIPTION_ACCOUNT_ANALYTIC_APPLICABILITY'}),
    ('ir_actions_report.py', 'IrActionsReport', {'_inherit': '_inherit'}),
    ('ir_config_parameter.py', 'IrConfigParameter', {'_inherit': '_inherit'}),
    ('payment_provider.py', 'PaymentProvider', {'_inherit': '_inherit'}),
    ('product_document.py', 'ProductDocument', {'_inherit': '_inherit'}),
    ('product_pricelist_item.py', 'ProductPricelistItem',
     {'_inherit': '_inherit'}),
    ('res_company.py', 'ResCompany', {'_inherit': '_inherit'}),
    ('res_partner.py', 'ResPartner', {'_inherit': '_inherit'}),
]


@pytest.mark.parametrize(
    'filename,ref_class,attr_map', EXTENSION_ONLY_CLASSES,
    ids=[f'{f}::{c}' for f, c, _ in EXTENSION_ONLY_CLASSES],
)
def test_extension_only_file_declares_the_header_as_module_constant(
        filename, ref_class, attr_map):
    """La cabecera que la referencia declara EN LA CLASE existe aquí como
    constante de módulo, con el mismo valor — porque el archivo no tiene
    clase Django que la lleve (extiende con ``extend_model``).
    """
    ref_attrs = _class_header_attrs(REFERENCE_SALE_MODELS / filename)[ref_class]
    our_module = _module_level_assigns(OUR_SALE_MODELS / filename)

    for ref_attr, our_name in attr_map.items():
        assert ref_attr in ref_attrs, (
            f'la lista de atributos a comparar está desalineada con la '
            f'referencia: {ref_class} no declara {ref_attr}'
        )
        assert our_name in our_module, (
            f'{filename} no declara la constante de módulo {our_name!r} '
            f'para {ref_class}.{ref_attr}'
        )
        assert our_module[our_name] == ref_attrs[ref_attr], (
            f'{filename}::{our_name} = {our_module[our_name]!r}, la '
            f'referencia declara {ref_class}.{ref_attr} = '
            f'{ref_attrs[ref_attr]!r}'
        )


def test_no_extension_only_class_is_missing_from_the_parametrization():
    """Control de cobertura: todo archivo de ``addons/sale/models/`` con
    contraparte en la referencia, y cuya única clase-atributo es ``_inherit``
    (con o sin ``_description``), está cubierto por
    ``EXTENSION_ONLY_CLASSES`` — salvo ``chart_template.py``, que no declara
    ``_inherit`` en absoluto (divergencia de mecanismo medida en su propio
    docstring: extiende un cargador por decorador, no un ``_inherit``).
    """
    covered = {(f, c) for f, c, _ in EXTENSION_ONLY_CLASSES}
    covered |= {(f, c) for f, c, _ in NAME_OWNING_CLASSES}

    missing = []
    for our_file in sorted(OUR_SALE_MODELS.glob('*.py')):
        if our_file.name in ('__init__.py',):
            continue
        ref_file = REFERENCE_SALE_MODELS / our_file.name
        if not ref_file.is_file():
            continue
        if our_file.name == 'chart_template.py':
            continue
        for class_name, attrs in _class_header_attrs(ref_file).items():
            if '_inherit' in attrs or '_name' in attrs:
                if (our_file.name, class_name) not in covered:
                    missing.append((our_file.name, class_name))

    assert not missing, (
        f'clases con cabecera en la referencia y sin cobertura en este '
        f'archivo: {missing}'
    )

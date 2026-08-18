"""El gate de cabecera de modelo distingue ORM / objeto de tabla / constante
(H-API-580, H-API-668, tarea #336).

Mismo principio que ``test_check_porte_completo.py`` (:ref:`h-api-556`): un
gate se prueba contra un **positivo conocido del repo**, no contra un
incumplidor fabricado por quien escribió el patrón — un fabricado hereda el
encuadre de su autor y confirma el instrumento en vez de ponerlo a prueba.

El positivo conocido aquí es ``src/addons/base/models/res_partner.py``: su
propio docstring (líneas 52-87) documenta que porta 7 de los 9 atributos que
``odoo19c: odoo/addons/base/models/res_partner.py`` declara para
``ResPartner``, y nombra los dos que faltan: ``_check_company_domain``
(atributo de ORM) y el objeto de tabla ``_check_name``. Si el gate no
reproduce exactamente esos dos, o reproduce de más, el instrumento está mal
calibrado — no el archivo.
"""
import ast
import importlib.util
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    'check_model_class_attributes',
    REPO / 'scripts' / 'check_model_class_attributes.py')
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

_HAS_REFERENCE_TREE = gate.ODOO19C.is_dir()
requires_reference_tree = pytest.mark.skipif(
    not _HAS_REFERENCE_TREE,
    reason=f'árbol de referencia no montado en {gate.ODOO19C}')


def _class_def(source, name='C'):
    """El ``ClassDef`` llamado ``name`` del primer nivel del módulo."""
    tree = ast.parse(source)
    return next(n for n in tree.body
                if isinstance(n, ast.ClassDef) and n.name == name)


# --- class_underscore_attrs: las tres categorías, aisladas -----------------


def test_a_known_orm_attribute_is_classified_as_orm():
    orm, table, other = gate.class_underscore_attrs(_class_def(
        "class C(Model):\n"
        "    _name = 'res.partner'\n"
        "    _description = 'Contact'\n"
    ))
    assert set(orm) == {'_name', '_description'}
    assert table == {}
    assert other == {}


def test_a_constraint_call_is_classified_as_table_object_not_orm():
    """``_check_name = models.Constraint(...)`` — el caso real de res_partner.py:326."""
    orm, table, other = gate.class_underscore_attrs(_class_def(
        "class C(Model):\n"
        "    _check_name = models.Constraint(\n"
        "        \"CHECK(type='contact')\",\n"
        "        'Contacts require a name',\n"
        "    )\n"
    ))
    assert orm == {}
    assert set(table) == {'_check_name'}
    assert other == {}


@pytest.mark.parametrize('expression', [
    "models.Constraint('sql', 'msg')",
    "models.Index('CREATE INDEX ...')",
    "models.UniqueIndex('...')",
    "Constraint('sql', 'msg')",   # import directo, sin el prefijo del módulo
])
def test_the_three_table_object_constructors_are_all_recognized(expression):
    orm, table, other = gate.class_underscore_attrs(_class_def(
        f"class C(Model):\n    _x = {expression}\n"
    ))
    assert set(table) == {'_x'}
    assert orm == {}


def test_a_private_class_constant_outside_the_orm_universe_is_ignored():
    """``_complete_name_displayed_types`` — el caso real de res_partner.py:195.

    Snake_case, no SCREAMING_SNAKE, y aun así NO es un atributo de ORM: no
    está en el universo declarado (``models.py:370-464``). El gate lo manda a
    "other" y no lo compara — igual que hace el puerto real, cuyo propio
    docstring lo declara "una constante de clase, no un atributo de ORM".
    """
    orm, table, other = gate.class_underscore_attrs(_class_def(
        "class C(Model):\n"
        "    _complete_name_displayed_types = ('invoice', 'delivery', 'other')\n"
    ))
    assert orm == {}
    assert table == {}
    assert set(other) == {'_complete_name_displayed_types'}


def test_dunder_attributes_are_never_orm_candidates():
    orm, table, other = gate.class_underscore_attrs(_class_def(
        "class C(Model):\n    __slots__ = ['env']\n"
    ))
    assert orm == table == other == {}


def test_attributes_declared_inside_a_method_are_not_class_attributes():
    """Sólo el cuerpo directo de la clase cuenta — no lo que asigna un método."""
    orm, table, other = gate.class_underscore_attrs(_class_def(
        "class C(Model):\n"
        "    _name = 'res.partner'\n"
        "    def f(self):\n"
        "        self._description = 'no cuenta'\n"
    ))
    assert set(orm) == {'_name'}


def test_a_nested_meta_class_is_not_walked_into():
    """``class Meta:`` anidada no es un atributo de la clase contenedora."""
    orm, table, other = gate.class_underscore_attrs(_class_def(
        "class C(Model):\n"
        "    _name = 'res.partner'\n"
        "    class Meta:\n"
        "        _table = 'ignored'\n"
    ))
    assert set(orm) == {'_name'}


def test_annotated_assignment_without_value_is_not_a_declaration():
    """``_x: bool`` sin valor es sólo un anuncio de tipo — no una declaración."""
    orm, table, other = gate.class_underscore_attrs(_class_def(
        "class C(Model):\n    _log_access: bool\n"
    ))
    assert orm == table == other == {}


def test_annotated_assignment_with_value_is_a_declaration():
    orm, table, other = gate.class_underscore_attrs(_class_def(
        "class C(Model):\n    _log_access: bool = True\n"
    ))
    assert set(orm) == {'_log_access'}


# --- top_level_classes -------------------------------------------------


def test_only_module_level_classes_are_returned(tmp_path):
    path = tmp_path / 'm.py'
    path.write_text(
        "class A(Model):\n"
        "    _name = 'a'\n"
        "def f():\n"
        "    class B(Model):\n"
        "        _name = 'b'\n"
        "    return B\n"
    )
    classes = gate.top_level_classes(path)
    assert set(classes) == {'A'}


def test_unparseable_file_returns_empty_dict(tmp_path):
    path = tmp_path / 'broken.py'
    path.write_text('class C(:\n    esto no parsea')
    assert gate.top_level_classes(path) == {}


# --- addon_and_relpath ------------------------------------------------


def test_addon_and_relpath_resolves_a_real_file_of_this_repo():
    addon, relpath = gate.addon_and_relpath(
        REPO / 'addons' / 'stock' / 'models' / 'stock_picking.py')
    assert addon == 'stock'
    assert relpath == pathlib.Path('models/stock_picking.py')


def test_addon_and_relpath_is_none_outside_any_addons_root():
    addon, relpath = gate.addon_and_relpath(REPO / 'README.rst')
    assert (addon, relpath) == (None, None)


# --- el positivo conocido del repo: res_partner.py ----------------------


@requires_reference_tree
def test_the_real_positive_res_partner_names_exactly_its_two_known_gaps():
    """``res_partner.py`` — 7 de 9 portados; el gate reproduce los 2 que faltan.

    Ninguno de más, ninguno de menos: los siete ya portados (``_name``,
    ``_description``, ``_inherit``, ``_order``, ``_rec_names_search``,
    ``_allow_sudo_commands``, ``_check_company_auto``) no deben salir como
    ausentes, y la constante ``_complete_name_displayed_types`` (categoría
    "otros") tampoco — sólo así el gate confirma que sabe leer las tres
    categorías, no sólo detectar *algo*.
    """
    addon, relpath = 'base', pathlib.Path('models/res_partner.py')
    ref_addon = gate.ref_addon_dir(addon)
    assert ref_addon is not None, "'base' no resuelve bajo odoo/addons ni addons"
    ref_path = ref_addon / relpath
    our_path = REPO / 'src' / 'addons' / addon / relpath
    assert our_path.is_file()

    findings = gate.compare_file_pair(addon, relpath, ref_path, our_path)
    by_kind = {(f[0], f[4]) for f in findings}

    assert by_kind == {
        ('orm', '_check_company_domain'),
        ('table', '_check_name'),
    }
    # Ninguno de los siete ya portados sale como ausente:
    missing = {f[4] for f in findings}
    for ported in ('_name', '_description', '_inherit', '_order',
                   '_rec_names_search', '_allow_sudo_commands',
                   '_check_company_auto'):
        assert ported not in missing
    # La constante de clase no es un hallazgo — categoría "otros", ignorada:
    assert '_complete_name_displayed_types' not in missing


@requires_reference_tree
def test_a_genuinely_clean_pair_of_the_repo_yields_no_findings():
    """``account_add_gln`` — par limpio real, medido con el propio barrido default.

    Complementa el positivo (que SÍ falla): un gate que sólo supiera decir
    que sí no sería un gate. ``account_add_gln`` se eligió corriendo
    ``default_scope()`` y filtrando los addons con 0 hallazgos — no se
    fabricó.
    """
    pairs = [p for p in gate.default_scope() if p[0] == 'account_add_gln']
    assert pairs, 'account_add_gln no aparece en el barrido default'
    findings = []
    for addon, relpath, ref_path, our_path in pairs:
        findings += gate.compare_file_pair(addon, relpath, ref_path, our_path)
    assert findings == []


# --- finding_key() / baseline --------------------------------------------


def test_finding_key_format_matches_the_baseline_line_format():
    finding = ('orm', 'base', 'models/res_partner.py', 'ResPartner',
               '_check_company_domain', 192)
    assert gate.finding_key(finding) == (
        'orm::base/models/res_partner.py::ResPartner::_check_company_domain')


def test_load_baseline_returns_empty_set_when_file_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(gate, 'BASELINE', tmp_path / 'no-existe.txt')
    assert gate.load_baseline() == set()


def test_load_baseline_skips_comments_and_blank_lines(tmp_path, monkeypatch):
    baseline = tmp_path / 'baseline.txt'
    baseline.write_text('# comentario\n\norm::a/b.py::C::_name\n')
    monkeypatch.setattr(gate, 'BASELINE', baseline)
    assert gate.load_baseline() == {'orm::a/b.py::C::_name'}


# --- CLI end-to-end: los dos sentidos, SIN el baseline congelado real ------
#
# El baseline real del repo (scripts/model_class_attributes_baseline.txt) ya
# absorbió la deuda heredada, incluida la de res_partner.py — correrlo contra
# el CLI real daría exit 0 (baselined), no exit 1. Estos tests apuntan
# gate.BASELINE a un archivo vacío para medir el comportamiento SIN deuda
# congelada, que es la pregunta real: ¿el gate detecta y nombra un hallazgo
# nuevo?


@requires_reference_tree
def test_cli_exits_zero_on_a_clean_scope(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(gate, 'BASELINE', tmp_path / 'vacio.txt')
    our_dir = REPO / 'addons' / 'account_add_gln' / 'models'
    path = next(our_dir.glob('*.py'))
    monkeypatch.setattr(gate.sys, 'argv', [
        'check_model_class_attributes.py', '--strict', str(path)])
    assert gate.main() == 0
    assert 'OK' in capsys.readouterr().out


@requires_reference_tree
def test_cli_exits_one_and_names_the_real_positive(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(gate, 'BASELINE', tmp_path / 'vacio.txt')
    path = REPO / 'src' / 'addons' / 'base' / 'models' / 'res_partner.py'
    monkeypatch.setattr(gate.sys, 'argv', [
        'check_model_class_attributes.py', '--strict', str(path)])
    assert gate.main() == 1
    output = capsys.readouterr().out
    assert '_check_company_domain' in output
    assert '_check_name' in output


@requires_reference_tree
def test_cli_write_baseline_freezes_current_findings(monkeypatch, tmp_path):
    destination = tmp_path / 'baseline.txt'
    monkeypatch.setattr(gate, 'BASELINE', destination)
    path = REPO / 'src' / 'addons' / 'base' / 'models' / 'res_partner.py'
    monkeypatch.setattr(gate.sys, 'argv', [
        'check_model_class_attributes.py', '--write-baseline', str(path)])
    assert gate.main() == 0
    content = destination.read_text()
    assert 'orm::base/models/res_partner.py::ResPartner::_check_company_domain' \
        in content
    assert 'table::base/models/res_partner.py::ResPartner::_check_name' \
        in content

    # Con ese baseline ya escrito, correr --strict sobre el MISMO archivo
    # ahora da limpio: es deuda congelada, no un hallazgo nuevo.
    monkeypatch.setattr(gate.sys, 'argv', [
        'check_model_class_attributes.py', '--strict', str(path)])
    assert gate.main() == 0

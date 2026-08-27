"""El gate de cabecera de modelo distingue ORM / objeto de tabla / constante
(H-API-580, H-API-668, tarea #336).

Mismo principio que ``test_check_porte_completo.py`` (:ref:`h-api-556`): un
gate se prueba contra un **positivo conocido del repo**, no contra un
incumplidor fabricado por quien escribió el patrón — un fabricado hereda el
encuadre de su autor y confirma el instrumento en vez de ponerlo a prueba.

El positivo conocido aquí es ``src/addons/base/models/res_partner.py``: su
propio docstring documenta cuántos de los 9 atributos que
``odoo19c: odoo/addons/base/models/res_partner.py`` declara para
``ResPartner`` están portados, y nombra el que falta —
``_check_company_domain``, un atributo de ORM cuyo mecanismo vive en
``src/orm`` y todavía no existe. Si el gate no reproduce exactamente ése, o
reproduce de más, el instrumento está mal calibrado — no el archivo.

El objeto de tabla ``_check_name`` **no** es un hallazgo: aterrizó en
``Meta.constraints`` como ``res_partner_check_name``, que es su hogar
declarado por ``atributos-de-clase-de-modelo.md``. El gate lo reportaba
ausente hasta que aprendió a leer ``Meta`` — un falso positivo sobre trabajo
correcto, que es peor que no medir (:ref:`h-api-675`).
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
def test_the_real_positive_res_partner_names_its_one_remaining_gap():
    """``res_partner.py`` — 8 de 9 portados; el gate reproduce el que falta.

    Ninguno de más, ninguno de menos: los ya portados (``_name``,
    ``_description``, ``_inherit``, ``_order``, ``_rec_names_search``,
    ``_allow_sudo_commands``, ``_check_company_auto``) no deben salir como
    ausentes, y la constante ``_complete_name_displayed_types`` (categoría
    "otros") tampoco — sólo así el gate confirma que sabe leer las tres
    categorías, no sólo detectar *algo*.

    ``_check_name`` **tampoco** sale: es un objeto de tabla y aterrizó en
    ``Meta.constraints`` como ``res_partner_check_name``, que es su hogar
    declarado. El gate lo daba por ausente hasta que aprendió a leer ``Meta``
    — un falso positivo sobre trabajo correcto (:ref:`h-api-675`).
    """
    addon, relpath = 'base', pathlib.Path('models/res_partner.py')
    ref_addon = gate.ref_addon_dir(addon)
    assert ref_addon is not None, "'base' no resuelve bajo odoo/addons ni addons"
    ref_path = ref_addon / relpath
    our_path = REPO / 'src' / 'addons' / addon / relpath
    assert our_path.is_file()

    findings = gate.compare_file_pair(addon, relpath, ref_path, our_path)
    by_kind = {(f[0], f[4]) for f in findings}

    assert by_kind == {('orm', '_check_company_domain')}
    # Ninguno de los ya portados sale como ausente — el objeto de tabla
    # incluido, porque su hogar es Meta.constraints:
    missing = {f[4] for f in findings}
    for ported in ('_name', '_description', '_inherit', '_order',
                   '_rec_names_search', '_allow_sudo_commands',
                   '_check_company_auto', '_check_name'):
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
    # El objeto de tabla NO entra al baseline: está portado en Meta.constraints.
    assert '_check_name' not in content

    # Con ese baseline ya escrito, correr --strict sobre el MISMO archivo
    # ahora da limpio: es deuda congelada, no un hallazgo nuevo.
    monkeypatch.setattr(gate.sys, 'argv', [
        'check_model_class_attributes.py', '--strict', str(path)])
    assert gate.main() == 0


# --- Meta.constraints / Meta.indexes: el hogar del objeto de tabla ---------


def test_meta_names_reads_db_table_and_the_declared_constraint_names():
    """El gate lee ``Meta`` para saber dónde aterrizó el objeto de tabla."""
    node = _class_def(
        'class C:\n'
        '    class Meta:\n'
        '        db_table = "res_partner"\n'
        '        constraints = [models.CheckConstraint(condition=Q(),'
        ' name="res_partner_check_name")]\n'
        '        indexes = [models.Index(fields=["a"], name="res_partner_a_idx")]\n'
    )
    db_table, names = gate.meta_table_object_names(node)
    assert db_table == 'res_partner'
    assert names == {'res_partner_check_name', 'res_partner_a_idx'}


def test_meta_names_is_empty_when_the_class_has_no_meta():
    db_table, names = gate.meta_table_object_names(_class_def('class C:\n    x = 1\n'))
    assert (db_table, names) == ('', set())


def test_a_table_object_is_placed_when_meta_uses_the_derived_full_name():
    """``full_name()`` de la referencia: ``f'{_table}_{attr[1:]}'``.

    ``odoo19c: odoo/orm/table_objects.py:54-57`` — el nombre real de la
    restricción es la tabla más el atributo sin su guion bajo.
    """
    assert gate.table_object_is_placed(
        '_check_name', 'res_partner', {'res_partner_check_name'})


def test_a_table_object_is_placed_when_only_the_suffix_survives():
    """Un puerto puede nombrar su tabla distinto y conservar el sufijo."""
    assert gate.table_object_is_placed(
        '_check_name', 'otra_tabla', {'system_parameter_check_name'})


def test_a_table_object_is_not_placed_when_meta_names_something_else():
    """El control negativo: sin el sufijo, no está — el gate sigue viendo."""
    assert not gate.table_object_is_placed(
        '_check_name', 'res_partner', {'res_partner_unique_vat'})

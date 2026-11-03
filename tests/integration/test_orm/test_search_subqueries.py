"""Porte semántico de ``TestSubqueries`` (``odoo19c: odoo/addons/test_orm/
tests/test_search.py:6-384``).

Revisión de referencia: ``odoo-tools@abe4040ec1``. La fuente afirma el texto
SQL de cada consulta (``assertQueries``). Aquí el SQL lo emite Django, así que
se afirma **qué filas** salen con datos que separan las dos formas posibles:
una subconsulta por condición (la fuente) contra una sola unión compartida.
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def partners(env):
    Partner = env['res.partner']
    return {
        'both': Partner.objects.create(name='jack', phone='01234'),
        'name': Partner.objects.create(name='jack', phone='999'),
        'none': Partner.objects.create(name='daniel', phone='777'),
    }


@pytest.fixture
def multis(env, partners):
    Multi = env['test_orm.multi']
    return {key: Multi.create({'partner': partner.id})
            for key, partner in partners.items()} | {
        'orphan': Multi.create({}),
    }


def _found(env, domain):
    return set(env['test_orm.multi'].search(domain).ids)


def test_and_many2one_with_subfield(env, multis):
    assert _found(env, [('partner.name', 'like', 'jack'),
                        ('partner.phone', 'like', '01234')]) == {
        multis['both'].id}


def test_or_many2one_with_subfield(env, multis):
    assert _found(env, ['|', ('partner.name', 'like', 'jack'),
                        ('partner.phone', 'like', '01234')]) == {
        multis['both'].id, multis['name'].id}


def test_not_and_many2one_with_subfield(env, multis):
    """``partner IS NULL OR partner NOT IN (...)``: el huérfano entra."""
    assert _found(env, ['!', '&', ('partner.name', 'like', 'jack'),
                        ('partner.phone', 'like', '01234')]) == {
        multis['name'].id, multis['none'].id, multis['orphan'].id}


def test_and_one2many_with_subfield(env):
    """Un ``EXISTS`` por condición: dos líneas distintas satisfacen el AND."""
    Multi, Line = env['test_orm.multi'], env['test_orm.multi.line']
    split = Multi.create({})
    Line.create({'multi': split.id, 'name': 'jack'})
    Line.create({'multi': split.id, 'name': '01234'})
    single = Multi.create({})
    Line.create({'multi': single.id, 'name': 'jack'})
    assert _found(env, [('lines.name', 'like', 'jack'),
                        ('lines.name', 'like', '01234')]) == {split.id}


def test_many2many_applies_the_field_domain(env):
    """``tags`` declara ``domain=[('name', 'ilike', 'a')]`` y la fuente lo
    añade a la subconsulta: una etiqueta sin ``a`` no cuenta."""
    Multi, Tag = env['test_orm.multi'], env['test_orm.multi.tag']
    with_a = Tag.create({'name': 'jack'})
    without_a = Tag.create({'name': '01234'})
    multi = Multi.create({'tags': [with_a.id, without_a.id]})
    assert _found(env, [('tags.name', 'like', 'jack')]) == {multi.id}
    assert _found(env, [('tags.name', 'like', '01234')]) == set()


def test_mixed_and_or_many2one_with_subfield(env, partners, multis):
    Partner = env['res.partner']
    colonel = Partner.objects.create(name='jack', phone='5', email='o@sgc.us')
    phone_only = Partner.objects.create(name='sam', phone='01234',
                                        email='c@sgc.us')
    other = Partner.objects.create(name='jack', phone='5', email='x@y.z')
    Multi = env['test_orm.multi']
    ids = {Multi.create({'partner': p.id}).id for p in (colonel, phone_only)}
    Multi.create({'partner': other.id})
    assert _found(env, [('partner.email', 'like', '@sgc.us'), '|',
                        ('partner.name', 'like', 'jack'),
                        ('partner.phone', 'like', '01234')]) == ids


def _multi_with_lines(env, *names):
    multi = env['test_orm.multi'].create({})
    for name in names:
        env['test_orm.multi.line'].create({'multi': multi.id, 'name': name})
    return multi


def test_or_one2many_with_subfield(env):
    x, y = _multi_with_lines(env, 'x'), _multi_with_lines(env, 'y')
    _multi_with_lines(env, 'w')
    assert _found(env, ['|', ('lines.name', 'like', 'x'),
                        ('lines.name', 'like', 'y')]) == {x.id, y.id}


def test_mixed_and_or_one2many_with_subfield(env):
    """``x AND (y OR z)``: cada término puede cumplirlo una línea distinta."""
    split = _multi_with_lines(env, 'x', 'z')
    _multi_with_lines(env, 'x')
    _multi_with_lines(env, 'z')
    assert _found(env, [('lines.name', 'like', 'x'), '|',
                        ('lines.name', 'like', 'y'),
                        ('lines.name', 'like', 'z')]) == {split.id}


def test_mixed_and_or_many2many_with_subfield(env):
    Tag = env['test_orm.multi.tag']
    xa, za = Tag.create({'name': 'xa'}), Tag.create({'name': 'za'})
    Multi = env['test_orm.multi']
    split = Multi.create({'tags': [xa.id, za.id]})
    Multi.create({'tags': [xa.id]})
    assert _found(env, [('tags.name', 'like', 'x'), '|',
                        ('tags.name', 'like', 'y'),
                        ('tags.name', 'like', 'z')]) == {split.id}


def test_empty_many2many(env, multis):
    """``('tags', 'any', <consulta vacía>)`` no devuelve nada."""
    empty = env['test_orm.multi.tag']._search([('id', '=', 0)])
    assert _found(env, [('tags', 'any', empty)]) == set()

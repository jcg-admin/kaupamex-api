"""La optimizacion de indice del campo dependiente de empresa — tarea #211.

Porta ``Field._condition_to_sql_company``
(``odoo19c: odoo/orm/fields.py:1368-1377``) y la fachada de dos pasos
``Field.condition_to_sql`` (``:1249-1260``), que compone el cuerpo de la
condicion con esta optimizacion.

**Que hace, y por que no es cosmetica.** Un campo dependiente de empresa vive
en una columna ``jsonb`` con ``{empresa: valor}``, y la fila que no tiene
entrada propia responde el respaldo de ``ir.default``. Cuando ese respaldo
**no** satisface la condicion, ninguna fila con la columna nula puede
satisfacerla tampoco: anteponer ``columna IS NOT NULL`` no cambia el conjunto
de filas y deja que PostgreSQL use el indice parcial
``WHERE columna IS NOT NULL`` que ``registry.check_indexes()`` crea para
``index='btree_not_null'``.

**Su poblacion activadora es cero en los dos arboles, medido.** De los 69
campos que declaran ``company_dependent=True`` en ``odoo19c``, ninguno declara
ademas ``index='btree_not_null'`` (recorrido AST sobre ``addons/`` y
``odoo/addons/``); aqui son 2 y 0 (``django.apps`` sobre el arbol cargado). La
optimizacion se porta porque el contrato de ``Field`` la declara, no porque hoy
tenga consumidor; los casos construyen el campo que la activa con
``monkeypatch``.

**El operador es ``in``, no ``=``.** La fachada recibe la condicion ya
normalizada por el optimizador de dominio (``_operator_equal_as_in``), y el
cuerpo solo conoce los operadores reducidos. Pasarle ``=`` mediria una entrada
que en produccion nunca llega.

**Como se mide la rama, y por que no con ``in q.children``.** Django **aplana**
al componer dos ``Q`` con el mismo conector: ``Q(a) & Q(b)`` deja
``children == [('a', ...), ('b', ...)]`` — tuplas, no objetos ``Q``. Medido::

    >>> (Q(barcode__isnull=False) & Q(barcode__in=['MX-1'])).children
    [('barcode__isnull', False), ('barcode__in', ['MX-1'])]
    >>> Q(barcode__isnull=False) in _.children
    False

Un caso escrito como ``Q(...) in q.children`` daria **False siempre**: fallaria
con la implementacion correcta y su forma negada pasaria sin distinguir nada.
Es el verde que no discrimina de ``metrica-decide-la-conclusion.md``, y aqui se
evita midiendo la tupla que Django si produce.

**El control que discrimina** es
``test_a_fallback_that_satisfies_leaves_the_condition_alone``: una
implementacion que antepusiera ``IS NOT NULL`` siempre pasaria los demas casos
y **cambiaria el conjunto de filas** justo cuando el respaldo satisface la
condicion, que es cuando las filas sin valor propio SI deben entrar.
"""
import pytest
from django.db import models

from orm.domains import Domain, DomainCondition
from orm.fields import condition_to_q
from orm.registry import MODELS_BY_NAME
from orm.utils import model_field_registry

#: La rama que la optimizacion antepone, en la forma en que Django la deja.
NOT_NULL = ('barcode__isnull', False)


@pytest.fixture
def model(db):
    return MODELS_BY_NAME['res.partner']


@pytest.fixture
def field(model):
    """``res.partner.barcode`` — un campo dependiente de empresa del arbol."""
    return model_field_registry(model)['barcode']


def _indexed(monkeypatch, field):
    """Da al campo el indice que activa la optimizacion.

    Ningun campo del arbol lo declara —ni de la referencia—, asi que la
    precondicion se construye aqui en vez de buscarse.
    """
    monkeypatch.setattr(field, 'index', 'btree_not_null', raising=False)


def _fallback(monkeypatch, verdict):
    """Fija lo que ``ir.default`` responde sobre el respaldo del campo."""
    monkeypatch.setattr(
        MODELS_BY_NAME['ir.default'], '_evaluate_condition_with_fallback',
        classmethod(lambda cls, *args, **kwargs: verdict), raising=False)


class TestConditionToQCompany:

    def test_a_fallback_that_fails_prepends_the_not_null(
            self, field, model, monkeypatch):
        """El respaldo no satisface: las filas sin valor propio no pueden entrar."""
        _indexed(monkeypatch, field)
        _fallback(monkeypatch, False)

        q = field.condition_to_q('barcode', 'in', ['MX-1'], model)

        assert NOT_NULL in q.children

    def test_a_fallback_that_satisfies_leaves_the_condition_alone(
            self, field, model, monkeypatch):
        """El control: con el respaldo satisfecho la fila sin valor propio SI
        entra, y anteponer ``IS NOT NULL`` la excluiria."""
        _indexed(monkeypatch, field)
        _fallback(monkeypatch, True)

        q = field.condition_to_q('barcode', 'in', ['MX-1'], model)

        assert NOT_NULL not in q.children

    def test_an_undecidable_fallback_leaves_the_condition_alone(
            self, field, model, monkeypatch):
        """``None`` es «no se puede decidir», y la fuente exige ``is False``."""
        _indexed(monkeypatch, field)
        _fallback(monkeypatch, None)

        q = field.condition_to_q('barcode', 'in', ['MX-1'], model)

        assert NOT_NULL not in q.children

    def test_a_field_without_the_partial_index_is_left_alone(
            self, field, model, monkeypatch):
        """Sin ``index='btree_not_null'`` no hay indice parcial que aprovechar."""
        monkeypatch.setattr(field, 'index', None, raising=False)
        _fallback(monkeypatch, False)

        q = field.condition_to_q('barcode', 'in', ['MX-1'], model)

        assert NOT_NULL not in q.children

    def test_without_a_model_the_optimization_is_not_decided(
            self, field, monkeypatch):
        """Sin modelo no hay a quien preguntarle el respaldo, y el cuerpo pasa tal cual."""
        _indexed(monkeypatch, field)
        _fallback(monkeypatch, False)

        q = field.condition_to_q('barcode', 'in', ['MX-1'])

        assert NOT_NULL not in q.children


class TestConditionToQPlainField:

    def test_a_field_that_is_not_company_dependent_never_gets_it(
            self, model, monkeypatch):
        """``name`` no depende de empresa: la fachada no consulta el respaldo."""
        plain = model_field_registry(model)['name']
        monkeypatch.setattr(plain, 'index', 'btree_not_null', raising=False)
        _fallback(monkeypatch, False)

        q = plain.condition_to_q('name', 'in', ['Titular'], model)

        assert ('name__isnull', False) not in q.children

    def test_the_body_is_the_same_the_free_function_gives(self, model):
        """La fachada no reescribe el cuerpo: sobre un campo llano coincide."""
        plain = model_field_registry(model)['name']

        assert (plain.condition_to_q('name', 'in', ['Titular'], model)
                == condition_to_q('name', 'in', ['Titular'], plain))


class TestDomainRoutesThroughTheFacade:
    """El cableado — ≙ ``odoo19c: odoo/orm/domains.py:1096``.

    La fuente llama **siempre** a ``field.condition_to_sql(...)``, nunca al
    cuerpo. Sin este caso, la optimizacion existiria como metodo y no la
    alcanzaria ninguna busqueda real: un porte que compila y no se invoca.
    """

    def test_a_domain_on_a_company_field_gets_the_optimization(
            self, field, model, monkeypatch):
        _indexed(monkeypatch, field)
        _fallback(monkeypatch, False)

        q = Domain('barcode', 'in', ['MX-1'])._to_q(model)

        assert NOT_NULL in q.children

    def test_a_domain_on_a_plain_field_is_left_alone(self, model, monkeypatch):
        """El control del cableado: sin campo dependiente de empresa, nada cambia."""
        _fallback(monkeypatch, False)

        q = Domain('name', 'in', ['Titular'])._to_q(model)

        assert ('name__isnull', False) not in q.children


class TestTheFacadeRouteIsBoundedToRealFields:
    """La frontera del cableado — la relacion inversa NO es un campo.

    ``DomainCondition._field()`` puede devolver un ``ForeignObjectRel``: el
    objeto que Django fabrica del **otro lado** de una FK. No hereda de
    ``models.Field``, asi que no lleva ninguno de los metodos que
    ``orm/fields.py`` le cuelga, y llamarle la fachada da
    ``AttributeError: 'ManyToOneRel' object has no attribute 'condition_to_q'``.

    En la fuente esa asimetria no existe: el lado inverso **tambien** es un
    ``Field`` (un ``One2many`` con su ``inverse_name``), asi que responde al
    mismo contrato. Darle aqui el vocabulario de campo es la tarea **#347**.

    Este caso es el control del cableado. Escrito con ``field is not None`` en
    vez de ``isinstance(field, models.Field)``, el compilador de hoja revienta
    — medido: dos rojos en ``tests/unit/website/test_website_page.py``
    (``TestPageSearch``), que fue como se destapo.
    """

    def test_a_reverse_relation_is_not_given_the_field_vocabulary(self, db):
        page_model = MODELS_BY_NAME['website.page']
        reverse = DomainCondition('menu_ids', 'in', [1])._field(page_model)

        assert not isinstance(reverse, models.Field)
        assert not hasattr(reverse, 'condition_to_q')

    def test_a_condition_over_a_reverse_relation_still_compiles(self, db):
        page_model = MODELS_BY_NAME['website.page']

        q = Domain('menu_ids', 'in', [1])._to_q(page_model)

        assert ('menu_ids__in', [1]) in q.children

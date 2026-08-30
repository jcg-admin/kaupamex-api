"""Dónde vive el protocolo de descriptor — cierra el DESCONOCIDO de #216.

La fuente aloja ``__get__``/``__set__`` en ``Field`` (``odoo19c: :1642`` y
``:1807``). Django los aloja en ``DeferredAttribute``, OTRA clase, instalada
sobre el **atributo del modelo** y no sobre el campo
(``fields/__init__.py:955``).

No es una diferencia de estilo. Si el campo fuera además descriptor, todo
acceso a un campo desde la clase —``_meta`` los guarda como atributos— pasaría
a invocarlo. El riesgo no es un test rojo: es el arranque.

**Veredicto medido: divergencia de mecanismo declarada, no porte.** Y no se
decide por preferencia — este árbol ya construyó DOS descriptores propios, de
forma independiente, y los dos los puso en el atributo. La conducta correcta ya
se ejercía; lo que faltaba era medirla y fijarla.

Los cinco pasos de ``Field.__get__`` de la fuente no desaparecen: se reparten
entre quien ya los tiene. Su reparto es la tabla de ``TestTheFiveSteps``.
"""
import pytest
from django.apps import apps
from django.db import models
from django.db.models.query_utils import DeferredAttribute

from orm.environments import transaction_scope
from orm.fields_company_dependent import _CompanyDependentAttribute
from orm.fields_nonstored import NonStored


def descriptor_of(model, name):
    """El descriptor que gobierna la lectura de ``name``, o ``None``."""
    for klass in model.__mro__:
        if name in vars(klass):
            return vars(klass)[name]
    return None


@pytest.fixture
def partner_class():
    return apps.get_model('base', 'ResPartner')


class TestWhereTheProtocolLives:

    def test_the_field_is_not_a_descriptor(self):
        """EL CONTROL QUE DISCRIMINA. Si alguien portara ``__get__`` sobre
        ``models.Field`` —como la fuente lo declara— esto cae, y cae ANTES de
        que el arranque lo descubra por su cuenta.

        No es un test de estilo: ``Model._meta`` guarda campos como atributos,
        así que un campo-descriptor se invocaría al leerlos.
        """
        assert not hasattr(models.Field, '__get__')
        assert not hasattr(models.Field, '__set__')

    def test_django_puts_it_on_the_attribute(self, partner_class):
        assert isinstance(descriptor_of(partner_class, 'name'), DeferredAttribute)
        assert models.Field.descriptor_class is DeferredAttribute

    def test_our_two_precedents_did_the_same(self, partner_class):
        """Los dos descriptores propios de este árbol, construidos en pases
        distintos, coinciden con Django y no con la fuente: los dos van en el
        atributo. Es el precedente que decide, y son dos y no uno."""
        assert isinstance(descriptor_of(partner_class, 'barcode'),
                          _CompanyDependentAttribute)
        assert isinstance(descriptor_of(partner_class, 'active_lang_count'),
                          NonStored)

    def test_the_company_dependent_one_extends_djangos(self):
        """Extiende ``DeferredAttribute`` en vez de sustituirlo: el camino de
        lectura ordinario se conserva y sólo se intercepta lo propio."""
        assert issubclass(_CompanyDependentAttribute, DeferredAttribute)


class TestTheFiveSteps:
    """Los cinco pasos de ``Field.__get__`` no desaparecen: se reparten.

    Cada caso fija quién responde por uno de ellos aquí, para que el reparto
    sea verificable y no una afirmación del docstring.
    """

    def test_access_control_already_has_its_home(self, partner_class):
        """Paso 1 — ``_has_field_access``/``_check_field_access``, portados en
        el mixin de SQL y no en el descriptor."""
        assert hasattr(partner_class, '_has_field_access')
        assert hasattr(partner_class, '_check_field_access')

    def test_ensure_one_has_no_counterpart_by_construction(self, partner_class):
        """Paso 2 — la fuente lo necesita porque su recordset puede tener N
        filas. Aquí una instancia ES una fila, así que el paso no tiene a qué
        aplicarse: es divergencia por forma del objeto, no hueco de porte."""
        instance = partner_class(name='una fila')
        assert not isinstance(instance, (list, tuple))
        assert instance.pk is None

    def test_the_transaction_cache_exists_and_is_by_field(self):
        """Paso 4 — la caché por transacción que se construyó en esta misma
        iniciativa. Es de CAMPOS, como la fuente, no de consultas."""
        with transaction_scope() as transaction:
            assert hasattr(transaction, 'field_data')
            assert hasattr(transaction, 'field_dirty')

    def test_the_prefetch_is_djangos_and_is_declared(self, partner_class):
        """Paso 5 — la prelectura por lote la hace ``select_related`` /
        ``prefetch_related`` del QuerySet, no el campo. Se declara aquí para
        que el reparto quede completo y no por omisión."""
        queryset = partner_class.objects.all()
        assert hasattr(queryset, 'select_related')
        assert hasattr(queryset, 'prefetch_related')

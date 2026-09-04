"""El bloque de setup del campo — tarea #211.

Porta el tramo que la referencia declara sobre ``Field`` y que aqui no tenia
contraparte:

===========================  =============================================
Simbolo                      ``odoo19c: odoo/orm/fields.py``
===========================  =============================================
``__set_name__``                   ``:382-407``
``_get_attrs``                     ``:414-486``
``_setup_attrs__``                 ``:491-500``
===========================  =============================================

**El enganche NO es ``__set_name__``, y es un hecho del stack, no una
preferencia.** ``ModelBase.__new__`` separa en ``contributable_attrs`` todo
objeto que declare ``contribute_to_class`` y pasa solo ``new_attrs`` a
``super_new`` (``django/db/models/base.py:116-122``); el campo nunca entra al
espacio de nombres que ``type.__new__`` recibe, asi que Python jamas ejecuta el
protocolo ``__set_name__`` sobre el. Django se lo entrega despues con
``add_to_class`` (``:212``) -> ``contribute_to_class``. Portar el cuerpo bajo el
nombre de la fuente seria codigo que nunca corre; va al enganche equivalente
vivo, y la divergencia queda declarada en ``orm/fields.py``.

**El sustrato ``_args__``.** La fuente lee ``self._args__`` —los parametros que
``__init__`` recibio— para distinguir *"lo declaro el autor"* de *"es el defecto
de la clase"*, que es lo unico que permite rellenar solo lo no declarado. Aqui
figuraba como default de clase con valor ``None`` y **cero sitios lo poblaban**;
esta pieza lo puebla en el envoltorio de ``__init__``.

**Los dos controles, y lo que cada uno NO ve.** Son distintos y hacen falta
los dos:

- ``test_a_field_of_the_tree_comes_out_derived`` mide que el bloque **exista**.
  Medido con el bloque de empresa retirado, el subconjunto pasa de 30 passed a
  ``1 failed, 30 passed``: cae este caso y **solo** este.
- ``test_an_explicit_index_survives_the_company_derivation`` mide que el bloque
  no **pise** lo declarado — una implementacion que asignara en vez de usar
  ``attrs.get(...)`` lo tumbaria. Es ciego a la ausencia del bloque: sin el,
  lo declarado sobrevive trivialmente y el caso pasa. Eso no lo invalida;
  mide otro defecto, y esta escrito para que nadie lo lea como el primero.
"""
import warnings

import pytest
from django.db import models

from orm.registry import MODELS_BY_NAME
from orm.utils import model_field_registry


class _Owner:
    """El minimo que ``_get_attrs`` consulta del propietario: su ``_name``."""

    _name = 'test.owner'


@pytest.fixture
def partner_model(db):
    return MODELS_BY_NAME['res.partner']


class TestTheSetupBlockIsInstalled:
    """El contrato existe antes que su comportamiento."""

    @pytest.mark.parametrize('name', ['_get_attrs', '_setup_attrs__'])
    def test_the_field_class_answers_to_it(self, name):
        assert callable(getattr(models.Field, name, None))

    def test_the_declared_parameters_are_recorded(self):
        """``_args__`` guarda lo declarado, no el defecto de la clase."""
        field = models.CharField(max_length=8, copy=False)

        assert field._args__['max_length'] == 8
        assert field._args__['copy'] is False

    def test_a_parameter_not_declared_is_absent_from_the_record(self):
        """El control del sustrato: sin esto, ``_get_attrs`` no distingue
        ``copy=True`` declarado de ``copy`` no declarado, y sus derivaciones
        pisarian al autor."""
        assert 'copy' not in models.CharField(max_length=8)._args__


class TestCompanyDependentDerivations:
    """``:466-478`` — los cuatro derivados de un campo de empresa.

    La fuente los deriva porque el valor vive en un ``jsonb`` por empresa: no
    viaja en una copia (``copy=False``), se busca por indice parcial
    (``index='btree_not_null'``), se prelee en su propio grupo
    (``prefetch='company_dependent'``) y su valor depende de la empresa activa
    (``_depends_context=('company',)``).
    """

    def test_a_field_of_the_tree_comes_out_derived(self, partner_model):
        """EL ROJO CON POBLACION: ``res.partner.barcode`` es un campo real del
        arbol, no uno fabricado para el caso."""
        barcode = model_field_registry(partner_model)['barcode']

        assert barcode.index == 'btree_not_null'
        assert barcode.prefetch == 'company_dependent'
        assert barcode.copy is False
        assert barcode._depends_context == ('company',)

    def test_a_plain_field_gets_none_of_them(self, partner_model):
        """El control: sin ``company_dependent`` nada de esto se deriva."""
        plain = model_field_registry(partner_model)['name']

        assert plain.index != 'btree_not_null'
        assert plain.prefetch is True
        assert plain.copy is True

    def test_an_explicit_index_survives_the_company_derivation(self):
        """EL CONTROL DE LA DERIVACION: la fuente escribe ``attrs.get(...)``,
        no una asignacion — lo declarado gana."""
        field = models.CharField(max_length=8, company_dependent=True,
                                 index='btree')
        field._setup_attrs__(_Owner, 'x')

        assert field.index == 'btree'

    def test_an_explicit_copy_survives_the_company_derivation(self):
        field = models.CharField(max_length=8, company_dependent=True,
                                 copy=True)
        field._setup_attrs__(_Owner, 'x')

        assert field.copy is True


class TestStateBlock:
    """``:437-439`` — un campo llamado ``state`` no se copia por defecto."""

    def test_a_field_named_state_is_not_copied(self):
        field = models.CharField(max_length=8)
        field._setup_attrs__(_Owner, 'state')

        assert field.copy is False

    def test_a_field_with_another_name_keeps_the_default(self):
        field = models.CharField(max_length=8)
        field._setup_attrs__(_Owner, 'other')

        assert field.copy is True

    def test_an_explicit_copy_survives_on_state(self):
        field = models.CharField(max_length=8, copy=True)
        field._setup_attrs__(_Owner, 'state')

        assert field.copy is True


class TestDependsRenaming:
    """``:480-484`` — ``depends`` y ``depends_context`` se guardan con guion
    bajo, y como tupla."""

    def test_depends_becomes_a_private_tuple(self):
        field = models.CharField(max_length=8, depends=['a', 'b'])
        field._setup_attrs__(_Owner, 'x')

        assert field._depends == ('a', 'b')

    def test_depends_context_becomes_a_private_tuple(self):
        field = models.CharField(max_length=8, depends_context=['company'])
        field._setup_attrs__(_Owner, 'x')

        assert field._depends_context == ('company',)

    def test_the_public_name_does_not_survive(self):
        """``attrs.pop`` en la fuente: el nombre publico se consume."""
        field = models.CharField(max_length=8, depends=['a'])
        field._setup_attrs__(_Owner, 'x')

        assert not hasattr(field, 'depends')


class TestGroupOperatorDeprecation:
    """``:486-488`` — ``group_operator`` se renombra a ``aggregator`` y avisa."""

    def test_it_becomes_aggregator(self):
        field = models.CharField(max_length=8, group_operator='sum')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            field._setup_attrs__(_Owner, 'x')

        assert field.aggregator == 'sum'

    def test_it_warns(self):
        field = models.CharField(max_length=8, group_operator='sum')
        with pytest.warns(DeprecationWarning, match='aggregator'):
            field._setup_attrs__(_Owner, 'x')


class TestExtraKeys:
    """``:493-496`` — los parametros que la clase no conoce quedan censados."""

    def test_an_unknown_parameter_is_recorded(self):
        field = models.CharField(max_length=8, invented_parameter=1)
        field._setup_attrs__(_Owner, 'x')

        assert 'invented_parameter' in field._extra_keys__

    def test_a_known_parameter_is_not(self):
        field = models.CharField(max_length=8, company_dependent=True)
        field._setup_attrs__(_Owner, 'x')

        assert 'company_dependent' not in field._extra_keys__


class TestOwnerIdentity:
    """``:392-393`` — el campo aprende de quien es y como se llama."""

    def test_it_learns_its_model_and_name(self):
        field = models.CharField(max_length=8)
        field._setup_attrs__(_Owner, 'x')

        assert field.model_name == 'test.owner'
        assert field.name == 'x'

    def test_a_field_of_the_tree_knows_its_model(self, partner_model):
        assert model_field_registry(partner_model)['name'].model_name == \
            'res.partner'

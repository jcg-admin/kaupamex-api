"""El acceso por clave a un modelo — ≙ ``odoo19c: odoo/orm/models.py:6669``.

Es la primitiva de la que cuelga la familia ``related=`` de ``Field``:
``_compute_related`` escribe ``record[name] = ...`` e ``_inverse_related`` lo
lee. Se porta sólo su rama de cadena; las otras dos —índice y rebanada— son
del contenedor, y aquí el contenedor es el ``QuerySet``.
"""
import pytest
from django.apps import apps
from django.db import models


@pytest.fixture
def partner():
    return apps.get_model('base', 'ResPartner')(name='Nombre de prueba')


class TestTheKeyAccess:

    def test_it_reads_the_field_by_name(self, partner):
        assert partner['name'] == 'Nombre de prueba'

    def test_it_writes_the_field_by_name(self, partner):
        partner['name'] = 'Otro nombre'
        assert partner.name == 'Otro nombre'

    def test_it_goes_through_the_descriptor_not_the_dict(self, partner):
        """La fuente subraya que se llama al getter del campo, no a un acceso
        crudo. Aquí el getter es el descriptor de Django, y la prueba de que
        se invoca es que un campo diferido levanta su error, no devuelve el
        valor del ``__dict__``."""
        assert partner['name'] is getattr(partner, 'name')

    def test_an_unknown_name_raises_key_error(self, partner):
        """Es acceso por clave: quien lo escribe espera el error del mapa, no
        el del atributo."""
        with pytest.raises(KeyError):
            partner['campo_que_no_existe']
        with pytest.raises(KeyError):
            partner['campo_que_no_existe'] = 'valor'

    def test_a_non_string_key_says_where_the_container_is(self, partner):
        """Control que discrimina: si las ramas de índice y rebanada se
        hubieran portado sobre la instancia, esto devolvería un registro en
        vez de explicar dónde vive el contenedor."""
        with pytest.raises(TypeError, match='QuerySet'):
            partner[3]
        with pytest.raises(TypeError, match='QuerySet'):
            partner[10:20]


class TestWhatWasNotPorted:

    def test_the_container_keeps_its_django_meaning(self, db):
        """Las dos ramas no portadas siguen viviendo donde Django las puso, y
        eso es el motivo de no portarlas: ya existen."""
        queryset = apps.get_model('base', 'ResPartner').objects.all()
        assert isinstance(queryset[0:1], models.QuerySet)

    def test_the_model_class_itself_answers(self):
        assert models.Model.__getitem__ is not None
        assert models.Model.__setitem__ is not None

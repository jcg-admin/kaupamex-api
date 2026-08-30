"""El contrato de ``_fields`` — ≙ ``odoo19c: odoo/orm/models.py:368``.

El mapa es el **registro del modelo**, no el de sus columnas: entran todos los
campos, como allá. Hasta la tarea #215 filtraba por ``concrete``, un contrato
más estrecho que el de la fuente que nadie había comparado.

El rechazo del campo sin columna no desapareció: se mudó a ``_field_to_sql``,
que es quien compone SQL y quien sabe qué puede convertir. Los dos casos de
``TestTheRejectionMovedNotVanished`` fijan que sigue ahí y con el mismo
mensaje.
"""
import pytest
from django.apps import apps


@pytest.fixture
def partner_class():
    return apps.get_model('base', 'ResPartner')


class TestTheMapIsTheModelRegistry:

    def test_it_holds_every_field_meta_declares(self, partner_class):
        declared = {f.name for f in partner_class._meta.get_fields()}
        assert set(partner_class()._fields) == declared

    def test_a_non_concrete_field_is_in_the_map(self, partner_class):
        """El control que discrimina el ensanchado: con el filtro por
        ``concrete`` esta relación inversa quedaba fuera, y con ella el 38 %
        del registro de ``ResPartner`` (41 de 107, medido)."""
        fields = partner_class()._fields
        non_concrete = [f for f in partner_class._meta.get_fields()
                        if not getattr(f, 'concrete', False)]
        assert non_concrete, 'el modelo de prueba ya no tiene campos no concretos'
        for field in non_concrete:
            assert field.name in fields

    def test_the_ratio_is_worth_the_change(self, partner_class):
        """La cifra que justifica la tarea #215, medida y no citada: el filtro
        escondía más de un tercio del registro."""
        todos = partner_class._meta.get_fields()
        concretos = [f for f in todos if getattr(f, 'concrete', False)]
        assert len(concretos) < len(todos)


class TestTheRejectionMovedNotVanished:
    """Lo que el filtro protegía sigue protegido, en su sitio."""

    def test_a_non_concrete_name_is_still_rejected(self, partner_class, db):
        instance = partner_class()
        non_concrete = next(f for f in partner_class._meta.get_fields()
                            if not getattr(f, 'concrete', False))
        with pytest.raises(ValueError, match='Invalid field'):
            instance._field_to_sql('res_partner', non_concrete.name)

    def test_an_unknown_name_is_rejected_the_same_way(self, partner_class, db):
        with pytest.raises(ValueError, match='Invalid field'):
            partner_class()._field_to_sql('res_partner', 'campo_inventado')

    def test_a_concrete_name_still_converts(self, partner_class, db):
        """El control positivo: si el rechazo se hubiera pasado de largo,
        también caería lo que sí tiene columna."""
        assert partner_class()._field_to_sql('res_partner', 'name') is not None

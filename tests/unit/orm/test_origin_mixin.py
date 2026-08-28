"""``OriginMixin._origin`` — el registro guardado frente al del formulario.

≙ ``BaseModel._origin`` (``odoo19c: odoo/orm/models.py:6462-6469``). Su razón
de ser es un ``onchange``: comparar lo que el usuario acaba de teclear con lo
que hay en base. Hasta la tarea #112 el mecanismo existía sin test directo —
sólo se ejercitaba de refilón, por el ``onchange`` de ``res.partner``.

La divergencia de forma, declarada
==================================

Allá el discriminador es el **tipo del id**: un registro de formulario lleva
un ``NewId`` cuyo ``.origin`` apunta a la fila real, y ``_origin`` devuelve
``self`` cuando todos los ids ya son reales. Aquí el discriminador es el
**estado de la instancia**: con ``pk`` la fila existe y se relee; sin ``pk``
no hay nada que traer.

Qué haría fallar a estos casos
==============================

Que ``_origin`` devolviera ``self`` teniendo ``pk`` — o sea, que leyera la
memoria en vez de la fila. Ése es el defecto que el mecanismo existe para
impedir, y es invisible sin un caso que modifique el atributo sin guardar: la
instancia se ve bien formada, sólo responde el valor equivocado.
"""
import pytest

from addons.base.models import ResPartner
from orm.models import OriginMixin


@pytest.mark.django_db
class TestOrigin:
    def test_a_saved_record_reads_the_stored_value_not_the_one_in_memory(self):
        partner = ResPartner.objects.create(name='Guardado')
        partner.name = 'Cambiado sin guardar'

        assert partner._origin.name == 'Guardado'
        assert partner.name == 'Cambiado sin guardar'

    def test_after_saving_the_origin_catches_up(self):
        partner = ResPartner.objects.create(name='Guardado')
        partner.name = 'Nuevo'
        partner.save()

        assert partner._origin.name == 'Nuevo'

    def test_an_unsaved_record_is_its_own_origin(self):
        """Sin ``pk`` no hay fila que traer.

        Divergencia declarada: la fuente devolvería un recordset vacío (su
        ``NewId`` no tiene ``origin``). Aquí devuelve ``self``, que es lo que
        hace que ``(partner.campo or self.campo)`` —el idiom de la fuente en
        los ``onchange``— siga leyendo el valor del formulario en el alta, que
        es su caso más común.
        """
        partner = ResPartner(name='Sin guardar')
        assert partner._origin is partner

    def test_the_origin_is_a_different_instance(self):
        """No es un alias: modificar uno no toca al otro."""
        partner = ResPartner.objects.create(name='Guardado')
        origin = partner._origin
        assert origin is not partner
        assert origin.pk == partner.pk

    def test_it_is_not_memoized(self):
        """Cada lectura vuelve a la fila.

        Memorizarlo rompería el sentido del atributo: lo que se quiere ver es
        lo guardado *ahora*, y entre dos lecturas puede haber un ``save``.
        """
        partner = ResPartner.objects.create(name='Uno')
        assert partner._origin.name == 'Uno'
        ResPartner.objects.filter(pk=partner.pk).update(name='Dos')
        assert partner._origin.name == 'Dos'

    def test_res_partner_adopts_the_mixin(self):
        """El consumidor que registró la tarea #112 lo adopta de verdad.

        Sin esta aserción, alguien podría retirar el mixin de la declaración y
        los casos de arriba seguirían pasando por otro camino sin que nadie lo
        notara.
        """
        assert issubclass(ResPartner, OriginMixin)

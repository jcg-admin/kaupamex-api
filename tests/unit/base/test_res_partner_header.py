"""
Tests unitarios de la cabecera de ``res.partner`` — tarea #504.

Cierra los tres atributos de clase que ``hallazgo-H-API-668`` dejó
registrados como pendientes (``odoo19c: res_partner.py:185-195,326``):
``_check_company_domain`` (bloqueado, ver ``hallazgo-H-API-675``),
``_complete_name_displayed_types`` (constante de clase, portada) y
``_check_name`` (objeto de tabla, portado a ``Meta.constraints``).

BD: kaupamex_core_qa
"""
import pytest
from django.db import IntegrityError, transaction

from addons.base.models import ResPartner

pytestmark = pytest.mark.unit


class TestCompleteNameDisplayedTypes:
    """``_complete_name_displayed_types`` (``odoo19c: res_partner.py:195``).

    Constante de clase, no atributo de ORM — categoría 3 de
    ``atributos-de-clase-de-modelo.md``. Se porta verbatim aunque su único
    consumidor (el compute de ``complete_name``) no esté construido aquí.
    """

    def test_the_constant_is_declared(self):
        assert ResPartner._complete_name_displayed_types == (
            'invoice', 'delivery', 'other',
        )

    def test_the_constant_matches_the_non_contact_types(self):
        """Los tres valores son exactamente los tipos de ``TYPES`` que no
        son ``TYPE_CONTACT`` — la fuente no incluye ``contact`` porque un
        contacto normal no necesita anexar su tipo al nombre completo."""
        non_contact_types = {
            value for value, _label in ResPartner.TYPES
            if value != ResPartner.TYPE_CONTACT
        }
        assert set(ResPartner._complete_name_displayed_types) == non_contact_types


class TestCheckNameConstraint:
    """``_check_name`` (``odoo19c: res_partner.py:326``) — objeto de tabla.

    Un ``type='contact'`` requiere ``name``; una dirección
    (``invoice``/``delivery``/``other``) puede carecer de él. Nombre
    conservado de la fuente: ``res_partner_check_name``
    (``full_name()`` en ``odoo19c: odoo/orm/table_objects.py:55-58``).
    """

    def test_the_constraint_is_declared_in_meta(self):
        names = {c.name for c in ResPartner._meta.constraints}
        assert 'res_partner_check_name' in names

    def test_a_contact_without_name_is_rejected(self, db):
        """Se rechaza — pero lo rechaza el NOT NULL, no la restricción.

        Ver ``test_the_constraint_is_inert_because_our_column_is_not_null``:
        este caso pasaría igual sin haber portado ``_check_name``. Se conserva
        porque documenta el comportamiento observable del contrato, no porque
        ejercite el objeto de tabla.
        """
        with pytest.raises(IntegrityError), transaction.atomic():
            ResPartner.objects.create(name=None, type=ResPartner.TYPE_CONTACT)

    def test_a_contact_with_name_is_accepted(self, db):
        partner = ResPartner.objects.create(
            name='Nestor', type=ResPartner.TYPE_CONTACT,
        )
        assert partner.pk is not None

    def test_a_delivery_address_without_name_is_also_rejected_here(self, db):
        """DIVERGENCIA declarada: la fuente lo acepta, nuestra columna no.

        ``odoo19c: res_partner.py:213`` declara ``name = fields.Char(index=True,
        …)`` **sin** ``required=True``: allá la columna es nullable y una
        dirección sin nombre es válida. Aquí ``name`` es
        ``fields.Char(max_length=200, db_index=True)`` — ``NOT NULL`` por el
        default de Django — así que el INSERT muere antes de que la restricción
        pueda opinar.

        Este test afirma **lo que nuestro esquema hace hoy**, no lo que la
        fuente haría; declarar la divergencia es lo que
        ``porte-completo-no-parcial.md`` exige cuando el porte no reproduce el
        comportamiento. El cierre es la tarea **#507**.
        """
        holder = ResPartner.objects.create(
            name='Empresa', type=ResPartner.TYPE_CONTACT,
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            ResPartner.objects.create(
                name=None, type=ResPartner.TYPE_DELIVERY, parent=holder,
            )

    def test_the_constraint_is_inert_because_our_column_is_not_null(self):
        """La restricción está declarada y no puede dispararse nunca.

        Con ``NOT NULL``, ``name IS NOT NULL`` es tautológico: la rama que la
        fuente usa para rechazar un contacto sin nombre nunca se evalúa. El
        objeto de tabla está **portado en forma** y **muerto en efecto** — la
        clase de defecto que ``porte-completo-no-parcial.md`` llama porte que
        pasa sus tests porque los tests se escribieron sobre lo que se portó.
        """
        assert not ResPartner._meta.get_field('name').null
        assert 'res_partner_check_name' in {
            c.name for c in ResPartner._meta.constraints
        }


class TestCheckCompanyDomainBlocked:
    """``_check_company_domain`` — el único de los nueve que NO se porta.

    Bloqueo de alcance de escritura de la tarea #504 (sólo
    ``res_partner.py``, sus migraciones y sus tests — no ``src/orm/**``,
    donde vive el hogar correcto de ``check_company_domain_parent_of``
    por raíz espejada). Ver ``hallazgo-H-API-675`` para la condición de
    cierre: DESCONOCIDO hasta que una tarea con alcance en ``src/orm/``
    construya el símbolo y su consumidor en ``save()``.
    """

    def test_the_attribute_is_not_yet_declared(self):
        assert not hasattr(ResPartner, '_check_company_domain')

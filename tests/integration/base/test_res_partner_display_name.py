"""Tests — ``display_name`` de ``res.partner`` y sus cinco claves de contexto.

Contrato adaptado de ``_compute_display_name``
(``odoo19c: odoo/addons/base/models/res_partner.py:1038-1069``).

Por que no basta con ``_get_complete_name``
============================================

``complete_name`` es el name para una lista: «Empresa, Persona». ``display_name``
es ese name **enriquecido segun quien lo pide**: el mismo partner se muestra
distinto en un selector de correo (con el buzon), en una pantalla de soporte
(con el id de base) o en un documento fiscal (con el RFC).

La fuente resuelve eso con cinco claves de contexto, y **cada una se mide**:

``formatted_display_name``
    Cambia la FORMA entera: «Empresa \\t --Persona--» en vez de «Empresa,
    Persona». Es la que usa el selector enriquecido.
``show_email``      anexa el buzon.
``partner_show_db_id``  anexa el id, entre parentesis.
``show_address``    anexa la direccion multilinea, sin la company.
``show_vat``        anexa el identificador fiscal.

Que haria fallar a cada control: quitar la lectura de su clave. El caso base
—sin contexto— es el que distingue «no lee la clave» de «no hay clave»: sin el,
un ``display_name`` que ignorara TODO el contexto seguiria pasando los cinco
controles negativos.
"""
import pytest

from addons.base.models.res_partner import ResPartner
from orm.environments import context_scope

pytestmark = pytest.mark.integration


@pytest.fixture
def contact(db):
    company = ResPartner.objects.create(name='Kaupamex SA', is_company=True)
    return ResPartner.objects.create(
        name='Ana Ruiz', parent=company, email='ana@kaupamex.mx',
        vat='RUAA800101AAA', street='Reforma 1', city='CDMX')


class TestWithoutContext:
    """El caso base — ≙ la rama ``else`` de la fuente sin ninguna clave."""

    def test_it_is_the_complete_name(self, contact):
        assert contact.display_name == 'Kaupamex SA, Ana Ruiz'

    def test_a_loose_partner_is_just_its_name(self, db):
        assert ResPartner.objects.create(name='Sola').display_name == 'Sola'


class TestContextKeys:
    """Cada clave anexa lo suyo — ≙ ``:1052-1064``."""

    def test_show_email_appends_the_mailbox(self, contact):
        with context_scope(show_email=True):
            assert contact.display_name.endswith('<ana@kaupamex.mx>')

    def test_show_email_without_email_appends_nothing(self, db):
        """CONTROL — la fuente exige ``and partner.email``. Sin esa mitad
        saldria «Sola <>», que es peor que no anexar nada."""
        loose = ResPartner.objects.create(name='Sola')
        with context_scope(show_email=True):
            assert loose.display_name == 'Sola'

    def test_partner_show_db_id_appends_the_id(self, contact):
        with context_scope(partner_show_db_id=True):
            assert contact.display_name.endswith(f'({contact.pk})')

    def test_show_vat_appends_the_tax_id(self, contact):
        with context_scope(show_vat=True):
            assert contact.display_name.endswith('- RUAA800101AAA')

    def test_show_address_appends_the_address_on_its_own_lines(self, contact):
        with context_scope(show_address=True):
            name = contact.display_name
        assert '\n' in name, 'la direccion va en lineas propias'
        assert 'Reforma 1' in name

    def test_show_vat_with_show_address_uses_the_other_separator(self, contact):
        """CONTROL del par: la fuente separa el RFC con ``' \\n '`` cuando ya
        hay direccion y con ``' - '`` cuando no. Sin esa rama el RFC quedaria
        pegado a la ultima linea de la direccion."""
        with context_scope(show_address=True, show_vat=True):
            name = contact.display_name
        assert '\n RUAA800101AAA' in name


class TestFormattedDisplayName:
    """≙ la rama ``if`` de la fuente (``:1041-1049``) — otra FORMA, no un
    sufijo."""

    def test_it_uses_the_double_dash_form(self, contact):
        with context_scope(formatted_display_name=True):
            assert contact.display_name == 'Kaupamex SA \t --Ana Ruiz--'

    def test_a_nameless_address_falls_back_to_its_type(self, db):
        """La fuente usa la etiqueta del tipo cuando no hay name, igual que
        ``_get_complete_name`` pero en esta forma."""
        company = ResPartner.objects.create(name='Kaupamex SA', is_company=True)
        warehouse = ResPartner.objects.create(name='', parent=company,
                                           type=ResPartner.TYPE_DELIVERY)
        with context_scope(formatted_display_name=True):
            assert warehouse.display_name == 'Kaupamex SA \t --Entrega--'

    def test_show_email_uses_the_double_dash_too(self, contact):
        """CONTROL — en esta rama el correo va con ``--…--``, no con ``<…>``.
        Sin la rama propia se colaria el formato de la otra."""
        with context_scope(formatted_display_name=True, show_email=True):
            assert contact.display_name.endswith('--ana@kaupamex.mx--')

    def test_db_id_is_the_alternative_not_the_addition(self, contact):
        """CONTROL — aqui la fuente usa ``elif``: con correo NO se anexa el
        id. Es la diferencia con la otra rama, donde los dos se acumulan."""
        with context_scope(formatted_display_name=True, show_email=True,
                           partner_show_db_id=True):
            name = contact.display_name
        assert f'--{contact.pk}--' not in name


class TestLineCleanup:
    """≙ ``re.sub(r'\\s+\\n', '\\n', name)`` y el ``.strip()`` final
    (``:1067-1068``)."""

    def test_it_leaves_no_trailing_blanks_before_a_newline(self, contact):
        """El par ``show_address`` + ``show_vat`` es lo que ejercita la
        limpieza, y sólo ese par.

        Medido con una sonda sobre ``_display_address(without_company=True)``:
        la plantilla del país devuelve ``'Reforma 1\n\nCDMX  \n'`` — dos
        espacios antes del salto final, porque el estado y el código postal
        van vacíos. Con **sólo** ``show_address`` ese blanco queda al FINAL y
        se lo lleva el ``.strip()``, así que la limpieza no tiene nada que
        hacer y un control con esa sola clave **pasa con la limpieza
        anulada** — medido: 13 passed.

        Con ``show_vat`` detrás, el blanco queda en MEDIO y sólo el
        ``re.sub`` lo colapsa.

        *Métrica:* presencia de ``' \n'`` en el resultado.
        *Ciega a:* un blanco que la plantilla de otro país deje en una
        posición distinta; se midió con la de México.
        """
        with context_scope(show_address=True, show_vat=True):
            name = contact.display_name
        assert ' \n' not in name, 'la fuente colapsa el blanco antes del salto'
        assert name == name.strip()

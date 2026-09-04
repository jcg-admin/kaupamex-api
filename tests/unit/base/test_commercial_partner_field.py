"""#314 — la entidad comercial es una COLUMNA, no una property pelada.

La fuente la declara ``fields.Many2one('res.partner',
compute='_compute_commercial_partner', store=True, recursive=True, index=True)``
(``odoo19c: base/models/res_partner.py:301-304``), y su hermana
``commercial_company_name`` tambien lleva ``store=True`` (``:305-306``). Aqui las
dos eran ``@property`` sin columna, asi que ningun ``filter`` las alcanzaba — lo
midio :ref:`h-api-1034` sobre el consumidor de ``crm``.

Veredicto por el criterio de las dos categorias: **el stack lo trae hecho**. El
motor de computo almacenado se construyo en #273/#305, y ``recursive=True`` ya
esta declarado (``orm/fields.py:1271``), autodetectado (``:2173``) y honrado al
computar (``:2517``). Aqui solo se declara el campo y se le da su cuerpo.

Medido con cada guarda anulada
==============================

La columna sola no discrimina: un campo declarado y nunca computado da ``NULL``
y el filtro devuelve vacio sin quejarse. Por eso ningun caso se conforma con
*"el campo existe"* — cada uno siembra una cadena de parentesco concreta y exige
el valor que la fuente daria.

Son dos las guardas, y cada una se midio por separado con
``scripts/evidence/control_314_guardas.py`` (sustituye el cuerpo, corre el
modulo y restaura desde la copia en memoria — nunca ``git checkout``, regla
#177; cierra comprobando que el sha256 del archivo no cambio).

**1. El propagador al guardar** (``res_partner.py:1675``). Con
``_store_commercial_entity()`` sustituido por ``pass``, el modulo pasa de
**14 passed** a **1 failed, 5 passed, 8 errors**. Los cinco que sobreviven son
los de :class:`TestTheFieldIsAColumn`, y es correcto: miden la DECLARACION del
campo, no su valor. Los ocho errores no son ruido — son la consecuencia real:
sin entidad comercial escrita, ``_commercial_sync_from_company`` lee ``.pk``
sobre ``None`` y la creacion de un hijo revienta.

**2. La subida recursiva por el padre** (``res_partner.py:1532``). Con
``self.parent.commercial_partner_id or self.parent`` reducido a
``self.parent``, pasa a **3 failed, 11 passed**: caen exactamente los tres que
necesitan tres niveles —la nieta, el nombre que la sigue, y el filtro por
familia—, y sobreviven los de dos niveles, que un salto simple ya resuelve.
Es lo que ``recursive=True`` compra, medido.

*Metrica:* casos de este modulo que caen al anular cada guarda.
*Ciega a:* la reentrada por un ciclo padre/hijo —la impide ``_check_parent_id``
antes, no este campo— y al coste del recorrido en una cadena larga, que no se
mide aqui.
"""
import pytest

from django.apps import apps

from addons.base.models.res_partner import ResPartner

pytestmark = pytest.mark.django_db


def field_of(name):
    return ResPartner._meta.get_field(name)


@pytest.fixture
def chain(db):
    """Abuela empresa, madre contacto, nieta contacto — tres niveles.

    Es el minimo para que ``recursive=True`` tenga algo que resolver: la nieta
    no llega a la empresa en un salto, sino atravesando a su madre.
    """
    grandmother = ResPartner.objects.create(name='Kaupamex SA', is_company=True)
    mother = ResPartner.objects.create(name='Direccion', parent=grandmother)
    daughter = ResPartner.objects.create(name='Ana', parent=mother)
    return grandmother, mother, daughter


class TestTheFieldIsAColumn:
    """La declaracion, contra los cuatro atributos de la fuente."""

    def test_it_is_a_relation_to_res_partner(self):
        field = field_of('commercial_partner_id')
        assert field.related_model is ResPartner

    def test_it_keeps_its_column_and_index(self):
        field = field_of('commercial_partner_id')
        assert field.store is True
        assert field.db_index is True

    def test_the_column_is_not_id_id(self):
        """Forma C de :ref:`h-api-275`: el nombre declarado lleva el sufijo
        —para que el accessor devuelva el REGISTRO, como la fuente— y
        ``db_column`` fuerza la columna a la de la fuente. Sin el, Django la
        llamaria ``commercial_partner_id_id``."""
        assert field_of('commercial_partner_id').db_column == 'commercial_partner_id'

    def test_it_declares_its_recursion(self):
        """``recursive=True`` no es decoracion: decide que el computo corre
        fila a fila para que la cadena se resuelva en orden
        (``orm/fields.py:2517``)."""
        assert field_of('commercial_partner_id').recursive is True

    def test_the_sibling_name_is_stored_too(self):
        field = field_of('commercial_company_name')
        assert field.store is True
        assert field.compute == '_compute_commercial_company_name'


class TestTheValueIsTheOneTheSourceGives:
    """El corte es ``is_company or not parent``, verbatim de la fuente."""

    def test_a_company_is_its_own_commercial_entity(self, chain):
        grandmother, _mother, _daughter = chain
        grandmother.refresh_from_db()
        assert grandmother.commercial_partner_id == grandmother

    def test_a_loose_contact_is_its_own(self, db):
        """Sin padre no hay a quien subir, asi que se es la propia entidad. Es
        por eso que el corte de la fuente NO es solo ``is_company``."""
        loose = ResPartner.objects.create(name='Suelto', is_company=False)
        loose.refresh_from_db()
        assert loose.commercial_partner_id == loose

    def test_a_child_reaches_the_company(self, chain):
        grandmother, mother, _daughter = chain
        mother.refresh_from_db()
        assert mother.commercial_partner_id == grandmother

    def test_a_grandchild_reaches_the_company_too(self, chain):
        """El caso que ``recursive=True`` existe para resolver: la nieta no
        toca a la abuela, toca a su madre — y la madre ya la resolvio."""
        grandmother, _mother, daughter = chain
        daughter.refresh_from_db()
        assert daughter.commercial_partner_id == grandmother

    def test_the_company_name_follows_the_commercial_entity(self, chain):
        _grandmother, _mother, daughter = chain
        daughter.refresh_from_db()
        assert daughter.commercial_company_name == 'Kaupamex SA'


class TestTheColumnIsQueryable:
    """Lo que la property pelada no permitia, y era el consumidor real."""

    def test_the_lookup_compiles_and_finds_the_family(self, chain):
        """``crm_lead._compute_potential_lead_duplicates`` filtraba por esta
        columna y no compilaba (:ref:`h-api-1034`)."""
        grandmother, mother, daughter = chain
        found = set(ResPartner.objects
                    .filter(commercial_partner_id=grandmother.pk)
                    .values_list('pk', flat=True))
        assert found == {grandmother.pk, mother.pk, daughter.pk}

    def test_someone_from_another_family_is_not_found(self, chain):
        """El control que discrimina: si el computo apuntara a todo al mismo
        sitio —o si el filtro no filtrara— este caso pasaria igual que el de
        arriba."""
        grandmother, _mother, _daughter = chain
        other = ResPartner.objects.create(name='Otra SA', is_company=True)
        found = set(ResPartner.objects
                    .filter(commercial_partner_id=grandmother.pk)
                    .values_list('pk', flat=True))
        assert other.pk not in found


class TestMovingTheGrandmotherReachesTheGranddaughter:
    """La condicion de cierre de #314, y la unica que mide la ARISTA."""

    def test_giving_the_mother_her_own_company_flag_detaches_the_branch(self, chain):
        """La madre pasa a ser empresa: ella y su hija dejan de colgar de la
        abuela. Es el cambio que la fuente propaga por
        ``@api.depends('is_company', 'parent_id.commercial_partner_id')``."""
        grandmother, mother, daughter = chain
        mother.is_company = True
        mother.save()

        mother.refresh_from_db()
        daughter.refresh_from_db()
        assert mother.commercial_partner_id == mother
        assert daughter.commercial_partner_id == mother
        assert daughter.commercial_partner_id != grandmother

    def test_untouched_relatives_keep_their_value(self, chain):
        """El control que discrimina: un hermano fuera de la rama movida no se
        mueve. Sin el, un recalculo que reescribiera TODAS las filas daria
        verde en el caso de arriba."""
        grandmother, _mother, _daughter = chain
        aunt = ResPartner.objects.create(name='Tia', parent=grandmother)
        aunt.refresh_from_db()
        assert aunt.commercial_partner_id == grandmother
